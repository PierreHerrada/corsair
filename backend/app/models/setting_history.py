from __future__ import annotations

from tortoise import fields
from tortoise.models import Model


class SettingHistory(Model):
    id = fields.UUIDField(pk=True)
    setting_key = fields.CharField(max_length=255)
    old_value = fields.TextField(default="")
    new_value = fields.TextField(default="")
    change_source = fields.CharField(max_length=50, default="user")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "setting_history"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"SettingHistory({self.setting_key}, source={self.change_source})"
