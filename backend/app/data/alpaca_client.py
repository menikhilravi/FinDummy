"""
Alpaca Markets client — paper & live trading + market data.
Uses alpaca-py (the official v2 SDK).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestBarRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass, OrderSide, TimeInForce
from alpaca.trading.requests import GetAssetsRequest, GetOrdersRequest, MarketOrderRequest

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpen  # noqa: F401
from app.core.config import settings
from app.core.usage_tracker import usage_tracker

logger = logging.getLogger(__name__)

# ── Circuit breaker ───────────────────────────────────────────────────────────
# Opens after 5 consecutive failures; probes again after 60 s.
_circuit = CircuitBreaker("alpaca", failure_threshold=5, reset_timeout=60.0)

# ── Rate-limit tracking ───────────────────────────────────────────────────────
_ALPACA_CALL_LIMIT = 200          # calls per minute (free tier)
_call_timestamps: list[float] = []


def _rate_guard(fn):
    """Rate-limit back-off + circuit-breaker for every Alpaca API call."""
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        import time
        # Circuit-breaker check — raises CircuitBreakerOpen when service is down.
        _circuit._check()

        now = time.monotonic()
        # Purge timestamps older than 60 s
        global _call_timestamps
        _call_timestamps = [t for t in _call_timestamps if now - t < 60]

        utilisation = len(_call_timestamps) / _ALPACA_CALL_LIMIT
        if utilisation > settings.RATE_LIMIT_BUFFER:
            wait = 2 ** (utilisation * 5)          # exponential: up to ~32 s
            logger.warning("Alpaca rate-limit buffer hit (%.0f%%). Waiting %.1fs", utilisation * 100, wait)
            await asyncio.sleep(wait)

        _call_timestamps.append(time.monotonic())
        usage_tracker.increment("alpaca")
        try:
            result = await fn(*args, **kwargs)
            _circuit._record_success()
            return result
        except CircuitBreakerOpen:
            raise
        except Exception as exc:
            _circuit._record_failure(exc)
            raise
    return wrapper


class AlpacaClient:
    def __init__(self) -> None:
        self._trading = TradingClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
            paper=(settings.TRADING_MODE == "PAPER"),
        )
        self._data = StockHistoricalDataClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
        )

    # ── Account ───────────────────────────────────────────────────────────────

    @_rate_guard
    async def get_account(self) -> dict[str, Any]:
        account = await asyncio.to_thread(self._trading.get_account)
        return {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "portfolio_value": float(account.portfolio_value),
            "daytrade_count": account.daytrade_count,
        }

    # ── Market data ───────────────────────────────────────────────────────────

    @_rate_guard
    async def get_latest_bar(self, symbol: str) -> dict[str, Any]:
        req = StockLatestBarRequest(symbol_or_symbols=symbol)
        bars = await asyncio.to_thread(self._data.get_stock_latest_bar, req)
        bar = bars[symbol]
        return {
            "symbol": symbol,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "timestamp": bar.timestamp.isoformat(),
        }

    @_rate_guard
    async def get_intraday_bars(
        self, symbol: str, minutes: int = 15, days: int = 2
    ) -> list[dict[str, Any]]:
        """Fetch sub-daily OHLCV bars. minutes=1/5/15/30/60."""
        start = datetime.now(timezone.utc) - timedelta(days=days)
        tf = TimeFrame(minutes, TimeFrameUnit.Minute)
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start,
        )
        try:
            bars = await asyncio.to_thread(self._data.get_stock_bars, req)
            return [
                {
                    "time": b.timestamp.isoformat(),
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                }
                for b in bars[symbol]
            ]
        except Exception as exc:
            logger.warning("Intraday bars unavailable for %s: %s", symbol, exc)
            return []

    @_rate_guard
    async def get_bars(self, symbol: str, days: int = 30) -> list[dict[str, Any]]:
        start = datetime.now(timezone.utc) - timedelta(days=days)
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
        )
        bars = await asyncio.to_thread(self._data.get_stock_bars, req)
        return [
            {
                "time": b.timestamp.isoformat(),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in bars[symbol]
        ]

    # ── Positions ─────────────────────────────────────────────────────────────

    @_rate_guard
    async def get_positions(self) -> list[dict[str, Any]]:
        positions = await asyncio.to_thread(self._trading.get_all_positions)
        return [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
                "market_value": float(p.market_value),
                "side": p.side.value,
            }
            for p in positions
        ]

    @_rate_guard
    async def get_position(self, symbol: str) -> dict[str, Any] | None:
        try:
            p = await asyncio.to_thread(self._trading.get_open_position, symbol)
            return {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
                "market_value": float(p.market_value),
                "side": p.side.value,
            }
        except Exception:
            return None

    # ── Orders ────────────────────────────────────────────────────────────────

    @_rate_guard
    async def place_market_order(
        self,
        symbol: str,
        qty: float,
        side: str,
    ) -> dict[str, Any]:
        req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        order = await asyncio.to_thread(self._trading.submit_order, req)
        return {
            "id": str(order.id),
            "symbol": order.symbol,
            "qty": float(order.qty),
            "side": order.side.value,
            "status": order.status.value,
            "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
        }

    @_rate_guard
    async def cancel_all_orders(self) -> None:
        await asyncio.to_thread(self._trading.cancel_orders)

    @_rate_guard
    async def close_all_positions(self) -> None:
        await asyncio.to_thread(self._trading.close_all_positions, cancel_orders=True)

    # ── Asset validation ──────────────────────────────────────────────────────

    @_rate_guard
    async def get_asset(self, symbol: str) -> dict[str, Any] | None:
        try:
            asset = await asyncio.to_thread(self._trading.get_asset, symbol)
            return {
                "symbol": asset.symbol,
                "exchange": asset.exchange.value if asset.exchange else "",
                "asset_class": asset.asset_class.value if asset.asset_class else "",
                "tradable": asset.tradable,
                "status": asset.status.value if asset.status else "",
                "shortable": asset.shortable,
            }
        except Exception:
            return None

    async def is_tradable_us_equity(self, symbol: str) -> bool:
        """Returns True only if the symbol is an active, tradable US equity on Alpaca."""
        asset = await self.get_asset(symbol)
        if not asset:
            return False
        return (
            asset["asset_class"] == "us_equity"
            and asset["tradable"] is True
            and asset["status"] == "active"
        )

    @_rate_guard
    async def get_today_orders(self) -> list[dict[str, Any]]:
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        req = GetOrdersRequest(after=today)
        orders = await asyncio.to_thread(self._trading.get_orders, req)
        return [
            {
                "id": str(o.id),
                "symbol": o.symbol,
                "qty": float(o.qty) if o.qty else 0,
                "filled_qty": float(o.filled_qty) if o.filled_qty else 0,
                "side": o.side.value,
                "status": o.status.value,
                "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else None,
                "submitted_at": o.submitted_at.isoformat() if o.submitted_at else None,
            }
            for o in orders
        ]


alpaca = AlpacaClient()
