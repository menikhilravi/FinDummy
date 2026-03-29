"""
TradingAgent — the core autonomous reasoning & execution loop.

Each cycle (configurable interval):
  1. Fetch price data + news + macro for every watched ticker.
  2. Send context to Groq for LLM reasoning.
  3. Run decision through SafetyManager.
  4. If approved, execute via Alpaca.
  5. Persist trade + thought log to Supabase.
  6. Broadcast thoughts + trade alerts to connected WebSocket clients.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.agent.reasoning_engine import reasoning_engine
from app.agent.safety_manager import safety_manager
from app.agent.watchlist_manager import watchlist_manager
from app.core.config import settings
from app.data.alpaca_client import alpaca
from app.data.alpha_vantage_client import alpha_vantage
from app.data.finnhub_client import finnhub_client
from app.data.market_clock import MarketState, market_clock
from app.data.technical_analysis import technical_analysis
from app.database.supabase_client import db

logger = logging.getLogger(__name__)

# Shared broadcast queue — the WebSocket handler drains this.
# Bounded to prevent unbounded memory growth when broadcast consumers are slow.
# put_nowait is used for non-critical events; put() for critical ones.
_BROADCAST_QUEUE_MAX = 200
_broadcast_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=_BROADCAST_QUEUE_MAX)


def get_broadcast_queue() -> asyncio.Queue[dict]:
    return _broadcast_queue


def _safe_broadcast(payload: dict) -> None:
    """Put a message on the broadcast queue, dropping it (with a warning) if full."""
    try:
        _broadcast_queue.put_nowait(payload)
    except asyncio.QueueFull:
        logger.warning(
            "Broadcast queue full (%d items) — dropping event type '%s'",
            _BROADCAST_QUEUE_MAX, payload.get("type", "?"),
        )


class TradingAgent:
    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None
        self._shutdown_requested = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._shutdown_requested = False
            self._task = asyncio.create_task(self._loop(), name="trading-agent")
            logger.info("TradingAgent started (mode=%s)", settings.TRADING_MODE)

    async def stop(self) -> None:
        self._running = False
        self._shutdown_requested = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("TradingAgent stopped.")

    async def emergency_shutdown(self) -> dict[str, Any]:
        """Panic button: cancel orders + close all positions."""
        await self.stop()
        try:
            await alpaca.cancel_all_orders()
            await alpaca.close_all_positions()
            msg = "Emergency shutdown complete. All positions closed."
            logger.critical(msg)
            await _broadcast_queue.put({"type": "shutdown", "message": msg})
            return {"status": "ok", "message": msg}
        except Exception as exc:
            logger.error("Emergency shutdown error: %s", exc, exc_info=True)
            return {"status": "error", "message": str(exc)}

    # ── Main loop ─────────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._cycle()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Agent loop error: %s", exc, exc_info=True)
                _safe_broadcast({
                    "type": "error",
                    "message": f"Agent loop error: {exc}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            # Dynamic interval based on market state
            interval = market_clock.loop_interval()
            logger.info("Next cycle in %ds (market=%s)", interval, market_clock._last_state.value)
            await asyncio.sleep(interval)

    async def _cycle(self) -> None:
        # ── Check market state ────────────────────────────────────────────────
        state = await market_clock.get_state(alpaca)
        trading_allowed = market_clock.trading_allowed
        logger.info("─── Agent cycle start | market=%s | trading=%s ───",
                    state.value, trading_allowed)

        _safe_broadcast({
            "type": "market_state",
            "state": state.value,
            "trading_allowed": trading_allowed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # ── Fetch shared context once per cycle ───────────────────────────────
        account, macro = await asyncio.gather(
            alpaca.get_account(),
            alpha_vantage.get_macro_snapshot(),
            return_exceptions=True,
        )
        if isinstance(account, Exception):
            logger.error("Failed to fetch account: %s", account)
            return
        if isinstance(macro, Exception):
            logger.warning("Macro data unavailable: %s", macro)
            macro = {}

        # Log equity snapshot
        try:
            await db.log_equity_snapshot(account["equity"], account["portfolio_value"])
        except Exception as exc:
            logger.warning("Failed to log equity snapshot: %s", exc)

        # Broadcast account update
        _safe_broadcast({
            "type": "account_update",
            "data": account,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # ── Dynamic watchlist discovery (every N cycles) ──────────────────────
        await watchlist_manager.run_discovery(finnhub_client, alpaca, db)

        # ── Per-ticker analysis ───────────────────────────────────────────────
        pending_watchlist: list[dict] = []
        for symbol in watchlist_manager.active:
            if not self._running:
                break
            wl_row = await self._analyse_ticker(symbol, account, macro, trading_allowed)
            if wl_row:
                pending_watchlist.append(wl_row)
            await asyncio.sleep(2)           # brief pause between tickers

        # Flush all watchlist updates in a single DB call
        if pending_watchlist:
            try:
                await db.batch_upsert_watchlist(pending_watchlist)
            except Exception as exc:
                logger.warning("Batch watchlist upsert failed: %s", exc)

    async def _analyse_ticker(
        self, symbol: str, account: dict, macro: dict, trading_allowed: bool
    ) -> dict | None:
        """Analyse a single ticker. Returns a watchlist row dict to be batch-upserted, or None on error."""
        try:
            price_data, fh_quote, news, current_position, asset, daily_bars, intraday_bars = \
                await asyncio.gather(
                    alpaca.get_latest_bar(symbol),
                    finnhub_client.get_quote(symbol),
                    finnhub_client.get_company_news(symbol),
                    alpaca.get_position(symbol),
                    alpaca.get_asset(symbol),
                    alpaca.get_bars(symbol, days=60),
                    alpaca.get_intraday_bars(symbol, minutes=15, days=2),
                    return_exceptions=True,
                )
            if isinstance(price_data, Exception):
                logger.warning("[%s] Price data error: %s", symbol, price_data)
                return None
            if isinstance(fh_quote, Exception):
                fh_quote = None
            if isinstance(news, Exception):
                news = []
            if isinstance(current_position, Exception):
                current_position = None
            if isinstance(asset, Exception):
                asset = None
            if isinstance(daily_bars, Exception):
                daily_bars = []
            if isinstance(intraday_bars, Exception):
                intraday_bars = []
        except Exception as exc:
            logger.error("[%s] Data fetch error: %s", symbol, exc, exc_info=True)
            return None

        # ── Multi-source price verification ───────────────────────────────────
        price_data = self._verify_price(symbol, price_data, fh_quote, daily_bars)

        shortable = bool(asset.get("shortable", False)) if asset else False

        # ── Technical analysis ────────────────────────────────────────────────
        ta_daily    = technical_analysis.compute_daily(daily_bars)
        ta_intraday = technical_analysis.compute_intraday(intraday_bars, "15Min")
        ta_text     = technical_analysis.to_llm_text(ta_daily, ta_intraday)

        # Broadcast TA signals to UI
        _safe_broadcast({
            "type": "ta_update",
            "symbol": symbol,
            "daily": ta_daily,
            "intraday": ta_intraday,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # ── Groq reasoning ────────────────────────────────────────────────────
        decision = await reasoning_engine.analyze(
            symbol, price_data, news, macro, account,
            current_position=current_position,
            shortable=shortable,
            ta_text=ta_text,
        )

        # ── Process dynamic watchlist suggestions ─────────────────────────────
        await watchlist_manager.process_decision(symbol, decision, alpaca, db)

        # ── Stage watchlist update (batched at end of cycle) ─────────────────
        day_change_pct = price_data.get("day_change_pct", 0.0)
        watchlist_row = {
            "symbol": symbol,
            "sentiment_score": round(day_change_pct, 4),
            "last_price": price_data.get("close", 0),
            "notes": decision.get("reasoning", ""),
            "is_active": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Broadcast thought to UI
        _safe_broadcast({
            "type": "thought",
            "symbol": symbol,
            "action": decision["action"],
            "confidence": decision["confidence"],
            "thought_log": decision["thought_log"],
            "reasoning": decision["reasoning"],
            "watchlist_add": decision.get("watchlist_add", []),
            "watchlist_remove": decision.get("watchlist_remove", False),
            "price": price_data.get("close", 0),
            "market_state": market_clock._last_state.value,
            "trading_allowed": trading_allowed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # ── Safety check ──────────────────────────────────────────────────────
        current_price = price_data.get("close", 0)
        proposed_qty = (
            account["equity"] * decision["position_size_pct"] / current_price
            if current_price > 0 else 0
        )
        safety = safety_manager.evaluate(
            action=decision["action"],
            symbol=symbol,
            proposed_qty=proposed_qty,
            current_price=current_price,
            total_equity=account["equity"],
            confidence=decision["confidence"],
            shortable=shortable,
            trading_allowed=trading_allowed,
        )

        if not safety.approved:
            logger.info("[%s] Trade rejected: %s", symbol, safety.message)
            _safe_broadcast({
                "type": "safety_rejection",
                "symbol": symbol,
                "reason": safety.reason.value if safety.reason else "UNKNOWN",
                "message": safety.message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return watchlist_row

        final_qty = round(safety.adjusted_qty or proposed_qty, 6)
        if final_qty <= 0:
            return watchlist_row

        # ── Resolve order side from LONG/SHORT/EXIT + current position ────────
        order_side = self._resolve_order_side(
            action=decision["action"],
            current_position=current_position,
        )
        if order_side is None:
            logger.info("[%s] No order needed (already in target state)", symbol)
            return watchlist_row

        # ── Execute order ─────────────────────────────────────────────────────
        try:
            # If flipping direction, close existing position first
            if current_position and decision["action"] != "EXIT":
                existing_side = current_position.get("side", "")
                if (existing_side == "long" and decision["action"] == "SHORT") or \
                   (existing_side == "short" and decision["action"] == "LONG"):
                    await alpaca.place_market_order(
                        symbol=symbol,
                        qty=abs(float(current_position.get("qty", 0))),
                        side="SELL" if existing_side == "long" else "BUY",
                    )
                    logger.info("[%s] Closed existing %s before flip", symbol, existing_side)

            order = await alpaca.place_market_order(
                symbol=symbol,
                qty=final_qty,
                side=order_side,
            )
        except Exception as exc:
            logger.error("[%s] Order execution failed: %s", symbol, exc, exc_info=True)
            _safe_broadcast({
                "type": "order_error",
                "symbol": symbol,
                "error": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return watchlist_row

        # ── Persist ───────────────────────────────────────────────────────────
        try:
            thought_id = await db.log_thought(
                symbol=symbol,
                action=decision["action"],
                confidence=decision["confidence"],
                thought_log=decision["thought_log"],
            )
            await db.log_trade(
                symbol=symbol,
                side=order_side,
                qty=final_qty,
                price=current_price,
                order_id=order["id"],
                confidence=decision["confidence"],
                reasoning=decision["reasoning"],
                thought_log_id=thought_id,
            )
        except Exception as exc:
            logger.error("[%s] DB persist failed: %s", symbol, exc, exc_info=True)

        # Broadcast trade alert
        await _broadcast_queue.put({
            "type": "trade_alert",
            "symbol": symbol,
            "side": order_side,
            "direction": decision["action"],   # LONG / SHORT / EXIT
            "qty": final_qty,
            "price": current_price,
            "confidence": decision["confidence"],
            "reasoning": decision["reasoning"],
            "order_id": order["id"],
            "trading_mode": settings.TRADING_MODE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(
            "[%s] ✓ %s order placed: %s %.4f @ $%.2f",
            symbol, decision["action"], order_side, final_qty, current_price,
        )
        return watchlist_row

    @staticmethod
    def _verify_price(
        symbol: str,
        alpaca_bar: dict,
        fh_quote: dict | None,
        daily_bars: list[dict],
    ) -> dict:
        """
        Cross-verify price from Alpaca latest bar against:
          1. Finnhub real-time quote (independent source)
          2. Alpaca daily bars (last 2 closes for day-over-day change)

        Adds `day_change_pct` (fraction) to the returned price dict.
        Clamps implausible values and logs warnings.
        """
        close = alpaca_bar.get("close", 0)

        # ── 1. Cross-check price between Alpaca and Finnhub ──────────────────
        if fh_quote and fh_quote.get("price"):
            fh_price = fh_quote["price"]
            if fh_price > 0 and close > 0:
                divergence = abs(close - fh_price) / fh_price
                if divergence > 0.05:          # >5% gap between sources
                    logger.warning(
                        "[%s] Price divergence: Alpaca=%.2f Finnhub=%.2f (%.1f%%). "
                        "Using Finnhub price.", symbol, close, fh_price, divergence * 100
                    )
                    alpaca_bar = {**alpaca_bar, "close": fh_price}
                    close = fh_price

        # ── 2. Compute day-over-day change ────────────────────────────────────
        day_change_pct = 0.0

        # Source A: Finnhub dp field (most reliable — explicitly prev_close based)
        if fh_quote and fh_quote.get("change_pct") is not None:
            raw_pct = fh_quote["change_pct"] / 100.0   # Finnhub gives e.g. -1.42 → -0.0142
            if abs(raw_pct) <= 0.20:                   # sanity: reject >20% single-day move
                day_change_pct = raw_pct
            else:
                logger.warning(
                    "[%s] Finnhub change_pct=%.2f%% exceeds 20%% sanity limit. "
                    "Falling back to daily bars.", symbol, fh_quote["change_pct"]
                )

        # Source B: Alpaca daily bars (last 2 close prices)
        if day_change_pct == 0.0 and len(daily_bars) >= 2:
            prev_close = daily_bars[-2].get("close", 0)
            curr_close = daily_bars[-1].get("close", 0)
            if prev_close > 0 and curr_close > 0:
                raw_pct = (curr_close - prev_close) / prev_close
                if abs(raw_pct) <= 0.20:
                    day_change_pct = raw_pct
                else:
                    logger.warning(
                        "[%s] Daily bar change=%.2f%% exceeds 20%% sanity limit. "
                        "Setting to 0.", symbol, raw_pct * 100
                    )

        alpaca_bar["day_change_pct"] = round(day_change_pct, 4)
        return alpaca_bar

    @staticmethod
    def _resolve_order_side(
        action: str, current_position: dict | None
    ) -> str | None:
        """
        Maps agent action + current position to an Alpaca order side.
        Returns "BUY", "SELL", or None (no order needed).
        """
        pos_side = current_position.get("side", "") if current_position else ""
        pos_qty  = abs(float(current_position.get("qty", 0))) if current_position else 0

        if action == "LONG":
            if pos_side == "long":
                return None             # already long, nothing to do
            return "BUY"                # flat → go long  |  short → will be closed first

        if action == "SHORT":
            if pos_side == "short":
                return None             # already short, nothing to do
            return "SELL"               # flat → short sell  |  long → will be closed first

        if action == "EXIT":
            if not current_position or pos_qty == 0:
                return None             # already flat
            return "SELL" if pos_side == "long" else "BUY"

        return None                     # HOLD


trading_agent = TradingAgent()
