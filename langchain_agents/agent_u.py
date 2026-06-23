import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from xpander_sdk import Agents

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

os.environ.setdefault(
    "COMPOSIO_CACHE_DIR",
    str(Path(__file__).resolve().parent.parent / ".composio"),
)

from composio import Composio
from composio_langchain import LangchainProvider

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


def create_system_prompt(instructions: Any) -> str:
    parts: list[str] = []

    if getattr(instructions, "general", None):
        parts.append(f"System: {instructions.general}")

    if getattr(instructions, "goal_str", None):
        parts.append(f"Goals:\n{instructions.goal_str}")

    if getattr(instructions, "instructions", None):
        instr_list = "\n".join(f"- {instr}" for instr in instructions.instructions)
        parts.append(f"Instructions:\n{instr_list}")

    return "\n\n".join(parts)


def get_composio_tools(user_id: str) -> list[Any]:
    composio = Composio(provider=LangchainProvider())
    session = composio.create(user_id=user_id)
    session.update(toolkits={"enable": ["googlecalendar"]})
    return session.tools()


@lru_cache(maxsize=128)
def get_agent_bundle(user_id: str = DEFAULT_USER_ID) -> tuple[Any, str]:
    """Build and cache the LangGraph ReAct agent and system prompt per user."""
    validate_environment()

    xpander_agent = Agents().get(agent_id=os.getenv("XPANDER_AGENT_ID"))
    system_prompt = create_system_prompt(xpander_agent.instructions)
    tools = get_composio_tools(user_id)

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


def chat(
    user_message: str,
    user_id: str = DEFAULT_USER_ID,
    thread_id: str = DEFAULT_THREAD_ID,
) -> dict[str, Any]:
    """Run one turn, continuing the conversation identified by ``thread_id``."""
    agent, _ = get_agent_bundle(user_id)

    return agent.invoke(
        {"messages": [("user", user_message)]},
        config=_thread_config(thread_id),
    )


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
