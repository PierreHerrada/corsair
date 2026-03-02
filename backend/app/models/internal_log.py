from tortoise import fields
from tortoise.models import Model


class InternalLog(Model):
    id = fields.UUIDField(pk=True)
    source = fields.TextField()  # e.g. "jira", "slack", "main"
    level = fields.TextField()  # e.g. "INFO", "ERROR", "WARNING"
    logger_name = fields.TextField()  # full Python logger name
    message = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "internal_logs"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"InternalLog({self.source} {self.level}: {self.message[:60]})"
