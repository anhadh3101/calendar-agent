import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

os.environ.setdefault(
    "COMPOSIO_CACHE_DIR",
    str(Path(__file__).resolve().parent.parent / ".composio"),
)

from composio import Composio
from composio_langchain import LangchainProvider
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent

from langchain_agents.tools.check_notion import make_check_notion_connected_tool
from prompts.notion_agent import create_system_prompt

REQUIRED_VARS = ("OPENROUTER_API_KEY", "COMPOSIO_API_KEY")
DEFAULT_MODEL = os.getenv("NOTION_AGENT_MODEL", "gpt-4o")
DEFAULT_USER_ID = "default_user"
DEFAULT_THREAD_ID = "default"


def validate_environment() -> None:
    missing = [var for var in REQUIRED_VARS if not os.getenv(var)]
    if missing:
        raise KeyError(f"Missing required environment variables: {', '.join(missing)}")


def get_notion_tools(user_id: str) -> list[Any]:
    composio = Composio(provider=LangchainProvider())
    # Load the Notion toolkit directly so the agent gets real NOTION_* tools.
    # The default limit (20) is alphabetical and omits the SEARCH/QUERY tools,
    # so raise it to cover the full toolkit.
    notion_tools = composio.tools.get(
        user_id=user_id,
        toolkits=["notion"],
        limit=100,
    )
    return [
        make_check_notion_connected_tool(user_id),
        *notion_tools,
    ]


@lru_cache(maxsize=128)
def get_notion_agent_bundle(user_id: str = DEFAULT_USER_ID) -> tuple[Any, str]:
    """Build and cache the Notion-only LangGraph ReAct agent per user."""
    validate_environment()
    system_prompt = create_system_prompt()
    tools = get_notion_tools(user_id)

    llm = ChatOpenAI(
        model="openai/gpt-4o-mini", 
        temperature=0,
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )
    agent = create_react_agent(
        llm,
        tools,
        prompt=system_prompt,
        checkpointer=InMemorySaver(),
    )
    return agent, system_prompt


def _thread_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def extract_last_ai_message(response: dict[str, Any]) -> str:
    messages = response.get("messages", [])
    for message in reversed(messages):
        if getattr(message, "type", None) == "ai" and getattr(message, "content", None):
            return message.content
    return ""


def notion_chat(
    user_message: str,
    user_id: str = DEFAULT_USER_ID,
    thread_id: str = DEFAULT_THREAD_ID,
) -> dict[str, str]:
    """Run one Notion agent turn. Returns reply text for subagent delegation."""
    agent, _ = get_notion_agent_bundle(user_id)
    result = agent.invoke(
        {"messages": [("user", user_message)]},
        config=_thread_config(thread_id),
    )
    return {"reply": extract_last_ai_message(result)}
