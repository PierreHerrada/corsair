from __future__ import annotations

import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.auth import verify_ws_token
from app.models import AgentLog
from app.websocket.manager import ws_manager

router = APIRouter(tags=["agent"])


@router.websocket("/ws/runs/{run_id}")
async def websocket_logs(
    websocket: WebSocket, run_id: str, token: str = Query("")
) -> None:
    if not verify_ws_token(token):
        await websocket.close(code=4001)
        return
    await ws_manager.connect(run_id, websocket)
    try:
        # Send existing logs for this run
        existing_logs = await AgentLog.filter(run_id=run_id).order_by("created_at")
        for log in existing_logs:
            await websocket.send_text(
                json.dumps(
                    {
                        "id": str(log.id),
                        "run_id": str(log.run_id),
                        "type": log.type.value,
                        "content": log.content,
                        "created_at": log.created_at.isoformat() if log.created_at else None,
                    }
                )
            )

        # Keep connection alive until client disconnects
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(run_id, websocket)
