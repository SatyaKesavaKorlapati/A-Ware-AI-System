from __future__ import annotations

import json
import os

import chromadb
from chromadb.utils import embedding_functions
from transformers.utils import logging as hf_logging

from utils.project_paths import DB_DIR, METADATA_PATH, ensure_local_model_dirs


COLLECTION_NAME = "warehouse_inventory"
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
hf_logging.set_verbosity_error()


def build_embedding_function():
    model_paths = ensure_local_model_dirs()
    model_path = str(model_paths["minilm"] or "sentence-transformers/all-MiniLM-L6-v2")
    return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_path)


def load_metadata() -> list[dict]:
    if not METADATA_PATH.exists():
        raise FileNotFoundError(f"Metadata file not found: {METADATA_PATH}")

    with METADATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def run_ingestion(reset: bool = True, batch_size: int = 256):
    DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(DB_DIR))
    embedding_model = build_embedding_function()
    data = load_metadata()

    if reset:
        existing_names = {collection.name for collection in client.list_collections()}
        if COLLECTION_NAME in existing_names:
            client.delete_collection(COLLECTION_NAME)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_model,
        metadata={"description": "Spatial warehouse metadata for multimodal RAG"},
    )

    total_items = len(data)
    print(f"📦 Total items to process: {total_items}")

    for start_idx in range(0, total_items, batch_size):
        batch = data[start_idx : start_idx + batch_size]
        ids = []
        documents = []
        metadatas = []

        for offset, entry in enumerate(batch):
            world_position = entry.get("world_position", {})
            prim_path = entry.get("prim_path", f"/unknown/{start_idx + offset}")
            name = entry.get("name", "unknown")
            category = entry.get("category", "unknown")
            x = world_position.get("x", 0.0)
            y = world_position.get("y", 0.0)
            z = world_position.get("z", 0.0)

            ids.append(prim_path)
            documents.append(
                entry.get(
                    "text_context",
                    f"Object {name} belongs to category {category} at coordinates ({x}, {y}, {z}).",
                )
            )
            metadatas.append(
                {
                    "prim_path": prim_path,
                    "name": name,
                    "category": category,
                    "x": x,
                    "y": y,
                    "z": z,
                }
            )

        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        end_idx = min(start_idx + batch_size, total_items)
        print(f"✅ Indexed items {start_idx} to {end_idx}")

    print(f"🚀 Ingestion complete. Database saved to {DB_DIR}")
    return collection


def ensure_database(populate_if_missing: bool = True):
    DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(DB_DIR))
    embedding_model = build_embedding_function()
    expected_count = len(load_metadata())
    existing_names = {collection.name for collection in client.list_collections()}

    if COLLECTION_NAME not in existing_names:
        if not populate_if_missing:
            raise RuntimeError(f"Collection {COLLECTION_NAME} does not exist.")
        return run_ingestion(reset=True)

    collection = client.get_collection(name=COLLECTION_NAME, embedding_function=embedding_model)
    actual_count = collection.count()
    if actual_count != expected_count and populate_if_missing:
        print(f"♻️ Rebuilding index because count mismatch was detected: {actual_count} != {expected_count}")
        return run_ingestion(reset=True)
    return collection


if __name__ == "__main__":
    run_ingestion(reset=True)
