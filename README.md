# terrariaRAG

> Retrieval-Augmented-Generation (RAG) helper for Terraria wiki content — a small project to scrape, index, and query Terraria wiki pages using vector embeddings and a local Chroma DB.

## Project Structure

- `main.py` — main entry point for running the example query/assistant (project-specific behavior may vary).
- `vector.py` — utilities for building or querying vector embeddings.
- `whatToScrape2.py` — scraping helper used to collect pages from the Terraria wiki.
- `requirements.txt` — Python dependencies.
- `scraped_pages/` — local HTML copies of scraped Terraria wiki pages used as the knowledge source.
- `chrome_langchain_db/` — local Chroma DB (SQLite) used to store embeddings (`chroma.sqlite3`).

## Purpose

Objective: provide an easy way to ask questions about Terraria while playing, so you don't have to repeatedly search Google or the wiki during gameplay.

This repository demonstrates a small Retrieval-Augmented Generation workflow: scrape relevant Terraria wiki pages, convert text into embeddings, store them in a local vector database, and run retrieval + generation workflows against that indexed knowledge.

Intended uses:

- Experiment with question-answering over game documentation.
- Prototype a small RAG assistant for Terraria-related information.

## Requirements

- Python 3.9+ (3.10 recommended)
- A virtual environment (venv) is recommended

Install dependencies:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # PowerShell on Windows
pip install -r requirements.txt
```

## Quick Start

1. (Optional) Scrape pages — run the scraper to refresh `scraped_pages/`:

```bash
python whatToScrape2.py
```

2. Build or update the vector index (embeddings) using `vector.py` or the provided scripts. Example:

```bash
python vector.py
```

3. Run the assistant / query script. Depending on the repo entrypoint you may run:

```bash
python main.py
```

Adjust the scripts as needed for your model keys, embedding provider, or retrieval settings.

## Notes

- The repository includes a local Chroma SQLite database at `chrome_langchain_db/chroma.sqlite3`. Back this up if you need to preserve embeddings.
- The scraped HTML files in `scraped_pages/` are the source documents for indexing — you can add, remove, or update files and then rebuild the index.

## Contributing

Feel free to open issues or pull requests. Useful improvements include:

- Better scraping/parsing to extract cleaner text from pages.
- Indexing performance improvements and chunking strategies.
- Example notebooks or tests demonstrating typical queries.

## License

This project does not include a license file. Add a `LICENSE` if you want to make the terms explicit.
