"""PyInstaller entry point for the packaged backend."""
import multiprocessing
import sys
from pathlib import Path

import uvicorn

# Ensure the project root is on the path so `backend` can be imported.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.main import app  # noqa: E402


def main():
    multiprocessing.freeze_support()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        http="httptools",
        ws="websockets",
        loop="asyncio",
        log_level="info",
    )


if __name__ == "__main__":
    main()
