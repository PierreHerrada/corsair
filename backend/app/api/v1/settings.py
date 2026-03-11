from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.models.setting import Setting
from app.models.setting_history import SettingHistory

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    value: str


class EnvVarInput(BaseModel):
    name: str
    value: str


class EnvVarsUpdate(BaseModel):
    items: list[EnvVarInput]


@router.get("/env-vars")
async def get_env_vars() -> dict:
    setting = await Setting.filter(key="env_vars").first()
    if not setting or not setting.value:
        return {"items": [], "updated_at": None}
    try:
        items = json.loads(setting.value)
    except (json.JSONDecodeError, TypeError):
        return {"items": [], "updated_at": setting.updated_at.isoformat() if setting.updated_at else None}
    masked = [
        {"name": item.get("name", ""), "masked_value": "*" * len(item.get("value", ""))}
        for item in items
        if item.get("name")
    ]
    return {
        "items": masked,
        "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
    }


@router.put("/env-vars")
async def update_env_vars(body: EnvVarsUpdate) -> dict:
    # Load existing values to preserve masked entries
    existing: dict[str, str] = {}
    setting = await Setting.filter(key="env_vars").first()
    if setting and setting.value:
        try:
            for item in json.loads(setting.value):
                if item.get("name") and item.get("value"):
                    existing[item["name"]] = item["value"]
        except (json.JSONDecodeError, TypeError):
            pass

    # Build new list, preserving old values for all-asterisk entries
    new_items = []
    for item in body.items:
        name = item.name.strip()
        if not name:
            continue
        value = item.value
        # If value is all asterisks and name exists in old data, keep old value
        if value and all(c == "*" for c in value) and name in existing:
            value = existing[name]
        new_items.append({"name": name, "value": value})

    serialized = json.dumps(new_items)
    if setting:
        setting.value = serialized
        await setting.save()
    else:
        setting = await Setting.create(
            id=uuid.uuid4(),
            key="env_vars",
            value=serialized,
        )

    masked = [
        {"name": item["name"], "masked_value": "*" * len(item["value"])}
        for item in new_items
    ]
    return {
        "items": masked,
        "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
    }


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
