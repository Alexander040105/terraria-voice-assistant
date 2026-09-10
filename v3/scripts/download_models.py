"""Download all local models into v3/backend/models.

Run from the v3/ directory:
    python -m scripts.download_models
"""
import logging
import os
import shutil
from pathlib import Path

# Keep the Hugging Face cache on the project drive, not the system drive.
_HF_CACHE = Path(__file__).resolve().parent.parent / "backend" / "models" / ".hf_cache"
_HF_CACHE.mkdir(parents=True, exist_ok=True)
os.environ["HF_HUB_CACHE"] = str(_HF_CACHE)

import requests
from huggingface_hub import hf_hub_download

from backend.config import (
    EMBED_FILE,
    EMBED_MODEL,
    EMBED_REPO,
    LLM_FILE,
    LLM_MODEL,
    LLM_REPO,
    MODELS_DIR,
    PIPER_CONFIG,
    PIPER_JSON,
    PIPER_MODEL,
    PIPER_ONNX,
    PIPER_REPO,
    VAD_MODEL,
    VAD_URL,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _download_with_progress(url: str, dest: Path, chunk_size: int = 8192) -> None:
    logger.info(f"Downloading {url} -> {dest}")
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    total = int(r.headers.get("content-length", 0))
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        downloaded = 0
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    logger.info(f"{dest.name}: {downloaded / total * 100:.1f}%")
    logger.info(f"Saved {dest}")


def _hf_download(repo_id: str, filename: str, dest: Path) -> None:
    if dest.exists():
        logger.info(f"Already exists: {dest}")
        return
    logger.info(f"Downloading {repo_id}/{filename}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    local_path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=str(MODELS_DIR),
        local_dir_use_symlinks=False,
    )
    # If the downloaded location is not the final destination, move it there.
    local_path = Path(local_path).resolve()
    if local_path != dest.resolve():
        shutil.move(str(local_path), str(dest))
    logger.info(f"Saved {dest}")


def download_vad():
    if VAD_MODEL.exists():
        logger.info(f"Already exists: {VAD_MODEL}")
        return
    _download_with_progress(VAD_URL, VAD_MODEL)


def download_embed():
    _hf_download(EMBED_REPO, EMBED_FILE, EMBED_MODEL)


def download_llm():
    _hf_download(LLM_REPO, LLM_FILE, LLM_MODEL)


def download_piper():
    _hf_download(PIPER_REPO, PIPER_ONNX, PIPER_MODEL)
    _hf_download(PIPER_REPO, PIPER_JSON, PIPER_CONFIG)


def main():
    logger.info(f"Models will be stored in {MODELS_DIR}")
    download_vad()
    download_embed()
    download_llm()
    download_piper()
    logger.info("All models downloaded.")


if __name__ == "__main__":
    main()
