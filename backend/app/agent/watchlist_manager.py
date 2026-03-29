"""
WatchlistManager — dynamic, agentic watchlist.

How it works:
  1. Seeds from WATCHLIST_RAW env var on startup.
  2. Every agent cycle, processes Groq suggestions:
       - watchlist_add:    list of tickers the LLM noticed in news cross-mentions
       - watchlist_remove: True if the LLM thinks this ticker is dead/uninteresting
  3. Finnhub market-news scan (every DISCOVERY_INTERVAL cycles) surfaces trending
     US tickers by extracting $ symbols from headlines.
  4. Every candidate is validated via Alpaca's asset API — only active, tradable
     US equities make it through.
  5. Tickers are auto-evicted after WATCHLIST_HOLD_EVICT_COUNT consecutive
     low-confidence HOLDs (configurable in .env).
  6. Hard cap: MAX_WATCHLIST_SIZE tickers at once.

State is mirrored to Supabase watchlist table (is_active flag) so the
frontend always reflects the live set.
"""
from __future__ import annotations

import asyncio
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from app.data.alpaca_client import AlpacaClient
    from app.data.finnhub_client import FinnhubClient
    from app.database.supabase_client import SupabaseDB

logger = logging.getLogger(__name__)

# Regex for bare ticker mentions in news headlines, e.g. "$AAPL" or "(NVDA)"
_TICKER_RE = re.compile(r"\$([A-Z]{1,5})\b|\b([A-Z]{2,5})\b")

# Well-known non-ticker uppercase words to filter out
_STOP_WORDS = {
    "A", "AN", "THE", "AND", "OR", "FOR", "IN", "ON", "AT", "TO",
    "BY", "OF", "WITH", "FROM", "US", "UK", "EU", "CEO", "CFO", "IPO",
    "ETF", "SEC", "FED", "GDP", "CPI", "AI", "Q1", "Q2", "Q3", "Q4",
    "YOY", "QOQ", "EPS", "PE", "NEW", "OLD", "AS", "IS", "IT", "BE",
    "UP", "DOWN", "LOW", "HIGH", "BUY", "SELL", "HOLD",
}

_DISCOVERY_INTERVAL = 10   # run market-news discovery every N agent cycles


