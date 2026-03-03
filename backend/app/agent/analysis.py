from __future__ import annotations

import logging

import httpx
from tortoise.queryset import Q

from app.config import settings
from app.models.chat_message import ChatMessage
from app.models.task import Task

logger = logging.getLogger(__name__)


async def analyze_task(task: Task) -> str:
    """Run a lightweight analysis on a task and store the result.

    Gathers Slack conversation context and Jira description, asks Claude
    to summarise the request, then writes the analysis back to the task
    and notifies integrations.
    """
    try:
        # --- Gather conversation messages ---
        messages: list[ChatMessage] = []
        if task.slack_channel and task.slack_thread_ts:
            messages = await ChatMessage.filter(
                Q(channel_id=task.slack_channel)
                & (
                    Q(thread_ts=task.slack_thread_ts)
                    | Q(slack_ts=task.slack_thread_ts)
                )
            ).order_by("created_at").all()

        conversation_text = "\n".join(
            f"[{m.user_name or m.user_id}]: {m.message}" for m in messages
        )

        prompt = (
            "Analyze the following task and provide:\n"
            "1. A concise summary of what is being requested\n"
            "2. Pre-assumptions about scope, approach, and affected areas\n"
            "3. Open questions or ambiguities that need clarification\n"
            "4. Suggested acceptance criteria (if not already provided)\n\n"
            f"Task title: {task.title}\n"
            f"Task description: {task.description}\n"
            f"Acceptance criteria: {task.acceptance or 'Not specified'}\n\n"
        )
        if conversation_text:
            prompt += f"Conversation context:\n{conversation_text}"
        else:
            prompt += "No conversation context available."

        # --- Call Anthropic API ---
        analysis = await _call_anthropic(prompt)

        # --- Store result ---
        await Task.filter(id=task.id).update(analysis=analysis)

        # --- Notify integrations ---
        await _post_analysis_notifications(task, analysis)

        return analysis

    except Exception:
        logger.exception("Failed to analyze task %s", task.id)
        error_msg = "Analysis failed — see logs for details."
        try:
            await Task.filter(id=task.id).update(analysis=error_msg)
        except Exception:
            logger.exception("Failed to store analysis error for task %s", task.id)
        return error_msg


async def _call_anthropic(prompt: str) -> str:
    """Call the Anthropic Messages API and return the assistant text."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]


async def _post_analysis_notifications(task: Task, analysis: str) -> None:
    """Post the analysis as a Jira comment and Slack thread reply."""
    from app.integrations.registry import IntegrationRegistry

    # Jira comment
    try:
        jira = IntegrationRegistry.get("jira")
        if jira is not None and task.jira_key:
            await jira.add_comment(task.jira_key, f"Task Analysis:\n{analysis}")
    except Exception:
        logger.exception("Failed to post analysis Jira comment for task %s", task.id)

    # Slack thread reply
    try:
        slack = IntegrationRegistry.get("slack")
        if slack is not None and task.slack_channel and task.slack_thread_ts:
            await slack.post_thread_update(
                task.slack_channel, task.slack_thread_ts, f"Analysis:\n{analysis}"
            )
    except Exception:
        logger.exception("Failed to post analysis Slack update for task %s", task.id)
