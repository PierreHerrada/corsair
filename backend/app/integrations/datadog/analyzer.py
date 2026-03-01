from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.integrations.datadog.client import DatadogIntegration

logger = logging.getLogger(__name__)

MAX_RAW_LOGS = 200


async def analyze_logs(logs: list[dict]) -> str:
    """Produce a human-readable summary from Datadog log entries.

    Groups by service/status, extracts error messages, builds timeline.
    """
    if not logs:
        return "No log entries found."

    by_service: dict[str, list[dict]] = defaultdict(list)
    by_status: dict[str, int] = defaultdict(int)
    errors: list[str] = []

    for log in logs:
        attrs = log.get("attributes", {})
        service = attrs.get("service", "unknown")
        status = attrs.get("status", "unknown")
        by_service[service].append(log)
        by_status[status] += 1
        if status == "error":
            message = attrs.get("message", "")
            if message:
                errors.append(f"[{service}] {message[:200]}")

    lines = [f"Log Analysis — {len(logs)} entries"]
    lines.append("")

    lines.append("Status breakdown:")
    for status, count in sorted(by_status.items(), key=lambda x: -x[1]):
        lines.append(f"  {status}: {count}")
    lines.append("")

    lines.append("Services:")
    for service, svc_logs in sorted(by_service.items(), key=lambda x: -len(x[1])):
        lines.append(f"  {service}: {len(svc_logs)} entries")
    lines.append("")

    if errors:
        lines.append(f"Error messages ({len(errors)}):")
        for err in errors[:20]:
            lines.append(f"  - {err}")
    else:
        lines.append("No errors found.")

    return "\n".join(lines)


async def analyze_trace(spans: list[dict]) -> str:
    """Produce a trace breakdown: root span, error spans, latency waterfall."""
    if not spans:
        return "No spans found for this trace."

    parsed = []
    for span in spans:
        attrs = span.get("attributes", {})
        parsed.append(
            {
                "service": attrs.get("service", "unknown"),
                "operation": attrs.get("resource_name", attrs.get("operation_name", "unknown")),
                "duration_ns": attrs.get("duration", 0),
                "error": attrs.get("status", "") == "error",
                "start": attrs.get("start", ""),
            }
        )

    parsed.sort(key=lambda s: s["start"])

    error_spans = [s for s in parsed if s["error"]]
    total_duration_ms = max(s["duration_ns"] for s in parsed) / 1_000_000 if parsed else 0

    lines = [f"Trace Analysis — {len(parsed)} spans, {total_duration_ms:.1f}ms total"]
    lines.append("")

    if parsed:
        root = parsed[0]
        dur_ms = root["duration_ns"] / 1_000_000
        lines.append(
            f"Root span: {root['service']} → {root['operation']}"
            f" ({dur_ms:.1f}ms)"
        )
    lines.append("")

    lines.append("Span waterfall:")
    for span in parsed[:30]:
        dur_ms = span["duration_ns"] / 1_000_000
        err_marker = " [ERROR]" if span["error"] else ""
        lines.append(f"  {span['service']} → {span['operation']} ({dur_ms:.1f}ms){err_marker}")
    if len(parsed) > 30:
        lines.append(f"  ... and {len(parsed) - 30} more spans")
    lines.append("")

    if error_spans:
        lines.append(f"Error spans ({len(error_spans)}):")
        for s in error_spans:
            lines.append(f"  - {s['service']} → {s['operation']}")
    else:
        lines.append("No error spans found.")

    return "\n".join(lines)


async def run_analysis(
    client: DatadogIntegration,
    *,
    query: str | None = None,
    trace_id: str | None = None,
    url: str | None = None,
) -> dict:
    """Main entry point. Resolves input, fetches data, produces analysis.

    Returns dict for DB storage.
    """
    if url:
        parsed = client.parse_datadog_url(url)
        if "trace_id" in parsed:
            trace_id = parsed["trace_id"]
        elif "query" in parsed:
            query = parsed["query"]

    raw_logs: list[dict] = []
    raw_trace: list[dict] = []
    summary_parts: list[str] = []

    now = datetime.now(timezone.utc)
    from_ts = (now - timedelta(hours=24)).isoformat()
    to_ts = now.isoformat()

    if trace_id:
        raw_trace = await client.get_trace(trace_id)
        summary_parts.append(await analyze_trace(raw_trace))

    if query:
        raw_logs = await client.search_logs(query, from_ts, to_ts)
        summary_parts.append(await analyze_logs(raw_logs))

    if not trace_id and not query:
        return {
            "query": "",
            "trace_id": None,
            "log_count": 0,
            "raw_logs": [],
            "raw_trace": [],
            "summary": "No query or trace ID could be determined from the input.",
            "error_message": "Could not extract a query or trace ID from the provided input.",
        }

    return {
        "query": query or "",
        "trace_id": trace_id,
        "log_count": len(raw_logs),
        "raw_logs": raw_logs[:MAX_RAW_LOGS],
        "raw_trace": raw_trace,
        "summary": "\n\n".join(summary_parts),
        "error_message": None,
    }
