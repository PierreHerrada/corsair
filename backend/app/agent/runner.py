from __future__ import annotations

import asyncio
import json
import logging
import os
import pwd
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.agent.cost import INPUT_PRICE_PER_M, OUTPUT_PRICE_PER_M
from app.agent.prompts import build_plan_prompt, build_review_prompt, build_work_prompt
from app.agent.workspace import (
    capture_file_tree,
    clone_repo,
    create_workspace,
    write_claude_md,
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


def _build_prompt(task: Task, stage: RunStage) -> str:
    if stage == RunStage.PLAN:
        return build_plan_prompt(task.title, task.description, task.acceptance)
    elif stage == RunStage.WORK:
        return build_work_prompt()
    elif stage == RunStage.REVIEW:
        return build_review_prompt(
            task.jira_key or "UNKNOWN",
            task.title,
            task.jira_url or "",
        )
    raise ValueError(f"Unknown stage: {stage}")


_STAGE_TO_TASK_STATUS = {
    RunStage.PLAN: TaskStatus.PLANNED,
    RunStage.WORK: TaskStatus.WORKING,
    RunStage.REVIEW: TaskStatus.REVIEWING,
}


def _classify_event(event: dict) -> tuple[LogType, dict]:
    """Classify a stream-json event into a log type and content dict."""
    event_type = event.get("type", "")

    if event_type == "assistant" and "message" in event:
        # Assistant text message
        msg = event["message"]
        content_blocks = msg.get("content", [])
        texts = []
        for block in content_blocks:
            if block.get("type") == "text":
                texts.append(block.get("text", ""))
        if texts:
            return LogType.TEXT, {"message": "\n".join(texts)}
        return LogType.TEXT, {"message": json.dumps(event)}

    if event_type == "tool_use":
        return LogType.TOOL_USE, {
            "tool": event.get("tool", event.get("name", "unknown")),
            "input": event.get("input", {}),
            "message": f"Tool: {event.get('tool', event.get('name', 'unknown'))}",
        }

    if event_type == "tool_result":
        return LogType.TOOL_RESULT, {
            "tool": event.get("tool", event.get("name", "unknown")),
            "output": event.get("output", ""),
            "message": f"Result: {event.get('tool', event.get('name', 'unknown'))}",
        }

    if event_type == "error":
        return LogType.ERROR, {
            "message": event.get("error", {}).get("message", json.dumps(event)),
        }

    if event_type == "result":
        # Final result event with cost info
        return LogType.TEXT, {
            "message": "Run completed",
            "is_result": True,
            "cost": event.get("cost_usd"),
            "duration": event.get("duration_ms"),
            "tokens_in": event.get("num_input_tokens", event.get("usage", {}).get("input_tokens", 0)),
            "tokens_out": event.get("num_output_tokens", event.get("usage", {}).get("output_tokens", 0)),
        }

    # Fallback: store as text
    return LogType.TEXT, {"message": json.dumps(event)}


async def _notify_run_complete(task: Task, stage: RunStage, success: bool) -> None:
    """Send Jira comment and Slack thread message when an agent run finishes."""
    status_text = "completed successfully" if success else "failed"
    stage_label = stage.value.capitalize()
    message = f"{stage_label} stage {status_text}."

    from app.integrations.registry import IntegrationRegistry

    # Jira comment
    try:
        jira = IntegrationRegistry.get("jira")
        if jira is not None and task.jira_key:
            await jira.add_comment(task.jira_key, message)
    except Exception:
        logger.exception("Failed to post Jira comment for task %s", task.id)

    # Slack thread reply
    try:
        slack = IntegrationRegistry.get("slack")
        if slack is not None and task.slack_channel and task.slack_thread_ts:
            await slack.post_thread_update(task.slack_channel, task.slack_thread_ts, message)
    except Exception:
        logger.exception("Failed to post Slack update for task %s", task.id)


async def run_agent(
    task: Task,
    stage: RunStage,
    ws_broadcast: Optional[object] = None,
    repo_path: Optional[str] = None,
    existing_run: Optional[AgentRun] = None,
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
    prompt = _build_prompt(task, stage)
    base_prompt = await _get_base_prompt()
    if base_prompt:
        prompt = base_prompt + "\n\n" + prompt
        logger.info("Base prompt prepended (%d chars)", len(base_prompt))

    # Set up workspace: create → clone → CLAUDE.md → capture file tree
    workspace_dir: Optional[str] = None
    if task.repo and not repo_path:
        try:
            from app.models.repository import Repository

            repo_record = await Repository.filter(full_name=task.repo).first()
            branch = repo_record.default_branch if repo_record else "main"
            token = settings.github_token

            # Step 1: Create workspace
            log = await save_log(run.id, {"message": "Creating workspace..."})
            if ws_broadcast:
                await ws_broadcast(str(run.id), log)
            ws_path = await create_workspace(run_id_str)
            workspace_dir = str(ws_path)
            await AgentRun.filter(id=run.id).update(workspace_path=workspace_dir)
            logger.info("Workspace created: %s", workspace_dir)

            # Step 2: Clone repository
            log = await save_log(
                run.id, {"message": f"Cloning {task.repo} (branch: {branch})..."}
            )
            if ws_broadcast:
                await ws_broadcast(str(run.id), log)
            await clone_repo(ws_path, task.repo, branch, token)
            log = await save_log(
                run.id, {"message": f"Cloned {task.repo} successfully."}
            )
            if ws_broadcast:
                await ws_broadcast(str(run.id), log)
            logger.info("Cloned %s (branch %s) into %s", task.repo, branch, workspace_dir)

            # Step 3: Write CLAUDE.md
            if base_prompt:
                log = await save_log(
                    run.id, {"message": "Writing CLAUDE.md to workspace..."}
                )
                if ws_broadcast:
                    await ws_broadcast(str(run.id), log)
                write_claude_md(ws_path, base_prompt)
                log = await save_log(
                    run.id,
                    {"message": f"CLAUDE.md written ({len(base_prompt)} chars)."},
                )
                if ws_broadcast:
                    await ws_broadcast(str(run.id), log)

            # Step 4: Capture initial file tree so frontend can show it during the run
            initial_tree = capture_file_tree(ws_path)
            await AgentRun.filter(id=run.id).update(file_tree=initial_tree)
            log = await save_log(
                run.id, {"message": f"Workspace ready — {len(initial_tree)} files."}
            )
            if ws_broadcast:
                await ws_broadcast(str(run.id), log)
            logger.info(
                "Workspace ready: %s (repo=%s branch=%s files=%d)",
                workspace_dir, task.repo, branch, len(initial_tree),
            )
        except Exception as e:
            logger.exception("Workspace setup failed for run %s: %s", run.id, e)
            await AgentRun.filter(id=run.id).update(
                status=RunStatus.FAILED,
                finished_at=datetime.now(timezone.utc),
            )
            await Task.filter(id=task.id).update(status=TaskStatus.FAILED)
            error_log = await save_log(
                run.id, {"message": f"Workspace setup failed: {e}"}, LogType.ERROR,
            )
            if ws_broadcast:
                await ws_broadcast(str(run.id), error_log)
            return await AgentRun.get(id=run.id)

    cwd = workspace_dir or repo_path or os.getcwd()
    logger.info(
        "Launching Claude CLI — run=%s cwd=%s prompt_length=%d",
        run.id, cwd, len(prompt),
    )

    # Log the Claude CLI launch so users can see the transition from setup to agent
    log = await save_log(run.id, {"message": "Launching Claude Code agent..."})
    if ws_broadcast:
        await ws_broadcast(str(run.id), log)

    tokens_in = 0
    tokens_out = 0
    event_count = 0

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

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                **os.environ,
                "ANTHROPIC_API_KEY": settings.anthropic_api_key,
                "HOME": pwd.getpwnam("corsair").pw_dir if os.getuid() == 0 else os.environ.get("HOME", ""),
            },
            preexec_fn=_demote_to_corsair if os.getuid() == 0 else None,
        )
        _active_processes[run_id_str] = process
        logger.info("Claude CLI process started — pid=%s run=%s", process.pid, run.id)

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

            # Extract token usage from result events
            if content.get("is_result"):
                tokens_in = content.get("tokens_in", 0)
                tokens_out = content.get("tokens_out", 0)
                logger.info(
                    "Result event — tokens_in=%d tokens_out=%d run=%s",
                    tokens_in, tokens_out, run.id,
                )

            log = await save_log(run.id, content, log_type)
            if ws_broadcast:
                await ws_broadcast(str(run.id), log)

        await process.wait()

        # Always capture stderr
        stderr_output = ""
        if process.stderr:
            stderr_output = (await process.stderr.read()).decode().strip()
        if stderr_output:
            logger.warning(
                "CLI stderr (run=%s, exit=%d):\n%s",
                run.id, process.returncode, stderr_output[:2000],
            )

        logger.info(
            "Claude CLI exited — run=%s pid=%s returncode=%d events=%d",
            run.id, process.pid, process.returncode, event_count,
        )

        # Compute cost
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
            await _notify_run_complete(task, stage, success=True)
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
                await save_log(
                    run.id,
                    {"message": "Stopped by user"},
                    LogType.ERROR,
                )
                logger.info("Run %s stopped by user for task %s", run.id, task.id)
            else:
                await Task.filter(id=task.id).update(status=TaskStatus.FAILED)
                await save_log(
                    run.id,
                    {"message": f"Process exited with code {process.returncode}\n{stderr_output}"},
                    LogType.ERROR,
                )
            await _notify_run_complete(task, stage, success=False)

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
            await save_log(run.id, {"message": "Stopped by user"}, LogType.ERROR)
        else:
            await Task.filter(id=task.id).update(status=TaskStatus.FAILED)
            await save_log(run.id, {"message": str(e)}, LogType.ERROR)
        await _notify_run_complete(task, stage, success=False)
    finally:
        _active_processes.pop(run_id_str, None)

        # Capture file tree from workspace after run completes
        if workspace_dir and os.path.isdir(workspace_dir):
            try:
                from pathlib import Path

                file_tree = capture_file_tree(Path(workspace_dir))
                await AgentRun.filter(id=run.id).update(file_tree=file_tree)
                logger.info(
                    "Captured file tree (%d entries) for run %s",
                    len(file_tree), run.id,
                )
            except Exception:
                logger.exception("Failed to capture file tree for run %s", run.id)

        logger.info("=== Agent run cleanup done === run=%s task=%s", run_id_str, task.id)

    return await AgentRun.get(id=run.id)
