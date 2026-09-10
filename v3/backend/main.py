import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .audio.stt import STT
from .audio.vad import VAD
from .config import TERRARIA_DB
from .rag.embed import Embedder
from .rag.llm import LLM
from .rag.retriever import Retriever
from .tts.piper_tts import PiperTTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SHARED = {}


def set_low_priority():
    try:
        import psutil

        p = psutil.Process()
        if sys.platform == "win32":
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            p.nice(10)
        logger.info("Set process priority to below-normal.")
    except Exception as e:
        logger.warning(f"Could not set process priority: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    set_low_priority()
    SHARED["stt"] = STT()
    SHARED["embedder"] = Embedder()
    SHARED["retriever"] = Retriever()
    if not TERRARIA_DB.exists():
        logger.warning(f"Knowledge base not found: {TERRARIA_DB}")
    SHARED["llm"] = LLM()
    SHARED["tts"] = PiperTTS()
    logger.info("Backend ready.")
    yield
    SHARED.clear()


app = FastAPI(title="Terraria Voice Assistant v3", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/test")
async def test_page():
    return FileResponse(Path(__file__).resolve().parent.parent / "scripts" / "test_ws.html")


@app.get("/audio-processor.js")
async def audio_processor():
    return FileResponse(
        Path(__file__).resolve().parent.parent / "frontend" / "public" / "audio" / "audio-processor.js",
        media_type="application/javascript",
    )


@app.websocket("/ws/voice")
async def voice_ws(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connected")
    vad = VAD()
    in_speech = False
    try:
        while True:
            chunk = await websocket.receive_bytes()
            speech = vad.is_speech(chunk)
            if in_speech and not speech:
                audio = vad.get_speech()
                if audio:
                    transcript = SHARED["stt"].transcribe(audio)
                    if transcript:
                        await websocket.send_json({"transcript": transcript, "answer": None})
                        context = SHARED["retriever"].query(transcript, SHARED["embedder"])
                        answer = SHARED["llm"].generate(transcript, context)
                        await websocket.send_json({"transcript": transcript, "answer": answer})
                        wav = SHARED["tts"].synthesize(answer)
                        await websocket.send_bytes(wav)
                in_speech = False
            elif not in_speech and speech:
                in_speech = True
    except Exception:
        logger.exception("WebSocket error")
    finally:
        await websocket.close()
