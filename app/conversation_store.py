from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.database import supabase

MAX_TITLE_LEN = 50


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def title_from_message(message: str) -> str:
    text = message.strip().replace("\n", " ")
    if not text:
        return "New chat"
    if len(text) <= MAX_TITLE_LEN:
        return text
    return text[: MAX_TITLE_LEN - 1] + "\u2026"


def list_for_user(user_id: str) -> list[dict[str, Any]]:
    response = (
        supabase.table("conversations")
        .select("id, title, updated_at")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return response.data or []


def get_for_user(user_id: str, conversation_id: str) -> dict[str, Any]:
    response = (
        supabase.table("conversations")
        .select("id, title, messages, updated_at")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return response.data[0]


def exists_for_user(user_id: str, conversation_id: str) -> bool:
    response = (
        supabase.table("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return bool(response.data)


def ensure_conversation(
    user_id: str,
    conversation_id: str,
    *,
    title: str = "New chat",
) -> None:
    if exists_for_user(user_id, conversation_id):
        return
    supabase.table("conversations").insert(
        {
            "id": conversation_id,
            "user_id": user_id,
            "title": title,
            "messages": [],
            "updated_at": _now_iso(),
        }
    ).execute()


def append_messages(
    user_id: str,
    conversation_id: str,
    new_messages: list[dict[str, str]],
    *,
    title: str | None = None,
) -> None:
    ensure_conversation(
        user_id,
        conversation_id,
        title=title or "New chat",
    )

    row = get_for_user(user_id, conversation_id)
    messages = list(row.get("messages") or [])
    messages.extend(new_messages)

    update_payload: dict[str, Any] = {
        "messages": messages,
        "updated_at": _now_iso(),
    }
    if title and row.get("title") in (None, "", "New chat"):
        update_payload["title"] = title

    (
        supabase.table("conversations")
        .update(update_payload)
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )
