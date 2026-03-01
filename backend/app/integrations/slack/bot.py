from __future__ import annotations

import logging
from typing import Optional

from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from app.config import settings
from app.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


class SlackIntegration(BaseIntegration):
    name = "slack"
    description = "Slack bot for task creation and status updates"
    required_env_vars = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"]

    _app: Optional[AsyncApp] = None
    _client: Optional[AsyncWebClient] = None

    def get_app(self) -> AsyncApp:
        if self._app is None:
            self._app = AsyncApp(token=settings.slack_bot_token)
        return self._app

    def get_client(self) -> AsyncWebClient:
        if self._client is None:
            self._client = AsyncWebClient(token=settings.slack_bot_token)
        return self._client

    async def health_check(self) -> bool:
        try:
            client = self.get_client()
            resp = await client.auth_test()
            return resp["ok"]
        except Exception:
            logger.exception("Slack health check failed")
            return False

    async def post_thread_update(
        self, channel: str, thread_ts: str, message: str
    ) -> Optional[dict]:
        try:
            client = self.get_client()
            resp = await client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=message,
            )
            return {"ts": resp["ts"], "channel": resp["channel"]}
        except Exception:
            logger.exception("Failed to post Slack thread update")
            return None
