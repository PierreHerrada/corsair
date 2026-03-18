from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys

from config import AgentConfig
from log_streamer import LogStreamer, post_status
from prompt_loader import get_prompt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("agent.harness")


async def run() -> None:
    config = AgentConfig()  # type: ignore[call-arg]
    streamer = LogStreamer(config.callback_url, config.agent_run_id, config.internal_api_secret)
    timed_out = False
    token_usage: dict | None = None
    cost_data: dict | None = None
    exit_code = 1

    try:
        # Notify control plane we're starting
        await streamer.add("system", f"Starting {config.stage} stage for task {config.task_id}")

        # Clone repo
        workspace = os.path.join(config.work_dir, config.task_id)
        clone_url = config.repo_url
        if config.github_token and clone_url.startswith("https://"):
            clone_url = clone_url.replace("https://", f"https://x-access-token:{config.github_token}@")

        clone_result = subprocess.run(
            ["git", "clone", "--branch", config.branch, "--depth", "1", clone_url, workspace],
            capture_output=True,
            text=True,
        )
        if clone_result.returncode != 0:
            error_msg = f"Git clone failed: {clone_result.stderr}"
            await streamer.add("error", error_msg)
            await streamer.close()
            await post_status(
                config.callback_url, config.agent_run_id, config.internal_api_secret,
                status="failed", exit_code=1, error_message=error_msg,
            )
            sys.exit(1)

        await streamer.add("system", f"Repository cloned to {workspace}")

        # Build prompt
        if config.prompt_override:
            prompt = config.prompt_override
        else:
            prompt = get_prompt(config.stage, config.task_description, config.plan_output)

        # Build environment
        env = os.environ.copy()
        env["ANTHROPIC_API_KEY"] = config.anthropic_api_key
        if config.docker_host:
            env["DOCKER_HOST"] = config.docker_host

        # Build command
        cmd = [
            "claude",
            "--print",
            "--output-format", "stream-json",
            "--dangerously-skip-permissions",
            "--max-turns", "50",
            "-p", prompt,
        ]

        # Spawn subprocess
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workspace,
            env=env,
        )

        # Watchdog timer
        async def watchdog() -> None:
            nonlocal timed_out
            await asyncio.sleep(config.max_duration_seconds)
            timed_out = True
            proc.kill()

        watchdog_task = asyncio.create_task(watchdog())

        # Read stdout line by line
        assert proc.stdout is not None
        async for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                event_type = event.get("type", "")
                if event_type == "result":
                    # Extract token usage and cost
                    token_usage = {
                        "input_tokens": event.get("input_tokens", 0),
                        "output_tokens": event.get("output_tokens", 0),
                    }
                    cost_val = event.get("cost_usd") or event.get("total_cost_usd") or 0
                    cost_data = {"total_cost": cost_val}
                else:
                    # Classify and stream log
                    log_type = "text"
                    content = line
                    if event_type == "assistant":
                        content = event.get("message", line)
                    elif event_type == "tool_use":
                        log_type = "tool_use"
                        content = json.dumps({"name": event.get("name", ""), "input": event.get("input", {})})
                    elif event_type == "tool_result":
                        log_type = "tool_result"
                        content = str(event.get("content", ""))[:500]
                    elif event_type == "error":
                        log_type = "error"
                        content = event.get("error", line)
                    await streamer.add(log_type, content)
            except json.JSONDecodeError:
                await streamer.add("text", line)

        # Read stderr
        assert proc.stderr is not None
        stderr_output = await proc.stderr.read()
        if stderr_output:
            stderr_text = stderr_output.decode("utf-8", errors="replace").strip()
            if stderr_text:
                await streamer.add("error", stderr_text[:2000])

        # Wait for process
        await proc.wait()
        watchdog_task.cancel()

        if timed_out:
            exit_code = 124
        else:
            exit_code = proc.returncode or 0

        # Determine status
        status = "completed" if exit_code == 0 else "failed"
        error_msg = None
        if timed_out:
            error_msg = f"Timed out after {config.max_duration_seconds}s"
        elif exit_code != 0:
            error_msg = f"Process exited with code {exit_code}"

        await streamer.close()
        await post_status(
            config.callback_url, config.agent_run_id, config.internal_api_secret,
            status=status, exit_code=exit_code,
            token_usage=token_usage, cost=cost_data,
            error_message=error_msg,
        )

        sys.exit(0 if status == "completed" else 1)

    except Exception as e:
        logger.exception("Unhandled exception in agent harness")
        await streamer.close()
        try:
            await post_status(
                config.callback_url, config.agent_run_id, config.internal_api_secret,
                status="failed", exit_code=1, error_message=str(e),
            )
        except Exception:
            logger.exception("Failed to report failure to control plane")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
