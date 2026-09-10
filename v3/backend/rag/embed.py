import logging
from pathlib import Path
from typing import Optional, Union

import numpy as np
from llama_cpp import Llama

from ..config import CPU_THREADS, EMBED_MODEL, SAMPLE_RATE

logger = logging.getLogger(__name__)


class Embedder:
    """nomic-embed-text-v1.5 via llama-cpp-python."""

    def __init__(
        self,
        model_path: Optional[Path] = None,
        n_ctx: int = 2048,
        n_batch: Optional[int] = None,
    ):
        self.model_path = model_path or EMBED_MODEL
        if not self.model_path.exists():
            raise FileNotFoundError(f"Embedding model not found at {self.model_path}")
        n_batch = n_batch or n_ctx
        logger.info(f"Loading embedding model from {self.model_path}...")
        self.model = Llama(
            model_path=str(self.model_path),
            embedding=True,
            n_ctx=n_ctx,
            n_batch=n_batch,
            n_ubatch=n_batch,
            n_threads=CPU_THREADS,
            verbose=False,
        )
        logger.info("Embedding model loaded.")

    def embed(self, text: Union[str, list[str]]) -> Union[list[float], list[list[float]]]:
        if isinstance(text, list):
            return self._encode_many(text, prefix="search_document: ")
        return self._encode_one(text, prefix="search_document: ")

    def embed_query(self, text: str) -> list[float]:
        return self._encode_one(text, prefix="search_query: ")

    def _encode_one(self, text: str, prefix: str) -> list[float]:
        results = self._encode_many([text], prefix=prefix)
        return results[0]

    def _encode_many(self, texts: list[str], prefix: str) -> list[list[float]]:
        prompts = [f"{prefix}{t}" for t in texts]
        output = self.model.create_embedding(prompts)
        embeddings = []
        for item in output["data"]:
            embedding = item["embedding"]
            if isinstance(embedding, np.ndarray):
                embeddings.append(embedding.tolist())
            else:
                embeddings.append(list(embedding))
        return embeddings
