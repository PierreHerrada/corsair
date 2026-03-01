from __future__ import annotations

import asyncio
import logging
import uuid
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
    _listening: bool = False

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

    async def start_listening(self) -> None:
        if self._listening:
            return

        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

        from app.models.chat_message import ChatMessage

        bolt_app = self.get_app()
        client = self.get_client()

        @bolt_app.event("app_mention")
        async def handle_mention(event: dict, say: object) -> None:
            """Create a task when someone @mentions Corsair."""
            from app.models.task import Task

            user_id = event.get("user", "")
            channel_id = event.get("channel", "")
            text = event.get("text", "")
            slack_ts = event.get("ts", "")

            # Strip the bot mention from text to get the actual request
            import re

            clean_text = re.sub(r"<@[A-Z0-9]+>\s*", "", text).strip()
            if not clean_text:
                await say(text="Please include a task description after the mention.", thread_ts=slack_ts)
                return

            title = clean_text[:120]

            task = await Task.create(
                title=title,
                description=clean_text,
                slack_channel=channel_id,
                slack_thread_ts=slack_ts,
                slack_user_id=user_id,
            )

            await say(
                text=f"Task created: *{task.title}* (status: {task.status.value})",
                thread_ts=slack_ts,
            )
            logger.info("Task %s created from Slack mention by %s", task.id, user_id)

        @bolt_app.event("message")
        async def handle_message(event: dict, say: object) -> None:
            # Skip bot messages
            if event.get("bot_id") or event.get("subtype"):
                return

            user_id = event.get("user", "")
            channel_id = event.get("channel", "")
            text = event.get("text", "")
            slack_ts = event.get("ts", "")
            thread_ts = event.get("thread_ts")

            # Best-effort resolve names
            user_name = ""
            channel_name = ""
            try:
                user_info = await client.users_info(user=user_id)
                user_name = user_info["user"].get("real_name", user_info["user"].get("name", ""))
            except Exception:
                logger.debug("Could not resolve user name for %s", user_id)
            try:
                conv_info = await client.conversations_info(channel=channel_id)
                channel_name = conv_info["channel"].get("name", "")
            except Exception:
                logger.debug("Could not resolve channel name for %s", channel_id)

            await ChatMessage.create(
                id=uuid.uuid4(),
                channel_id=channel_id,
                channel_name=channel_name,
                user_id=user_id,
                user_name=user_name,
                message=text,
                slack_ts=slack_ts,
                thread_ts=thread_ts,
            )

        handler = AsyncSocketModeHandler(bolt_app, settings.slack_app_token)
        self._listening = True
        asyncio.create_task(handler.start_async())

        try:
            await client.chat_postMessage(
                channel="U08HF50FEH0",
                text="Hello! Corsair is online and ready.",
            )
        except Exception:
            logger.exception("Failed to send startup DM")
