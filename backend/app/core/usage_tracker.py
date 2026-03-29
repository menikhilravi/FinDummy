"""
UsageTracker — in-memory API call counter per service.

Tracks calls_session (since last restart) and calls_today (resets at midnight UTC).
Limits are the free-tier caps for each service.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from threading import Lock
from typing import Any


@dataclass
class _ServiceUsage:
    calls_session: int = 0
    calls_today: int = 0
    _reset_date: str = ""

    def tick(self) -> None:
        today = date.today().isoformat()
        if self._reset_date != today:
            self.calls_today = 0
            self._reset_date = today
        self.calls_session += 1
        self.calls_today += 1

    def snapshot(self) -> dict[str, int]:
        today = date.today().isoformat()
        return {
            "calls_session": self.calls_session,
            "calls_today": self.calls_today if self._reset_date == today else 0,
        }


# Free-tier hard limits for each service (None = no published daily cap)
LIMITS: dict[str, dict[str, Any]] = {
    "groq": {
        "label": "Groq (LLM)",
        "daily_limit": 14_400,
        "rpm_limit": 30,
        "tier": "Free",
        "color": "orange",
    },
    "gemini": {
        "label": "Gemini (Chat)",
        "daily_limit": 1_500,
        "rpm_limit": 15,
        "tier": "Free (AI Studio)",
        "color": "blue",
    },
    "finnhub": {
        "label": "Finnhub (News)",
        "daily_limit": None,
        "rpm_limit": 60,
        "tier": "Free",
        "color": "cyan",
    },
    "alpha_vantage": {
        "label": "Alpha Vantage (Macro)",
        "daily_limit": 25,
        "rpm_limit": 5,
        "tier": "Free",
        "color": "yellow",
    },
    "alpaca": {
        "label": "Alpaca (Trading)",
        "daily_limit": None,
        "rpm_limit": 200,
        "tier": "Paper (Free)",
        "color": "green",
    },
    "supabase": {
        "label": "Supabase (DB)",
        "daily_limit": None,
        "rpm_limit": None,
        "tier": "Free",
        "color": "emerald",
    },
}


class UsageTracker:
    def __init__(self) -> None:
        self._lock = Lock()
        self._services: dict[str, _ServiceUsage] = {k: _ServiceUsage() for k in LIMITS}

    def increment(self, service: str) -> None:
        with self._lock:
            if service in self._services:
                self._services[service].tick()

    def get_all(self) -> dict[str, Any]:
        with self._lock:
            result = {}
            for key, meta in LIMITS.items():
                usage = self._services[key].snapshot()
                result[key] = {
                    **meta,
                    **usage,
                    "daily_pct": (
                        round(usage["calls_today"] / meta["daily_limit"] * 100, 1)
                        if meta["daily_limit"]
                        else None
                    ),
                }
            return result


usage_tracker = UsageTracker()
