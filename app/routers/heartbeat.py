from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import supabase
from app.deps import get_current_user
from app.instance_owner import register_owner

router = APIRouter(prefix="/api", tags=["heartbeat"])


class HeartbeatRequest(BaseModel):
    agent_url: str


def _check_calendar_connected(user_id: str) -> bool:
    try:
        from composio import Composio

        composio = Composio()
        result = composio.client.connected_accounts.list(
            toolkit_slugs=["googlecalendar"],
            user_ids=[user_id],
        )
        return any(getattr(item, "status", None) == "ACTIVE" for item in result.items)
    except Exception:
        return False


@router.post("/heartbeat")
async def heartbeat(
    data: HeartbeatRequest,
    user: Annotated[Any, Depends(get_current_user)],
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    response = (
        supabase.table("agent_profiles")
        .update(
            {
                "agent_url": data.agent_url,
                "last_seen_at": now,
                "status": "online",
                "google_calendar_connected": _check_calendar_connected(user.id),
                "updated_at": now,
            }
        )
        .eq("user_id", user.id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Agent profile not found")

    register_owner(user.id)

    return {"ok": True, "last_seen_at": now}