class WatchlistManager:
    def __init__(self) -> None:
        self._active: set[str] = set(settings.WATCHLIST)
        self._seed: set[str] = set(settings.WATCHLIST)      # never evict seeds
        self._hold_counts: dict[str, int] = defaultdict(int)
        self._cycle_count: int = 0
        self._lock = asyncio.Lock()

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def active(self) -> list[str]:
        return sorted(self._active)

    async def process_decision(
        self,
        symbol: str,
        decision: dict,
        alpaca: "AlpacaClient",
        db: "SupabaseDB",
    ) -> None:
        """
        Called after each Groq decision.  Updates hold counters and
        processes watchlist_add / watchlist_remove suggestions.
        """
        action = decision.get("action", "HOLD")
        confidence = decision.get("confidence", 0.0)
        suggestions_add: list[str] = decision.get("watchlist_add", [])
        should_remove: bool = bool(decision.get("watchlist_remove", False))

        async with self._lock:
            # ── Hold eviction ─────────────────────────────────────────────────
            if action == "HOLD" and confidence < 0.55:
                self._hold_counts[symbol] += 1
                if (
                    self._hold_counts[symbol] >= settings.WATCHLIST_HOLD_EVICT_COUNT
                    and symbol not in self._seed
                ):
                    await self._remove(symbol, db, reason="consecutive low-conf HOLDs")
            else:
                self._hold_counts[symbol] = 0   # reset on any actionable signal

            # ── Agent-suggested removal ────────────────────────────────────────
            if should_remove and symbol not in self._seed:
                await self._remove(symbol, db, reason="agent suggested removal")

            # ── Agent-suggested additions ──────────────────────────────────────
            for candidate in suggestions_add[:3]:               # max 3 per cycle
                await self._try_add(candidate.upper(), alpaca, db)

    async def run_discovery(
        self,
        finnhub: "FinnhubClient",
        alpaca: "AlpacaClient",
        db: "SupabaseDB",
    ) -> None:
        """
        Scans Finnhub general market news for trending US tickers.
        Called every DISCOVERY_INTERVAL agent cycles.
        """
        self._cycle_count += 1
        if self._cycle_count % _DISCOVERY_INTERVAL != 0:
            return

        logger.info("WatchlistManager: running market-news discovery scan…")
        try:
            news = await finnhub.get_market_news()
        except Exception as exc:
            logger.warning("Discovery news fetch failed: %s", exc)
            return

        candidates: dict[str, int] = defaultdict(int)
        for article in news:
            headline = article.get("headline", "")
            for match in _TICKER_RE.finditer(headline):
                ticker = (match.group(1) or match.group(2) or "").upper()
                if ticker and ticker not in _STOP_WORDS and len(ticker) >= 2:
                    candidates[ticker] += 1

        # Sort by mention frequency, try top candidates
        top = sorted(candidates, key=lambda t: candidates[t], reverse=True)[:5]
        async with self._lock:
            for ticker in top:
                if ticker not in self._active:
                    await self._try_add(ticker, alpaca, db)

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _try_add(
        self, symbol: str, alpaca: "AlpacaClient", db: "SupabaseDB"
    ) -> None:
        if symbol in self._active:
            return
        if len(self._active) >= settings.MAX_WATCHLIST_SIZE:
            logger.info(
                "WatchlistManager: at max size (%d), skipping %s",
                settings.MAX_WATCHLIST_SIZE, symbol,
            )
            return

        is_valid = await alpaca.is_tradable_us_equity(symbol)
        if not is_valid:
            logger.info("WatchlistManager: %s rejected (not tradable US equity)", symbol)
            return

        self._active.add(symbol)
        self._hold_counts[symbol] = 0
        logger.info("WatchlistManager: ✚ added %s", symbol)

        try:
            await db.upsert_watchlist(
                symbol=symbol,
                sentiment_score=0.0,
                price=0.0,
                notes="Auto-added by agent discovery",
                is_active=True,
            )
        except Exception as exc:
            logger.warning("DB upsert for new ticker %s failed: %s", symbol, exc)

        # Broadcast the change via queue (imported lazily to avoid circular import)
        try:
            from app.agent.trading_agent import get_broadcast_queue
            await get_broadcast_queue().put({
                "type": "watchlist_update",
                "action": "add",
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except ImportError:
            logger.warning("Could not import broadcast queue for watchlist add event.")
        except Exception as exc:
            logger.warning("Failed to broadcast watchlist add for %s: %s", symbol, exc)

    async def _remove(
        self, symbol: str, db: "SupabaseDB", reason: str = ""
    ) -> None:
        if symbol not in self._active:
            return
        self._active.discard(symbol)
        self._hold_counts.pop(symbol, None)
        logger.info("WatchlistManager: ✖ removed %s (%s)", symbol, reason)

        try:
            await db.upsert_watchlist(
                symbol=symbol,
                sentiment_score=0.0,
                price=0.0,
                notes=f"Auto-removed: {reason}",
                is_active=False,
            )
        except Exception as exc:
            logger.warning("DB update for removed ticker %s failed: %s", symbol, exc)

        try:
            from app.agent.trading_agent import get_broadcast_queue
            await get_broadcast_queue().put({
                "type": "watchlist_update",
                "action": "remove",
                "symbol": symbol,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except ImportError:
            logger.warning("Could not import broadcast queue for watchlist remove event.")
        except Exception as exc:
            logger.warning("Failed to broadcast watchlist remove for %s: %s", symbol, exc)


watchlist_manager = WatchlistManager()
