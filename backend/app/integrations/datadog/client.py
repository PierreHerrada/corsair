from __future__ import annotations

import logging
import re

import httpx

from app.config import settings
from app.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)

# Patterns for parsing Datadog URLs
_TRACE_URL_RE = re.compile(r"/apm/traces\?.*traceID=([a-fA-F0-9]+)")
_TRACE_URL_RE2 = re.compile(r"/apm/trace/([a-fA-F0-9]+)")
_LOG_URL_RE = re.compile(r"/logs\?query=([^&]+)")


class DatadogIntegration(BaseIntegration):
    name = "datadog"
    description = "Datadog integration for log and trace analysis"
    required_env_vars = ["DD_API_KEY", "DD_APP_KEY"]

    def _get_headers(self) -> dict:
        return {
            "DD-API-KEY": settings.dd_api_key,
            "DD-APPLICATION-KEY": settings.dd_app_key,
            "Content-Type": "application/json",
        }

    def _get_base_url(self) -> str:
        return f"https://api.{settings.dd_site}/api"

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._get_base_url()}/v1/validate",
                    headers=self._get_headers(),
                    timeout=10,
                )
                return resp.status_code == 200
        except Exception:
            logger.exception("Datadog health check failed")
            return False

    async def search_logs(
        self, query: str, from_ts: str, to_ts: str
    ) -> list[dict]:
        payload = {
            "filter": {
                "query": query,
                "from": from_ts,
                "to": to_ts,
            },
            "sort": "-timestamp",
            "page": {"limit": 100},
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._get_base_url()}/v2/logs/events/search",
                headers=self._get_headers(),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])

    async def get_trace(self, trace_id: str) -> list[dict]:
        payload = {
            "data": {
                "attributes": {
                    "filter": {
                        "query": f"trace_id:{trace_id}",
                        "from": "now-24h",
                        "to": "now",
                    },
                    "sort": "timestamp",
                    "page": {"limit": 200},
                },
                "type": "search_request",
            },
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._get_base_url()}/v2/spans/events/search",
                headers=self._get_headers(),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])

    @staticmethod
    def parse_datadog_url(url: str) -> dict:
        """Extract trace_id or log query from a Datadog URL.

        Returns a dict with optional keys: trace_id, query.
        """
        result: dict[str, str] = {}

        match = _TRACE_URL_RE.search(url)
        if match:
            result["trace_id"] = match.group(1)
            return result

        match = _TRACE_URL_RE2.search(url)
        if match:
            result["trace_id"] = match.group(1)
            return result

        match = _LOG_URL_RE.search(url)
        if match:
            from urllib.parse import unquote

            result["query"] = unquote(match.group(1))
            return result

        return result
