from __future__ import annotations

from tortoise import fields
from tortoise.models import Model


class Setting(Model):
    id = fields.UUIDField(pk=True)
    key = fields.CharField(max_length=255, unique=True)
    value = fields.TextField(default="")
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "settings"

    def __str__(self) -> str:
        return f"Setting({self.key}={self.value[:60]})"
