from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from diskcache import Cache
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_ollama.llms import OllamaLLM
from sentence_transformers import CrossEncoder
import speech_recognition as sr
import pyttsx3

from vector import load_or_build_retriever

APP_PORT = int(os.getenv("TERRARIA_ASSISTANT_PORT", "8765"))
OLLAMA_CHAT_MODEL = os.getenv("TERRARIA_CHAT_MODEL", "qwen2.5:1.5b")
EMBEDDING_MODEL = os.getenv("TERRARIA_EMBED_MODEL", "nomic-embed-text")
RERANKER_MODEL = os.getenv("TERRARIA_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
TOP_K = int(os.getenv("TERRARIA_TOP_K", "6"))
RERANK_K = int(os.getenv("TERRARIA_RERANK_K", "12"))
MAX_DOC_CHARS = int(os.getenv("TERRARIA_MAX_DOC_CHARS", "900"))
MAX_CONTEXT_CHARS = int(os.getenv("TERRARIA_MAX_CONTEXT_CHARS", "3600"))
RERANK_ENABLED = os.getenv("TERRARIA_RERANK_ENABLED", "true").lower() == "true"
DATA_DIR = os.path.join(os.path.dirname(__file__), "scraped_pages")
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
TTS_ENABLED = os.getenv("TERRARIA_TTS_ENABLED", "true").lower() == "true"
EAGER_INIT = os.getenv("TERRARIA_EAGER_INIT", "true").lower() == "true"
PORT_FILE = os.path.join(os.path.dirname(__file__), "runtime_port.txt")

ANSWER_TEMPLATE = """You are a Terraria wiki assistant.
Only answer using the provided wiki context. If the context does not support the answer, say you don't know.

Return in this exact format:
ANSWER: <1-3 sentence direct answer>
EVIDENCE: <quote or paraphrase from wiki chunk, with source>
CONFIDENCE: <"Supported by wiki" | "Not found in wiki -- I don't know">

Wiki context:
{wiki}

Question:
{question}
"""


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    question: str
    answer: str
    evidence: str
    confidence: str
    sources: List[Dict[str, Any]]


@dataclass
class AppState:
    model: Optional[OllamaLLM] = None
    reranker: Optional[CrossEncoder] = None
    retriever: Optional[Any] = None
    cache: Optional[Cache] = None
    recognizer: Optional[sr.Recognizer] = None
    microphone: Optional[sr.Microphone] = None
    tts_engine: Optional[Any] = None


state = AppState()
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _write_runtime_port() -> None:
    with open(PORT_FILE, "w", encoding="utf-8") as handle:
        handle.write(str(APP_PORT))
    if EAGER_INIT:
        _ensure_initialized()


def _normalize_question(question: str) -> str:
    cleaned = re.sub(r"\s+", " ", question.strip().lower())
    return cleaned


def _ensure_initialized() -> None:
    print("[backend] initializing resources...")
    if state.cache is None:
        state.cache = Cache(CACHE_DIR)

    if state.model is None:
        state.model = OllamaLLM(model=OLLAMA_CHAT_MODEL)
        print(f"[backend] chat model loaded: {OLLAMA_CHAT_MODEL}")

    if state.reranker is None:
        state.reranker = CrossEncoder(RERANKER_MODEL)
        print(f"[backend] reranker loaded: {RERANKER_MODEL}")

    if state.retriever is None:
        state.retriever = load_or_build_retriever(
            data_dir=DATA_DIR,
            embedding_model=EMBEDDING_MODEL,
            top_k=RERANK_K,
        )
        print(f"[backend] retriever ready with embeddings: {EMBEDDING_MODEL}")
    print("[backend] initialization complete")


def _ensure_voice() -> None:
    if state.recognizer is None:
        state.recognizer = sr.Recognizer()
    if state.microphone is None:
        state.microphone = sr.Microphone()
    if state.tts_engine is None and TTS_ENABLED:
        state.tts_engine = pyttsx3.init()


def _rerank(question: str, docs: List[Any]) -> List[Any]:
    if not docs:
        return []

    if not RERANK_ENABLED:
        return docs[:TOP_K]

    pairs = [(question, doc.page_content) for doc in docs]
    scores = state.reranker.predict(pairs)
    ranked = sorted(zip(scores, docs), key=lambda item: item[0], reverse=True)
    return [doc for _, doc in ranked[:TOP_K]]


def _format_sources(docs: List[Any]) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    for doc in docs:
        meta = doc.metadata or {}
        sources.append(
            {
                "page_title": meta.get("page_title"),
                "section_title": meta.get("section_title"),
                "source_file": meta.get("source_file"),
                "url": meta.get("url"),
            }
        )
    return sources


def _extract_response_fields(raw_answer: str) -> Dict[str, str]:
    answer = ""
    evidence = ""
    confidence = "Not found in wiki -- I don't know"
    for line in raw_answer.splitlines():
        if line.startswith("ANSWER:"):
            answer = line.replace("ANSWER:", "", 1).strip()
        elif line.startswith("EVIDENCE:"):
            evidence = line.replace("EVIDENCE:", "", 1).strip()
        elif line.startswith("CONFIDENCE:"):
            confidence = line.replace("CONFIDENCE:", "", 1).strip()

    return {
        "answer": answer or raw_answer.strip(),
        "evidence": evidence,
        "confidence": confidence,
    }


def _speak(text: str) -> None:
    if not TTS_ENABLED or state.tts_engine is None:
        return
    engine = state.tts_engine
    engine.say(text)
    engine.runAndWait()


def _answer_question(question: str) -> Dict[str, Any]:
    normalized = _normalize_question(question)

    cached_answer = state.cache.get(f"answer::{normalized}")
    if cached_answer:
        return cached_answer

    cached_docs = state.cache.get(f"docs::{normalized}")
    if cached_docs:
        docs = cached_docs
    else:
        docs = state.retriever.invoke(question)
        docs = _rerank(question, docs)
        state.cache.set(f"docs::{normalized}", docs, expire=60 * 60 * 24)

    context_parts = []
    current_len = 0
    for doc in docs:
        header = f"[{doc.metadata.get('page_title', 'Unknown')} - {doc.metadata.get('section_title', 'Overview')}]\n"
        body = doc.page_content[:MAX_DOC_CHARS]
        segment = f"{header}{body}"
        if current_len + len(segment) > MAX_CONTEXT_CHARS:
            break
        context_parts.append(segment)
        current_len += len(segment)

    wiki_context = "\n\n".join(context_parts)

    prompt = ANSWER_TEMPLATE.format(wiki=wiki_context, question=question)
    raw_answer = state.model.invoke(prompt)
    fields = _extract_response_fields(raw_answer)

    response = {
        "question": question,
        "answer": fields["answer"],
        "evidence": fields["evidence"],
        "confidence": fields["confidence"],
        "sources": _format_sources(docs),
    }
    state.cache.set(f"answer::{normalized}", response, expire=60 * 60 * 24)
    return response


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/status")
def status() -> Dict[str, Any]:
    return {
        "model_loaded": state.model is not None,
        "retriever_loaded": state.retriever is not None,
        "reranker_loaded": state.reranker is not None,
        "cache_ready": state.cache is not None,
        "chat_model": OLLAMA_CHAT_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "reranker_model": RERANKER_MODEL,
        "top_k": TOP_K,
        "rerank_k": RERANK_K,
    }


@app.post("/init")
def init() -> Dict[str, str]:
    _ensure_initialized()
    return {"status": "ready"}


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    print(f"[backend] /ask received: {question}")
    _ensure_initialized()
    response = _answer_question(question)
    print("[backend] /ask response sent")
    return AskResponse(**response)


@app.post("/listen", response_model=AskResponse)
def listen() -> AskResponse:
    _ensure_initialized()
    _ensure_voice()

    try:
        with state.microphone as source:
            state.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = state.recognizer.listen(source, timeout=10, phrase_time_limit=12)
        question = state.recognizer.recognize_google(audio)
    except sr.WaitTimeoutError:
        raise HTTPException(status_code=408, detail="Listening timed out.")
    except sr.UnknownValueError:
        raise HTTPException(status_code=422, detail="Could not understand audio.")
    except sr.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Speech service error: {exc}")

    response = _answer_question(question)
    print(f"[backend] /listen recognized: {question}")
    _speak(response["answer"])
    return AskResponse(**response)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=APP_PORT, reload=False)
    