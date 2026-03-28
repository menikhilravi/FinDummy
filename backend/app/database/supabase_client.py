"""
Supabase (PostgreSQL) persistence layer.

Tables (see supabase_schema.sql):
  - trade_history
  - thought_logs
  - watchlist
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from supabase import Client, create_client

from app.core.config import settings

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupabaseDB:
    def __init__(self) -> None:
        self._client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY,
        )

    # ── Trade History ─────────────────────────────────────────────────────────

    async def log_trade(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        order_id: str,
        confidence: float,
        reasoning: str,
        thought_log_id: str | None = None,
    ) -> dict[str, Any]:
        row = {
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "entry_price": price,
            "order_id": order_id,
            "confidence": confidence,
            "reasoning": reasoning,
            "thought_log_id": thought_log_id,
            "created_at": _now(),
            "trading_mode": settings.TRADING_MODE,
        }
        result = self._client.table("trade_history").insert(row).execute()
        return result.data[0] if result.data else row

    async def update_trade_exit(
        self,
        order_id: str,
        exit_price: float,
        pnl: float,
    ) -> None:
        self._client.table("trade_history").update(
            {"exit_price": exit_price, "pnl": pnl, "closed_at": _now()}
        ).eq("order_id", order_id).execute()

    async def get_trade_history(self, limit: int = 50) -> list[dict[str, Any]]:
        result = (
            self._client.table("trade_history")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    async def get_today_pnl(self) -> float:
        """Sum of realised PnL for today (closed trades only)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        result = (
            self._client.table("trade_history")
            .select("pnl")
            .gte("created_at", today)
            .not_.is_("pnl", "null")
            .execute()
        )
        rows = result.data or []
        return sum(r["pnl"] for r in rows if r.get("pnl") is not None)

    # ── Thought Logs ──────────────────────────────────────────────────────────

    async def log_thought(
        self,
        symbol: str,
        action: str,
        confidence: float,
        thought_log: dict,
    ) -> str:
        row = {
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "thought_log": thought_log,
            "created_at": _now(),
        }
        result = self._client.table("thought_logs").insert(row).execute()
        return result.data[0]["id"] if result.data else ""

    async def get_thought_logs(self, limit: int = 20) -> list[dict[str, Any]]:
        result = (
            self._client.table("thought_logs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    # ── Watchlist ─────────────────────────────────────────────────────────────

    async def upsert_watchlist(
        self,
        symbol: str,
        sentiment_score: float,
        price: float,
        notes: str = "",
        is_active: bool = True,
    ) -> None:
        row = {
            "symbol": symbol,
            "sentiment_score": sentiment_score,
            "last_price": price,
            "notes": notes,
            "is_active": is_active,
            "updated_at": _now(),
        }
        self._client.table("watchlist").upsert(row, on_conflict="symbol").execute()

    async def get_watchlist(self, active_only: bool = True) -> list[dict[str, Any]]:
        query = self._client.table("watchlist").select("*")
        if active_only:
            query = query.eq("is_active", True)
        result = query.order("updated_at", desc=True).execute()
        return result.data or []

    # ── Equity snapshots (for chart) ──────────────────────────────────────────

    async def log_equity_snapshot(self, equity: float, portfolio_value: float) -> None:
        row = {
            "equity": equity,
            "portfolio_value": portfolio_value,
            "created_at": _now(),
        }
        self._client.table("equity_snapshots").insert(row).execute()

    async def get_equity_history(self, limit: int = 200) -> list[dict[str, Any]]:
        result = (
            self._client.table("equity_snapshots")
            .select("equity,portfolio_value,created_at")
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return result.data or []


db = SupabaseDB()
