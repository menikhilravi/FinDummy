"""
Circuit breaker for external API calls.

Three states:
  CLOSED   — normal operation; failures are counted.
  OPEN     — service deemed down; calls are rejected immediately.
  HALF-OPEN — after `reset_timeout` seconds one probe call is allowed;
               success → CLOSED, failure → back to OPEN.

Usage
-----
    _cb = CircuitBreaker("alpaca", failure_threshold=5, reset_timeout=60)

    @_cb.guard
    async def some_api_call():
        ...

Callers should catch CircuitBreakerOpen and treat it like a temporary
service-unavailable (skip the ticker, return None, etc.).
"""
from __future__ import annotations

import logging
import time
from functools import wraps
from threading import Lock

logger = logging.getLogger(__name__)


class CircuitBreakerOpen(Exception):
    """Raised when a circuit is OPEN and the call is rejected."""


class CircuitBreaker:
    _CLOSED    = "closed"
    _OPEN      = "open"
    _HALF_OPEN = "half_open"

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._state = self._CLOSED
        self._failures = 0
        self._opened_at: float = 0.0
        self._lock = Lock()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _effective_state(self) -> str:
        """Compute current state, auto-transitioning OPEN → HALF_OPEN after timeout."""
        if (
            self._state == self._OPEN
            and (time.monotonic() - self._opened_at) >= self.reset_timeout
        ):
            return self._HALF_OPEN
        return self._state

    def _record_success(self) -> None:
        with self._lock:
            if self._state != self._CLOSED:
                logger.info("Circuit '%s' recovered — closing.", self.name)
            self._state = self._CLOSED
            self._failures = 0

    def _record_failure(self, exc: Exception) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold and self._state != self._OPEN:
                self._state = self._OPEN
                self._opened_at = time.monotonic()
                logger.error(
                    "Circuit '%s' OPENED after %d consecutive failures. Last: %s",
                    self.name,
                    self._failures,
                    exc,
                )

    def _check(self) -> None:
        """Raise CircuitBreakerOpen if the circuit is currently open."""
        with self._lock:
            state = self._effective_state()
        if state == self._OPEN:
            remaining = self.reset_timeout - (time.monotonic() - self._opened_at)
            raise CircuitBreakerOpen(
                f"Circuit '{self.name}' is OPEN — retry in {remaining:.0f}s"
            )
        if state == self._HALF_OPEN:
            logger.info("Circuit '%s' is HALF-OPEN, allowing probe call.", self.name)

    # ── Public decorator ──────────────────────────────────────────────────────

    def guard(self, fn):
        """Async decorator that wraps a coroutine function with circuit-breaker logic."""
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            self._check()
            try:
                result = await fn(*args, **kwargs)
                self._record_success()
                return result
            except CircuitBreakerOpen:
                raise
            except Exception as exc:
                self._record_failure(exc)
                raise
        return wrapper
