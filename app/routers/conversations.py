from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.conversation_store import get_for_user, list_for_user
from app.deps import get_current_user

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class ConversationSummary(BaseModel):
    id: str
    title: str
    updated_at: str


class StoredMessage(BaseModel):
    role: str
    content: str


class ConversationDetail(BaseModel):
    id: str
    title: str
    messages: list[StoredMessage]
    updated_at: str


@router.get("", response_model=list[ConversationSummary])
def list_conversations(
    user: Annotated[Any, Depends(get_current_user)],
) -> list[ConversationSummary]:
    rows = list_for_user(user.id)
    return [
        ConversationSummary(
            id=row["id"],
            title=row.get("title") or "New chat",
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    user: Annotated[Any, Depends(get_current_user)],
) -> ConversationDetail:
    row = get_for_user(user.id, conversation_id)
    raw_messages = row.get("messages") or []
    messages = [
        StoredMessage(role=m.get("role", "assistant"), content=m.get("content", ""))
        for m in raw_messages
        if isinstance(m, dict)
    ]
    return ConversationDetail(
        id=row["id"],
        title=row.get("title") or "New chat",
        messages=messages,
        updated_at=row["updated_at"],
    )
