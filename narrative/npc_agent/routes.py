import uuid
from fastapi import APIRouter, HTTPException, Request

from shared.models import MemoryEntry, MemorySearchResult
from npc_agent.api_models import (
    CreateNpcRequest, UpdateNpcRequest, NpcResponse,
    AddMemoryRequest, SearchMemoriesRequest,
    CreateGoalRequest, UpdateGoalRequest, GoalResponse,
)

router = APIRouter(prefix="/api")


def _check_npc(request: Request, npc_id: str):
    if not request.app.state.metadata.get_npc(npc_id):
        raise HTTPException(404, f"NPC {npc_id} 不存在")


# ── NPC 管理 ──

@router.post("/npcs", response_model=NpcResponse)
def create_npc(req: CreateNpcRequest, request: Request):
    meta = request.app.state.metadata
    if meta.get_npc(req.npc_id):
        raise HTTPException(409, f"NPC {req.npc_id} 已存在")
    npc = meta.create_npc(req.npc_id, req.name, req.personality, req.traits, req.faction, req.location)
    npc["memory_count"] = 0
    return npc


@router.get("/npcs", response_model=list[NpcResponse])
def list_npcs(request: Request):
    meta = request.app.state.metadata
    manager = request.app.state.memory_manager
    npcs = meta.list_npcs()
    for npc in npcs:
        npc["memory_count"] = manager.count_memories(npc["npc_id"])
    return npcs


@router.get("/npcs/{npc_id}", response_model=NpcResponse)
def get_npc(npc_id: str, request: Request):
    _check_npc(request, npc_id)
    npc = request.app.state.metadata.get_npc(npc_id)
    npc["memory_count"] = request.app.state.memory_manager.count_memories(npc_id)
    return npc


@router.put("/npcs/{npc_id}", response_model=NpcResponse)
def update_npc(npc_id: str, req: UpdateNpcRequest, request: Request):
    _check_npc(request, npc_id)
    npc = request.app.state.metadata.update_npc(npc_id, **req.model_dump(exclude_none=True))
    npc["memory_count"] = request.app.state.memory_manager.count_memories(npc_id)
    return npc


@router.delete("/npcs/{npc_id}")
def delete_npc(npc_id: str, request: Request):
    _check_npc(request, npc_id)
    request.app.state.memory_manager.delete_npc_memories(npc_id)
    request.app.state.metadata.delete_npc(npc_id)
    return {"ok": True}


# ── 记忆管理 ──

@router.post("/npcs/{npc_id}/memories", response_model=MemoryEntry)
def add_memory(npc_id: str, req: AddMemoryRequest, request: Request):
    _check_npc(request, npc_id)
    return request.app.state.memory_manager.add_memory(npc_id, req)


@router.post("/npcs/{npc_id}/memories/batch", response_model=list[MemoryEntry])
def add_memories_batch(npc_id: str, memories: list[AddMemoryRequest], request: Request):
    _check_npc(request, npc_id)
    return request.app.state.memory_manager.add_memories_batch(npc_id, memories)


@router.get("/npcs/{npc_id}/memories")
def list_memories(npc_id: str, request: Request, limit: int = 50):
    _check_npc(request, npc_id)
    return request.app.state.memory_manager.list_memories(npc_id, limit=limit)


@router.post("/npcs/{npc_id}/memories/search", response_model=list[MemorySearchResult])
def search_memories(npc_id: str, req: SearchMemoriesRequest, request: Request):
    _check_npc(request, npc_id)
    return request.app.state.memory_manager.search_memories(
        npc_id, req.query, req.top_k,
        memory_type=req.memory_type.value if req.memory_type else None,
        related_npc_id=req.related_npc_id,
    )


@router.delete("/npcs/{npc_id}/memories/{memory_id}")
def delete_memory(npc_id: str, memory_id: str, request: Request):
    _check_npc(request, npc_id)
    request.app.state.memory_manager.delete_memory(memory_id)
    return {"ok": True}


# ── 目标管理 ──

@router.post("/npcs/{npc_id}/goals", response_model=GoalResponse)
def create_goal(npc_id: str, req: CreateGoalRequest, request: Request):
    _check_npc(request, npc_id)
    goal_id = str(uuid.uuid4())[:8]
    return request.app.state.metadata.create_goal(
        goal_id, npc_id, req.goal_type, req.description,
        req.priority, req.created_game_time, req.deadline_game_time,
    )


@router.get("/npcs/{npc_id}/goals", response_model=list[GoalResponse])
def list_goals(npc_id: str, request: Request, status: str | None = "active"):
    _check_npc(request, npc_id)
    return request.app.state.metadata.list_goals(npc_id, status=status)


@router.put("/npcs/{npc_id}/goals/{goal_id}", response_model=GoalResponse)
def update_goal(npc_id: str, goal_id: str, req: UpdateGoalRequest, request: Request):
    _check_npc(request, npc_id)
    goal = request.app.state.metadata.update_goal(goal_id, **req.model_dump(exclude_none=True))
    if not goal:
        raise HTTPException(404, f"目标 {goal_id} 不存在")
    return goal


@router.delete("/npcs/{npc_id}/goals/{goal_id}")
def delete_goal(npc_id: str, goal_id: str, request: Request):
    _check_npc(request, npc_id)
    if not request.app.state.metadata.delete_goal(goal_id):
        raise HTTPException(404, f"目标 {goal_id} 不存在")
    return {"ok": True}
