from fastapi import APIRouter, Request

from event.api_models import SimulateSceneRequest, SimulateSceneResponse

router = APIRouter(prefix="/api")


@router.post("/scenes/simulate", response_model=SimulateSceneResponse)
def simulate_scene(req: SimulateSceneRequest, request: Request):
    engine = request.app.state.engine
    rounds = engine.simulate_scene(
        req.description, req.location, req.characters,
        req.intensity, req.game_time, req.preset_event,
    )
    total = sum(len(r.decisions) for r in rounds)
    return SimulateSceneResponse(rounds=rounds, total_decisions=total)
