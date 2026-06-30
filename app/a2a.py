"""Agent-to-Agent (A2A) integration.

Each running instance is symmetric: it always *serves* the A2A routes (so any
peer can reach it) and it can *initiate* a negotiation against any peer URL it is
handed at call time. Roles are decided per conversation, never per process.

The calendar stays a tool inside the LangGraph agent and is never exposed over
A2A. Targets a2a-sdk 1.1.0 (protobuf-based).
"""

import asyncio
import concurrent.futures

import httpx
from fastapi import FastAPI

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    Role,
    SendMessageRequest,
)
from a2a.helpers import get_message_text, new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.client import ClientConfig, create_client

from app.instance_owner import resolve_instance_owner_id
from langchain_agents.agent_u import (
    DEFAULT_USER_ID,
    extract_last_ai_message,
    get_negotiation_agent_bundle,
    negotiate_chat,
)

MAX_NEGOTIATION_ROUNDS = 5

RPC_PATH = "/api/v1/jsonrpc/"

# Agent work runs in this dedicated pool, never on the server event loop.
# xpander_sdk's Agents().get() bridges async->sync by driving the *running* loop
# (nest_asyncio + run_until_complete), which shuts down that loop's default
# executor. Running the build+invoke in a worker thread (no live loop) keeps
# xpander off the request loop, and dispatching through an explicit executor
# avoids the default-executor "Executor shutdown has been called" check.
_AGENT_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="agent"
)

# A bare httpx.AsyncClient (the A2A factory's default) times out after 5s, but a
# peer's first turn (agent build + LLM + calendar tools) takes far longer. Share
# one client with a generous timeout across all negotiation rounds.
_PEER_TIMEOUT_SECONDS = 120.0
_A2A_HTTPX = httpx.AsyncClient(timeout=httpx.Timeout(_PEER_TIMEOUT_SECONDS))


def build_card(name: str, base_url: str) -> AgentCard:
    """Build the discovery document this instance advertises about itself."""
    skill = AgentSkill(
        id="negotiate_meeting",
        name="Meeting Negotiator",
        description="Proposes, counters, and accepts meeting slots.",
        tags=["scheduling", "negotiation"],
        examples=["Find a 30-min slot next week"],
    )
    return AgentCard(
        name=name,
        description="Schedules meetings on its owner's behalf.",
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                url=f"{base_url.rstrip('/')}{RPC_PATH}",
            ),
        ],
        version="0.1.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )


class NegotiatorExecutor(AgentExecutor):
    """Receiver side: a peer's message arrives, our agent crafts the reply."""

    def _run_turn(self, incoming: str, thread_id: str) -> str:
        # Runs in a worker thread with no live event loop, so xpander_sdk's
        # sync bridge never touches (and corrupts) the server's loop.
        user_id = resolve_instance_owner_id()
        agent, _ = get_negotiation_agent_bundle(user_id)
        result = agent.invoke(
            {"messages": [("user", incoming)]},
            {"configurable": {"thread_id": thread_id}},
        )
        return extract_last_ai_message(result)

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        incoming = get_message_text(context.message)
        thread_id = context.context_id or "a2a-default"

        loop = asyncio.get_running_loop()
        reply = await loop.run_in_executor(
            _AGENT_POOL, self._run_turn, incoming, thread_id
        )

        await event_queue.enqueue_event(
            new_text_message(reply, role=Role.ROLE_AGENT, context_id=thread_id)
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("cancel not supported")


def mount_a2a(app: FastAPI, card: AgentCard) -> None:
    """Register the agent-card and JSON-RPC routes on an existing FastAPI app."""
    handler = DefaultRequestHandler(
        agent_executor=NegotiatorExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    routes = []
    routes.extend(create_agent_card_routes(card))
    routes.extend(create_jsonrpc_routes(handler, rpc_url=RPC_PATH))
    # Insert before the catch-all StaticFiles("/") mount, otherwise "/" shadows
    # these routes and discovery/JSON-RPC would 404.
    for route in reversed(routes):
        app.router.routes.insert(0, route)


async def send_to_peer(peer_base_url: str, text: str, thread_id: str) -> str | None:
    """Initiator side: send one message to a peer, return its reply text."""
    config = ClientConfig(httpx_client=_A2A_HTTPX)
    client = await create_client(peer_base_url, client_config=config)
    msg = new_text_message(text, role=Role.ROLE_USER, context_id=thread_id)
    request = SendMessageRequest(message=msg)
    async for chunk in client.send_message(request):
        if chunk.HasField("message"):
            return get_message_text(chunk.message)
    return None


async def run_negotiation(
    peer_url: str,
    opening: str,
    thread_id: str,
    user_id: str = DEFAULT_USER_ID,
) -> list[dict[str, str]]:
    """Exchange availability with a peer; return the full free-flow transcript.

    The sender agent runs after each peer reply and reports whether to continue
    via report_negotiation_status (done / stuck / needs_more_slots).
    """
    transcript: list[dict[str, str]] = []
    loop = asyncio.get_running_loop()

    transcript.append({"from": "me", "text": opening})
    peer_reply = await send_to_peer(peer_url, opening, thread_id)
    transcript.append({"from": "peer", "text": peer_reply or ""})

    rounds = 0
    while peer_reply and rounds < MAX_NEGOTIATION_ROUNDS:
        turn = await loop.run_in_executor(
            _AGENT_POOL,
            negotiate_chat,
            peer_reply,
            user_id,
            thread_id,
        )
        reply_text = turn["reply"]
        status = turn["status"]
        transcript.append({"from": "me", "text": reply_text, "status": status})

        if status != "needs_more_slots":
            break

        peer_reply = await send_to_peer(peer_url, reply_text, thread_id)
        transcript.append({"from": "peer", "text": peer_reply or ""})
        rounds += 1

    return transcript
