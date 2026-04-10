from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import QDRANT_STORAGE_PATH, COLLECTION_NAME, EMBEDDING_DIMENSION, DB_PATH
from vector_store import VectorStore
from embedding_service import EmbeddingService
from metadata_store import MetadataStore
from npc_memory_manager import NpcMemoryManager
from api_models import (
    CreateNpcRequest, UpdateNpcRequest, NpcResponse,
    AddMemoryRequest, SearchMemoriesRequest,
    CreateGoalRequest, UpdateGoalRequest, GoalResponse,
)
from models import MemoryEntry, MemorySearchResult


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = VectorStore(QDRANT_STORAGE_PATH, COLLECTION_NAME, EMBEDDING_DIMENSION)
    app.state.store = store
    app.state.embedder = EmbeddingService()
    app.state.manager = NpcMemoryManager(store, app.state.embedder)
    app.state.metadata = MetadataStore(DB_PATH)
    yield
    store.close()
    app.state.metadata.close()


app = FastAPI(title="NPC Memory Service", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _check_npc(npc_id: str):
    if not app.state.metadata.get_npc(npc_id):
        raise HTTPException(404, f"NPC {npc_id} 不存在")


# ── NPC 管理 ──

@app.post("/api/npcs", response_model=NpcResponse)
def create_npc(req: CreateNpcRequest):
    meta: MetadataStore = app.state.metadata
    if meta.get_npc(req.npc_id):
        raise HTTPException(409, f"NPC {req.npc_id} 已存在")
    npc = meta.create_npc(req.npc_id, req.name, req.personality, req.traits, req.faction, req.location)
    npc["memory_count"] = 0
    return npc


@app.get("/api/npcs", response_model=list[NpcResponse])
def list_npcs():
    meta: MetadataStore = app.state.metadata
    manager: NpcMemoryManager = app.state.manager
    npcs = meta.list_npcs()
    for npc in npcs:
        npc["memory_count"] = manager.count_memories(npc["npc_id"])
    return npcs


@app.get("/api/npcs/{npc_id}", response_model=NpcResponse)
def get_npc(npc_id: str):
    _check_npc(npc_id)
    npc = app.state.metadata.get_npc(npc_id)
    npc["memory_count"] = app.state.manager.count_memories(npc_id)
    return npc


@app.put("/api/npcs/{npc_id}", response_model=NpcResponse)
def update_npc(npc_id: str, req: UpdateNpcRequest):
    _check_npc(npc_id)
    npc = app.state.metadata.update_npc(npc_id, **req.model_dump(exclude_none=True))
    npc["memory_count"] = app.state.manager.count_memories(npc_id)
    return npc


@app.delete("/api/npcs/{npc_id}")
def delete_npc(npc_id: str):
    _check_npc(npc_id)
    app.state.manager.delete_npc_memories(npc_id)
    app.state.metadata.delete_npc(npc_id)
    return {"ok": True}


# ── 记忆管理 ──

@app.post("/api/npcs/{npc_id}/memories", response_model=MemoryEntry)
def add_memory(npc_id: str, req: AddMemoryRequest):
    _check_npc(npc_id)
    return app.state.manager.add_memory(npc_id, req)


@app.post("/api/npcs/{npc_id}/memories/batch", response_model=list[MemoryEntry])
def add_memories_batch(npc_id: str, memories: list[AddMemoryRequest]):
    _check_npc(npc_id)
    return app.state.manager.add_memories_batch(npc_id, memories)


@app.get("/api/npcs/{npc_id}/memories")
def list_memories(npc_id: str, limit: int = 50):
    _check_npc(npc_id)
    return app.state.manager.list_memories(npc_id, limit=limit)


@app.post("/api/npcs/{npc_id}/memories/search", response_model=list[MemorySearchResult])
def search_memories(npc_id: str, req: SearchMemoriesRequest):
    _check_npc(npc_id)
    return app.state.manager.search_memories(
        npc_id, req.query, req.top_k,
        memory_type=req.memory_type.value if req.memory_type else None,
        related_npc_id=req.related_npc_id,
    )


@app.delete("/api/npcs/{npc_id}/memories/{memory_id}")
def delete_memory(npc_id: str, memory_id: str):
    _check_npc(npc_id)
    app.state.manager.delete_memory(memory_id)
    return {"ok": True}


# ── 目标管理 ──

@app.post("/api/npcs/{npc_id}/goals", response_model=GoalResponse)
def create_goal(npc_id: str, req: CreateGoalRequest):
    _check_npc(npc_id)
    import uuid
    goal_id = str(uuid.uuid4())[:8]
    return app.state.metadata.create_goal(
        goal_id, npc_id, req.goal_type, req.description,
        req.priority, req.created_game_time, req.deadline_game_time,
    )


@app.get("/api/npcs/{npc_id}/goals", response_model=list[GoalResponse])
def list_goals(npc_id: str, status: str | None = "active"):
    _check_npc(npc_id)
    return app.state.metadata.list_goals(npc_id, status=status)


@app.put("/api/npcs/{npc_id}/goals/{goal_id}", response_model=GoalResponse)
def update_goal(npc_id: str, goal_id: str, req: UpdateGoalRequest):
    _check_npc(npc_id)
    goal = app.state.metadata.update_goal(goal_id, **req.model_dump(exclude_none=True))
    if not goal:
        raise HTTPException(404, f"目标 {goal_id} 不存在")
    return goal


@app.delete("/api/npcs/{npc_id}/goals/{goal_id}")
def delete_goal(npc_id: str, goal_id: str):
    _check_npc(npc_id)
    if not app.state.metadata.delete_goal(goal_id):
        raise HTTPException(404, f"目标 {goal_id} 不存在")
    return {"ok": True}
