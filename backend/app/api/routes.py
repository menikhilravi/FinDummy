"""
REST API routes — mounted under /api/v1
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
from pydantic import BaseModel

from app.agent.safety_manager import safety_manager
from app.agent.trading_agent import trading_agent
from app.agent.watchlist_manager import watchlist_manager
from app.api.websocket import manager as ws_manager
from app.core.config import settings
from app.data.alpaca_client import alpaca
from app.data.alpha_vantage_client import alpha_vantage
from app.data.finnhub_client import finnhub_client
from app.database.supabase_client import db

router = APIRouter(prefix="/api/v1")


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {
        "status": "ok",
        "trading_mode": settings.TRADING_MODE,
        "ws_connections": ws_manager.connection_count,
    }


# ── Agent control ─────────────────────────────────────────────────────────────

@router.post("/agent/start")
async def start_agent():
    trading_agent.start()
    return {"status": "started", "trading_mode": settings.TRADING_MODE}


@router.post("/agent/stop")
async def stop_agent():
    await trading_agent.stop()
    return {"status": "stopped"}


@router.post("/shutdown")
async def emergency_shutdown():
    """Panic button — closes all positions and stops the agent."""
    result = await trading_agent.emergency_shutdown()
    return result


# ── Account ───────────────────────────────────────────────────────────────────

@router.get("/account")
async def get_account():
    try:
        return await alpaca.get_account()
    except Exception as exc:
        logger.error("API error: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Upstream service error. Check server logs.")


@router.get("/positions")
async def get_positions():
    try:
        return await alpaca.get_positions()
    except Exception as exc:
        logger.error("API error: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Upstream service error. Check server logs.")


@router.get("/orders/today")
async def get_today_orders():
    try:
        return await alpaca.get_today_orders()
    except Exception as exc:
        logger.error("API error: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Upstream service error. Check server logs.")


# ── Trade history & logs ──────────────────────────────────────────────────────

@router.get("/trades")
async def get_trades(limit: int = 50):
    try:
        return await db.get_trade_history(limit=limit)
    except Exception as exc:
        logger.error("API error: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Upstream service error. Check server logs.")


@router.get("/thoughts")
async def get_thoughts(limit: int = 20):
    try:
        return await db.get_thought_logs(limit=limit)
    except Exception as exc:
        logger.error("API error: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Upstream service error. Check server logs.")


@router.get("/equity/history")
async def get_equity_history(limit: int = 200):
    try:
        return await db.get_equity_history(limit=limit)
    except Exception as exc:
        logger.error("API error: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Upstream service error. Check server logs.")


# ── Watchlist ─────────────────────────────────────────────────────────────────

@router.get("/watchlist")
async def get_watchlist(active_only: bool = True):
    try:
        return await db.get_watchlist(active_only=active_only)
    except Exception as exc:
        logger.error("API error: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Upstream service error. Check server logs.")


@router.get("/watchlist/live")
async def get_live_watchlist():
    """Returns the in-memory active ticker set (no DB round-trip)."""
    return {"tickers": watchlist_manager.active, "count": len(watchlist_manager.active)}


class WatchlistAddRequest(BaseModel):
    symbol: str


@router.post("/watchlist/add")
async def manual_add_to_watchlist(body: WatchlistAddRequest):
    """Manually add a ticker — still validates it's a tradable US equity."""
    symbol = body.symbol.upper().strip()
    if not symbol or not symbol.isalpha() or not (1 <= len(symbol) <= 5):
        raise HTTPException(status_code=400, detail="Invalid ticker symbol.")
    is_valid = await alpaca.is_tradable_us_equity(symbol)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"{symbol} is not a tradable US equity on Alpaca.",
        )
    # Bypass lock — just call _try_add via the public helper
    from app.agent.watchlist_manager import watchlist_manager as wm
    await wm._try_add(symbol, alpaca, db)
    return {"status": "ok", "symbol": symbol, "active": wm.active}


@router.delete("/watchlist/{symbol}")
async def manual_remove_from_watchlist(symbol: str):
    """Manually remove a ticker from the active watchlist."""
    symbol = symbol.upper().strip()
    if not symbol or not symbol.isalpha() or not (1 <= len(symbol) <= 5):
        raise HTTPException(status_code=400, detail="Invalid ticker symbol.")
    from app.agent.watchlist_manager import watchlist_manager as wm
    async with wm._lock:
        await wm._remove(symbol, db, reason="manual removal via API")
    return {"status": "ok", "symbol": symbol, "active": wm.active}


# ── Market data ───────────────────────────────────────────────────────────────

@router.get("/market/bar/{symbol}")
async def get_bar(symbol: str):
    try:
        return await alpaca.get_latest_bar(symbol.upper())
    except Exception as exc:
        logger.error("API error: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Upstream service error. Check server logs.")


@router.get("/market/news/{symbol}")
async def get_news(symbol: str):
    try:
        return await finnhub_client.get_company_news(symbol.upper())
    except Exception as exc:
        logger.error("API error: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Upstream service error. Check server logs.")


@router.get("/market/macro")
async def get_macro():
    try:
        return await alpha_vantage.get_macro_snapshot()
    except Exception as exc:
        logger.error("API error: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Upstream service error. Check server logs.")


# ── Safety stats ──────────────────────────────────────────────────────────────

@router.get("/safety/stats")
async def get_safety_stats():
    return safety_manager.daily_stats
