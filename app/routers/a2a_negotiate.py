import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.a2a import run_negotiation
from app.deps import get_current_user

router = APIRouter(prefix="/api/a2a", tags=["a2a"])


class StartRequest(BaseModel):
    peer_url: str
    proposal: str
    thread_id: str | None = None


class StartResponse(BaseModel):
    thread_id: str
    transcript: list[dict[str, str]]


@router.post("/start", response_model=StartResponse)
async def start(
    req: StartRequest,
    user: Annotated[Any, Depends(get_current_user)],
) -> StartResponse:
    """Initiate a negotiation against the peer URL chosen by the caller.

    The peer is supplied per request (from the frontend), so any instance can
    initiate to any other; roles are decided here, not in config.
    """
    thread_id = req.thread_id or str(uuid.uuid4())
    transcript = await run_negotiation(req.peer_url, req.proposal, thread_id, user.id)
    return StartResponse(thread_id=thread_id, transcript=transcript)
