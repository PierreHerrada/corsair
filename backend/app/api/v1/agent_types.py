from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.agent_type import AgentType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent-types", tags=["agent-types"])


class AgentTypeCreate(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    docker_image: str = ""
    ecs_task_definition: str
    task_role_arn: str = ""
    secrets_config: dict = {}
    capabilities: list[str] = []
    cpu: int = 1024
    memory: int = 2048
    max_duration_seconds: int = 3600
    security_group_ids: list[str] = []
    subnet_ids: list[str] = []
    enable_dind: bool = False
    is_default: bool = False


class AgentTypeUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    docker_image: Optional[str] = None
    ecs_task_definition: Optional[str] = None
    task_role_arn: Optional[str] = None
    secrets_config: Optional[dict] = None
    capabilities: Optional[list[str]] = None
    cpu: Optional[int] = None
    memory: Optional[int] = None
    max_duration_seconds: Optional[int] = None
    security_group_ids: Optional[list[str]] = None
    subnet_ids: Optional[list[str]] = None
    enable_dind: Optional[bool] = None
    is_default: Optional[bool] = None


def _to_response(at: AgentType) -> dict:
    return {
        "id": str(at.id),
        "name": at.name,
        "display_name": at.display_name,
        "description": at.description,
        "docker_image": at.docker_image,
        "ecs_task_definition": at.ecs_task_definition,
        "task_role_arn": at.task_role_arn,
        "secrets_config": at.secrets_config,
        "capabilities": at.capabilities,
        "cpu": at.cpu,
        "memory": at.memory,
        "max_duration_seconds": at.max_duration_seconds,
        "security_group_ids": at.security_group_ids,
        "subnet_ids": at.subnet_ids,
        "enable_dind": at.enable_dind,
        "is_default": at.is_default,
        "created_at": at.created_at.isoformat() if at.created_at else None,
        "updated_at": at.updated_at.isoformat() if at.updated_at else None,
    }


@router.get("")
async def list_agent_types() -> list[dict]:
    types = await AgentType.all().order_by("name")
    return [_to_response(at) for at in types]


@router.post("", status_code=201)
async def create_agent_type(body: AgentTypeCreate) -> dict:
    if body.is_default:
        await AgentType.filter(is_default=True).update(is_default=False)

    at = await AgentType.create(**body.model_dump())
    return _to_response(at)


@router.get("/{agent_type_id}")
async def get_agent_type(agent_type_id: str) -> dict:
    at = await AgentType.filter(id=agent_type_id).first()
    if not at:
        raise HTTPException(status_code=404, detail="Agent type not found")
    return _to_response(at)


@router.put("/{agent_type_id}")
async def update_agent_type(agent_type_id: str, body: AgentTypeUpdate) -> dict:
    at = await AgentType.filter(id=agent_type_id).first()
    if not at:
        raise HTTPException(status_code=404, detail="Agent type not found")

    updates = body.model_dump(exclude_unset=True)
    if updates.get("is_default"):
        await AgentType.filter(is_default=True).update(is_default=False)

    if updates:
        await AgentType.filter(id=agent_type_id).update(**updates)

    at = await AgentType.get(id=agent_type_id)
    return _to_response(at)


@router.delete("/{agent_type_id}", status_code=204)
async def delete_agent_type(agent_type_id: str) -> None:
    at = await AgentType.filter(id=agent_type_id).first()
    if not at:
        raise HTTPException(status_code=404, detail="Agent type not found")
    if at.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete the default agent type")
    await at.delete()
