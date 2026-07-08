import json
import uuid
from collections.abc import Iterator
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.conversation_store import append_messages, exists_for_user, title_from_message
from app.deps import get_current_user
from langchain_agents.gaia import (
    build_chat_result,
    chat,
    get_agent_bundle,
    resume_chat,
    stream_chat,
)

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


def _thread_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def _message_chunk_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return ""


def _iter_stream_events(chunks: Iterator[Any]) -> Iterator[dict[str, str]]:
    """Translate LangGraph stream chunks into SSE event dicts."""
    for chunk in chunks:
        mode: str | None = None
        payload = chunk

        if isinstance(chunk, tuple) and len(chunk) == 2:
            first, second = chunk
            if isinstance(first, str):
                mode, payload = first, second
            elif hasattr(first, "content"):
                payload = chunk

        if mode == "messages" or (
            mode is None
            and isinstance(payload, tuple)
            and len(payload) == 2
            and hasattr(payload[0], "content")
        ):
            message_chunk = payload[0] if isinstance(payload, tuple) else payload
            text = _message_chunk_text(getattr(message_chunk, "content", ""))
            if text:
                yield {
                    "event": "token",
                    "data": json.dumps({"content": text}),
                }
            continue

        if mode == "updates" or (mode is None and isinstance(payload, dict)):
            update = payload if isinstance(payload, dict) else {}
            for node in update:
                yield {
                    "event": "step",
                    "data": json.dumps({"node": node}),
                }


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


@router.post("/chat/stream")
def chat_stream_endpoint(
    req: ChatRequest,
    user: Annotated[Any, Depends(get_current_user)],
) -> EventSourceResponse:
    """Stream one orchestrator turn over SSE (token chunks + final done event)."""
    user_id = user.id
    thread_id = _resolve_conversation_id(req.conversation_id)
    is_new = not exists_for_user(user_id, thread_id)
    append_messages(
        user_id,
        thread_id,
        [{"role": "user", "content": req.message}],
        title=title_from_message(req.message) if is_new else None,
    )

    def event_generator() -> Iterator[dict[str, str]]:
        try:
            yield from _iter_stream_events(
                stream_chat(req.message, user_id=user_id, thread_id=thread_id)
            )

            agent, _ = get_agent_bundle(user_id)
            state = agent.get_state(_thread_config(thread_id))
            messages = (state.values or {}).get("messages", [])
            result = build_chat_result(
                agent, {"messages": messages}, thread_id, user_id
            )
            if result["status"] == "complete":
                _persist_assistant_reply(user_id, thread_id, result)
            result["conversation_id"] = thread_id
            yield {"event": "done", "data": json.dumps(result)}
        except Exception as exc:
            yield {
                "event": "error",
                "data": json.dumps({"detail": str(exc)}),
            }

    return EventSourceResponse(event_generator())


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
