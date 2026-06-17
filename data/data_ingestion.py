from __future__ import annotations
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from transformers.utils import logging as hf_logging
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from utils.project_paths import DB_DIR

MANUALS_DIR = Path(__file__).parent / "manuals"
SPECS_DIR = Path(__file__).parent / "specs"

os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
hf_logging.set_verbosity_error()

class GeminiEmbeddingFunction(EmbeddingFunction):
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-2",
            google_api_key=api_key
        )
    def __call__(self, input: Documents) -> Embeddings:
        # chromadb passes a list of strings
        return self.embeddings.embed_documents(list(input))

def load_markdown_files(directory: Path) -> list[dict]:
    docs = []
    if not directory.exists():
        return docs
    for md_file in directory.glob("*.md"):
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
            chunks = content.split("## ")
            for i, chunk in enumerate(chunks):
                if not chunk.strip(): continue
                title = chunk.split("\n")[0].strip() if i > 0 else "Introduction"
                text = ("## " + chunk) if i > 0 else chunk
                docs.append({
                    "id": f"{md_file.stem}_chunk_{i}",
                    "document": text.strip(),
                    "metadata": {"source": md_file.name, "section": title}
                })
    return docs

def ingest_collection(client: chromadb.PersistentClient, collection_name: str, directory: Path, reset: bool = True):
    embedding_model = GeminiEmbeddingFunction()
    
    if reset:
        existing_names = {c.name for c in client.list_collections()}
        if collection_name in existing_names:
            client.delete_collection(collection_name)

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_model,
        metadata={"description": f"A-Ware DB for {collection_name}"},
    )

    data = load_markdown_files(directory)
    if not data:
        print(f"No files found in {directory} to ingest.")
        return collection

    ids = [d["id"] for d in data]
    documents = [d["document"] for d in data]
    metadatas = [d["metadata"] for d in data]

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    print(f"Indexed {len(data)} chunks into '{collection_name}'.")
    return collection

def run_ingestion(reset: bool = True):
    DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(DB_DIR))
    
    print("Ingesting system manuals...")
    ingest_collection(client, "system_manuals", MANUALS_DIR, reset)
    
    print("Ingesting system specs and research...")
    ingest_collection(client, "system_specs_and_research", SPECS_DIR, reset)
    
    print("All databases ingested successfully.")

def ensure_databases(populate_if_missing: bool = True):
    DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(DB_DIR))
    embedding_model = GeminiEmbeddingFunction()
    
    existing_names = {c.name for c in client.list_collections()}
    
    if "system_manuals" not in existing_names or "system_specs_and_research" not in existing_names:
        if not populate_if_missing:
            raise RuntimeError("Required ChromaDB collections do not exist.")
        run_ingestion(reset=True)

    return {
        "manuals": client.get_collection(name="system_manuals", embedding_function=embedding_model),
        "specs": client.get_collection(name="system_specs_and_research", embedding_function=embedding_model)
    }

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    run_ingestion(reset=True)
