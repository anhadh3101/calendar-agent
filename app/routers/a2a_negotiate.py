import os
import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.a2a import run_negotiation

router = APIRouter(prefix="/api/a2a", tags=["a2a"])

USER_ID = os.getenv("APP_USER_ID", "default_user")


class StartRequest(BaseModel):
    peer_url: str
    proposal: str
    thread_id: str | None = None


class StartResponse(BaseModel):
    thread_id: str
    transcript: list[dict[str, str]]


@router.post("/start", response_model=StartResponse)
async def start(req: StartRequest) -> StartResponse:
    """Initiate a negotiation against the peer URL chosen by the caller.

    The peer is supplied per request (from the frontend), so any instance can
    initiate to any other; roles are decided here, not in config.
    """
    thread_id = req.thread_id or str(uuid.uuid4())
    transcript = await run_negotiation(req.peer_url, req.proposal, thread_id, USER_ID)
    return StartResponse(thread_id=thread_id, transcript=transcript)
