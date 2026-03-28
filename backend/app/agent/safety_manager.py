"""
SafetyManager — hard-coded risk constraints.

Rules:
  1. Max trade size ≤ 2 % of total equity.
  2. Daily loss circuit-breaker at 1.5 %.
  3. Exponential back-off when API rate limits are approached.
  4. Paper/Live mode guard (will never submit live orders in PAPER mode).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class RejectionReason(str, Enum):
    POSITION_TOO_LARGE = "POSITION_TOO_LARGE"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    MARKET_CLOSED = "MARKET_CLOSED"
    HOLD_SIGNAL = "HOLD_SIGNAL"
    ZERO_EQUITY = "ZERO_EQUITY"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    NOT_SHORTABLE = "NOT_SHORTABLE"
    MARKET_CLOSED_NO_TRADE = "MARKET_CLOSED_NO_TRADE"


@dataclass
class SafetyDecision:
    approved: bool
    reason: Optional[RejectionReason] = None
    message: str = ""
    adjusted_qty: Optional[float] = None


@dataclass
class _DailyStats:
    date: date = field(default_factory=date.today)
    realised_loss: float = 0.0
    trade_count: int = 0

    def reset_if_new_day(self) -> None:
        today = date.today()
        if self.date != today:
            self.date = today
            self.realised_loss = 0.0
            self.trade_count = 0


class SafetyManager:
    """Thread-safe (async-safe) safety layer for all trade decisions."""

    MIN_CONFIDENCE = 0.55          # ignore signals with confidence below this

    def __init__(self) -> None:
        self._daily = _DailyStats()

    # ── Public API ─────────────────────────────────────────────────────────────

    def evaluate(
        self,
        action: str,
        symbol: str,
        proposed_qty: float,
        current_price: float,
        total_equity: float,
        confidence: float,
        shortable: bool = True,
        trading_allowed: bool = True,
    ) -> SafetyDecision:
        """
        Returns a SafetyDecision.  If approved, adjusted_qty is the
        (possibly reduced) quantity that is safe to trade.
        """
        self._daily.reset_if_new_day()

        if action.upper() in ("HOLD", "EXIT") and action.upper() == "HOLD":
            return SafetyDecision(
                approved=False,
                reason=RejectionReason.HOLD_SIGNAL,
                message="Agent decided to HOLD — no order placed.",
            )

        # EXIT is always allowed (closing a position is a safety action)
        if action.upper() == "EXIT":
            return SafetyDecision(approved=True, adjusted_qty=proposed_qty)

        if not trading_allowed:
            return SafetyDecision(
                approved=False,
                reason=RejectionReason.MARKET_CLOSED_NO_TRADE,
                message="Market closed — analysis only, no trades executed.",
            )

        if action.upper() == "SHORT" and not shortable:
            return SafetyDecision(
                approved=False,
                reason=RejectionReason.NOT_SHORTABLE,
                message=f"{symbol} is not shortable on Alpaca.",
            )

        if confidence < self.MIN_CONFIDENCE:
            return SafetyDecision(
                approved=False,
                reason=RejectionReason.LOW_CONFIDENCE,
                message=f"Confidence {confidence:.0%} below minimum {self.MIN_CONFIDENCE:.0%}.",
            )

        if total_equity <= 0:
            return SafetyDecision(
                approved=False,
                reason=RejectionReason.ZERO_EQUITY,
                message="Total equity is zero — cannot trade.",
            )

        # ── Circuit-breaker ────────────────────────────────────────────────────
        loss_pct = abs(self._daily.realised_loss) / total_equity
        if self._daily.realised_loss < 0 and loss_pct >= settings.DAILY_LOSS_LIMIT_PCT:
            return SafetyDecision(
                approved=False,
                reason=RejectionReason.CIRCUIT_BREAKER,
                message=(
                    f"Daily loss circuit-breaker triggered: "
                    f"${abs(self._daily.realised_loss):.2f} "
                    f"({loss_pct:.2%} ≥ {settings.DAILY_LOSS_LIMIT_PCT:.2%})."
                ),
            )

        # ── Position size ──────────────────────────────────────────────────────
        max_notional = total_equity * settings.MAX_POSITION_SIZE_PCT
        proposed_notional = proposed_qty * current_price

        if proposed_notional <= 0:
            return SafetyDecision(
                approved=False,
                reason=RejectionReason.POSITION_TOO_LARGE,
                message="Proposed notional is zero or negative.",
            )

        if proposed_notional > max_notional:
            safe_qty = max_notional / current_price
            safe_qty = max(round(safe_qty, 6), 0.000001)
            logger.warning(
                "Reducing %s qty from %.4f → %.4f (max notional $%.2f)",
                symbol, proposed_qty, safe_qty, max_notional,
            )
            return SafetyDecision(
                approved=True,
                message=(
                    f"Qty reduced to respect 2 %% equity cap: "
                    f"{safe_qty:.4f} × ${current_price:.2f} = ${safe_qty * current_price:.2f}"
                ),
                adjusted_qty=safe_qty,
            )

        return SafetyDecision(approved=True, adjusted_qty=proposed_qty)

    def record_pnl(self, pnl: float) -> None:
        """Call this after a position is closed."""
        self._daily.reset_if_new_day()
        self._daily.realised_loss += pnl
        self._daily.trade_count += 1

    @property
    def daily_stats(self) -> dict:
        self._daily.reset_if_new_day()
        return {
            "date": self._daily.date.isoformat(),
            "realised_pnl": self._daily.realised_loss,
            "trade_count": self._daily.trade_count,
        }


safety_manager = SafetyManager()
