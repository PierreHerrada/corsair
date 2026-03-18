from __future__ import annotations

from tortoise import fields
from tortoise.models import Model


class AgentType(Model):
    id = fields.UUIDField(pk=True)
    name = fields.CharField(max_length=100, unique=True)
    display_name = fields.CharField(max_length=200)
    description = fields.TextField(null=True)
    docker_image = fields.CharField(max_length=500, default="")
    ecs_task_definition = fields.CharField(max_length=500)
    task_role_arn = fields.CharField(max_length=500, default="")
    secrets_config = fields.JSONField(default=dict)
    capabilities = fields.JSONField(default=list)
    cpu = fields.IntField(default=1024)
    memory = fields.IntField(default=2048)
    max_duration_seconds = fields.IntField(default=3600)
    security_group_ids = fields.JSONField(default=list)
    subnet_ids = fields.JSONField(default=list)
    enable_dind = fields.BooleanField(default=False)
    is_default = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    tasks: fields.ReverseRelation["Task"]  # noqa: F821

    class Meta:
        table = "agent_types"

    def __str__(self) -> str:
        return f"AgentType({self.name})"
