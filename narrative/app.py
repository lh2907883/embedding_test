from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import QDRANT_STORAGE_PATH, COLLECTION_NAME, EMBEDDING_DIMENSION, DB_PATH
from shared.vector_store import VectorStore
from shared.embedding_service import EmbeddingService
from shared.llm_service import LlmService
from npc_agent.metadata_store import MetadataStore
from npc_agent.memory_manager import NpcMemoryManager
from event.decision_engine import DecisionEngine
from npc_agent.routes import router as npc_router
from event.routes import router as event_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = VectorStore(QDRANT_STORAGE_PATH, COLLECTION_NAME, EMBEDDING_DIMENSION)
    app.state.store = store
    app.state.embedder = EmbeddingService()
    app.state.memory_manager = NpcMemoryManager(store, app.state.embedder)
    app.state.metadata = MetadataStore(DB_PATH)
    app.state.llm = LlmService()
    app.state.engine = DecisionEngine(app.state.memory_manager, app.state.metadata, app.state.llm)
    yield
    store.close()
    app.state.metadata.close()


app = FastAPI(title="NPC Narrative Service", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(npc_router)
app.include_router(event_router)
