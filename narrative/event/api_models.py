from pydantic import BaseModel, Field
from typing import Optional


class InjectEventRequest(BaseModel):
    description: str
    location: str
    intensity: float = Field(default=1.0, ge=0.0, le=1.0)
    involved_npc_ids: list[str] = Field(default_factory=list)
    game_time: int = 0


class NpcDecisionOutput(BaseModel):
    npc_id: str
    npc_name: str
    action: str
    memory_note: Optional[str] = None
    new_events: list[dict] = Field(default_factory=list)
    goal_changes: list[dict] = Field(default_factory=list)


class RoundResult(BaseModel):
    round: int
    event_description: str
    decisions: list[NpcDecisionOutput]


class InjectEventResponse(BaseModel):
    rounds: list[RoundResult]
    total_decisions: int
