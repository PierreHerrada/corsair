import logging

from github import Github

from app.config import settings
from app.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


class GitHubIntegration(BaseIntegration):
    name = "github"
    description = "GitHub integration for PR creation and repository management"
    required_env_vars = ["GITHUB_TOKEN", "GITHUB_ORG"]

    def _get_client(self) -> Github:
        return Github(settings.github_token)

    async def health_check(self) -> bool:
        try:
            gh = self._get_client()
            gh.get_user().login
            return True
        except Exception:
            logger.exception("GitHub health check failed")
            return False

    async def create_pr(
        self,
        repo_name: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> dict:
        gh = self._get_client()
        repo = gh.get_repo(repo_name)
        pr = repo.create_pull(
            title=title,
            body=body,
            head=head,
            base=base,
        )
        return {
            "url": pr.html_url,
            "number": pr.number,
        }
