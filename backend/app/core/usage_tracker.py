"""
UsageTracker — persistent API call counter per service.

Counts survive Railway restarts and redeployments by syncing to Supabase.

Architecture:
  - In-memory counters for zero-latency increments.
  - Background flush every 60 s writes dirty rows to Supabase.
  - On startup, persisted counts are loaded from Supabase so today's
    usage (calls_today) and all-time usage (calls_total) are restored.
  - Daily counts (calls_today) auto-reset at UTC midnight.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

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
        "label": "Finnhub (News/Quotes)",
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


@dataclass
class _ServiceUsage:
    calls_session: int = 0   # since last process start — not persisted
    calls_today: int = 0     # resets at UTC midnight — persisted
    calls_total: int = 0     # all-time — persisted
    _reset_date: str = ""
    _dirty: bool = False     # needs flush to DB

    def tick(self) -> None:
        today = date.today().isoformat()
        if self._reset_date != today:
            self.calls_today = 0
            self._reset_date = today
        self.calls_session += 1
        self.calls_today += 1
        self.calls_total += 1
        self._dirty = True

    def snapshot(self) -> dict[str, int]:
        today = date.today().isoformat()
        return {
            "calls_session": self.calls_session,
            "calls_today": self.calls_today if self._reset_date == today else 0,
            "calls_total": self.calls_total,
        }


class UsageTracker:
    def __init__(self) -> None:
        self._lock = Lock()
        self._services: dict[str, _ServiceUsage] = {k: _ServiceUsage() for k in LIMITS}
        self._db: Any = None          # lazy Supabase client

    # ── Public API ─────────────────────────────────────────────────────────────

    def increment(self, service: str) -> None:
        """Thread-safe increment. Returns immediately (no I/O)."""
        with self._lock:
            if service in self._services:
                self._services[service].tick()

    def get_all(self) -> dict[str, Any]:
        with self._lock:
            result = {}
            for key, meta in LIMITS.items():
                usage = self._services[key].snapshot()
                daily_pct = (
                    round(usage["calls_today"] / meta["daily_limit"] * 100, 1)
                    if meta["daily_limit"] else None
                )
                result[key] = {**meta, **usage, "daily_pct": daily_pct}
            return result

    # ── Persistence ────────────────────────────────────────────────────────────

    def _get_db(self) -> Any:
        """Lazy-init a raw Supabase client (avoids circular imports)."""
        if self._db is None:
            from supabase import create_client
            from app.core.config import settings
            self._db = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        return self._db

    async def load_from_db(self) -> None:
        """
        Called once on startup. Restores calls_today (if same UTC date)
        and calls_total from Supabase so restarts don't lose counts.
        """
        try:
            db = await asyncio.to_thread(self._get_db)
            result = await asyncio.to_thread(
                lambda: db.table("api_usage").select("*").execute()
            )
            today = date.today().isoformat()
            with self._lock:
                for row in (result.data or []):
                    svc = row.get("service")
                    if svc not in self._services:
                        continue
                    usage = self._services[svc]
                    usage.calls_total = int(row.get("calls_total", 0))
                    if str(row.get("reset_date", "")) == today:
                        usage.calls_today = int(row.get("calls_today", 0))
                        usage._reset_date = today
                    else:
                        usage.calls_today = 0
                        usage._reset_date = today
            logger.info("UsageTracker: loaded persisted counts from Supabase.")
        except Exception as exc:
            logger.warning("UsageTracker: could not load from DB (starting fresh): %s", exc)

    async def flush_to_db(self) -> None:
        """Write dirty services to Supabase. Called by the background task."""
        with self._lock:
            dirty: dict[str, dict] = {}
            for svc, usage in self._services.items():
                if usage._dirty:
                    dirty[svc] = usage.snapshot()
                    usage._dirty = False

        if not dirty:
            return

        try:
            db = await asyncio.to_thread(self._get_db)
            today = date.today().isoformat()
            now = datetime.now(timezone.utc).isoformat()
            for svc, snap in dirty.items():
                await asyncio.to_thread(
                    lambda s=svc, d=snap: db.table("api_usage").upsert(
                        {
                            "service":     s,
                            "calls_today": d["calls_today"],
                            "calls_total": d["calls_total"],
                            "reset_date":  today,
                            "updated_at":  now,
                        },
                        on_conflict="service",
                    ).execute()
                )
            logger.debug("UsageTracker: flushed %d service(s) to Supabase.", len(dirty))
        except Exception as exc:
            logger.warning("UsageTracker: flush failed (counts safe in memory): %s", exc)

    async def run_flush_loop(self, interval: int = 60) -> None:
        """Background coroutine: flush dirty counts every `interval` seconds."""
        while True:
            await asyncio.sleep(interval)
            await self.flush_to_db()


usage_tracker = UsageTracker()
