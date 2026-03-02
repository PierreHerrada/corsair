from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.models.setting import Setting

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    value: str


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
    if setting:
        setting.value = body.value
        await setting.save()
    else:
        setting = await Setting.create(
            id=uuid.uuid4(),
            key=key,
            value=body.value,
        )
    return {
        "key": setting.key,
        "value": setting.value,
        "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
    }
