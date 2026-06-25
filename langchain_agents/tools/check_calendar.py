from composio import Composio
from langchain_core.tools import tool

GOOGLE_CALENDAR_TOOLKIT = "googlecalendar"


def is_calendar_connected(user_id: str) -> bool:
    """Return True when the user has an ACTIVE Composio Google Calendar account."""
    try:
        composio = Composio()
        result = composio.client.connected_accounts.list(
            toolkit_slugs=[GOOGLE_CALENDAR_TOOLKIT],
            user_ids=[user_id],
        )
        return any(getattr(item, "status", None) == "ACTIVE" for item in result.items)
    except Exception:
        return False


def make_check_calendar_connected_tool(current_user_id: str):
    @tool
    def check_calendar_connected() -> dict:
        """Check whether the current user's Google Calendar is connected via Composio.

        Call this before booking a meeting. Returns {"connected": true/false}.
        """
        return {"connected": is_calendar_connected(current_user_id)}

    return check_calendar_connected
