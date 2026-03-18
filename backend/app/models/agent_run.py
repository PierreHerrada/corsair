from enum import Enum

from tortoise import fields
from tortoise.models import Model


class RunStage(str, Enum):
    PLAN = "plan"
    WORK = "work"
    REVIEW = "review"
    INVESTIGATE = "investigate"


class RunStatus(str, Enum):
    LAUNCHING = "launching"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRun(Model):
    id = fields.UUIDField(pk=True)
    task = fields.ForeignKeyField("models.Task", related_name="runs", on_delete=fields.CASCADE)
    stage = fields.CharEnumField(RunStage, max_length=15)
    status = fields.CharEnumField(RunStatus, default=RunStatus.RUNNING, max_length=15)
    tokens_in = fields.IntField(default=0)
    tokens_out = fields.IntField(default=0)
    cost_usd = fields.DecimalField(max_digits=10, decimal_places=6, default=0)
    started_at = fields.DatetimeField(auto_now_add=True)
    finished_at = fields.DatetimeField(null=True)
    workspace_path = fields.TextField(null=True)
    file_tree = fields.JSONField(null=True)
    ecs_task_arn = fields.CharField(max_length=500, null=True)
    error_message = fields.TextField(null=True)

    logs: fields.ReverseRelation["AgentLog"]  # noqa: F821

    class Meta:
        table = "agent_runs"
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"AgentRun({self.stage.value}, status={self.status.value})"
