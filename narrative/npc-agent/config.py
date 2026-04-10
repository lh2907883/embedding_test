from pathlib import Path

QDRANT_STORAGE_PATH = str(Path(__file__).parent / "data" / "qdrant_storage")
COLLECTION_NAME = "npc_memories"
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
EMBEDDING_DIMENSION = 1024
DB_PATH = str(Path(__file__).parent / "data" / "metadata.db")
