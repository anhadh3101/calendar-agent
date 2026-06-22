import os

from fastapi import APIRouter
from pydantic import BaseModel

from langchain_agents.agent_u import DEFAULT_THREAD_ID, chat, extract_last_ai_message

router = APIRouter(prefix="/api", tags=["chat"])

USER_ID = os.getenv("APP_USER_ID", "default_user")


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    user_id: str
    conversation_id: str


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest) -> ChatResponse:
    """Run one agent turn for this instance's user.

    Defined as a sync `def` so FastAPI runs the blocking LLM/Composio calls in a
    threadpool instead of blocking the event loop. ``conversation_id`` selects the
    LangGraph thread so multi-turn context is preserved.
    """
    thread_id = req.conversation_id or DEFAULT_THREAD_ID
    response = chat(req.message, user_id=USER_ID, thread_id=thread_id)
    return ChatResponse(
        reply=extract_last_ai_message(response),
        user_id=USER_ID,
        conversation_id=thread_id,
    )
