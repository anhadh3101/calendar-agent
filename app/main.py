import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.a2a import build_card, mount_a2a
from app.instance_owner import set_agent_url
from app.routers import (
    a2a_negotiate,
    auth,
    calendar,
    chat,
    conversations,
    health,
    heartbeat,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"

app = FastAPI(
    title="Xpander API",
    description="FastAPI application",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(calendar.router)
app.include_router(a2a_negotiate.router)
app.include_router(heartbeat.router)


@app.get("/api")
async def api_root():
    return {"message": "Welcome to Xpander API"}


# Mount the A2A serving routes (agent card + JSON-RPC) before the catch-all
# StaticFiles mount, otherwise "/" shadows them.
_a2a_base_url = os.getenv("A2A_BASE_URL", "http://localhost:8001")
_a2a_agent_name = os.getenv("A2A_AGENT_NAME", "Agent A")
set_agent_url(_a2a_base_url)
mount_a2a(app, build_card(_a2a_agent_name, _a2a_base_url))

app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
