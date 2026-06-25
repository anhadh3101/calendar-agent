import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from xpander_sdk import Agents

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

os.environ.setdefault(
    "COMPOSIO_CACHE_DIR",
    str(Path(__file__).resolve().parent.parent / ".composio"),
)

from composio import Composio
from composio_langchain import LangchainProvider

from langchain_agents.tools.check_calendar import make_check_calendar_connected_tool
from langchain_agents.tools.search_contacts import make_search_contacts_tool
from langchain_agents.tools.skills import (
    build_skills_catalog_prompt,
    discover_skills,
    load_skill_body,
    make_load_skill_tool,
    merge_xpander_skills,
)

CONTACT_SEARCH_PROMPT = (
    "When the user refers to another person by name, call search_contacts with that "
    "name before answering. Use agent_url from the result to reach their agent. "
    "If multiple matches are returned, ask the user to clarify which contact they mean."
)

A2A_NEGOTIATION_PROMPT = """\
You are negotiating a meeting time on behalf of your owner via agent-to-agent (A2A) messaging.

Rules:
- Do NOT search for contacts. The peer agent is already connected — you are responding to them.
- Do NOT use the book-meeting workflow. Only negotiate times.
- Check calendar availability using Google Calendar tools.
- Reply with exactly one of:
  - ACCEPT: [ISO datetime]
  - COUNTER: [slot1], [slot2], [slot3]
- Keep responses short — no extra prose.

{skill_body}
"""

REQUIRED_VARS = (
    "OPENAI_API_KEY",
    "XPANDER_API_KEY",
    "XPANDER_ORGANIZATION_ID",
    "XPANDER_AGENT_ID",
    "COMPOSIO_API_KEY",
)

DEFAULT_USER_ID = "default_user"
DEFAULT_THREAD_ID = "default"


def validate_environment() -> None:
    missing = [var for var in REQUIRED_VARS if not os.getenv(var)]
    if missing:
        raise KeyError(f"Missing required environment variables: {', '.join(missing)}")


def create_system_prompt(
    instructions: Any, skills: list[dict] | None = None
) -> str:
    parts: list[str] = []

    if getattr(instructions, "general", None):
        parts.append(f"System: {instructions.general}")

    if getattr(instructions, "goal_str", None):
        parts.append(f"Goals:\n{instructions.goal_str}")

    if getattr(instructions, "instructions", None):
        instr_list = "\n".join(f"- {instr}" for instr in instructions.instructions)
        parts.append(f"Instructions:\n{instr_list}")

    parts.append(CONTACT_SEARCH_PROMPT)

    catalog = build_skills_catalog_prompt(skills or [])
    if catalog:
        parts.append(catalog)

    return "\n\n".join(parts)


def get_composio_tools(user_id: str) -> list[Any]:
    composio = Composio(provider=LangchainProvider())
    session = composio.create(user_id=user_id)
    session.update(toolkits={"enable": ["googlecalendar"]})
    return session.tools()


def get_agent_tools(user_id: str) -> list[Any]:
    return get_composio_tools(user_id) + [
        make_check_calendar_connected_tool(user_id),
        make_search_contacts_tool(user_id),
        make_load_skill_tool(),
    ]


def get_negotiation_tools(user_id: str) -> list[Any]:
    return get_composio_tools(user_id) + [
        make_check_calendar_connected_tool(user_id),
    ]


def create_negotiation_prompt() -> str:
    skill_body = load_skill_body("meeting-negotiation") or ""
    return A2A_NEGOTIATION_PROMPT.format(skill_body=skill_body)


@lru_cache(maxsize=128)
def get_negotiation_agent_bundle(user_id: str = DEFAULT_USER_ID) -> tuple[Any, str]:
    """Build a headless agent for A2A slot negotiation (no contact search or interrupts)."""
    validate_environment()

    xpander_agent = Agents().get(agent_id=os.getenv("XPANDER_AGENT_ID"))
    system_prompt = create_negotiation_prompt()
    tools = get_negotiation_tools(user_id)

    llm = ChatOpenAI(model=xpander_agent.model_name, temperature=0)
    agent = create_react_agent(
        llm,
        tools,
        prompt=system_prompt,
        checkpointer=InMemorySaver(),
    )

    return agent, system_prompt


