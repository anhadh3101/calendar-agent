from datetime import datetime, timedelta, timezone

from langchain_core.tools import tool
from langgraph.types import interrupt

from app.database import supabase

CONTACT_FIELDS = (
    "id, user_id, display_name, email, agent_url, agent_id, "
    "status, last_seen_at, google_calendar_connected"
)

# Heartbeat runs every 60s; treat stale after 3 missed beats.
AGENT_TTL = timedelta(seconds=180)
UNAVAILABLE_REASON = "Agent is down"


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def contact_availability(contact: dict) -> dict:
    """Annotate a contact with selectable/unavailable_reason for the UI and agent."""
    agent_down = False

    if not contact.get("agent_url"):
        agent_down = True
    else:
        last_seen = _parse_timestamp(contact.get("last_seen_at"))
        if last_seen is None:
            agent_down = True
        else:
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - last_seen > AGENT_TTL:
                agent_down = True

    if not contact.get("google_calendar_connected"):
        agent_down = True

    selectable = not agent_down
    return {
        **contact,
        "selectable": selectable,
        "unavailable_reason": None if selectable else UNAVAILABLE_REASON,
    }


def enrich_contacts(matches: list[dict]) -> list[dict]:
    return [contact_availability(c) for c in matches]


def query_contacts(name: str, current_user_id: str) -> list[dict]:
    term = name.strip()
    if not term:
        return []
    result = (
        supabase.table("agent_profiles")
        .select(CONTACT_FIELDS)
        .neq("user_id", current_user_id)
        .or_(f"display_name.ilike.%{term}%,email.ilike.%{term}%")
        .limit(10)
        .execute()
    )
    return enrich_contacts(result.data or [])


def make_search_contacts_tool(current_user_id: str):
    @tool
    def search_contacts(name: str, confirm_selection: bool = False) -> list[dict] | dict:
        """Search registered agent contacts by display name (partial, case-insensitive).

        Use when the user mentions a person to message, schedule with, or connect to.
        Returns matching profiles with agent_url, online status, and selectable flag.

        Set confirm_selection=True when booking a meeting so the user can pick
        a contact from the results before proceeding. Unavailable contacts have
        selectable=False and unavailable_reason set.
        """
        matches = query_contacts(name, current_user_id)

        if not confirm_selection:
            return matches

        if not matches:
            return {"status": "not_found", "query": name, "matches": []}

        selection = interrupt(
            {
                "type": "contact_selection",
                "query": name,
                "matches": matches,
            }
        )

        if isinstance(selection, dict) and selection.get("cancelled"):
            return {"status": "cancelled", "query": name, "matches": matches}

        selected = next(
            (c for c in matches if c["id"] == selection.get("contact_id")),
            None,
        )
        if not selected or not selected.get("selectable"):
            return {"status": "cancelled", "query": name, "matches": matches}

        result: dict = {
            "status": "selected",
            "query": name,
            "contact": selected,
        }
        negotiation = selection.get("negotiation")
        if isinstance(negotiation, dict):
            result["negotiation"] = negotiation
        return result

    return search_contacts
