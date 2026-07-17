from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Annotated, Any

from app.deps import get_current_user
from langchain_agents.orchestrator_graph import orchestrator_chat

router = APIRouter(prefix="/api/orchestrator", tags=["orchestrator"])

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None

@router.post("/chat")
def orchestrator_chat_endpoint(
    req: ChatRequest,
    user: Annotated[Any, Depends(get_current_user)],
):
    thread_id = req.conversation_id or "default"
    return orchestrator_chat(req.message, user_id=user.id, thread_id=thread_id)