import logging
from pathlib import Path
from typing import Optional

import numpy as np
from faster_whisper import WhisperModel

from ..config import CPU_THREADS, MODELS_DIR, SAMPLE_RATE, WHISPER_MODEL_SIZE

logger = logging.getLogger(__name__)


class STT:
    """faster-whisper STT wrapper for 16 kHz int16 mono PCM."""

    def __init__(
        self,
        model_size: str = WHISPER_MODEL_SIZE,
        download_root: Optional[Path] = None,
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        self.download_root = download_root or MODELS_DIR
        logger.info(f"Loading faster-whisper model '{model_size}'...")
        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            download_root=str(self.download_root),
            cpu_threads=CPU_THREADS,
        )
        logger.info("STT model loaded.")

    def transcribe(self, audio_bytes: bytes) -> str:
        if not audio_bytes:
            return ""
        samples = (
            np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        )
        segments, _ = self.model.transcribe(
            samples,
            language="en",
            condition_on_previous_text=False,
            suppress_blank=True,
        )
        text = " ".join([segment.text.strip() for segment in segments]).strip()
        logger.info(f"Transcribed: {text}")
        return text
