from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # run_id -> list of websocket connections
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, run_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if run_id not in self._connections:
            self._connections[run_id] = []
        self._connections[run_id].append(websocket)
        logger.info("WebSocket connected for run %s", run_id)

    def disconnect(self, run_id: str, websocket: WebSocket) -> None:
        if run_id in self._connections:
            self._connections[run_id] = [
                ws for ws in self._connections[run_id] if ws != websocket
            ]
            if not self._connections[run_id]:
                del self._connections[run_id]
        logger.info("WebSocket disconnected for run %s", run_id)

    async def broadcast(self, run_id: str, log: object) -> None:
        """Broadcast a log entry to all connected clients for a run."""
        if run_id not in self._connections:
            return

        message = json.dumps(
            {
                "id": str(log.id),
                "run_id": str(log.run_id),
                "type": log.type.value if hasattr(log.type, "value") else str(log.type),
                "content": log.content,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
        )

        dead_connections = []
        for websocket in self._connections[run_id]:
            try:
                await websocket.send_text(message)
            except Exception:
                dead_connections.append(websocket)

        for ws in dead_connections:
            self.disconnect(run_id, ws)

    def get_connections(self, run_id: str) -> list[WebSocket]:
        return self._connections.get(run_id, [])


ws_manager = ConnectionManager()
