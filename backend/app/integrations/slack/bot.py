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


async def _analyze_task_safe(task) -> None:
    try:
        from app.agent.analysis import analyze_task
        await analyze_task(task)
    except Exception:
        logger.exception("Failed to analyze task %s", task.id)


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
        logger.info("Slack bot: initializing Socket Mode listener")

        # Log bot identity for debugging
        bot_user_id = None
        try:
            auth = await client.auth_test()
            bot_user_id = auth.get("user_id")
            logger.info(
                "Slack bot: authenticated as %s (bot_id=%s, user_id=%s)",
                auth.get("bot_id", "?"), auth.get("bot_id", "?"), auth.get("user_id", "?"),
            )
        except Exception:
            logger.exception("Slack bot: auth_test failed")

        # Catch-all middleware to log every incoming event
        @bolt_app.middleware
        async def log_all_events(body, next):
            event = body.get("event", {})
            event_type = event.get("type", body.get("type", "unknown"))
            logger.info(
                "Slack bot: incoming event type=%s subtype=%s channel=%s",
                event_type,
                event.get("subtype", "none"),
                event.get("channel", "?"),
            )
            await next()

        @bolt_app.event("app_mention")
        async def handle_mention(event: dict, say: object) -> None:
            """Create a task when someone @mentions Corsair."""
            from app.models.task import Task

            user_id = event.get("user", "")
            channel_id = event.get("channel", "")
            text = event.get("text", "")
            slack_ts = event.get("ts", "")

            logger.info(
                "Slack bot: received @mention from user=%s channel=%s text='%s'",
                user_id, channel_id, text[:100],
            )

            # Strip the bot mention from text to get the actual request
            import re

            clean_text = re.sub(r"<@[A-Z0-9]+>\s*", "", text).strip()
            if not clean_text:
                logger.warning("Slack bot: empty mention from user=%s, skipping task creation", user_id)
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

            # Create a matching Jira issue if Jira is configured
            jira_msg = ""
            try:
                from app.integrations.registry import IntegrationRegistry
                from app.integrations.jira.client import JiraIntegration

                jira = IntegrationRegistry.get("jira")
                if jira is not None and isinstance(jira, JiraIntegration):
                    result = await jira.create_issue(
                        title=title,
                        description=clean_text,
                        acceptance="",
                    )
                    task.jira_key = result["key"]
                    task.jira_url = result["url"]
                    await task.save()
                    jira_msg = f" | Jira: <{result['url']}|{result['key']}>"
                    logger.info("Slack bot: linked task %s to Jira %s", task.id, result["key"])
            except Exception:
                logger.exception("Slack bot: failed to create Jira issue for task %s", task.id)

            await say(
                text=f"Task created: *{task.title}* (status: {task.status.value}){jira_msg}",
                thread_ts=slack_ts,
            )
            logger.info("Slack bot: task %s created — '%s'", task.id, title)

            # Trigger analysis in background
            asyncio.create_task(_analyze_task_safe(task))

        @bolt_app.event("message")
        async def handle_message(event: dict, say: object) -> None:
            from app.models.task import Task

            # Skip bot messages
            if event.get("bot_id") or event.get("subtype"):
                return

            user_id = event.get("user", "")
            channel_id = event.get("channel", "")
            text = event.get("text", "")
            slack_ts = event.get("ts", "")
            thread_ts = event.get("thread_ts")

            # Only persist messages that @mention Corsair or are replies
            # in a thread started by a @mention
            is_mention = bot_user_id and f"<@{bot_user_id}>" in text
            is_mention_thread_reply = False
            if thread_ts:
                is_mention_thread_reply = await Task.exists().filter(
                    slack_channel=channel_id,
                    slack_thread_ts=thread_ts,
                )

            if not is_mention and not is_mention_thread_reply:
                return

            logger.info(
                "Slack bot: message from user=%s channel=%s (thread=%s, mention=%s)",
                user_id, channel_id, thread_ts or "none", is_mention,
            )

            # Best-effort resolve names
            user_name = ""
            channel_name = ""
            try:
                user_info = await client.users_info(user=user_id)
                user_name = user_info["user"].get("real_name", user_info["user"].get("name", ""))
            except Exception:
                logger.warning("Slack bot: could not resolve user name for %s", user_id)
            try:
                conv_info = await client.conversations_info(channel=channel_id)
                channel_name = conv_info["channel"].get("name", "")
            except Exception:
                logger.warning("Slack bot: could not resolve channel name for %s", channel_id)

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
            logger.info(
                "Slack bot: persisted message from %s in #%s",
                user_name or user_id, channel_name or channel_id,
            )

        handler = AsyncSocketModeHandler(bolt_app, settings.slack_app_token)
        self._listening = True
        asyncio.create_task(handler.start_async())
        logger.info("Slack bot: Socket Mode handler started")

        try:
            await client.chat_postMessage(
                channel="U08HF50FEH0",
                text="Hello! Corsair is online and ready.",
            )
            logger.info("Slack bot: startup DM sent successfully")
        except Exception:
            logger.exception("Slack bot: failed to send startup DM")
