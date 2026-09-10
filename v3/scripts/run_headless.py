"""Headless proof-of-concept: mic -> VAD -> STT -> RAG -> LLM -> TTS."""
import argparse
import io
import logging
import queue
import sys
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.audio.stt import STT
from backend.audio.vad import VAD
from backend.config import SAMPLE_RATE, TERRARIA_DB
from backend.rag.embed import Embedder
from backend.rag.llm import LLM
from backend.rag.retriever import Retriever
from backend.tts.piper_tts import PiperTTS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


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


def play_wav(wav_bytes: bytes, blocking: bool = True):
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            frames = w.readframes(w.getnframes())
            rate = w.getframerate()
            channels = w.getnchannels()
            arr = np.frombuffer(frames, dtype=np.int16)
            if channels > 1:
                arr = arr.reshape(-1, channels)
            sd.play(arr, samplerate=rate, blocking=blocking)
    except Exception as e:
        logger.error(f"Could not play audio: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", type=int, default=-1, help="Input audio device")
    parser.add_argument(
        "--no-tts", action="store_true", help="Skip TTS (print answer only)"
    )
    args = parser.parse_args()

    set_low_priority()

    logger.info("Loading models...")
    vad = VAD()
    stt = STT()
    embedder = Embedder()
    retriever = Retriever()
    if not TERRARIA_DB.exists():
        logger.error(
            f"Knowledge base not found: {TERRARIA_DB}. "
            "Run 'python -m build_scripts.scrape_and_embed' first."
        )
        sys.exit(1)
    llm = LLM()
    tts = None if args.no_tts else PiperTTS()
    logger.info("All models loaded. Say something about Terraria (Ctrl+C to stop).")

    audio_queue = queue.Queue()
    in_speech = False

    def callback(indata, frames, time_info, status):
        if status:
            logger.warning(f"Audio status: {status}")
        audio_queue.put(indata.copy().tobytes())

    try:
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=128,
            device=args.device,
            callback=callback,
        ):
            while True:
                chunk = audio_queue.get()
                speech = vad.is_speech(chunk)
                if in_speech and not speech:
                    audio = vad.get_speech()
                    if not audio:
                        in_speech = False
                        continue
                    transcript = stt.transcribe(audio)
                    if not transcript:
                        in_speech = False
                        continue
                    logger.info(f"User: {transcript}")
                    context = retriever.query(transcript, embedder)
                    answer = llm.generate(transcript, context)
                    logger.info(f"Assistant: {answer}")
                    if tts:
                        try:
                            wav = tts.synthesize(answer)
                            play_wav(wav)
                        except Exception as e:
                            logger.error(f"TTS failed: {e}")
                    in_speech = False
                elif not in_speech and speech:
                    in_speech = True
    except KeyboardInterrupt:
        logger.info("Stopped.")


if __name__ == "__main__":
    main()
