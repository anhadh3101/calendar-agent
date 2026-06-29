from contextvars import ContextVar

from langchain_core.tools import tool

parent_thread_id: ContextVar[str] = ContextVar("parent_thread_id", default="default")


def make_ask_notion_agent_tool(user_id: str):
    @tool
    def ask_notion_agent(task: str) -> str:
        """Delegate a Notion-only task to the Notion specialist agent.

        Use when the user wants to search, read, create, or update pages,
        databases, or workspace content in Notion.

        Pass a clear, self-contained task (what to find or do).
        Do not use for calendar, email, or contact tasks.
        """
        from langchain_agents.notion_agent import notion_chat

        thread = parent_thread_id.get()
        result = notion_chat(
            task,
            user_id=user_id,
            thread_id=f"notion:{thread}",
        )
        return result["reply"]

    return ask_notion_agent