@lru_cache(maxsize=128)
def get_agent_bundle(user_id: str = DEFAULT_USER_ID) -> tuple[Any, str]:
    """Build and cache the LangGraph ReAct agent and system prompt per user."""
    validate_environment()

    xpander_agent = Agents().get(agent_id=os.getenv("XPANDER_AGENT_ID"))
    skills = merge_xpander_skills(
        discover_skills(), getattr(xpander_agent, "skills", None)
    )
    system_prompt = create_system_prompt(xpander_agent.instructions, skills)
    tools = get_agent_tools(user_id)

    llm = ChatOpenAI(model=xpander_agent.model_name, temperature=0)
    # The checkpointer persists conversation state per thread_id. It lives on the
    # cached agent, so all turns for a user share the same in-process memory.
    agent = create_react_agent(
        llm,
        tools,
        prompt=system_prompt,
        checkpointer=InMemorySaver(),
    )

    return agent, system_prompt


def _thread_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def get_pending_interrupt(agent: Any, thread_id: str) -> dict[str, Any] | None:
    """Return the interrupt payload if the graph is paused waiting for human input."""
    state = agent.get_state(_thread_config(thread_id))
    if state.interrupts:
        return state.interrupts[0].value
    for task in state.tasks:
        for intr in task.interrupts:
            return intr.value
    return None


def build_chat_result(
    agent: Any,
    response: dict[str, Any],
    thread_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Normalize invoke output into complete or interrupt status for the API."""
    interrupt_payload = get_pending_interrupt(agent, thread_id)
    if interrupt_payload is not None:
        return {
            "status": "interrupt",
            "interrupt": interrupt_payload,
            "reply": None,
            "user_id": user_id,
            "conversation_id": thread_id,
        }
    return {
        "status": "complete",
        "interrupt": None,
        "reply": extract_last_ai_message(response),
        "user_id": user_id,
        "conversation_id": thread_id,
    }


def chat(
    user_message: str,
    user_id: str = DEFAULT_USER_ID,
    thread_id: str = DEFAULT_THREAD_ID,
) -> dict[str, Any]:
    """Run one turn, continuing the conversation identified by ``thread_id``."""
    agent, _ = get_agent_bundle(user_id)

    response = agent.invoke(
        {"messages": [("user", user_message)]},
        config=_thread_config(thread_id),
    )
    return build_chat_result(agent, response, thread_id, user_id)


def negotiate_chat(
    user_message: str,
    user_id: str,
    thread_id: str,
) -> dict[str, Any]:
    """Run one A2A negotiation turn (calendar tools only, no UI interrupts)."""
    agent, _ = get_negotiation_agent_bundle(user_id)
    return agent.invoke(
        {"messages": [("user", user_message)]},
        config=_thread_config(thread_id),
    )


def resume_chat(
    resume_value: dict[str, Any],
    user_id: str = DEFAULT_USER_ID,
    thread_id: str = DEFAULT_THREAD_ID,
) -> dict[str, Any]:
    """Resume a paused graph after human input (e.g. contact selection)."""
    agent, _ = get_agent_bundle(user_id)

    response = agent.invoke(
        Command(resume=resume_value),
        config=_thread_config(thread_id),
    )
    return build_chat_result(agent, response, thread_id, user_id)


def extract_last_ai_message(response: dict[str, Any]) -> str:
    messages = response.get("messages", [])
    for message in reversed(messages):
        if getattr(message, "type", None) == "ai" and getattr(message, "content", None):
            return message.content
    return ""


def stream_chat(
    user_message: str,
    user_id: str = DEFAULT_USER_ID,
    thread_id: str = DEFAULT_THREAD_ID,
) -> Iterator[dict[str, Any]]:
    """Yield LangGraph stream chunks (useful for SSE later)."""
    agent, _ = get_agent_bundle(user_id)

    yield from agent.stream(
        {"messages": [("user", user_message)]},
        config=_thread_config(thread_id),
    )


def main() -> None:
    validate_environment()
    _, system_prompt = get_agent_bundle()

    print("ReAct agent ready.")
    print(f"System prompt:\n{system_prompt}\n")

    test_query = "What events do I have on my calendar tomorrow?"
    print(f"Test query: {test_query}\n")

    for chunk in stream_chat(test_query):
        if "agent" in chunk and chunk["agent"].get("messages"):
            for message in chunk["agent"]["messages"]:
                if getattr(message, "content", None):
                    print(f"Agent: {message.content}")


if __name__ == "__main__":
    main()
