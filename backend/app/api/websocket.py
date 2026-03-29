"""
WebSocket connection manager + broadcaster.

Clients connect to /ws and receive a real-time stream of:
  - thought      : AI internal monologue for each ticker
  - trade_alert  : Executed order notification
  - account_update: Equity / cash snapshot
  - safety_rejection: Rejected trade with reason
  - shutdown     : Emergency stop event
  - error        : Agent loop errors
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info("WS client connected. Total: %d", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info("WS client disconnected. Total: %d", len(self._connections))

    async def broadcast(self, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


_WS_IDLE_TIMEOUT = 600  # seconds — close zombie connections after 10 min of silence


async def ws_endpoint(websocket: WebSocket) -> None:
    """FastAPI WebSocket endpoint handler — mount at /ws."""
    await manager.connect(websocket)
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=_WS_IDLE_TIMEOUT)
            except asyncio.TimeoutError:
                logger.info("WS client idle for %ds — closing.", _WS_IDLE_TIMEOUT)
                await websocket.close(code=1000, reason="Idle timeout")
                break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
    finally:
        manager.disconnect(websocket)


async def broadcast_loop(queue: asyncio.Queue[dict]) -> None:
    """
    Background coroutine — drains the agent broadcast queue
    and fans out to all connected WebSocket clients.
    """
    while True:
        try:
            payload = await queue.get()
        except asyncio.CancelledError:
            raise
        try:
            await manager.broadcast(payload)
        except Exception as exc:
            logger.error("Broadcast loop error: %s", exc)
        finally:
            queue.task_done()
