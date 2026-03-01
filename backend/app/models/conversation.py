from enum import Enum

from tortoise import fields
from tortoise.models import Model


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Conversation(Model):
    id = fields.UUIDField(pk=True)
    task = fields.ForeignKeyField(
        "models.Task", related_name="conversations", on_delete=fields.CASCADE
    )
    role = fields.CharEnumField(MessageRole, max_length=10)
    message = fields.TextField()
    slack_ts = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "conversations"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Conversation({self.role.value})"
