from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
MAX_CHUNK_CHARS = int(os.getenv("TERRARIA_MAX_CHUNK_CHARS", "900"))

import numpy as np
from bs4 import BeautifulSoup
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings


@dataclass
class Chunk:
    page_title: str
    section_title: str
    chunk_text: str
    source_file: str
    url: str


def _hash_file(file_path: str) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _collect_source_hashes(source_dir: str) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for name in sorted(os.listdir(source_dir)):
        if not name.endswith(".html"):
            continue
        full_path = os.path.join(source_dir, name)
        hashes[name] = _hash_file(full_path)
    return hashes


def _needs_reindex(manifest_path: str, source_hashes: Dict[str, str]) -> bool:
    if not os.path.exists(manifest_path):
        return True

    with open(manifest_path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    return manifest.get("source_hashes") != source_hashes


def _write_manifest(manifest_path: str, source_hashes: Dict[str, str]) -> None:
    payload = {"source_hashes": source_hashes}
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _clean_content(container: BeautifulSoup) -> None:
    for tag in container.find_all(["aside", "nav", "table", "script", "style", "figure"]):
        tag.decompose()


def _chunk_sections(container: BeautifulSoup, page_title: str, source_file: str, url: str) -> List[Chunk]:
    chunks: List[Chunk] = []
    headings = container.find_all(["h2", "h3", "h4"])

    if not headings:
        text = container.get_text("\n", strip=True)
        if text:
            chunks.append(
                Chunk(
                    page_title=page_title,
                    section_title="Overview",
                    chunk_text=text,
                    source_file=source_file,
                    url=url,
                )
            )
        return chunks

    first_heading = headings[0]
    intro_text = "".join(str(node) for node in container.contents if node is not first_heading)
    if intro_text.strip():
        intro_soup = BeautifulSoup(intro_text, "lxml")
        intro_value = intro_soup.get_text("\n", strip=True)
        if intro_value:
            chunks.append(
                Chunk(
                    page_title=page_title,
                    section_title="Overview",
                    chunk_text=intro_value,
                    source_file=source_file,
                    url=url,
                )
            )

    for heading in headings:
        section_title = heading.get_text(" ", strip=True)
        section_nodes = []
        for sibling in heading.next_siblings:
            if getattr(sibling, "name", None) in ["h2", "h3", "h4"]:
                break
            section_nodes.append(str(sibling))

        if not section_nodes:
            continue

        section_html = "".join(section_nodes)
        section_soup = BeautifulSoup(section_html, "lxml")
        section_text = section_soup.get_text("\n", strip=True)
        if not section_text:
            continue

        chunks.extend(
            _split_long_chunk(
                Chunk(
                    page_title=page_title,
                    section_title=section_title,
                    chunk_text=section_text,
                    source_file=source_file,
                    url=url,
                )
            )
        )

    return chunks


def _split_long_chunk(chunk: Chunk, max_chars: int = 1200) -> List[Chunk]:
    text = chunk.chunk_text.strip()
    if len(text) <= max_chars:
        return [chunk]

    parts: List[Chunk] = []
    start = 0
    index = 1
    while start < len(text):
        end = min(start + max_chars, len(text))
        segment = text[start:end].strip()
        if segment:
            parts.append(
                Chunk(
                    page_title=chunk.page_title,
                    section_title=f"{chunk.section_title} (part {index})",
                    chunk_text=segment,
                    source_file=chunk.source_file,
                    url=chunk.url,
                )
            )
            index += 1
        start = end

    return parts


def _load_chunks_from_html(source_dir: str) -> List[Chunk]:
    chunks: List[Chunk] = []
    for name in sorted(os.listdir(source_dir)):
        if not name.endswith(".html"):
            continue

        full_path = os.path.join(source_dir, name)
        with open(full_path, "r", encoding="utf-8") as handle:
            soup = BeautifulSoup(handle.read(), "lxml")

        content = soup.find("div", class_="mw-parser-output")
        if not content:
            continue

        _clean_content(content)

        page_title = os.path.splitext(name)[0]
        url = f"https://terraria.fandom.com/wiki/{page_title}"
        chunks.extend(_chunk_sections(content, page_title, name, url))

    return chunks


def _deduplicate_chunks(chunks: Iterable[Chunk], embeddings: OllamaEmbeddings, threshold: float = 0.95) -> List[Chunk]:
    kept: List[Chunk] = []
    kept_vectors: List[np.ndarray] = []

    for chunk in chunks:
        safe_text = chunk.chunk_text[:MAX_CHUNK_CHARS]
        vector = np.array(embeddings.embed_query(safe_text), dtype=np.float32)
        if kept_vectors:
            norms = np.linalg.norm(kept_vectors, axis=1) * np.linalg.norm(vector)
            sims = np.dot(np.vstack(kept_vectors), vector) / np.maximum(norms, 1e-8)
            if float(np.max(sims)) >= threshold:
                continue

        kept.append(chunk)
        kept_vectors.append(vector)

    return kept


def _chunks_to_documents(chunks: List[Chunk]) -> List[Document]:
    documents: List[Document] = []
    for index, chunk in enumerate(chunks):
        metadata = {
            "page_title": chunk.page_title,
            "section_title": chunk.section_title,
            "source_file": chunk.source_file,
            "url": chunk.url,
        }
        documents.append(
            Document(page_content=chunk.chunk_text, metadata=metadata, id=str(index))
        )
    return documents


def load_or_build_retriever(
    data_dir: str,
    embedding_model: str,
    top_k: int,
    persist_directory: Optional[str] = None,
) -> Any:
    if persist_directory is None:
        persist_directory = os.path.join(os.path.dirname(__file__), "..", "chrome_langchain_db")

    persist_directory = os.path.abspath(persist_directory)
    os.makedirs(persist_directory, exist_ok=True)

    manifest_path = os.path.join(persist_directory, "index_manifest.json")
    source_hashes = _collect_source_hashes(data_dir)
    needs_reindex = _needs_reindex(manifest_path, source_hashes)

    embeddings = OllamaEmbeddings(model=embedding_model)

    if needs_reindex:
        shutil.rmtree(persist_directory, ignore_errors=True)
        os.makedirs(persist_directory, exist_ok=True)

        chunks = _load_chunks_from_html(data_dir)
        deduped = _deduplicate_chunks(chunks, embeddings)
        documents = _chunks_to_documents(deduped)

        vector_store = Chroma(
            collection_name="terraria_wiki",
            persist_directory=persist_directory,
            embedding_function=embeddings,
        )
        vector_store.add_documents(documents=documents)
        _write_manifest(manifest_path, source_hashes)
    else:
        vector_store = Chroma(
            collection_name="terraria_wiki",
            persist_directory=persist_directory,
            embedding_function=embeddings,
        )

    return vector_store.as_retriever(search_kwargs={"k": top_k})
