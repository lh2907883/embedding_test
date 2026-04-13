from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class MemoryType(str, Enum):
    BACKGROUND = "background"
    AFFECTED = "affected"
    WITNESSED = "witnessed"
    HEARD = "heard"
    ACTION = "action"
    THOUGHT = "thought"


class MemoryEntry(BaseModel):
    memory_id: str
    npc_id: str
    memory_type: MemoryType
    game_time: str
    content: str
    source_npc_id: Optional[str] = None
    related_npc_ids: list[str] = Field(default_factory=list)
    location: Optional[str] = None


class MemorySearchResult(BaseModel):
    memory_id: str
    npc_id: str
    content: str
    score: float
    memory_type: str
    game_time: str
    source_npc_id: Optional[str] = None
    related_npc_ids: list[str] = Field(default_factory=list)
    location: Optional[str] = None
