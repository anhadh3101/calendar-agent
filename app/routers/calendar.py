import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(ENV_PATH)

os.environ.setdefault(
    "COMPOSIO_CACHE_DIR",
    str(Path(__file__).resolve().parent.parent.parent / ".composio"),
)

from composio import Composio
from composio_langchain import LangchainProvider

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

USER_ID = os.getenv("APP_USER_ID", "default_user")
TOOLKIT = "googlecalendar"


@router.post("/connect")
def connect() -> dict:
    """Start the Google Calendar OAuth flow for this instance's user.

    Returns the Composio-hosted redirect URL. The frontend opens it; once the
    user grants access, Composio stores the OAuth tokens keyed by ``user_id``.
    """
    try:
        composio = Composio(provider=LangchainProvider())
        request = composio.toolkits.authorize(user_id=USER_ID, toolkit=TOOLKIT)
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the client
        raise HTTPException(status_code=502, detail=f"Composio authorize failed: {exc}")

    return {
        "redirect_url": request.redirect_url,
        "connection_id": request.id,
        "user_id": USER_ID,
    }


@router.get("/status")
def status() -> dict:
    """Report whether this user has an ACTIVE Google Calendar connection."""
    try:
        composio = Composio()
        result = composio.client.connected_accounts.list(
            toolkit_slugs=[TOOLKIT],
            user_ids=[USER_ID],
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Composio status failed: {exc}")

    connected = any(getattr(item, "status", None) == "ACTIVE" for item in result.items)
    return {"connected": connected, "user_id": USER_ID}
