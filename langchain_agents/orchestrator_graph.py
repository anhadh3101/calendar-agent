from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from pydantic import config

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import MessagesState
from langgraph.types import Command

from langchain_agents.gaia import build_gaia_graph

def _thread_config(thread_id: str) -> dict[str, Any]:
    return {
        "configurable": { "thread_id": thread_id }
    }
    
def get_pending_interrupt(agent: Any, thread_id: str) -> dict[str, Any] | None:
    """Return the interrupt payload if the graph is paused waiting for human input."""
    state = agent.get_state(_thread_config(thread_id))
    if state.interrupts:
        return state.interrupts[0].value
    for task in state.tasks:
        for intr in task.interrupts:
            return intr.value
    return None

def extract_last_ai_message(response: dict[str, Any]) -> str:
    messages = response.get("messages", [])
    for message in reversed(messages):
        if getattr(message, "type", None) == "ai" and getattr(message, "content", None):
            return message.content
    return ""

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

@lru_cache(maxsize=128)
def get_orchestrator_bundle(user_id: str):
    gaia_subgraph = build_gaia_graph(user_id)
    
    workflow = StateGraph(MessagesState)
    workflow.add_node("gaia", gaia_subgraph)
    
    workflow.add_edge(START, "gaia")
    workflow.add_edge("gaia", END)
    
    agent = workflow.compile(checkpointer=InMemorySaver())
    
    return agent

def orchestrator_chat(
    user_message: str,
    user_id: str,
    thread_id: str,
):
    agent = get_orchestrator_bundle(user_id)
    response = agent.invoke(
        { "messages": [("user", user_message)] },
        config=_thread_config(thread_id),
    )
    
    return build_chat_result(agent, response, thread_id, user_id)

def orchestrator_stream(
    user_message: str,
    user_id: str ,
    thread_id: str,
) -> Iterator[Any]:
    agent = get_orchestrator_bundle(user_id)
    
    yield from agent.stream(
        { "messages": [("user", user_message)] },
        config=_thread_config(thread_id),
        stream_mode=["messages", "updates"],
        subgraphs=True,
    )
    
def orchestrator_resume(
    resume_value: dict[str, Any],
    user_id: str,
    thread_id: str,
) -> dict[str, Any]:
    agent = get_orchestrator_bundle(user_id)
    
    response = agent.invoke(
        Command(resume=resume_value),
        config=_thread_config(thread_id),
    )
    
    return build_chat_result(agent, response, thread_id, user_id)