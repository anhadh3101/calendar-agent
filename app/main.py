from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import calendar, chat, health

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Xpander API",
    description="FastAPI application",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(calendar.router)


@app.get("/api")
async def api_root():
    return {"message": "Welcome to Xpander API"}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
