import uuid
from pydantic import BaseModel, Field
from typing import Optional
from models import MemoryType


class CreateNpcRequest(BaseModel):
    npc_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    personality: str = ""
    traits: dict = Field(default_factory=dict)
    faction: Optional[str] = None
    location: Optional[str] = None


class UpdateNpcRequest(BaseModel):
    name: Optional[str] = None
    personality: Optional[str] = None
    traits: Optional[dict] = None
    faction: Optional[str] = None
    location: Optional[str] = None


class NpcResponse(BaseModel):
    npc_id: str
    name: str
    personality: str
    traits: dict
    faction: Optional[str] = None
    location: Optional[str] = None
    memory_count: int = 0
    created_at: str = ""


class AddMemoryRequest(BaseModel):
    game_time: str
    content: str
    memory_type: MemoryType = MemoryType.WITNESSED
    source_npc_id: Optional[str] = None
    related_npc_ids: list[str] = Field(default_factory=list)
    location: Optional[str] = None


class SearchMemoriesRequest(BaseModel):
    query: str
    top_k: int = Field(default=10, ge=1, le=100)
    memory_type: Optional[MemoryType] = None
    related_npc_id: Optional[str] = None
