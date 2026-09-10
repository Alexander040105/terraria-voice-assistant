import io
import logging
import wave
from pathlib import Path
from typing import Optional

from ..config import PIPER_CONFIG, PIPER_MODEL

logger = logging.getLogger(__name__)


class PiperTTS:
    """Piper text-to-speech using the ONNX voice model."""

    def __init__(
        self,
        model_path: Optional[Path] = None,
        config_path: Optional[Path] = None,
    ):
        from piper.voice import PiperVoice

        self.model_path = model_path or PIPER_MODEL
        self.config_path = config_path or PIPER_CONFIG
        if not self.model_path.exists():
            raise FileNotFoundError(f"Piper model not found at {self.model_path}")
        if not self.config_path.exists():
            raise FileNotFoundError(f"Piper config not found at {self.config_path}")
        logger.info(f"Loading Piper voice from {self.model_path}...")
        self.voice = PiperVoice.load(str(self.model_path), str(self.config_path))
        logger.info("Piper voice loaded.")

    def synthesize(self, text: str) -> bytes:
        if not text:
            text = "I don't know."
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.voice.config.sample_rate)
            for chunk in self.voice.synthesize(text):
                wav_file.writeframes(chunk.audio_int16_bytes)
        wav_io.seek(0)
        return wav_io.read()
