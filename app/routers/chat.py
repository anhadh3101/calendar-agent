import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.conversation_store import append_messages, exists_for_user, title_from_message
from app.deps import get_current_user
from langchain_agents.agent_u import chat, resume_chat

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


def _resolve_conversation_id(conversation_id: str | None) -> str:
    return conversation_id or str(uuid.uuid4())


def _persist_assistant_reply(
    user_id: str, conversation_id: str, result: dict[str, Any]
) -> None:
    if result.get("status") != "complete":
        return
    reply = result.get("reply")
    if not reply:
        return
    append_messages(
        user_id,
        conversation_id,
        [{"role": "assistant", "content": reply}],
    )


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
    thread_id = _resolve_conversation_id(req.conversation_id)
    is_new = not exists_for_user(user_id, thread_id)
    append_messages(
        user_id,
        thread_id,
        [{"role": "user", "content": req.message}],
        title=title_from_message(req.message) if is_new else None,
    )
    result = chat(req.message, user_id=user_id, thread_id=thread_id)
    _persist_assistant_reply(user_id, thread_id, result)
    result["conversation_id"] = thread_id
    return ChatResponse(**result)


@router.post("/chat/resume", response_model=ChatResponse)
def chat_resume_endpoint(
    req: ChatResumeRequest,
    user: Annotated[Any, Depends(get_current_user)],
) -> ChatResponse:
    """Resume the agent after a HITL interrupt (e.g. contact selection)."""
    user_id = user.id
    thread_id = _resolve_conversation_id(req.conversation_id)
    result = resume_chat(req.resume, user_id=user_id, thread_id=thread_id)
    _persist_assistant_reply(user_id, thread_id, result)
    result["conversation_id"] = thread_id
    return ChatResponse(**result)
