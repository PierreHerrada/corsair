from enum import Enum

from tortoise import fields
from tortoise.models import Model


class LogType(str, Enum):
    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    ERROR = "error"


class AgentLog(Model):
    id = fields.UUIDField(pk=True)
    run = fields.ForeignKeyField("models.AgentRun", related_name="logs", on_delete=fields.CASCADE)
    type = fields.CharEnumField(LogType, max_length=15)
    content = fields.JSONField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "agent_logs"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"AgentLog({self.type})"
