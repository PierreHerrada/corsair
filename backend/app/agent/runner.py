from __future__ import annotations

import asyncio
import json
import logging
import os
import pwd
import random
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.agent.cost import INPUT_PRICE_PER_M, OUTPUT_PRICE_PER_M
from app.agent.prompts import (
    build_investigate_prompt,
    build_plan_prompt,
    build_review_prompt,
    build_work_prompt,
)
from app.agent.workspace import (
    capture_file_tree,
    clone_all_repos,
    create_workspace,
    read_investigation_md,
    read_lessons_md,
    read_pr_url,
    write_claude_md,
    write_datadog_helper,
    write_lessons_md,
    write_plan_md,
    write_skill_files,
    write_subagent_files,
)
from app.config import settings
from app.models import AgentLog, AgentRun, LogType, RunStage, RunStatus, Task, TaskStatus

logger = logging.getLogger(__name__)

# In-memory process registry for stopping running agents
_active_processes: dict[str, asyncio.subprocess.Process] = {}
_stopped_runs: set[str] = set()


def stop_run(run_id: str) -> bool:
    """Terminate a running agent process. Returns True if process was found and signaled."""
    process = _active_processes.get(run_id)
    if process is None:
        return False
    _stopped_runs.add(run_id)
    process.terminate()
    return True


async def save_log(
    run_id: uuid.UUID, content: dict, log_type: LogType = LogType.TEXT
) -> AgentLog:
    return await AgentLog.create(
        id=uuid.uuid4(),
        run_id=run_id,
        type=log_type,
        content=content,
    )


async def _emit(
    run_id: uuid.UUID,
    message: str,
    ws_broadcast: Optional[object] = None,
    log_type: LogType = LogType.TEXT,
) -> AgentLog:
    """Save a log entry and optionally broadcast it via WebSocket."""
    log = await save_log(run_id, {"message": message}, log_type)
    if ws_broadcast:
        await ws_broadcast(str(run_id), log)
    return log


async def update_run_cost(
    run_id: uuid.UUID, tokens_in: int, tokens_out: int, cost_usd: float
) -> None:
    await AgentRun.filter(id=run_id).update(
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        status=RunStatus.DONE,
        finished_at=datetime.now(timezone.utc),
    )


async def _get_enabled_repos() -> set[str]:
    """Return set of full_name strings for enabled repos, or empty set if none configured."""
    from app.models.repository import Repository

    repos = await Repository.filter(enabled=True).all()
    return {r.full_name for r in repos}


async def _get_base_prompt() -> str:
    """Fetch the base prompt from settings, returning empty string if not set."""
    from app.models.setting import Setting

    setting = await Setting.filter(key="base_prompt").first()
    if setting and setting.value.strip():
        return setting.value.strip()
    return ""


async def _get_setting_value(key: str) -> str:
    """Fetch a setting value by key, returning empty string if not set."""
    from app.models.setting import Setting

    setting = await Setting.filter(key=key).first()
    if setting and setting.value.strip():
        return setting.value.strip()
    return ""


def _build_prompt(task: Task, stage: RunStage, datadog_context: str = "") -> str:
    if stage == RunStage.PLAN:
        return build_plan_prompt(task.title, task.description, task.acceptance, task_repo=task.repo)
    elif stage == RunStage.WORK:
        return build_work_prompt(
            task_repo=task.repo,
            title=task.title,
            description=task.description,
            jira_key=task.jira_key,
        )
    elif stage == RunStage.REVIEW:
        return build_review_prompt(
            task.jira_key or "UNKNOWN",
            task.title,
            task.jira_url or "",
        )
    elif stage == RunStage.INVESTIGATE:
        return build_investigate_prompt(task.title, task.description, datadog_context)
    raise ValueError(f"Unknown stage: {stage}")


_STAGE_TO_TASK_STATUS = {
    RunStage.PLAN: TaskStatus.PLANNED,
    RunStage.WORK: TaskStatus.WORKING,
    RunStage.REVIEW: TaskStatus.REVIEWING,
    RunStage.INVESTIGATE: TaskStatus.DONE,
}


