import logging
import sqlite3
from pathlib import Path
from typing import Optional

import numpy as np
import sqlite_vec

from ..config import RETRIEVER_TOP_K, TERRARIA_DB

logger = logging.getLogger(__name__)


class Retriever:
    """sqlite-vec based RAG retriever."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        top_k: int = RETRIEVER_TOP_K,
    ):
        self.db_path = db_path or TERRARIA_DB
        self.top_k = top_k

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return conn

    def _init_schema(self, dim: int):
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY, page_title TEXT, section_title TEXT, text TEXT)"
            )
            conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_documents USING vec0(embedding float[{dim}])"
            )

    def _serialize(self, vec: list[float]) -> bytes:
        return np.array(vec, dtype=np.float32).tobytes()

    def add(
        self,
        chunks: list[dict],
        embeddings: list[list[float]],
    ):
        """Insert chunks with their embeddings.

        chunks is a list of dicts with keys: page_title, section_title, text.
        """
        if not chunks:
            return
        dim = len(embeddings[0])
        self._init_schema(dim)

        with self._connect() as conn:
            rows = [
                (c["page_title"], c["section_title"], c["text"])
                for c in chunks
            ]
            conn.executemany(
                "INSERT INTO documents(page_title, section_title, text) VALUES (?, ?, ?)",
                rows,
            )

            # Get the rowids of the rows we just inserted.
            cur = conn.execute(
                "SELECT id FROM documents ORDER BY id DESC LIMIT ?", (len(rows),)
            )
            try:
                rowids = list(reversed([r[0] for r in cur.fetchall()]))
            finally:
                cur.close()

            conn.executemany(
                "INSERT INTO vec_documents(rowid, embedding) VALUES (?, ?)",
                [(rid, self._serialize(emb)) for rid, emb in zip(rowids, embeddings)],
            )
            logger.info(f"Inserted {len(chunks)} chunks into {self.db_path}")

    def query(self, text: str, embedder) -> list[str]:
        if not self.db_path.exists():
            return []
        query_vec = embedder.embed_query(text)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT d.text
                FROM vec_documents v
                JOIN documents d ON d.id = v.rowid
                WHERE v.embedding MATCH ? AND v.k = ?
                ORDER BY v.distance
                """,
                (self._serialize(query_vec), self.top_k),
            ).fetchall()
        return [row[0] for row in rows]
