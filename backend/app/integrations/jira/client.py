from __future__ import annotations

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
            url = f"{self._get_base_url()}/rest/api/3/myself"
            logger.info("Jira: running health check against %s", url)
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url,
                    headers=self._get_headers(),
                    timeout=10,
                )
                if resp.status_code == 200:
                    logger.info("Jira: health check passed (200)")
                else:
                    logger.warning("Jira: health check returned status %d", resp.status_code)
                return resp.status_code == 200
        except Exception:
            logger.exception("Jira: health check failed")
            return False

    async def search_issues(self, jql: str) -> list[dict]:
        """Search Jira issues using JQL and return the list of issues."""
        url = f"{self._get_base_url()}/rest/api/3/search/jql"
        logger.info("Jira: searching issues — JQL: %s", jql)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers=self._get_headers(),
                params={
                    "jql": jql,
                    "maxResults": 100,
                    "fields": "summary,description,status,labels",
                },
                timeout=30,
            )
            if resp.status_code != 200:
                logger.error(
                    "Jira: search failed with status %d — %s",
                    resp.status_code, resp.text[:500],
                )
                resp.raise_for_status()
            data = resp.json()
            issues = data.get("issues", [])
            logger.info("Jira: search returned %d issues", len(issues))

            # /rest/api/3/search/jql returns minimal objects (only 'id').
            # Fetch each issue individually to get full data including 'key'.
            full_issues = []
            for item in issues:
                if "key" in item:
                    full_issues.append(item)
                else:
                    issue_id = item.get("id")
                    if not issue_id:
                        continue
                    try:
                        full = await self.get_issue(issue_id)
                        full_issues.append(full)
                    except Exception:
                        logger.exception("Jira: failed to fetch issue id=%s", issue_id)

            return full_issues

    async def get_issue(self, issue_key: str) -> dict:
        """Fetch a single Jira issue by key."""
        url = f"{self._get_base_url()}/rest/api/3/issue/{issue_key}"
        logger.info("Jira: fetching issue %s", issue_key)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers=self._get_headers(),
                timeout=30,
            )
            if resp.status_code != 200:
                logger.error(
                    "Jira: get issue %s failed with status %d — %s",
                    issue_key, resp.status_code, resp.text[:500],
                )
                resp.raise_for_status()
            return resp.json()

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
                "labels": [settings.jira_sync_label],
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

    async def add_comment(self, issue_key: str, body: str) -> bool:
        """Add a comment to a Jira issue."""
        url = f"{self._get_base_url()}/rest/api/3/issue/{issue_key}/comment"
        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": body}],
                    }
                ],
            }
        }
        logger.info("Jira: adding comment to %s", issue_key)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url,
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30,
                )
                if resp.status_code == 201:
                    logger.info("Jira: comment added to %s", issue_key)
                    return True
                logger.error(
                    "Jira: add comment to %s failed with status %d — %s",
                    issue_key, resp.status_code, resp.text[:500],
                )
                return False
        except Exception:
            logger.exception("Jira: failed to add comment to %s", issue_key)
            return False

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
