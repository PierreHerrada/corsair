import logging
from base64 import b64encode

import httpx

from app.config import settings
from app.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


class JiraIntegration(BaseIntegration):
    name = "jira"
    description = "Jira integration for ticket management"
    required_env_vars = ["JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_PROJECT_KEY"]

    def _get_headers(self) -> dict:
        token = b64encode(
            f"{settings.jira_email}:{settings.jira_api_token}".encode()
        ).decode()
        return {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get_base_url(self) -> str:
        return settings.jira_base_url.rstrip("/")

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._get_base_url()}/rest/api/3/myself",
                    headers=self._get_headers(),
                    timeout=10,
                )
                return resp.status_code == 200
        except Exception:
            logger.exception("Jira health check failed")
            return False

    async def create_issue(self, title: str, description: str, acceptance: str) -> dict:
        payload = {
            "fields": {
                "project": {"key": settings.jira_project_key},
                "summary": title,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description}],
                        },
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": f"Acceptance: {acceptance}"}
                            ],
                        },
                    ],
                },
                "issuetype": {"name": "Task"},
            }
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._get_base_url()}/rest/api/3/issue",
                headers=self._get_headers(),
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "key": data["key"],
                "url": f"{self._get_base_url()}/browse/{data['key']}",
            }

    async def update_status(self, issue_key: str, transition_name: str) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._get_base_url()}/rest/api/3/issue/{issue_key}/transitions",
                headers=self._get_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            transitions = resp.json()["transitions"]

            transition_id = None
            for t in transitions:
                if t["name"].lower() == transition_name.lower():
                    transition_id = t["id"]
                    break

            if not transition_id:
                logger.warning("Transition '%s' not found for %s", transition_name, issue_key)
                return False

            resp = await client.post(
                f"{self._get_base_url()}/rest/api/3/issue/{issue_key}/transitions",
                headers=self._get_headers(),
                json={"transition": {"id": transition_id}},
                timeout=10,
            )
            return resp.status_code == 204
