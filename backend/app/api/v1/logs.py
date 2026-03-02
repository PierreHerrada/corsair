from typing import Optional

from fastapi import APIRouter, Query

from app.models.internal_log import InternalLog

router = APIRouter(prefix="/api/v1/logs", tags=["logs"])


def _log_to_dict(log: InternalLog) -> dict:
    return {
        "id": str(log.id),
        "source": log.source,
        "level": log.level,
        "logger_name": log.logger_name,
        "message": log.message,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


@router.get("")
async def list_logs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    source: Optional[str] = Query(default=None),
    level: Optional[str] = Query(default=None),
) -> dict:
    qs = InternalLog.all().order_by("-created_at")
    if source:
        qs = qs.filter(source=source)
    if level:
        qs = qs.filter(level=level.upper())
    total = await qs.count()
    logs = await qs.offset(offset).limit(limit)
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "logs": [_log_to_dict(entry) for entry in logs],
    }
