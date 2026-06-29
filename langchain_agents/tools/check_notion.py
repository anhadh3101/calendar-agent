from composio import Composio
from langchain_core.tools import tool

NOTION_TOOLKIT = "notion"


def is_notion_connected(user_id: str) -> bool:
    """Return True when the user has an ACTIVE Composio Notion account."""
    try:
        composio = Composio()
        result = composio.client.connected_accounts.list(
            toolkit_slugs=[NOTION_TOOLKIT],
            user_ids=[user_id],
        )
        return any(getattr(item, "status", None) == "ACTIVE" for item in result.items)
    except Exception:
        return False


def make_check_notion_connected_tool(current_user_id: str):
    @tool
    def check_notion_connected() -> dict:
        """Check whether the current user's Notion is connected via Composio.

        Call this before any Notion action. Returns {"connected": true/false}.
        """
        return {"connected": is_notion_connected(current_user_id)}

    return check_notion_connected
