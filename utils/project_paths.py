from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_DIR = PROJECT_ROOT / "chroma_db"
METADATA_PATH = PROJECT_ROOT / "MDta" / "warehouse_rag_metadata_full.json"
MODELS_DIR = PROJECT_ROOT / "Python" / "Models"

def ensure_local_model_dirs():
    return {"minilm": None}