def _summarize_tool_use(name: str, tool_input: dict) -> str:
    """Build a human-readable one-liner for a tool call."""
    if name in ("Read", "Write", "Edit"):
        path = tool_input.get("file_path", "")
        return f"{name} {path}" if path else name
    if name == "Bash":
        cmd = tool_input.get("command", "")
        desc = tool_input.get("description", "")
        label = desc or (cmd[:120] + "..." if len(cmd) > 120 else cmd)
        return f"Bash: {label}" if label else "Bash"
    if name in ("Grep", "Glob"):
        pattern = tool_input.get("pattern", "")
        return f"{name} {pattern}" if pattern else name
    if name == "Agent":
        desc = tool_input.get("description", tool_input.get("prompt", "")[:80])
        return f"Agent: {desc}" if desc else "Agent"
    return name


def _summarize_tool_result(content: str, is_error: bool = False) -> str:
    """Truncate tool result content for display."""
    if not content:
        return "(empty)" if not is_error else "(error, no output)"
    lines = content.split("\n")
    if len(lines) <= 3:
        return content[:300]
    preview = lines[0][:200]
    return f"{preview} ... ({len(lines)} lines)"


def _classify_event(event: dict) -> tuple[LogType, dict]:
    """Classify a Claude Code stream-json event into a log type and content dict."""
    event_type = event.get("type", "")
    subtype = event.get("subtype", "")

    # --- system events ---
    if event_type == "system":
        if subtype == "init":
            model = event.get("model", "unknown")
            version = event.get("claude_code_version", "?")
            n_tools = len(event.get("tools", []))
            return LogType.TEXT, {
                "message": f"Claude Code v{version} initialized (model: {model}, {n_tools} tools)",
            }
        if subtype == "task_started":
            desc = event.get("description", "")
            return LogType.TEXT, {
                "message": f"Subagent started: {desc}" if desc else "Subagent started",
            }
        # Other system subtypes
        return LogType.TEXT, {"message": f"[system] {subtype or json.dumps(event)}"}

    # --- assistant messages (text, thinking, tool_use) ---
    if event_type == "assistant" and "message" in event:
        msg = event["message"]
        content_blocks = msg.get("content", [])

        for block in content_blocks:
            block_type = block.get("type", "")

            if block_type == "text":
                text = block.get("text", "")
                # Check for auth / error markers
                if event.get("error") == "authentication_failed":
                    return LogType.ERROR, {"message": text}
                return LogType.TEXT, {"message": text}

            if block_type == "thinking":
                thinking = block.get("thinking", "")
                preview = thinking[:200] + "..." if len(thinking) > 200 else thinking
                return LogType.TEXT, {"message": f"Thinking: {preview}"}

            if block_type == "tool_use":
                name = block.get("name", "unknown")
                tool_input = block.get("input", {})
                summary = _summarize_tool_use(name, tool_input)
                return LogType.TOOL_USE, {
                    "tool": name,
                    "input": tool_input,
                    "message": summary,
                }

        # No recognized content blocks
        return LogType.TEXT, {"message": "(assistant message)"}

    # --- user messages (tool results) ---
    if event_type == "user" and "message" in event:
        msg = event["message"]
        content_items = msg.get("content", [])

        for item in content_items:
            if isinstance(item, dict) and item.get("type") == "tool_result":
                content = item.get("content", "")
                is_error = item.get("is_error", False)
                summary = _summarize_tool_result(str(content), is_error)
                log_type = LogType.ERROR if is_error else LogType.TOOL_RESULT
                return log_type, {"message": summary}

        # tool_use_result shorthand (from stream-json wrapper)
        result_text = event.get("tool_use_result", "")
        if isinstance(result_text, dict):
            stdout = result_text.get("stdout", "")
            stderr = result_text.get("stderr", "")
            content = stdout or stderr
            summary = _summarize_tool_result(content, bool(stderr and not stdout))
            return LogType.TOOL_RESULT, {"message": summary}
        if result_text:
            return LogType.TOOL_RESULT, {
                "message": _summarize_tool_result(str(result_text)),
            }

        return LogType.TOOL_RESULT, {"message": "(result)"}

    # --- top-level tool_use (older format) ---
    if event_type == "tool_use":
        name = event.get("tool", event.get("name", "unknown"))
        tool_input = event.get("input", {})
        summary = _summarize_tool_use(name, tool_input)
        return LogType.TOOL_USE, {
            "tool": name,
            "input": tool_input,
            "message": summary,
        }

    # --- top-level tool_result (older format) ---
    if event_type == "tool_result":
        content = event.get("output", event.get("content", ""))
        is_error = event.get("is_error", False)
        summary = _summarize_tool_result(str(content), is_error)
        return LogType.ERROR if is_error else LogType.TOOL_RESULT, {"message": summary}

    # --- error ---
    if event_type == "error":
        return LogType.ERROR, {
            "message": event.get("error", {}).get("message", json.dumps(event)),
        }

    # --- result (final summary) ---
    if event_type == "result":
        usage = event.get("usage", {})
        tokens_in = event.get("num_input_tokens", usage.get("input_tokens", 0))
        tokens_out = event.get("num_output_tokens", usage.get("output_tokens", 0))
        duration = event.get("duration_ms", 0)
        cost = event.get("total_cost_usd", event.get("cost_usd"))
        duration_s = f"{duration / 1000:.1f}s" if duration else "?"
        cost_str = f"${cost:.4f}" if cost else "?"
        is_error = event.get("is_error", False)
        msg = (
            f"Completed in {duration_s} — "
            f"Tokens: {tokens_in:,} in / {tokens_out:,} out — "
            f"Cost: {cost_str}"
        )
        return (LogType.ERROR if is_error else LogType.TEXT), {
            "message": msg,
            "is_result": True,
            "cost": cost,
            "duration": duration,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }

    # Fallback
    return LogType.TEXT, {"message": json.dumps(event)}


