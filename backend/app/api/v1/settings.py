from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.models.setting import Setting
from app.models.setting_history import SettingHistory

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    value: str


@router.get("/{key}/history")
async def get_setting_history(
    key: str,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    total = await SettingHistory.filter(setting_key=key).count()
    entries = (
        await SettingHistory.filter(setting_key=key)
        .order_by("-created_at")
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "entries": [
            {
                "id": str(e.id),
                "setting_key": e.setting_key,
                "old_value": e.old_value,
                "new_value": e.new_value,
                "change_source": e.change_source,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
    }


@router.get("/{key}")
async def get_setting(key: str) -> dict:
    setting = await Setting.filter(key=key).first()
    if not setting:
        return {"key": key, "value": "", "updated_at": None}
    return {
        "key": setting.key,
        "value": setting.value,
        "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
    }


@router.put("/{key}")
async def update_setting(key: str, body: SettingUpdate) -> dict:
    setting = await Setting.filter(key=key).first()
    old_value = setting.value if setting else ""

    if setting:
        setting.value = body.value
        await setting.save()
    else:
        setting = await Setting.create(
            id=uuid.uuid4(),
            key=key,
            value=body.value,
        )

    # Record history for lessons changes
    if key == "lessons" and old_value != body.value:
        await SettingHistory.create(
            id=uuid.uuid4(),
            setting_key=key,
            old_value=old_value,
            new_value=body.value,
            change_source="user",
        )

    return {
        "key": setting.key,
        "value": setting.value,
        "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
    }
