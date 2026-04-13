from pathlib import Path

QDRANT_STORAGE_PATH = str(Path(__file__).parent / "data" / "qdrant_storage")
COLLECTION_NAME = "npc_memories"
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
EMBEDDING_DIMENSION = 1024
DB_PATH = str(Path(__file__).parent / "data" / "metadata.db")

import os
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=True)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
MAX_DECISION_ROUNDS = 10