def _text_to_adf(text: str) -> dict:
    """Convert plain text to Atlassian Document Format (ADF)."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


_FUNNY_WORDS = [
    "Bazinga!", "Cowabunga!", "Wubba lubba dub dub!", "Shazam!", "Booyah!",
    "Yoink!", "Kaboom!", "Zoinks!", "Kapow!", "Wahoo!",
    "Bingo bongo!", "Holy guacamole!", "Schwifty!", "Crikey!", "Eureka!",
]


def _build_work_slack_message(task: Task, plan_text: str, pr_url: str) -> str:
    """Build a dynamic Slack message for a successful work stage completion."""
    funny = random.choice(_FUNNY_WORDS)
    lines = [f"*{funny}* Implementation complete for *{task.title}*"]

    if pr_url:
        lines.append(f"\n:rocket: *Pull Request:* {pr_url}")

    if task.jira_key:
        jira_link = task.jira_url or task.jira_key
        lines.append(f":ticket: *Ticket:* {jira_link}")

    if plan_text:
        # Truncate to a reasonable summary for Slack
        summary = plan_text.strip()
        if len(summary) > 500:
            summary = summary[:500] + "..."
        lines.append(f"\n:memo: *Summary:*\n{summary}")

    return "\n".join(lines)


async def _notify_run_complete(
    task: Task, stage: RunStage, success: bool, plan_text: str = "", pr_url: str = ""
) -> None:
    """Send Jira comment and Slack thread message when an agent run finishes."""
    status_text = "completed successfully" if success else "failed"
    stage_label = stage.value.capitalize()
    message = f"{stage_label} stage {status_text}."
    if pr_url and stage in (RunStage.WORK, RunStage.REVIEW) and success:
        message = f"{stage_label} stage {status_text}.\nPR: {pr_url}"

    from app.integrations.registry import IntegrationRegistry

    # Jira comment
    try:
        jira = IntegrationRegistry.get("jira")
        if jira is not None and task.jira_key:
            # For successful plan stage, post the plan content as the comment
            if stage == RunStage.PLAN and success and plan_text:
                await jira.add_comment(task.jira_key, plan_text)
                await jira.update_status(task.jira_key, "Planned")
                if settings.jira_plan_custom_field:
                    await jira.update_fields(
                        task.jira_key,
                        {settings.jira_plan_custom_field: _text_to_adf(plan_text)},
                    )
            else:
                await jira.add_comment(task.jira_key, message)
    except Exception:
        logger.exception("Failed to post Jira comment for task %s", task.id)

    # Slack thread reply
    try:
        slack = IntegrationRegistry.get("slack")
        if slack is not None and task.slack_channel and task.slack_thread_ts:
            if stage == RunStage.WORK and success:
                slack_message = _build_work_slack_message(task, plan_text, pr_url)
            elif stage == RunStage.PLAN and success and plan_text:
                slack_message = plan_text
            else:
                slack_message = message
            await slack.post_thread_update(task.slack_channel, task.slack_thread_ts, slack_message)
    except Exception:
        logger.exception("Failed to post Slack update for task %s", task.id)


async def run_agent(
    task: Task,
    stage: RunStage,
    ws_broadcast: Optional[object] = None,
    repo_path: Optional[str] = None,
    existing_run: Optional[AgentRun] = None,
    datadog_context: str = "",
) -> AgentRun:
    """Execute Claude Code CLI for a given task and stage."""
    logger.info(
        "=== Agent run starting === task=%s stage=%s repo=%s",
        task.id, stage.value, task.repo,
    )

    # Gate: reject if task targets a repo that isn't enabled
    if task.repo:
        enabled_repos = await _get_enabled_repos()
        logger.info("Enabled repos: %s", enabled_repos)
        if enabled_repos and task.repo not in enabled_repos:
            logger.warning(
                "Repo '%s' is not enabled — rejecting run for task %s",
                task.repo, task.id,
            )
            run = existing_run or await AgentRun.create(
                id=uuid.uuid4(),
                task=task,
                stage=stage,
                status=RunStatus.RUNNING,
            )
            await AgentRun.filter(id=run.id).update(
                status=RunStatus.FAILED,
                finished_at=datetime.now(timezone.utc),
            )
            await Task.filter(id=task.id).update(status=TaskStatus.FAILED)
            msg = (
                f"Repository '{task.repo}' is not enabled. "
                "Enable it in Settings > Repositories."
            )
            await save_log(run.id, {"message": msg}, LogType.ERROR)
            return await AgentRun.get(id=run.id)

    if existing_run is not None:
        run = existing_run
        logger.info("Reusing existing run %s", run.id)
    else:
        run = await AgentRun.create(
            id=uuid.uuid4(),
            task=task,
            stage=stage,
            status=RunStatus.RUNNING,
        )
        logger.info("Created new run %s", run.id)

    run_id_str = str(run.id)

    # --- Visible log: run initialization ---
    await _emit(
        run.id,
        f"Starting {stage.value} stage for: {task.title}",
        ws_broadcast,
    )
    if task.repo:
        await _emit(run.id, f"Target repository: {task.repo}", ws_broadcast)
    if task.jira_key:
        await _emit(run.id, f"Jira ticket: {task.jira_key}", ws_broadcast)

    # --- Build prompt ---
    await _emit(run.id, f"Building {stage.value} prompt...", ws_broadcast)
    prompt = _build_prompt(task, stage, datadog_context=datadog_context)
    base_prompt = await _get_base_prompt()
    if base_prompt:
        prompt = base_prompt + "\n\n" + prompt
        await _emit(
            run.id,
            f"Base prompt loaded ({len(base_prompt)} chars).",
            ws_broadcast,
        )
        logger.info("Base prompt prepended (%d chars)", len(base_prompt))
    await _emit(
        run.id,
        f"Prompt ready ({len(prompt)} chars).",
        ws_broadcast,
    )

    # --- Repo gating check ---
    if task.repo:
        await _emit(run.id, "Checking repository permissions...", ws_broadcast)
        await _emit(run.id, f"Repository {task.repo} is enabled.", ws_broadcast)

    # --- Set up workspace ---
    workspace_dir: Optional[str] = None
    lessons_before: Optional[str] = None

    # INVESTIGATE stage: lightweight workspace (no repo clone)
    if stage == RunStage.INVESTIGATE and not repo_path:
        try:
            await _emit(run.id, "Creating investigation workspace...", ws_broadcast)
            ws_path = await create_workspace(run_id_str)
            workspace_dir = str(ws_path)
            await AgentRun.filter(id=run.id).update(workspace_path=workspace_dir)

            # Write datadog helper script
            write_datadog_helper(
                ws_path, settings.dd_api_key, settings.dd_app_key, settings.dd_site,
            )
            await _emit(run.id, "Wrote datadog_helper.py to workspace.", ws_broadcast)

            # Write CLAUDE.md
            base_prompt = await _get_base_prompt()
            if base_prompt:
                write_claude_md(ws_path, base_prompt)

            # Write skill / subagent / lessons files
            skills_json = await _get_setting_value("skills")
            if skills_json:
                write_skill_files(ws_path, skills_json)
            subagents_json = await _get_setting_value("subagents")
            if subagents_json:
                write_subagent_files(ws_path, subagents_json)
            lessons_content = await _get_setting_value("lessons")
            if lessons_content:
                write_lessons_md(ws_path, lessons_content)
                lessons_before = lessons_content

            initial_tree = capture_file_tree(ws_path)
            await AgentRun.filter(id=run.id).update(file_tree=initial_tree)
            await _emit(
                run.id,
                f"Investigation workspace ready — {len(initial_tree)} files.",
                ws_broadcast,
            )
        except Exception as e:
            logger.exception("Investigation workspace setup failed for run %s: %s", run.id, e)
            await AgentRun.filter(id=run.id).update(
                status=RunStatus.FAILED,
                finished_at=datetime.now(timezone.utc),
            )
            await Task.filter(id=task.id).update(status=TaskStatus.FAILED)
            await _emit(run.id, f"Workspace setup failed: {e}", ws_broadcast, LogType.ERROR)
            return await AgentRun.get(id=run.id)

    if stage != RunStage.INVESTIGATE and not repo_path:
        try:
            from app.models.repository import Repository

            enabled_repo_records = await Repository.filter(enabled=True).all()
            token = settings.github_token

            if enabled_repo_records:
                # Step 1: Create workspace
                await _emit(run.id, "Creating workspace...", ws_broadcast)
                ws_path = await create_workspace(run_id_str)
                workspace_dir = str(ws_path)
                await AgentRun.filter(id=run.id).update(workspace_path=workspace_dir)
                await _emit(
                    run.id, f"Workspace created at {workspace_dir}", ws_broadcast,
                )
                logger.info("Workspace created: %s", workspace_dir)

                # Step 2: Clone all enabled repos into subfolders
                repos_to_clone = [
                    (r.full_name, r.default_branch) for r in enabled_repo_records
                ]
                repo_names = [r.full_name for r in enabled_repo_records]
                await _emit(
                    run.id,
                    f"Cloning {len(repos_to_clone)} repo(s): {', '.join(repo_names)}...",
                    ws_broadcast,
                )
                clone_results = await clone_all_repos(
                    ws_path, repos_to_clone, token, task_repo=task.repo,
                )
                cloned_count = sum(1 for p in clone_results.values() if p is not None)
                skipped = [fn for fn, p in clone_results.items() if p is None]
                await _emit(
                    run.id,
                    f"Cloned {cloned_count}/{len(repos_to_clone)} repo(s) successfully."
                    + (f" Skipped: {', '.join(skipped)}" if skipped else ""),
                    ws_broadcast,
                )
                logger.info(
                    "Cloned %d/%d repos into %s (skipped: %s)",
                    cloned_count, len(repos_to_clone), workspace_dir, skipped,
                )

                # Step 3: Write CLAUDE.md
                if base_prompt:
                    await _emit(
                        run.id, "Writing CLAUDE.md to workspace...", ws_broadcast,
                    )
                    write_claude_md(ws_path, base_prompt)
                    await _emit(
                        run.id,
                        f"CLAUDE.md written ({len(base_prompt)} chars):\n{base_prompt}",
                        ws_broadcast,
                    )

                # Step 3b: Write skill files
                skills_json = await _get_setting_value("skills")
                if skills_json:
                    n = write_skill_files(ws_path, skills_json)
                    if n:
                        await _emit(
                            run.id,
                            f"Wrote {n} skill file(s):\n{skills_json}",
                            ws_broadcast,
                        )

                # Step 3c: Write subagent files
                subagents_json = await _get_setting_value("subagents")
                if subagents_json:
                    n = write_subagent_files(ws_path, subagents_json)
                    if n:
                        await _emit(
                            run.id,
                            f"Wrote {n} subagent file(s):\n{subagents_json}",
                            ws_broadcast,
                        )

                # Step 3d: Write LESSONS.md
                lessons_content = await _get_setting_value("lessons")
                if lessons_content:
                    write_lessons_md(ws_path, lessons_content)
                    lessons_before = lessons_content
                    await _emit(
                        run.id,
                        f"LESSONS.md written ({len(lessons_content)} chars):\n{lessons_content}",
                        ws_broadcast,
                    )

                # Step 3e: Write PLAN.md from task.plan (for work/review stages)
                if task.plan and stage in (RunStage.WORK, RunStage.REVIEW):
                    write_plan_md(ws_path, task.plan)
                    await _emit(
                        run.id,
                        f"PLAN.md written ({len(task.plan)} chars):\n{task.plan}",
                        ws_broadcast,
                    )

                # Step 4: Capture initial file tree so frontend can show it during the run
                await _emit(run.id, "Scanning workspace file tree...", ws_broadcast)
                initial_tree = capture_file_tree(ws_path)
                await AgentRun.filter(id=run.id).update(file_tree=initial_tree)
                await _emit(
                    run.id,
                    f"Workspace ready — {len(initial_tree)} files.",
                    ws_broadcast,
                )
                logger.info(
                    "Workspace ready: %s (repos=%d files=%d)",
                    workspace_dir, cloned_count, len(initial_tree),
                )
        except Exception as e:
            logger.exception("Workspace setup failed for run %s: %s", run.id, e)
            await AgentRun.filter(id=run.id).update(
                status=RunStatus.FAILED,
                finished_at=datetime.now(timezone.utc),
            )
            await Task.filter(id=task.id).update(status=TaskStatus.FAILED)
            await _emit(
                run.id,
                f"Workspace setup failed: {e}",
                ws_broadcast,
                LogType.ERROR,
            )
            return await AgentRun.get(id=run.id)

    cwd = workspace_dir or repo_path or os.getcwd()
    logger.info(
        "Launching Claude CLI — run=%s cwd=%s prompt_length=%d",
        run.id, cwd, len(prompt),
    )

    # --- Launching Claude ---
    await _emit(
        run.id,
        f"Launching Claude Code agent (cwd: {cwd})...",
        ws_broadcast,
    )

    tokens_in = 0
    tokens_out = 0
    reported_cost: Optional[float] = None
    event_count = 0
    last_assistant_text = ""

    try:
        cmd = [
            "claude",
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
            "--max-turns", "200",
            "-p", prompt,
        ]
        logger.info("Subprocess command: %s", " ".join(cmd[:7]) + " -p <prompt>")

        # Run as non-root user — Claude CLI rejects --dangerously-skip-permissions under root
        def _demote_to_corsair() -> None:
            try:
                pw = pwd.getpwnam("corsair")
                os.setgid(pw.pw_gid)
                os.setuid(pw.pw_uid)
            except KeyError:
                logger.warning("User 'corsair' not found — running as current user")

        sub_env = {
            **os.environ,
            "ANTHROPIC_API_KEY": settings.anthropic_api_key,
            "HOME": (
                pwd.getpwnam("corsair").pw_dir
                if os.getuid() == 0
                else os.environ.get("HOME", "")
            ),
        }
        if stage == RunStage.INVESTIGATE:
            sub_env["DD_API_KEY"] = settings.dd_api_key
            sub_env["DD_APP_KEY"] = settings.dd_app_key
            sub_env["DD_SITE"] = settings.dd_site

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=sub_env,
            preexec_fn=_demote_to_corsair if os.getuid() == 0 else None,
        )
        _active_processes[run_id_str] = process
        logger.info("Claude CLI process started — pid=%s run=%s", process.pid, run.id)

        await _emit(
            run.id,
            f"Claude Code process started (PID: {process.pid}). Streaming output...",
            ws_broadcast,
        )

        # Drain stderr concurrently to prevent pipe deadlock.
        # The --verbose flag causes Claude CLI to write debug output to stderr.
        # If we only read stderr after stdout finishes, the stderr pipe buffer
        # can fill up (~64KB), blocking the CLI and deadlocking the runner.
        stderr_chunks: list[bytes] = []

        async def _drain_stderr() -> None:
            assert process.stderr is not None
            while True:
                chunk = await process.stderr.read(8192)
                if not chunk:
                    break
                stderr_chunks.append(chunk)

        stderr_task = asyncio.create_task(_drain_stderr())

        # Stream stdout line by line — each line is a JSON event
        async for line in process.stdout:
            decoded = line.decode().rstrip()
            if not decoded:
                continue
            event_count += 1
            try:
                event = json.loads(decoded)
            except json.JSONDecodeError:
                logger.warning(
                    "Non-JSON output from CLI (run=%s): %s",
                    run.id, decoded[:200],
                )
                log = await save_log(run.id, {"message": decoded})
                if ws_broadcast:
                    await ws_broadcast(str(run.id), log)
                continue

            log_type, content = _classify_event(event)
            logger.info(
                "Event #%d run=%s type=%s: %s",
                event_count, run.id, log_type.value,
                content.get("message", "")[:150],
            )

            # Track last assistant text block for plan extraction
            if event.get("type") == "assistant" and "message" in event:
                for block in event["message"].get("content", []):
                    if block.get("type") == "text" and block.get("text"):
                        last_assistant_text = block["text"]

            # Extract token usage and cost from result events
            if content.get("is_result"):
                tokens_in = content.get("tokens_in", 0)
                tokens_out = content.get("tokens_out", 0)
                if content.get("cost") is not None:
                    reported_cost = content["cost"]
                logger.info(
                    "Result event — tokens_in=%d tokens_out=%d run=%s",
                    tokens_in, tokens_out, run.id,
                )

            log = await save_log(run.id, content, log_type)
            if ws_broadcast:
                await ws_broadcast(str(run.id), log)

        await process.wait()
        await stderr_task

        # Collect stderr output
        stderr_output = b"".join(stderr_chunks).decode(errors="replace").strip()
        if stderr_output:
            logger.warning(
                "CLI stderr (run=%s, exit=%d):\n%s",
                run.id, process.returncode, stderr_output[:2000],
            )

        logger.info(
            "Claude CLI exited — run=%s pid=%s returncode=%d events=%d",
            run.id, process.pid, process.returncode, event_count,
        )

        # Use CLI-reported cost when available; fall back to estimate
        if reported_cost is not None:
            cost = Decimal(str(reported_cost))
        else:
            cost = (Decimal(tokens_in) / 1_000_000 * INPUT_PRICE_PER_M) + (
                Decimal(tokens_out) / 1_000_000 * OUTPUT_PRICE_PER_M
            )

        if process.returncode == 0:
            logger.info(
                "=== Agent run succeeded === run=%s task=%s stage=%s "
                "tokens_in=%d tokens_out=%d cost=$%.4f",
                run.id, task.id, stage.value, tokens_in, tokens_out, float(cost),
            )
            await update_run_cost(run.id, tokens_in, tokens_out, float(cost))
            new_status = _STAGE_TO_TASK_STATUS.get(stage)
            if new_status:
                await Task.filter(id=task.id).update(status=new_status)
            if stage == RunStage.PLAN and last_assistant_text:
                await Task.filter(id=task.id).update(plan=last_assistant_text)

            # Read INVESTIGATION.md from workspace (written by agent during investigate stage)
            if stage == RunStage.INVESTIGATE and workspace_dir and os.path.isdir(workspace_dir):
                try:
                    from pathlib import Path as _IPath

                    inv_text = read_investigation_md(_IPath(workspace_dir))
                    if inv_text:
                        await Task.filter(id=task.id).update(plan=inv_text)
                        await _emit(
                            run.id,
                            f"Investigation summary saved ({len(inv_text)} chars).",
                            ws_broadcast,
                        )
                        logger.info("Investigation summary saved for task %s", task.id)
                except Exception:
                    logger.exception("Failed to read INVESTIGATION.md for run %s", run.id)

            # Read PR URL from workspace (written by agent during work or review stage)
            detected_pr_url = ""
            if stage in (RunStage.WORK, RunStage.REVIEW) and workspace_dir and os.path.isdir(workspace_dir):
                try:
                    from pathlib import Path as _PPath

                    detected_pr_url = read_pr_url(_PPath(workspace_dir)) or ""
                    if detected_pr_url:
                        await Task.filter(id=task.id).update(
                            pr_url=detected_pr_url,
                        )
                        await _emit(
                            run.id,
                            f"PR created: {detected_pr_url}",
                            ws_broadcast,
                        )
                        logger.info("PR URL detected: %s for task %s", detected_pr_url, task.id)
                except Exception:
                    logger.exception("Failed to read PR URL for run %s", run.id)

            # --- Visible log: success summary ---
            await _emit(
                run.id,
                f"Agent completed successfully. "
                f"Tokens: {tokens_in:,} in / {tokens_out:,} out — Cost: ${float(cost):.4f}",
                ws_broadcast,
            )
            await _emit(
                run.id,
                f"Task status updated to {new_status.value if new_status else 'unchanged'}.",
                ws_broadcast,
            )

            # Notify integrations
            await _emit(run.id, "Notifying integrations...", ws_broadcast)
            await _notify_run_complete(
                task, stage, success=True,
                plan_text=last_assistant_text, pr_url=detected_pr_url,
            )
            await _emit(run.id, "Notifications sent.", ws_broadcast)
        else:
            stopped_by_user = run_id_str in _stopped_runs
            logger.error(
                "=== Agent run failed === run=%s task=%s stage=%s "
                "returncode=%d stopped_by_user=%s",
                run.id, task.id, stage.value,
                process.returncode, stopped_by_user,
            )
            await AgentRun.filter(id=run.id).update(
                status=RunStatus.FAILED,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=float(cost),
                finished_at=datetime.now(timezone.utc),
            )
            if stopped_by_user:
                _stopped_runs.discard(run_id_str)
                await Task.filter(id=task.id).update(status=TaskStatus.FAILED)
                await _emit(
                    run.id, "Stopped by user.", ws_broadcast, LogType.ERROR,
                )
                logger.info("Run %s stopped by user for task %s", run.id, task.id)
            else:
                await Task.filter(id=task.id).update(status=TaskStatus.FAILED)
                await _emit(
                    run.id,
                    f"Process exited with code {process.returncode}\n{stderr_output}",
                    ws_broadcast,
                    LogType.ERROR,
                )

            if tokens_in or tokens_out:
                await _emit(
                    run.id,
                    f"Tokens used before failure: {tokens_in:,} in / "
                    f"{tokens_out:,} out — Cost: ${float(cost):.4f}",
                    ws_broadcast,
                )

            await _emit(run.id, "Notifying integrations...", ws_broadcast)
            await _notify_run_complete(task, stage, success=False)
            await _emit(run.id, "Notifications sent.", ws_broadcast)

    except Exception as e:
        logger.exception(
            "=== Agent run exception === task=%s stage=%s error=%s",
            task.id, stage.value, e,
        )
        stopped_by_user = run_id_str in _stopped_runs
        await AgentRun.filter(id=run.id).update(
            status=RunStatus.FAILED,
            finished_at=datetime.now(timezone.utc),
        )
        if stopped_by_user:
            _stopped_runs.discard(run_id_str)
            await Task.filter(id=task.id).update(status=TaskStatus.FAILED)
            await _emit(
                run.id, "Stopped by user.", ws_broadcast, LogType.ERROR,
            )
        else:
            await Task.filter(id=task.id).update(status=TaskStatus.FAILED)
            await _emit(
                run.id, str(e), ws_broadcast, LogType.ERROR,
            )

        await _emit(run.id, "Notifying integrations...", ws_broadcast)
        await _notify_run_complete(task, stage, success=False)
        await _emit(run.id, "Notifications sent.", ws_broadcast)
    finally:
        _active_processes.pop(run_id_str, None)

        # Capture file tree from workspace after run completes
        if workspace_dir and os.path.isdir(workspace_dir):
            try:
                from pathlib import Path

                await _emit(
                    run.id, "Capturing final workspace file tree...", ws_broadcast,
                )
                file_tree = capture_file_tree(Path(workspace_dir))
                await AgentRun.filter(id=run.id).update(file_tree=file_tree)
                await _emit(
                    run.id,
                    f"Final file tree captured — {len(file_tree)} files.",
                    ws_broadcast,
                )
                logger.info(
                    "Captured file tree (%d entries) for run %s",
                    len(file_tree), run.id,
                )
            except Exception:
                logger.exception("Failed to capture file tree for run %s", run.id)

        # Post-run: detect LESSONS.md changes made by the agent
        if workspace_dir and os.path.isdir(workspace_dir):
            try:
                from pathlib import Path as _Path

                lessons_after = read_lessons_md(_Path(workspace_dir))
                if lessons_after is not None and lessons_after != (lessons_before or ""):
                    from app.models.setting import Setting as _Setting
                    from app.models.setting_history import SettingHistory

                    setting = await _Setting.filter(key="lessons").first()
                    old_val = setting.value if setting else ""
                    if setting:
                        setting.value = lessons_after
                        await setting.save()
                    else:
                        await _Setting.create(
                            id=uuid.uuid4(),
                            key="lessons",
                            value=lessons_after,
                        )
                    await SettingHistory.create(
                        id=uuid.uuid4(),
                        setting_key="lessons",
                        old_value=old_val,
                        new_value=lessons_after,
                        change_source="agent",
                    )
                    await _emit(
                        run.id,
                        "Agent updated LESSONS.md — synced to settings.",
                        ws_broadcast,
                    )
                    logger.info("LESSONS.md updated by agent for run %s", run.id)
            except Exception:
                logger.exception("Failed to sync LESSONS.md for run %s", run.id)

        await _emit(run.id, "Run complete. Cleaning up.", ws_broadcast)
        logger.info("=== Agent run cleanup done === run=%s task=%s", run_id_str, task.id)

    return await AgentRun.get(id=run.id)
