from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.deps import get_current_user
from langchain_agents.agent_u import DEFAULT_THREAD_ID, chat, resume_chat

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResumeRequest(BaseModel):
    resume: dict[str, Any]
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    status: Literal["complete", "interrupt"]
    reply: str | None = None
    interrupt: dict[str, Any] | None = None
    user_id: str
    conversation_id: str


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(
    req: ChatRequest,
    user: Annotated[Any, Depends(get_current_user)],
) -> ChatResponse:
    """Run one agent turn for the authenticated user.

    Defined as a sync `def` so FastAPI runs the blocking LLM/Composio calls in a
    threadpool instead of blocking the event loop. ``conversation_id`` selects the
    LangGraph thread so multi-turn context is preserved.
    """
    user_id = user.id
    thread_id = req.conversation_id or DEFAULT_THREAD_ID
    result = chat(req.message, user_id=user_id, thread_id=thread_id)
    return ChatResponse(**result)


@router.post("/chat/resume", response_model=ChatResponse)
def chat_resume_endpoint(
    req: ChatResumeRequest,
    user: Annotated[Any, Depends(get_current_user)],
) -> ChatResponse:
    """Resume the agent after a HITL interrupt (e.g. contact selection)."""
    user_id = user.id
    thread_id = req.conversation_id or DEFAULT_THREAD_ID
    result = resume_chat(req.resume, user_id=user_id, thread_id=thread_id)
    return ChatResponse(**result)
