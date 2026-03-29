"""
Alpha Vantage client — macro-economic indicators.

Free tier: 25 calls/day, 5 calls/min.
We cache results for 6 hours to stay well within limits.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from app.core.config import settings
from app.core.usage_tracker import usage_tracker

logger = logging.getLogger(__name__)

_BASE = "https://www.alphavantage.co/query"
_CACHE_TTL = 21_600  # 6 hours in seconds


class _Cache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        if key in self._store:
            ts, val = self._store[key]
            if time.monotonic() - ts < _CACHE_TTL:
                return val
        return None

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic(), value)


_cache = _Cache()


class AlphaVantageClient:
    def __init__(self) -> None:
        self._key = settings.ALPHA_VANTAGE_API_KEY

    async def _get(self, params: dict) -> dict:
        params["apikey"] = self._key
        usage_tracker.increment("alpha_vantage")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(_BASE, params=params)
            resp.raise_for_status()
            return resp.json()

    # ── Macro indicators ──────────────────────────────────────────────────────

    async def get_real_gdp(self) -> dict[str, Any]:
        cached = _cache.get("real_gdp")
        if cached:
            return cached
        data = await self._get({"function": "REAL_GDP", "interval": "annual"})
        points = data.get("data", [])[:4]
        result = {
            "indicator": "Real GDP (Annual)",
            "unit": data.get("unit", ""),
            "latest": points[0] if points else {},
            "trend": points,
        }
        _cache.set("real_gdp", result)
        return result

    async def get_inflation(self) -> dict[str, Any]:
        cached = _cache.get("inflation")
        if cached:
            return cached
        data = await self._get({"function": "INFLATION"})
        points = data.get("data", [])[:6]
        result = {
            "indicator": "CPI Inflation (Annual %)",
            "unit": data.get("unit", ""),
            "latest": points[0] if points else {},
            "trend": points,
        }
        _cache.set("inflation", result)
        return result

    async def get_fed_funds_rate(self) -> dict[str, Any]:
        cached = _cache.get("fed_funds")
        if cached:
            return cached
        data = await self._get({"function": "FEDERAL_FUNDS_RATE", "interval": "monthly"})
        points = data.get("data", [])[:6]
        result = {
            "indicator": "Federal Funds Rate",
            "unit": data.get("unit", ""),
            "latest": points[0] if points else {},
            "trend": points,
        }
        _cache.set("fed_funds", result)
        return result

    async def get_unemployment(self) -> dict[str, Any]:
        cached = _cache.get("unemployment")
        if cached:
            return cached
        data = await self._get({"function": "UNEMPLOYMENT"})
        points = data.get("data", [])[:6]
        result = {
            "indicator": "Unemployment Rate",
            "unit": data.get("unit", ""),
            "latest": points[0] if points else {},
            "trend": points,
        }
        _cache.set("unemployment", result)
        return result

    async def get_macro_snapshot(self) -> dict[str, Any]:
        """Fetch all macro indicators concurrently (hits cache after first call)."""
        gdp, inflation, fed_rate, unemployment = await asyncio.gather(
            self.get_real_gdp(),
            self.get_inflation(),
            self.get_fed_funds_rate(),
            self.get_unemployment(),
            return_exceptions=True,
        )

        def _safe(val, name):
            if isinstance(val, Exception):
                logger.warning("Alpha Vantage %s failed: %s", name, val)
                return {"indicator": name, "error": str(val)}
            return val

        return {
            "gdp": _safe(gdp, "Real GDP"),
            "inflation": _safe(inflation, "Inflation"),
            "fed_funds_rate": _safe(fed_rate, "Fed Funds Rate"),
            "unemployment": _safe(unemployment, "Unemployment"),
        }


alpha_vantage = AlphaVantageClient()
