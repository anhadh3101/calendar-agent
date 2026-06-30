from langchain_core.tools import tool
from langgraph.types import interrupt


def _normalize_slots(slots: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for index, slot in enumerate(slots):
        if not isinstance(slot, dict):
            continue
        label = slot.get("label") or slot.get("start") or ""
        if not label:
            continue
        normalized.append(
            {
                "id": slot.get("id") or f"slot-{index + 1}",
                "label": label,
                "start": slot.get("start") or "",
                "end": slot.get("end") or "",
            }
        )
    return normalized


def make_select_meeting_slot_tool():
    @tool
    def select_meeting_slot(slots: list[dict]) -> dict:
        """Show the user a picker to choose a meeting time.

        Call after A2A negotiation when outcome is done. Build slots from
        negotiation.transcript before calling. Each slot needs:
        - id: unique string (e.g. "slot-1")
        - label: display text (e.g. "Tue, Jun 30 2:00–3:00 PM PDT")
        - start: ISO 8601 UTC
        - end: ISO 8601 UTC
        """
        choices = _normalize_slots(slots)
        if not choices:
            return {"status": "no_slots"}

        selection = interrupt(
            {
                "type": "slot_selection",
                "slots": choices,
            }
        )

        if isinstance(selection, dict) and selection.get("cancelled"):
            return {"status": "cancelled"}

        chosen = next(
            (slot for slot in choices if slot.get("id") == selection.get("slot_id")),
            None,
        )
        if not chosen:
            return {"status": "cancelled"}

        return {"status": "selected", "slot": chosen}

    return select_meeting_slot
