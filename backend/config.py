from pathlib import Path

QDRANT_STORAGE_PATH = str(Path(__file__).parent / "data" / "qdrant_storage")
COLLECTION_NAME = "documents"
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
EMBEDDING_DIMENSION = 1024
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
DISTANCE_METRIC = "Cosine"
