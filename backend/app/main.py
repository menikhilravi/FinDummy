"""
FastAPI application entry-point.

Start with:
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.agent.trading_agent import get_broadcast_queue, trading_agent
from app.api.routes import router
from app.api.chat_routes import router as chat_router
from app.api.websocket import broadcast_loop, ws_endpoint
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Trading Agent",
    version="1.0.0",
    description="Autonomous trading agent with real-time WebSocket dashboard.",
)

# ── CORS (allow Next.js dev server) ──────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN, "http://localhost:3000", "https://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(router)
app.include_router(chat_router)


@app.websocket("/ws")
async def websocket_route(websocket: WebSocket):
    await ws_endpoint(websocket)


# ── Startup / Shutdown ────────────────────────────────────────────────────────

_broadcast_task: asyncio.Task | None = None


@app.on_event("startup")
async def on_startup():
    global _broadcast_task
    queue = get_broadcast_queue()
    _broadcast_task = asyncio.create_task(broadcast_loop(queue), name="ws-broadcaster")
    # Auto-start the agent
    trading_agent.start()
    logger.info("Application started. Trading mode: %s", settings.TRADING_MODE)


@app.on_event("shutdown")
async def on_shutdown():
    global _broadcast_task
    await trading_agent.stop()
    if _broadcast_task:
        _broadcast_task.cancel()
        try:
            await _broadcast_task
        except asyncio.CancelledError:
            pass
    logger.info("Application shut down cleanly.")
