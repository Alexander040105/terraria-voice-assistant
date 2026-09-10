import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "backend" / "models"
DATA_DIR = ROOT / "backend" / "data"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Model sources
VAD_URL = "https://github.com/snakers4/silero-vad/raw/refs/tags/v5.0/files/silero_vad.onnx"
WHISPER_MODEL_SIZE = "tiny.en"

EMBED_REPO = "nomic-ai/nomic-embed-text-v1.5-GGUF"
EMBED_FILE = "nomic-embed-text-v1.5.Q4_K_M.gguf"

LLM_REPO = "bartowski/Qwen2.5-1.5B-Instruct-GGUF"
LLM_FILE = "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf"

PIPER_REPO = "rhasspy/piper-voices"
PIPER_ONNX = "en/en_US/lessac/medium/en_US-lessac-medium.onnx"
PIPER_JSON = "en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

# Local model paths
VAD_MODEL = MODELS_DIR / "silero_vad.onnx"
EMBED_MODEL = MODELS_DIR / EMBED_FILE
LLM_MODEL = MODELS_DIR / LLM_FILE
PIPER_MODEL = MODELS_DIR / PIPER_ONNX
PIPER_CONFIG = MODELS_DIR / PIPER_JSON

# Data
TERRARIA_DB = DATA_DIR / "terraria.db"

# Performance
CPU_THREADS = max(1, os.cpu_count() - 2) if os.cpu_count() else 2
LLM_CONTEXT = 1024
RETRIEVER_TOP_K = 3
SAMPLE_RATE = 16000
