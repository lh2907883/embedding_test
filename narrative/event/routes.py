from fastapi import APIRouter, Request

from event.api_models import InjectEventRequest, InjectEventResponse

router = APIRouter(prefix="/api")


@router.post("/events/inject", response_model=InjectEventResponse)
def inject_event(req: InjectEventRequest, request: Request):
    engine = request.app.state.engine
    rounds = engine.inject_event(
        req.description, req.location, req.intensity,
        req.involved_npc_ids, req.game_time,
    )
    total = sum(len(r.decisions) for r in rounds)
    return InjectEventResponse(rounds=rounds, total_decisions=total)
