"""End-to-end pipeline tests for the v3 backend."""
import io
import wave
from pathlib import Path

import numpy as np
import pytest
from scipy import signal

from backend.audio.stt import STT
from backend.tts.piper_tts import PiperTTS
from backend.audio.vad import VAD
from backend.config import (
    EMBED_MODEL,
    LLM_MODEL,
    MODELS_DIR,
    TERRARIA_DB,
    VAD_MODEL,
)
from backend.rag.embed import Embedder
from backend.rag.llm import LLM
from backend.rag.retriever import Retriever


# --- sanity / fixture tests --------------------------------------------------

def test_terraria_db_exists():
    assert TERRARIA_DB.exists(), f"Knowledge base not found at {TERRARIA_DB}"


def test_model_files_present():
    for p in [EMBED_MODEL, LLM_MODEL, VAD_MODEL]:
        assert p.exists(), f"Model not found at {p}"


def test_embedder():
    e = Embedder()
    emb = e.embed(["what is the best weapon in terraria?"])
    assert len(emb) == 1
    assert len(emb[0]) > 0


def test_retriever_query():
    e = Embedder()
    r = Retriever()
    ctx = r.query("how do I defeat the Eye of Cthulhu?", e)
    assert len(ctx) > 0


# --- audio module tests ------------------------------------------------------

@pytest.mark.slow
class TestAudioModules:
    @pytest.fixture(scope="class")
    def tts(self):
        return PiperTTS()

    def test_tts(self, tts):
        wav = tts.synthesize("hello terraria")
        assert isinstance(wav, bytes)
        w = wave.open(io.BytesIO(wav), "rb")
        assert w.getnframes() > 0
        assert w.getframerate() == 22050

    @pytest.fixture(scope="class")
    def stt(self):
        return STT()

    def test_stt_tts_roundtrip(self, tts, stt):
        text = "hello terraria"
        wav = tts.synthesize(text)

        w = wave.open(io.BytesIO(wav), "rb")
        frames = w.readframes(w.getnframes())
        source_sr = w.getframerate()
        arr = np.frombuffer(frames, dtype=np.int16).astype(np.float32)

        # resample to 16 kHz
        target_sr = 16000
        if source_sr != target_sr:
            new_len = int(len(arr) * target_sr / source_sr)
            arr = signal.resample(arr, new_len)
        arr = np.clip(arr, -32768, 32767).astype(np.int16)

        transcript = stt.transcribe(arr.tobytes())
        assert transcript, "STT returned empty string"
        assert text in transcript.lower()


# --- VAD test ----------------------------------------------------------------

@pytest.mark.slow
class TestVAD:
    @pytest.fixture(scope="class")
    def tts(self):
        return PiperTTS()

    def _resample(self, arr, source_sr, target_sr=16000):
        if source_sr == target_sr:
            return arr
        new_len = int(len(arr) * target_sr / source_sr)
        res = signal.resample(arr.astype(np.float32), new_len)
        return np.clip(res, -32768, 32767).astype(np.int16)

    def test_vad_detects_speech_and_silence(self, tts):
        wav = tts.synthesize("hello terraria")
        w = wave.open(io.BytesIO(wav), "rb")
        frames = w.readframes(w.getnframes())
        source_sr = w.getframerate()
        arr = self._resample(np.frombuffer(frames, dtype=np.int16), source_sr)
        silence = np.zeros(8000, dtype=np.int16)

        vad = VAD()
        for i in range(0, len(arr), 512):
            chunk = arr[i : i + 512].tobytes()
            if len(chunk) == 1024:
                vad.is_speech(chunk)

        for i in range(0, len(silence), 512):
            chunk = silence[i : i + 512].tobytes()
            if len(chunk) == 1024:
                vad.is_speech(chunk)

        speech = vad.get_speech()
        assert speech, "VAD did not capture any speech"


# --- LLM test ----------------------------------------------------------------

@pytest.mark.slow
class TestLLM:
    @pytest.fixture(scope="class")
    def llm(self):
        return LLM()

    @pytest.fixture(scope="class")
    def embedder(self):
        return Embedder()

    @pytest.fixture(scope="class")
    def retriever(self):
        return Retriever()

    def test_llm_answers_from_context(self, llm, embedder, retriever):
        q = "How do I defeat the Eye of Cthulhu?"
        ctx = retriever.query(q, embedder)
        assert ctx
        answer = llm.generate(q, ctx)
        assert answer
        assert len(answer) > 0
