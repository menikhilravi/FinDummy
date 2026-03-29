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
from app.api.usage_routes import router as usage_router
from app.api.websocket import broadcast_loop, ws_endpoint
from app.core.config import settings
from app.core.usage_tracker import usage_tracker

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

# ── CORS ─────────────────────────────────────────────────────────────────────
_allowed_origins = [settings.FRONTEND_ORIGIN]
if settings.TRADING_MODE == "PAPER":
    # Allow local dev server only in paper-trading (non-production) mode
    _allowed_origins += ["http://localhost:3000", "https://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(router)
app.include_router(chat_router)
app.include_router(usage_router)


@app.websocket("/ws")
async def websocket_route(websocket: WebSocket):
    await ws_endpoint(websocket)


# ── Startup / Shutdown ────────────────────────────────────────────────────────

_broadcast_task: asyncio.Task | None = None
_usage_flush_task: asyncio.Task | None = None


@app.on_event("startup")
async def on_startup():
    global _broadcast_task, _usage_flush_task
    # Restore persisted API usage counts before anything else
    await usage_tracker.load_from_db()
    queue = get_broadcast_queue()
    _broadcast_task = asyncio.create_task(broadcast_loop(queue), name="ws-broadcaster")
    _usage_flush_task = asyncio.create_task(
        usage_tracker.run_flush_loop(interval=60), name="usage-flush"
    )
    trading_agent.start()
    logger.info("Application started. Trading mode: %s", settings.TRADING_MODE)


@app.on_event("shutdown")
async def on_shutdown():
    global _broadcast_task, _usage_flush_task
    await trading_agent.stop()
    # Final flush before shutdown so no counts are lost
    await usage_tracker.flush_to_db()
    for task in (_broadcast_task, _usage_flush_task):
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    logger.info("Application shut down cleanly.")
