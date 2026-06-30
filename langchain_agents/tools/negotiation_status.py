from typing import Literal

from langchain_core.tools import tool

NegotiationStatus = Literal["done", "stuck", "needs_more_slots"]

REPORT_NEGOTIATION_STATUS_TOOL = "report_negotiation_status"
DEFAULT_NEGOTIATION_STATUS: NegotiationStatus = "needs_more_slots"


def make_report_negotiation_status_tool():
    @tool
    def report_negotiation_status(status: NegotiationStatus) -> dict:
        """Report whether negotiation should continue after this turn.

        Call once at the end of every turn:
        - done: all mutually workable times are listed; owners will choose in the UI (do not pick a final time)
        - stuck: no progress possible (no overlap, peer unresponsive, etc.)
        - needs_more_slots: your reply should be sent to the peer for another round
        """
        return {"status": status}

    return report_negotiation_status
