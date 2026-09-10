"""Build-time only: produce v3/backend/data/terraria.db from v1/scraped_pages/."""
import argparse
import csv
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.config import TERRARIA_DB
from backend.rag.embed import Embedder
from backend.rag.retriever import Retriever

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    # Insert spaces between words that were concatenated during HTML extraction.
    # The scraped CSV sometimes contains strings like "The3DS versionofTerraria".
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", text)
    text = re.sub(r"(\d)([a-zA-Z])", r"\1 \2", text)
    return re.sub(r"\s+", " ", text).strip()


def load_chunks(csv_path: Path, max_length: int = 1000, limit: Optional[int] = None):
    chunks = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = clean_text(row.get("chunk_text", ""))
            if not text:
                continue
            # Split very long chunks into smaller pieces for better retrieval.
            if len(text) > max_length:
                words = text.split()
                piece = []
                current_len = 0
                for word in words:
                    piece.append(word)
                    current_len += len(word) + 1
                    if current_len >= max_length:
                        chunks.append(
                            {
                                "page_title": row.get("page_title", ""),
                                "section_title": row.get("section_title", ""),
                                "text": " ".join(piece),
                            }
                        )
                        piece = []
                        current_len = 0
                if piece:
                    chunks.append(
                        {
                            "page_title": row.get("page_title", ""),
                            "section_title": row.get("section_title", ""),
                            "text": " ".join(piece),
                        }
                    )
            else:
                chunks.append(
                    {
                        "page_title": row.get("page_title", ""),
                        "section_title": row.get("section_title", ""),
                        "text": text,
                    }
                )
            if limit and len(chunks) >= limit:
                break
    return chunks


def build_db(csv_path: Path, db_path: Path, batch_size: int = 16, limit: Optional[int] = None):
    if db_path.exists():
        db_path.unlink()
        logger.info(f"Removed existing {db_path}")

    chunks = load_chunks(csv_path, limit=limit)
    logger.info(f"Loaded {len(chunks)} chunks from {csv_path}")

    embedder = Embedder()
    retriever = Retriever(db_path=db_path)

    for i in tqdm(range(0, len(chunks), batch_size), desc="Embedding"):
        batch = chunks[i : i + batch_size]
        texts = [c["text"] for c in batch]
        embeddings = embedder.embed(texts)
        retriever.add(batch, embeddings)

    logger.info(f"Built {db_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv",
        default=os.path.join("..", "v1", "scraped_pages", "terraria_dataChunks.csv"),
        help="Path to the scraped CSV",
    )
    parser.add_argument(
        "--output",
        default=str(TERRARIA_DB),
        help="Output sqlite-vec database",
    )
    parser.add_argument(
        "--batch-size", type=int, default=16, help="Embedding batch size"
    )
    parser.add_argument(
        "--rebuild", action="store_true", help="Overwrite existing database"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Only embed the first N chunks (for testing)"
    )
    args = parser.parse_args()

    csv_path = Path(args.csv).resolve()
    db_path = Path(args.output).resolve()
    if db_path.exists() and not args.rebuild:
        logger.info(f"{db_path} already exists. Use --rebuild to overwrite.")
        return

    build_db(csv_path, db_path, batch_size=args.batch_size, limit=args.limit)


if __name__ == "__main__":
    main()
