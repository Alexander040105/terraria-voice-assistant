import logging
from pathlib import Path
from typing import Optional, Union

import numpy as np
import onnxruntime as ort

from ..config import VAD_MODEL, SAMPLE_RATE

logger = logging.getLogger(__name__)


class VAD:
    """Silero VAD ONNX wrapper with stateful speech segmentation.

    The VAD accumulates audio into 512-sample (16 kHz) windows and returns a
    boolean indicating whether the model is currently inside a speech segment.
    Callers can retrieve the accumulated speech audio with `get_speech()` after
    the flag goes from True to False.

    This wrapper uses the v5/v6 Silero VAD model, which expects a 64-sample
    context buffer to be prepended to each 512-sample window, and a single
    (2, 1, 128) LSTM state tensor.
    """

    def __init__(
        self,
        model_path: Optional[Path] = None,
        sample_rate: int = SAMPLE_RATE,
        threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 100,
    ):
        self.model_path = model_path or VAD_MODEL
        if not self.model_path.exists():
            raise FileNotFoundError(f"VAD model not found at {self.model_path}")
        self.sample_rate = sample_rate
        if sample_rate not in (8000, 16000):
            raise ValueError("Silero VAD supports 8 kHz and 16 kHz only")
        self.threshold = threshold
        self.neg_threshold = max(threshold - 0.15, 0.01)
        self.min_speech_samples = int(min_speech_duration_ms * sample_rate / 1000)
        self.min_silence_samples = int(min_silence_duration_ms * sample_rate / 1000)
        self.window_size = 512 if sample_rate == 16000 else 256
        self.context_size = 64 if sample_rate == 16000 else 32

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        self._session = ort.InferenceSession(
            str(self.model_path),
            sess_options=opts,
            providers=["CPUExecutionProvider"],
        )
        self._input_name = self._session.get_inputs()[0].name
        self._state_name = self._session.get_inputs()[1].name
        self._sr_name = self._session.get_inputs()[2].name
        self._output_name = self._session.get_outputs()[0].name
        self._state_out_name = self._session.get_outputs()[1].name

        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, self.context_size), dtype=np.float32)
        self._unprocessed = np.array([], dtype=np.int16)
        self._pre_buffer = np.array([], dtype=np.int16)
        self._speech_buffer = np.array([], dtype=np.int16)
        self._in_speech = False
        self._speech_candidate_samples = 0
        self._silence_samples = 0
        self.last_prob = 0.0

    def _process_window(self, window: np.ndarray) -> float:
        """Run a single 512-sample window through the ONNX model."""
        x = (window.astype(np.float32) / 32768.0).reshape(1, -1)
        x = np.concatenate([self._context, x], axis=1)
        sr = np.array(self.sample_rate, dtype=np.int64)
        feed = {
            self._input_name: x,
            self._state_name: self._state,
            self._sr_name: sr,
        }
        out, state = self._session.run(
            [self._output_name, self._state_out_name], feed
        )
        self._state = state
        self._context = x[..., -self.context_size :]
        return float(out[0][0])

    def is_speech(self, chunk: Union[bytes, np.ndarray]) -> bool:
        if isinstance(chunk, bytes):
            samples = np.frombuffer(chunk, dtype=np.int16)
        else:
            samples = chunk.astype(np.int16)
        if samples.size == 0:
            return self._in_speech

        self._unprocessed = np.concatenate([self._unprocessed, samples])

        while self._unprocessed.size >= self.window_size:
            window = self._unprocessed[: self.window_size].copy()
            self._unprocessed = self._unprocessed[self.window_size :]
            prob = self._process_window(window)
            self.last_prob = prob

            if prob >= self.threshold:
                if not self._in_speech:
                    self._pre_buffer = np.concatenate([self._pre_buffer, window])
                    self._speech_candidate_samples += self.window_size
                    if self._speech_candidate_samples >= self.min_speech_samples:
                        self._in_speech = True
                        self._speech_buffer = self._pre_buffer.copy()
                        self._pre_buffer = np.array([], dtype=np.int16)
                        self._speech_candidate_samples = 0
                        self._silence_samples = 0
                else:
                    self._speech_buffer = np.concatenate([self._speech_buffer, window])
                    self._silence_samples = 0
            elif prob < self.neg_threshold:
                if self._in_speech:
                    self._speech_buffer = np.concatenate([self._speech_buffer, window])
                    self._silence_samples += self.window_size
                    if self._silence_samples >= self.min_silence_samples:
                        self._in_speech = False
                else:
                    self._pre_buffer = np.array([], dtype=np.int16)
                    self._speech_candidate_samples = 0
            else:
                # In the hysteresis band: keep state, but keep counting silence
                # if we are already in speech so short dips are not too disruptive.
                if self._in_speech:
                    self._speech_buffer = np.concatenate([self._speech_buffer, window])
                    self._silence_samples += self.window_size
                    if self._silence_samples >= self.min_silence_samples:
                        self._in_speech = False
                else:
                    self._pre_buffer = np.array([], dtype=np.int16)
                    self._speech_candidate_samples = 0

        return self._in_speech

    def get_speech(self) -> bytes:
        """Return the completed speech segment and reset internal buffers."""
        data = self._speech_buffer.astype(np.int16).tobytes()
        self._speech_buffer = np.array([], dtype=np.int16)
        self._pre_buffer = np.array([], dtype=np.int16)
        self._speech_candidate_samples = 0
        self._silence_samples = 0
        return data
