from enum import Enum

from tortoise import fields
from tortoise.models import Model


class AnalysisSource(str, Enum):
    WEBHOOK = "webhook"
    MANUAL = "manual"


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    DONE = "done"
    FAILED = "failed"


class DatadogAnalysis(Model):
    id = fields.UUIDField(pk=True)
    source = fields.CharEnumField(AnalysisSource)
    trigger = fields.TextField()
    status = fields.CharEnumField(AnalysisStatus, default=AnalysisStatus.PENDING)
    query = fields.TextField(default="")
    trace_id = fields.TextField(null=True)
    log_count = fields.IntField(default=0)
    raw_logs = fields.JSONField(default=[])
    raw_trace = fields.JSONField(default=[])
    summary = fields.TextField(default="")
    error_message = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "datadog_analyses"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"DatadogAnalysis({self.source}:{self.trigger})"
