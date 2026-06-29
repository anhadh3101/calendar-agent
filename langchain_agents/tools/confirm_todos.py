from langchain_core.tools import tool
from langgraph.types import interrupt


def _normalize_todos(todos: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for index, todo in enumerate(todos):
        if not isinstance(todo, dict):
            continue
        title = todo.get("title") or todo.get("task") or ""
        if not title:
            continue
        normalized.append(
            {
                "id": todo.get("id") or f"todo-{index + 1}",
                "title": title,
                "note": todo.get("note", ""),
                "source": todo.get("source", ""),
            }
        )
    return normalized


def make_confirm_todos_tool():
    @tool
    def confirm_todos(todos: list[dict]) -> dict:
        """Show the user a confirmation picker for proposed to-do items.

        Call this after triaging the user's email but BEFORE writing anything to
        Notion. The user reviews the drafted to-dos and approves a subset. Each
        todo dict should include:
        - id: unique string (e.g. "todo-1")
        - title: the to-do text (required)
        - note: optional short context
        - source: optional email subject/sender the item came from

        Returns {"status": "confirmed", "todos": [...]} with only the approved
        items, or {"status": "cancelled"} / {"status": "no_todos"}.
        """
        choices = _normalize_todos(todos)
        if not choices:
            return {"status": "no_todos"}

        selection = interrupt(
            {
                "type": "todo_confirmation",
                "todos": choices,
            }
        )

        if isinstance(selection, dict) and selection.get("cancelled"):
            return {"status": "cancelled"}

        approved_ids = set()
        if isinstance(selection, dict):
            approved_ids = set(selection.get("approved_ids") or [])

        approved = [todo for todo in choices if todo["id"] in approved_ids]
        if not approved:
            return {"status": "cancelled"}

        return {"status": "confirmed", "todos": approved}

    return confirm_todos
