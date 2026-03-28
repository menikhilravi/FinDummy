"""
MarketClock — US market session awareness.

States:
  OPEN     — regular hours 09:30–16:00 ET weekdays
  EXTENDED — pre/after-market 04:00–09:30 and 16:00–20:00 ET weekdays
  CLOSED   — weekends, holidays, and overnight

Agent loop intervals per state:
  OPEN     →  60 s  (full cycle: analysis + trading)
  EXTENDED → 180 s  (analysis + trading, lower frequency)
  CLOSED   → 600 s  (news/watchlist discovery only, no trades)

Uses Alpaca's /v2/clock as the authoritative source (handles holidays
automatically), with a timezone-based fallback if the API is unreachable.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timezone
from enum import Enum
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

_REGULAR_OPEN  = time(9, 30)
_REGULAR_CLOSE = time(16, 0)
_EXTENDED_START = time(4, 0)
_EXTENDED_END   = time(20, 0)


class MarketState(str, Enum):
    OPEN     = "OPEN"
    EXTENDED = "EXTENDED"
    CLOSED   = "CLOSED"


# Loop interval (seconds) per state
LOOP_INTERVALS: dict[MarketState, int] = {
    MarketState.OPEN:     60,
    MarketState.EXTENDED: 180,
    MarketState.CLOSED:   600,
}


class MarketClock:
    def __init__(self) -> None:
        self._last_state: MarketState = MarketState.CLOSED
        self._alpaca_available: bool = True

    async def get_state(self, alpaca=None) -> MarketState:
        """
        Returns the current market state.
        Tries Alpaca clock first (handles holidays); falls back to time math.
        """
        if alpaca and self._alpaca_available:
            try:
                state = await self._from_alpaca(alpaca)
                self._last_state = state
                return state
            except Exception as exc:
                logger.warning("Alpaca clock unavailable, using time fallback: %s", exc)
                self._alpaca_available = False

        state = self._from_time()
        self._last_state = state
        return state

    async def _from_alpaca(self, alpaca) -> MarketState:
        import asyncio
        clock = await asyncio.to_thread(alpaca._trading.get_clock)
        if clock.is_open:
            return MarketState.OPEN
        # Market is closed per Alpaca — check if we're in extended window
        now_et = datetime.now(ET).time()
        if _EXTENDED_START <= now_et < _REGULAR_OPEN:
            return MarketState.EXTENDED
        if _REGULAR_CLOSE <= now_et < _EXTENDED_END:
            return MarketState.EXTENDED
        return MarketState.CLOSED

    def _from_time(self) -> MarketState:
        now = datetime.now(ET)
        if now.weekday() >= 5:          # Saturday = 5, Sunday = 6
            return MarketState.CLOSED
        t = now.time()
        if _REGULAR_OPEN <= t < _REGULAR_CLOSE:
            return MarketState.OPEN
        if _EXTENDED_START <= t < _EXTENDED_END:
            return MarketState.EXTENDED
        return MarketState.CLOSED

    @property
    def trading_allowed(self) -> bool:
        """True during OPEN and EXTENDED hours."""
        return self._last_state in (MarketState.OPEN, MarketState.EXTENDED)

    def loop_interval(self) -> int:
        return LOOP_INTERVALS[self._last_state]


market_clock = MarketClock()
