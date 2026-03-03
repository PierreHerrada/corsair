from __future__ import annotations

from enum import Enum

from tortoise import fields
from tortoise.models import Model
from tortoise.queryset import QuerySet


class TaskStatus(str, Enum):
    BACKLOG = "backlog"
    PLANNED = "planned"
    WORKING = "working"
    REVIEWING = "reviewing"
    DONE = "done"
    FAILED = "failed"


class Task(Model):
    id = fields.UUIDField(pk=True)
    title = fields.TextField()
    description = fields.TextField(default="")
    acceptance = fields.TextField(default="")
    status = fields.CharEnumField(TaskStatus, default=TaskStatus.BACKLOG, max_length=20)
    jira_key = fields.TextField(null=True)
    jira_url = fields.TextField(null=True)
    slack_channel = fields.TextField()
    slack_thread_ts = fields.TextField()
    slack_user_id = fields.TextField()
    pr_url = fields.TextField(null=True)
    pr_number = fields.IntField(null=True)
    repo = fields.TextField(null=True)
    plan = fields.TextField(default="")
    analysis = fields.TextField(default="")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    deleted_at = fields.DatetimeField(null=True, default=None)

    runs: fields.ReverseRelation["AgentRun"]  # noqa: F821
    conversations: fields.ReverseRelation["Conversation"]  # noqa: F821

    class Meta:
        table = "tasks"
        ordering = ["-created_at"]

    @classmethod
    def active(cls) -> QuerySet[Task]:
        """Return only non-soft-deleted tasks."""
        return cls.filter(deleted_at=None)

    def __str__(self) -> str:
        return f"Task({self.title}, status={self.status.value})"
