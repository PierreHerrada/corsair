from enum import Enum

from tortoise import fields
from tortoise.models import Model


class RunStage(str, Enum):
    PLAN = "plan"
    WORK = "work"
    REVIEW = "review"


class RunStatus(str, Enum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class AgentRun(Model):
    id = fields.UUIDField(pk=True)
    task = fields.ForeignKeyField("models.Task", related_name="runs", on_delete=fields.CASCADE)
    stage = fields.CharEnumField(RunStage, max_length=10)
    status = fields.CharEnumField(RunStatus, default=RunStatus.RUNNING, max_length=10)
    tokens_in = fields.IntField(default=0)
    tokens_out = fields.IntField(default=0)
    cost_usd = fields.DecimalField(max_digits=10, decimal_places=6, default=0)
    started_at = fields.DatetimeField(auto_now_add=True)
    finished_at = fields.DatetimeField(null=True)

    logs: fields.ReverseRelation["AgentLog"]  # noqa: F821

    class Meta:
        table = "agent_runs"
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"AgentRun({self.stage.value}, status={self.status.value})"
