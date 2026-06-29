from composio import Composio
from langchain_core.tools import tool

GMAIL_TOOLKIT = "gmail"


def is_gmail_connected(user_id: str) -> bool:
    """Return True when the user has an ACTIVE Composio Gmail account."""
    try:
        composio = Composio()
        result = composio.client.connected_accounts.list(
            toolkit_slugs=[GMAIL_TOOLKIT],
            user_ids=[user_id],
        )
        return any(getattr(item, "status", None) == "ACTIVE" for item in result.items)
    except Exception:
        return False


def make_check_gmail_connected_tool(current_user_id: str):
    @tool
    def check_gmail_connected() -> dict:
        """Check whether the current user's Gmail is connected via Composio.

        Call this before reading or sending email. Returns {"connected": true/false}.
        """
        return {"connected": is_gmail_connected(current_user_id)}

    return check_gmail_connected
