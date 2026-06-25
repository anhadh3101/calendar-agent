from langchain_agents.tools.skills import load_skill_body

A2A_NEGOTIATION_PROMPT = """\
You are finding mutually available meeting times on behalf of your owner via agent-to-agent (A2A) messaging.

Rules:
- Do NOT search for contacts. The peer agent is already connected — you are responding to them.
- Do NOT book meetings or send invites. Only discuss availability.
- Check your owner's calendar using Google Calendar tools.
- Reply in plain, natural language. List specific dates and times.

{skill_body}
"""

SENDER_TOOL_NOTE = (
    "You also have the report_negotiation_status tool. "
    "At the end of every turn, after your reply for the peer is ready, "
    "you MUST call it with done, stuck, or needs_more_slots."
)


def create_negotiation_prompt(extra_tool_note: str | None = None) -> str:
    skill_body = load_skill_body("meeting-negotiation") or ""
    prompt = A2A_NEGOTIATION_PROMPT.format(skill_body=skill_body)
    if extra_tool_note:
        prompt += f"\n\n{extra_tool_note}"
    return prompt
