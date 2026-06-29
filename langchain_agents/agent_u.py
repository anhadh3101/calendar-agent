import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator, Literal

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

from langchain_agents.tools.ask_notion_agent import (
    make_ask_notion_agent_tool,
    parent_thread_id,
)
from langchain_agents.tools.check_calendar import make_check_calendar_connected_tool
from langchain_agents.tools.check_gmail import make_check_gmail_connected_tool
from langchain_agents.tools.confirm_todos import make_confirm_todos_tool
from langchain_agents.tools.negotiation_status import (
    DEFAULT_NEGOTIATION_STATUS,
    REPORT_NEGOTIATION_STATUS_TOOL,
    make_report_negotiation_status_tool,
)
from langchain_agents.tools.search_contacts import make_search_contacts_tool
from langchain_agents.tools.select_meeting_slot import make_select_meeting_slot_tool
from langchain_agents.tools.skills import (
    discover_skills,
    make_load_skill_tool,
    merge_xpander_skills,
)
from prompts.agent_u import create_system_prompt
from prompts.negotiation import SENDER_TOOL_NOTE, create_negotiation_prompt

NegotiationRole = Literal["receiver", "sender"]

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


def _composio_tools(user_id: str, toolkits: list[str]) -> list[Any]:
    composio = Composio(provider=LangchainProvider())
    session = composio.create(user_id=user_id)
    session.update(toolkits={"enable": toolkits})
    return session.tools()


def get_composio_tools(user_id: str) -> list[Any]:
    return _composio_tools(user_id, ["googlecalendar"])


def get_main_composio_tools(user_id: str) -> list[Any]:
    return _composio_tools(user_id, ["googlecalendar", "gmail"])

def get_xpander_tools() -> list[Any]:
    xpander_agent = Agents().get(agent_id=os.getenv("XPANDER_AGENT_ID"))
    xpander_agent.tools.is_async = False
    return xpander_agent.tools.functions

def get_agent_tools(user_id: str) -> list[Any]:
    return get_main_composio_tools(user_id) + [
        make_check_calendar_connected_tool(user_id),
        make_check_gmail_connected_tool(user_id),
        make_search_contacts_tool(user_id),
        make_select_meeting_slot_tool(),
        make_confirm_todos_tool(),
        make_load_skill_tool(),
        make_ask_notion_agent_tool(user_id),
    ] + get_xpander_tools()


def get_negotiation_tools(
    user_id: str,
    role: NegotiationRole = "receiver",
) -> list[Any]:
    tools = get_composio_tools(user_id) + [
        make_check_calendar_connected_tool(user_id),
    ]
    if role == "sender":
        tools.append(make_report_negotiation_status_tool())
    return tools


@lru_cache(maxsize=128)
def get_negotiation_agent_bundle(
    user_id: str = DEFAULT_USER_ID,
    role: NegotiationRole = "receiver",
) -> tuple[Any, str]:
    """Build a headless agent for A2A slot negotiation (no contact search or interrupts)."""
    validate_environment()

    xpander_agent = Agents().get(agent_id=os.getenv("XPANDER_AGENT_ID"))
    system_prompt = create_negotiation_prompt(
        extra_tool_note=SENDER_TOOL_NOTE if role == "sender" else None
    )
    tools = get_negotiation_tools(user_id, role)

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

    token = parent_thread_id.set(thread_id)
    try:
        response = agent.invoke(
            {"messages": [("user", user_message)]},
            config=_thread_config(thread_id),
        )
    finally:
        parent_thread_id.reset(token)
    return build_chat_result(agent, response, thread_id, user_id)


def extract_negotiation_status(response: dict[str, Any]) -> str | None:
    """Read report_negotiation_status from tool results in an invoke response."""
    for message in reversed(response.get("messages", [])):
        if getattr(message, "type", None) == "tool":
            if getattr(message, "name", None) != REPORT_NEGOTIATION_STATUS_TOOL:
                continue
            content = message.content
            if isinstance(content, dict):
                return content.get("status")
            if isinstance(content, str):
                try:
                    return json.loads(content).get("status")
                except json.JSONDecodeError:
                    pass
        if getattr(message, "type", None) == "ai":
            for tool_call in getattr(message, "tool_calls", None) or []:
                name = (
                    tool_call.get("name")
                    if isinstance(tool_call, dict)
                    else getattr(tool_call, "name", None)
                )
                if name != REPORT_NEGOTIATION_STATUS_TOOL:
                    continue
                args = (
                    tool_call.get("args")
                    if isinstance(tool_call, dict)
                    else getattr(tool_call, "args", None)
                )
                if isinstance(args, dict):
                    return args.get("status")
    return None


def negotiate_chat(
    user_message: str,
    user_id: str,
    thread_id: str,
) -> dict[str, str]:
    """Run one sender A2A negotiation turn; returns reply text and continue flag."""
    agent, _ = get_negotiation_agent_bundle(user_id, "sender")
    result = agent.invoke(
        {"messages": [("user", user_message)]},
        config=_thread_config(thread_id),
    )
    status = extract_negotiation_status(result) or DEFAULT_NEGOTIATION_STATUS
    return {
        "reply": extract_last_ai_message(result),
        "status": status,
    }


def resume_chat(
    resume_value: dict[str, Any],
    user_id: str = DEFAULT_USER_ID,
    thread_id: str = DEFAULT_THREAD_ID,
) -> dict[str, Any]:
    """Resume a paused graph after human input (e.g. contact selection)."""
    agent, _ = get_agent_bundle(user_id)

    token = parent_thread_id.set(thread_id)
    try:
        response = agent.invoke(
            Command(resume=resume_value),
            config=_thread_config(thread_id),
        )
    finally:
        parent_thread_id.reset(token)
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

    token = parent_thread_id.set(thread_id)
    try:
        yield from agent.stream(
            {"messages": [("user", user_message)]},
            config=_thread_config(thread_id),
        )
    finally:
        parent_thread_id.reset(token)


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
