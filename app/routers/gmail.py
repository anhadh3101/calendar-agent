import os
from pathlib import Path
from typing import Annotated, Any

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(ENV_PATH)

os.environ.setdefault(
    "COMPOSIO_CACHE_DIR",
    str(Path(__file__).resolve().parent.parent.parent / ".composio"),
)

from composio import Composio
from composio_langchain import LangchainProvider

from app.deps import get_current_user

router = APIRouter(prefix="/api/gmail", tags=["gmail"])
TOOLKIT = "gmail"


def _get_auth_config_id(composio: Composio, toolkit: str) -> str:
    """Resolve the auth config for a toolkit, creating one if needed."""
    auth_configs = composio.client.auth_configs.list(toolkit_slug=toolkit)
    if auth_configs.items:
        auth_config = sorted(
            auth_configs.items,
            key=lambda item: getattr(item, "created_at", "") or "",
            reverse=True,
        )[0]
        return auth_config.id

    created = composio.client.auth_configs.create(
        toolkit={"slug": toolkit},
        auth_config={
            "type": "use_composio_managed_auth",
            "tool_access_config": {
                "tools_for_connected_account_creation": [],
            },
        },
    )
    return created.auth_config.id


@router.post("/connect")
def connect(user: Annotated[Any, Depends(get_current_user)]) -> dict:
    """Start the Gmail OAuth flow for this instance's user."""
    user_id = user.id
    try:
        composio = Composio(provider=LangchainProvider())
        auth_config_id = _get_auth_config_id(composio, TOOLKIT)
        request = composio.connected_accounts.link(
            user_id=user_id,
            auth_config_id=auth_config_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Composio connect failed: {exc}")

    return {
        "redirect_url": request.redirect_url,
        "connection_id": request.id,
        "user_id": user_id,
    }


@router.get("/status")
def status(user: Annotated[Any, Depends(get_current_user)]) -> dict:
    """Report whether this user has an ACTIVE Gmail connection."""
    user_id = user.id
    try:
        composio = Composio()
        result = composio.client.connected_accounts.list(
            toolkit_slugs=[TOOLKIT],
            user_ids=[user_id],
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Composio status failed: {exc}")

    connected = any(getattr(item, "status", None) == "ACTIVE" for item in result.items)
    return {"connected": connected, "user_id": user_id}
