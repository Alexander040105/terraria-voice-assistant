from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import os
import pandas as pd

current_dir  = os.getcwd()
df = pd.read_csv(f"{current_dir}\\backend\\scraped_pages\\terraria_dataChunks.csv")

# CSV_PATH = os.path.join(
#     PROJECT_ROOT,
#     "scraped_pages",
#     "terraria_dataChunks.csv"
# )

# df = pd.read_csv(CSV_PATH)

# Clean column names (important)
df.columns = df.columns.str.strip()
embeddings = OllamaEmbeddings(model="llama3.2")

# db_location = os.path.join(PROJECT_ROOT, "chroma_langchain_db")
db_location = "./chrome_langchain_db"
add_documents = not os.path.exists(db_location)

if add_documents:
    documents = []
    ids = []

    for i, row in df.iterrows():
        page_content = " ".join(
            str(x) for x in [
                row.get("page_title", ""),
                row.get("section_title", ""),
                row.get("chunk_text", "")
            ]
            if pd.notna(x)
        )

        metadata = {
            "csv_id": str(row.get("id", i)),
            "page_title": row.get("page_title"),
            "section_title": row.get("section_title"),
            "chunk_type": row.get("chunk_type"),
            "source_file": row.get("source_file"),
        }

        document = Document(
            page_content=page_content,
            metadata=metadata,
            id=str(i)
        )

        documents.append(document)
        ids.append(str(i))

vector_store = Chroma(
    collection_name="terraria_wiki",
    persist_directory=db_location,
    embedding_function=embeddings,
)

if add_documents:
    vector_store.add_documents(documents=documents, ids=ids)


retriever = vector_store.as_retriever(
    search_kwargs={"k": 5}
)
