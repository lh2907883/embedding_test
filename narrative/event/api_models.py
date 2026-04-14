from pydantic import BaseModel, Field
from typing import Optional


class PresetEvent(BaseModel):
    description: str
    actor_npc_id: str
    affected_npc_ids: list[str] = Field(default_factory=list)


class SimulateSceneRequest(BaseModel):
    description: str                                     # 场景背景
    location: str
    characters: list[str] = Field(default_factory=list)  # 在场主要人物
    intensity: float = Field(default=1.0, ge=0.0, le=1.0)
    game_time: int = 0
    preset_event: Optional[PresetEvent] = None


class NpcDecisionOutput(BaseModel):
    npc_id: str
    npc_name: str
    action: str
    new_events: list[dict] = Field(default_factory=list)
    goal_changes: list[dict] = Field(default_factory=list)


class RoundResult(BaseModel):
    round: int
    event_description: str
    decisions: list[NpcDecisionOutput]


class SimulateSceneResponse(BaseModel):
    rounds: list[RoundResult]
    total_decisions: int
