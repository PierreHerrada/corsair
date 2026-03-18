# Corsair Refactor — Complete Build Session Plan

This document is designed to be executed sequentially in a single coding session. Every file creation, modification, and deletion is listed with exact paths, exact code, and the reasoning for each change. Nothing is left implicit.

---

## CURRENT CODEBASE UNDERSTANDING

### File tree (relevant parts)

```
corsair/
├── .claude/
├── .github/workflows/
├── backend/
│   └── app/
│       ├── __init__.py
│       ├── main.py            # App factory, startup/shutdown, router registration
│       ├── config.py           # Pydantic Settings from env vars
│       ├── db.py               # Tortoise ORM init + Aerich migration config
│       ├── models/
│       │   ├── __init__.py     # Re-exports all models
│       │   ├── task.py         # Task model (status, title, description, repo_url, branch, etc.)
│       │   ├── agent_run.py    # AgentRun model (task FK, stage, status, token_usage, cost_data)
│       │   ├── agent_log.py    # AgentLog model (run FK, type, content JSON, created_at)
│       │   └── conversation.py # Conversation model (Slack thread messages)
│       ├── api/
│       │   └── v1/
│       │       ├── __init__.py
│       │       ├── tasks.py    # REST endpoints for tasks + stage execution trigger
│       │       ├── dashboard.py
│       │       ├── auth.py
│       │       └── ws.py       # WebSocket handler at /ws/runs/{run_id}
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── runner.py       # Spawns Claude Code CLI as subprocess, reads stdout
│       │   ├── prompts.py      # Prompt templates per stage
│       │   └── cost.py         # Parses token usage / cost from Claude output
│       ├── integrations/
│       │   ├── __init__.py
│       │   ├── base.py         # BaseIntegration ABC
│       │   ├── registry.py     # Discovers and validates integrations at startup
│       │   ├── slack/
│       │   │   ├── __init__.py
│       │   │   ├── client.py   # Slack bot (Socket Mode), app_mention handler
│       │   │   └── tests/
│       │   ├── jira/
│       │   │   ├── __init__.py
│       │   │   ├── client.py
│       │   │   └── tests/
│       │   ├── github/
│       │   │   ├── __init__.py
│       │   │   ├── client.py   # GitHub PR creation
│       │   │   └── tests/
│       │   └── datadog/
│       │       ├── __init__.py
│       │       ├── client.py
│       │       └── tests/
│       └── websocket/
│           ├── __init__.py
│           └── manager.py      # WebSocket connection manager, broadcast method
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Board.tsx       # Kanban board
│       │   ├── Dashboard.tsx   # Stats and cost charts
│       │   └── Login.tsx
│       ├── components/
│       │   ├── TaskCard.tsx
│       │   ├── TaskBoard.tsx
│       │   ├── AgentLogViewer.tsx
│       │   ├── CostWidget.tsx
│       │   ├── PRBadge.tsx
│       │   └── StageControls.tsx  # [Run Plan] [Run Work] [Run Review] buttons
│       ├── api/
│       │   └── client.ts       # Typed fetch wrappers
│       └── hooks/
│           ├── useTasks.ts
│           ├── useDashboard.ts
│           └── useWebSocket.ts
├── infra/
│   ├── nginx.conf
│   ├── supervisord.conf
│   ├── entrypoint.sh
│   └── ecs-task-definition.json  # Current Fargate task def (single container)
├── scripts/
├── Dockerfile                    # Multi-stage: frontend build → python deps → final with nginx+supervisord+node+claude-code+jdk
├── docker-compose.local.yml      # Single service, build from Dockerfile
├── .env.example
└── ARCHITECTURE.md
```

### How agent execution works today

1. User clicks [Run Plan] in the UI → `POST /api/v1/tasks/{id}/plan`
2. `backend/app/api/v1/tasks.py` creates an `AgentRun(task_id=..., stage="plan", status="running")`
3. Calls `backend/app/agent/runner.py` which does:
   ```python
   process = subprocess.Popen(
       ["claude", "--print", "--output-format", "stream-json", "--dangerously-skip-permissions", "-p", prompt],
       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
       cwd=workspace, env=env,
   )
   ```
4. Reads `process.stdout` line by line, creates `AgentLog` records
5. Broadcasts each log via `ws_manager.broadcast(run_id, log_data)`
6. On completion, parses cost/tokens, updates `AgentRun`
7. For review stage, calls GitHub integration to create PR

### Key facts

- **ORM**: Tortoise ORM with Aerich migrations
- **Async**: Fully async FastAPI
- **WebSocket**: Custom manager in `websocket/manager.py`, endpoint at `/ws/runs/{run_id}`
- **Auth**: Simple admin password auth in `api/v1/auth.py`
- **Current Dockerfile** installs: nginx, supervisord, Node.js 20, `@anthropic-ai/claude-code` (npm global), git, JDK, Python 3.12
- **Current ECS**: Single Fargate task, single container, ALB in front
- **Database**: PostgreSQL on RDS, tables: tasks, agent_runs, agent_logs, conversations

---

## STEP-BY-STEP BUILD PLAN

### STEP 1: Create `agent/` directory — the standalone agent container

This is a brand new top-level directory. The agent container is completely self-contained — no dependency on the backend code.

#### STEP 1.1: Create `agent/requirements.txt`

```
httpx>=0.27,<1.0
pydantic>=2.0,<3.0
pydantic-settings>=2.0,<3.0
```

Why these: `httpx` for async HTTP callbacks to the control plane. `pydantic-settings` for typed env var loading. Nothing else — keep it minimal.

#### STEP 1.2: Create `agent/config.py`

Full file. Uses `pydantic-settings` to load all env vars the agent container needs. Every field maps to an env var. Defaults are provided where sensible.

Fields:
- `task_id: str` — the Corsair task UUID
- `agent_run_id: str` — the agent run UUID
- `stage: str` — "plan", "work", or "review"
- `repo_url: str` — git URL to clone
- `branch: str = "main"` — branch to checkout
- `callback_url: str` — the control plane internal URL (e.g., `http://control-plane.corsair.local:8000`)
- `internal_api_secret: str` — shared secret for auth on callback endpoints
- `anthropic_api_key: str` — always present, needed by Claude Code
- `max_duration_seconds: int = 3600` — timeout
- `github_token: str = ""` — for cloning private repos and for PR creation
- `work_dir: str = "/home/corsair/workspaces"` — where to clone
- `prompt_override: str = ""` — if set, use this instead of the default stage prompt
- `docker_host: str = ""` — set to `tcp://localhost:2375` when DinD sidecar is present
- `task_description: str = ""` — the task title/description to pass to the prompt
- `plan_output: str = ""` — output from the plan stage, passed to work/review stages

#### STEP 1.3: Create `agent/log_streamer.py`

Two components:

**`LogStreamer` class:**
- Constructor takes `callback_url`, `run_id`, `secret`
- Builds the URL: `{callback_url}/api/v1/internal/runs/{run_id}/logs`
- Headers: `X-Internal-Secret: {secret}`, `Content-Type: application/json`
- Internal buffer: `list[dict]`, each dict has `type`, `content`, `timestamp`
- `max_batch = 10`, `max_wait_ms = 500`
- `async add(line_type: str, content: str)` — appends to buffer, flushes if buffer >= max_batch or time since last flush >= max_wait_ms
- `async flush()` — POSTs the batch as `{"lines": [...]}`, retries 3x with exponential backoff, falls back to `print()` (CloudWatch captures stdout)
- `async close()` — flushes remaining buffer, closes httpx client

**`post_status()` async function:**
- POSTs to `{callback_url}/api/v1/internal/runs/{run_id}/complete`
- Body: `{"status": ..., "exit_code": ..., "token_usage": ..., "cost": ..., "error_message": ...}`
- All fields optional except `status`
- Retries 3x

#### STEP 1.4: Create `agent/prompt_loader.py`

Simple dict of prompt templates keyed by stage name ("plan", "work", "review"). Each template has `{task_description}` and `{plan_output}` placeholders.

`get_prompt(stage, task_description, plan_output="") -> str` function that formats the template.

The prompts should match whatever the current `backend/app/agent/prompts.py` uses, just reformatted as a standalone module. If you don't have access to the exact prompts, use reasonable defaults (already provided in the previous plan artifact).

#### STEP 1.5: Create `agent/harness.py`

This is the entrypoint (`ENTRYPOINT ["python", "harness.py"]`). Full lifecycle:

```
1. Load config (AgentConfig from env vars)
2. Create LogStreamer instance
3. POST status "running" to control plane
4. Log "Starting {stage} stage for task {task_id}"
5. Clone repo:
   - Build clone URL (inject github_token if present)
   - git clone --branch {branch} --depth 1 {url} {work_dir}/{task_id}
   - If fails: log error, POST status "failed", exit 1
6. Set up environment:
   - Copy os.environ
   - If docker_host is set, add DOCKER_HOST to env
7. Build Claude Code command:
   - ["claude", "--print", "--output-format", "stream-json",
      "--dangerously-skip-permissions", "--max-turns", "50", "-p", prompt]
8. Spawn subprocess (asyncio.create_subprocess_exec)
9. Start watchdog timer (max_duration_seconds)
10. Read stdout line by line:
    - Try JSON parse (stream-json format)
    - If "result" type: extract token_usage and cost_data
    - Otherwise: send to LogStreamer
11. Read stderr (after stdout done)
12. Wait for process exit
13. Cancel watchdog
14. If timed out: set exit_code = 124
15. Determine status: "completed" if exit_code == 0, else "failed"
16. POST complete with exit_code, token_usage, cost
17. Close LogStreamer
18. sys.exit(0 if success else 1)
```

All wrapped in try/except — on any unhandled exception, POST "failed" status and exit 1.

#### STEP 1.6: Create `agent/Dockerfile`

Multi-stage is unnecessary here — it's a single stage:

```
FROM python:3.12-slim

# System deps: Node.js 20 (for Claude Code CLI), git, JDK, Docker CLI, openssh
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl git default-jdk-headless openssh-client && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g @anthropic-ai/claude-code && \
    rm -rf /var/lib/apt/lists/*

# Docker CLI (for Testcontainers via DinD sidecar)
RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-25.0.3.tgz | \
    tar xz --strip-components=1 -C /usr/local/bin docker/docker

ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV PATH="${JAVA_HOME}/bin:${PATH}"

WORKDIR /app

# Non-root user (Claude Code refuses to run as root)
RUN useradd -m -s /bin/bash corsair && \
    mkdir -p /home/corsair/workspaces && \
    chown -R corsair:corsair /home/corsair

# Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Harness code
COPY config.py log_streamer.py prompt_loader.py harness.py ./

USER corsair
ENTRYPOINT ["python", "harness.py"]
```

Note: Docker CLI is included even in the base image — it's small (~50MB) and harmless when no Docker daemon is present. When a DinD sidecar is attached, the CLI just works.

#### STEP 1.7: Create `agent/tests/test_harness.py`

Tests:
- `test_config_loads_from_env(monkeypatch)` — set all required env vars, instantiate `AgentConfig`, assert values
- `test_config_defaults(monkeypatch)` — set only required vars, check defaults (max_duration=3600, branch="main", etc.)
- `test_log_streamer_batching()` — mock httpx client, add 5 lines (should NOT flush), add 5 more (SHOULD flush at 10), verify post was called once
- `test_log_streamer_flush_on_close()` — add 3 lines, close(), verify post was called
- `test_log_streamer_retry_on_failure()` — mock httpx to fail twice then succeed, verify 3 attempts
- `test_log_streamer_fallback_to_stdout(capsys)` — mock httpx to always fail, verify lines printed to stdout
- `test_post_status_success()` — mock httpx, call post_status, verify URL and body
- `test_post_status_retry()` — mock httpx to fail once, verify retry
- `test_get_prompt_plan()` — verify prompt contains task_description
- `test_get_prompt_work()` — verify prompt contains both task_description and plan_output
- `test_get_prompt_unknown_stage()` — verify falls back to work prompt

#### STEP 1.8: Create `agent/tests/__init__.py`

Empty file.

---

### STEP 2: Modify the control plane Dockerfile

Changes to the root `Dockerfile`:

**Remove:**
- Node.js installation (`curl -fsSL https://deb.nodesource.com/setup_20.x | bash -`, `apt-get install nodejs`)
- `npm install -g @anthropic-ai/claude-code`
- `default-jdk-headless` from apt-get
- `JAVA_HOME` and `PATH` env vars
- `useradd -m -s /bin/bash corsair`
- `mkdir -p /home/corsair/workspaces` and related `chown`
- `curl` and `git` from apt-get (control plane doesn't clone repos anymore)

**Keep:**
- Multi-stage build for frontend (node:20-alpine) and python deps
- Final stage: `python:3.12-slim` with `nginx`, `supervisor`
- Copy backend code, frontend dist, nginx.conf, supervisord.conf, entrypoint.sh
- Expose 80 8000

**Result:** Control plane image goes from ~1.5GB to ~300MB.

---

### STEP 3: Add `boto3` to backend requirements

**Modify:** `backend/requirements.txt`

Add `boto3>=1.34,<2.0` (for ECS API calls).

Also add `docker>=7.0,<8.0` (for local development — spawning agent containers via Docker SDK when `USE_LOCAL_AGENT=true`).

---

### STEP 4: Extend `backend/app/config.py`

**Add these fields** to the existing `Settings` class:

```python
# ECS Agent Orchestration
ecs_cluster_arn: str = ""
internal_api_secret: str = ""
internal_callback_url: str = "http://control-plane.corsair.local:8000"
default_agent_task_definition: str = ""
aws_region: str = "eu-west-1"

# Agent monitor background task
agent_monitor_interval_seconds: int = 30

# Local development
use_local_agent: bool = False
local_agent_image: str = "corsair-agent:local"
```

The `use_local_agent` flag controls whether we call ECS RunTask or `docker.containers.run()` locally.

---

### STEP 5: Create the `AgentType` model

**Create:** `backend/app/models/agent_type.py`

Fields (all exact Tortoise ORM field types):
- `id: UUIDField(pk=True)`
- `name: CharField(max_length=100, unique=True)` — machine name like "db-agent"
- `display_name: CharField(max_length=200)` — human name like "Database Agent"
- `description: TextField(null=True)`
- `docker_image: CharField(max_length=500, default="")` — ECR URL, informational
- `ecs_task_definition: CharField(max_length=500)` — ECS task definition ARN
- `task_role_arn: CharField(max_length=500, default="")` — IAM task role ARN for the agent
- `secrets_config: JSONField(default=dict)` — map of env var name → Secrets Manager ARN
- `capabilities: JSONField(default=list)` — list of strings like ["github", "database", "dind"]
- `cpu: IntField(default=1024)` — ECS CPU units
- `memory: IntField(default=2048)` — MB
- `max_duration_seconds: IntField(default=3600)`
- `security_group_ids: JSONField(default=list)` — list of SG IDs
- `subnet_ids: JSONField(default=list)` — list of subnet IDs
- `enable_dind: BooleanField(default=False)` — whether DinD sidecar is attached
- `is_default: BooleanField(default=False)` — exactly one should be True
- `created_at: DatetimeField(auto_now_add=True)`
- `updated_at: DatetimeField(auto_now=True)`
- `class Meta: table = "agent_types"`

---

### STEP 6: Modify existing models

#### STEP 6.1: Modify `backend/app/models/task.py`

Add field:
```python
agent_type = fields.ForeignKeyField(
    "models.AgentType", related_name="tasks", null=True, on_delete=fields.SET_NULL
)
```

This means tasks can optionally be associated with an agent type. If null, the default agent type is used at runtime.

#### STEP 6.2: Modify `backend/app/models/agent_run.py`

Add fields:
```python
ecs_task_arn = fields.CharField(max_length=500, null=True)
error_message = fields.TextField(null=True)
```

If `ecs_task_arn` is null and status is "running", it means the run hasn't been launched yet (or is running locally in dev).

Ensure the `status` field (likely a `CharField` with choices) supports these values: `launching`, `running`, `completed`, `failed`, `cancelled`.

#### STEP 6.3: Modify `backend/app/models/__init__.py`

Add import and re-export of `AgentType`:
```python
from app.models.agent_type import AgentType
```

Also add `"models.AgentType"` to the Tortoise ORM `models` list in `db.py` if it uses explicit model paths.

---

### STEP 7: Create Aerich migration

**Create:** `backend/migrations/models/XX_add_agent_types.sql` (or let Aerich generate it)

SQL:
```sql
CREATE TABLE IF NOT EXISTS agent_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    docker_image VARCHAR(500) DEFAULT '',
    ecs_task_definition VARCHAR(500) NOT NULL,
    task_role_arn VARCHAR(500) DEFAULT '',
    secrets_config JSONB DEFAULT '{}',
    capabilities JSONB DEFAULT '[]',
    cpu INTEGER DEFAULT 1024,
    memory INTEGER DEFAULT 2048,
    max_duration_seconds INTEGER DEFAULT 3600,
    security_group_ids JSONB DEFAULT '[]',
    subnet_ids JSONB DEFAULT '[]',
    enable_dind BOOLEAN DEFAULT FALSE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS agent_type_id UUID REFERENCES agent_types(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_agent_type_id ON tasks(agent_type_id);

ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS ecs_task_arn VARCHAR(500);
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS error_message TEXT;
```

In practice, run `aerich migrate --name add_agent_types` and `aerich upgrade` to generate this, but the manual SQL is here as a reference.

---

### STEP 8: Create the Agent Orchestrator

**Create:** `backend/app/agent/orchestrator.py`

This is the core of the refactor — it replaces the subprocess-based runner with ECS RunTask calls.

**Class: `AgentOrchestrator`**

Constructor: takes `Settings` instance, creates `boto3.client("ecs")`.

**Method: `async launch(task, run, stage, agent_type) -> str`**

1. Build `env_overrides` list of `{"name": ..., "value": ...}` dicts:
   - `TASK_ID` = `str(task.id)`
   - `AGENT_RUN_ID` = `str(run.id)`
   - `STAGE` = stage
   - `REPO_URL` = `task.repo_url`
   - `BRANCH` = `task.branch or "main"`
   - `CALLBACK_URL` = `self.callback_url`
   - `MAX_DURATION_SECONDS` = `str(agent_type.max_duration_seconds)`
   - `TASK_DESCRIPTION` = `task.title or task.description or ""`
   - If stage is "work" or "review" and there's a prior plan run with output, include `PLAN_OUTPUT`
   - If `agent_type.enable_dind`: add `DOCKER_HOST` = `tcp://localhost:2375`

2. Build `overrides` dict:
   - `containerOverrides`: list with one entry for `"agent"` container with the env
   - If `agent_type.task_role_arn`: set `taskRoleArn`

3. Call `self.ecs.run_task()`:
   - `cluster` = `self.cluster`
   - `taskDefinition` = `agent_type.ecs_task_definition`
   - `capacityProviderStrategy`: FARGATE_SPOT weight=3, FARGATE weight=1 base=1
   - `overrides` = the overrides dict
   - `networkConfiguration.awsvpcConfiguration`:
     - `subnets` = `agent_type.subnet_ids`
     - `securityGroups` = `agent_type.security_group_ids`
     - `assignPublicIp` = `"DISABLED"`
   - `tags`: corsair:task-id, corsair:run-id, corsair:agent-type

4. Check response: if `tasks` is empty, raise with failure details.
5. Return `response["tasks"][0]["taskArn"]`

**Method: `async status(task_arn) -> dict`**

Calls `ecs.describe_tasks()`, returns the task dict (with `lastStatus`, `stoppedReason`, `containers`, etc.). Returns `{"lastStatus": "UNKNOWN"}` if task not found.

**Method: `async stop(task_arn, reason="Cancelled by user")`**

Calls `ecs.stop_task()`.

**Method: `async get_plan_output(task_id) -> str`**

Queries `AgentRun` for the most recent completed "plan" stage run for this task, then queries `AgentLog` for that run's "result" type entries, concatenates them. Returns empty string if no plan exists. This is used to pass plan output to the work/review stages.

---

### STEP 9: Create the Local Agent Runner (for development)

**Create:** `backend/app/agent/local_runner.py`

Uses the `docker` Python SDK to spawn a local Docker container instead of calling ECS. Same interface as `AgentOrchestrator` (launch, status, stop).

- `launch()`: calls `self.docker.containers.run(image, detach=True, environment=env, remove=True, name=f"corsair-agent-{run_id}")`
- `callback_url` is `http://host.docker.internal:8000` (Docker's magic DNS for the host)
- Returns `f"local:{container.id}"` as the "task ARN"
- `status()`: calls `docker.containers.get(id).status`
- `stop()`: calls `container.stop(timeout=10)`

---

### STEP 10: Create the Internal API (agent callback endpoints)

**Create:** `backend/app/api/v1/internal.py`

New FastAPI router with prefix `/api/v1/internal`.

**Authentication:** All endpoints check `X-Internal-Secret` header against `settings.internal_api_secret`. Return 403 if mismatch.

**Endpoint: `POST /api/v1/internal/runs/{run_id}/logs`**

Request body (Pydantic model `LogBatch`):
```python
class LogLine(BaseModel):
    type: str        # text | tool_use | tool_result | error | system | result
    content: str
    timestamp: float

class LogBatch(BaseModel):
    lines: list[LogLine]
```

Handler:
1. Get `AgentRun` by run_id, 404 if not found
2. If run status is "launching", update to "running"
3. For each line in `batch.lines`:
   a. Create `AgentLog(run_id=run.id, type=line.type, content={"text": line.content})`
   b. Call `await ws_manager.broadcast(str(run.id), {...})` with the log data as JSON matching the existing WebSocket protocol:
      ```json
      {
        "id": "<log_uuid>",
        "run_id": "<run_uuid>",
        "type": "text",
        "content": {"text": "..."},
        "created_at": "ISO 8601"
      }
      ```
4. Return `{"received": len(batch.lines)}`

This is critical: the WebSocket protocol to the frontend is **unchanged**. The frontend still connects to `/ws/runs/{run_id}` and receives the same JSON objects. The only difference is that logs now arrive via HTTP POST from the agent container instead of being read from a local subprocess.

**Endpoint: `POST /api/v1/internal/runs/{run_id}/complete`**

Request body (Pydantic model `RunCompletion`):
```python
class RunCompletion(BaseModel):
    status: str                          # completed | failed
    exit_code: Optional[int] = None
    token_usage: Optional[dict] = None   # {input_tokens: N, output_tokens: N}
    cost: Optional[dict] = None          # {total_cost: N, ...}
    error_message: Optional[str] = None
```

Handler:
1. Get `AgentRun`, 404 if not found
2. Update fields: status, exit_code, token_usage, cost_data, error_message
3. Save
4. Broadcast completion event via WebSocket:
   ```json
   {"type": "run_complete", "run_id": "...", "status": "completed", "exit_code": 0}
   ```
5. If status is "completed", call `handle_stage_completion(run)` (triggers PR creation for review stage, updates task status)
6. Return `{"ok": True}`

---

### STEP 11: Create post-stage handler

**Create:** `backend/app/agent/post_stage.py`

This extracts the post-completion logic that currently lives inside `runner.py` (after the subprocess finishes). It's called by the internal API's complete endpoint.

`async def handle_stage_completion(run: AgentRun)`:
1. `await run.fetch_related("task")`
2. If `run.stage == "plan"` and `run.status == "completed"`: set `task.status = "planned"`, save
3. If `run.stage == "work"` and `run.status == "completed"`: set `task.status = "in_review"`, save
4. If `run.stage == "review"` and `run.status == "completed"`:
   - Import and use the GitHub integration to create a PR (same logic as current runner.py)
   - Set `task.status = "done"`, save
5. For any failed stage: don't change task status (leave it where it is)

---

### STEP 12: Create the Task Monitor background job

**Create:** `backend/app/agent/task_monitor.py`

**Class: `AgentTaskMonitor`**

- Constructor: takes orchestrator instance and interval (default 30s)
- `async start()`: loops forever, calling `_check_runs()` every `interval` seconds
- `async stop()`: sets flag to break loop
- `async _check_runs()`:
  1. Query `AgentRun.filter(status__in=["launching", "running"], ecs_task_arn__not_isnull=True)`
  2. For each run:
     a. Call `orchestrator.status(run.ecs_task_arn)`
     b. If ECS task status is `STOPPED` but run status is still "running"/"launching":
        - This means the callback never arrived (container crashed, OOM, network issue)
        - Set `run.status = "failed"`, `run.error_message = f"Container stopped: {stop_reason}"`
        - Save
     c. If ECS task is `UNKNOWN`:
        - Set `run.status = "failed"`, `run.error_message = "ECS task not found"`
  3. Also check for timeout: if `run.created_at + max_duration_seconds < now()` and run is still active:
     - Call `orchestrator.stop(run.ecs_task_arn)`
     - Set `run.status = "failed"`, `run.error_message = "Timed out"`

---

### STEP 13: Create Agent Types CRUD API

**Create:** `backend/app/api/v1/agent_types.py`

Router prefix: `/api/v1/agent-types`

Pydantic models:
- `AgentTypeCreate` — all fields for creation
- `AgentTypeUpdate` — all fields optional (partial update)
- `AgentTypeResponse` — serialization model for responses

Endpoints:
- `GET /` → list all agent types, ordered by name
- `POST /` → create. If `is_default=True`, unset default on all others first. Return 201.
- `GET /{id}` → get by UUID
- `PUT /{id}` → partial update. If setting `is_default=True`, unset others.
- `DELETE /{id}` → delete. Reject if `is_default=True` (can't delete the default).
- `POST /{id}/test` → launch a quick ECS task with a no-op command to verify the config works. Return status.

---

### STEP 14: Modify the task execution endpoint

**Modify:** `backend/app/api/v1/tasks.py`

**Replace** the existing stage execution handler (the one that creates a subprocess).

Old flow (conceptual):
```python
@router.post("/{task_id}/{stage}")
async def run_stage(task_id, stage):
    run = await AgentRun.create(...)
    asyncio.create_task(run_claude_subprocess(run))  # ← this disappears
    return {"run_id": run.id}
```

New flow:
```python
@router.post("/{task_id}/{stage}")
async def run_stage(task_id, stage):
    task = await Task.get(id=task_id).prefetch_related("agent_type")
    agent_type = task.agent_type or await AgentType.filter(is_default=True).first()
    if not agent_type:
        raise HTTPException(500, "No default agent type configured")

    run = await AgentRun.create(task_id=task.id, stage=stage, status="launching")

    # Get the orchestrator from app state
    orchestrator = request.app.state.orchestrator

    try:
        task_arn = await orchestrator.launch(task, run, stage, agent_type)
        run.ecs_task_arn = task_arn
        await run.save()
    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        await run.save()
        raise HTTPException(500, f"Failed to launch agent: {e}")

    return {"run_id": str(run.id), "ecs_task_arn": task_arn, "status": "launching"}
```

**Add new endpoint** for cancellation:
```python
@router.post("/{task_id}/cancel")
async def cancel_run(task_id):
    run = await AgentRun.filter(
        task_id=task_id, status__in=["launching", "running"]
    ).order_by("-created_at").first()
    if not run or not run.ecs_task_arn:
        raise HTTPException(404, "No active run found")
    await request.app.state.orchestrator.stop(run.ecs_task_arn)
    run.status = "cancelled"
    await run.save()
    return {"status": "cancelled"}
```

**Also add** `agent_type_id` to the task creation endpoint (wherever that is — likely in the same file or the Slack bot integration). Accept it as an optional field.

---

### STEP 15: Delete the old subprocess agent runner

**Modify:** `backend/app/agent/runner.py`

Delete the entire subprocess-based implementation. This file can either be deleted entirely or gutted to just re-export the orchestrator for backwards compatibility. The `prompts.py` and `cost.py` files in the agent module can stay if other parts reference them, but the subprocess spawning logic is gone.

If the existing `runner.py` is imported elsewhere (e.g., in `tasks.py`), update those imports to use the orchestrator instead.

---

### STEP 16: Modify `backend/app/main.py`

**Add router registrations:**
```python
from app.api.v1 import internal, agent_types

app.include_router(internal.router)
app.include_router(agent_types.router)
```

**Add startup logic:**
```python
from app.agent.orchestrator import AgentOrchestrator
from app.agent.local_runner import LocalAgentRunner
from app.agent.task_monitor import AgentTaskMonitor

@app.on_event("startup")
async def startup():
    # ... existing DB init, integration registry, etc.

    settings = get_settings()

    # Create orchestrator
    if settings.use_local_agent:
        orchestrator = LocalAgentRunner(settings)
    else:
        orchestrator = AgentOrchestrator(settings)
    app.state.orchestrator = orchestrator

    # Start background task monitor
    monitor = AgentTaskMonitor(orchestrator, settings.agent_monitor_interval_seconds)
    app.state.monitor = monitor
    asyncio.create_task(monitor.start())

@app.on_event("shutdown")
async def shutdown():
    # ... existing shutdown
    if hasattr(app.state, "monitor"):
        await app.state.monitor.stop()
```

---

### STEP 17: Modify Slack bot to parse agent type

**Modify:** `backend/app/integrations/slack/client.py`

In the `app_mention` handler, after extracting the task description from the message:

1. Check for `[agent-type-name]` pattern using regex: `r'\[([a-z0-9-]+)\]'`
2. If found, look up `AgentType.filter(name=match).first()`
3. Strip the `[...]` tag from the message text
4. Pass the `agent_type_id` when creating the Task record

Example: `@Corsair [db-agent] Fix the migration that's breaking prod`
→ agent_type = the AgentType with name "db-agent"
→ task description = "Fix the migration that's breaking prod"

If the tag is not found or doesn't match any agent type, use `None` (falls back to default at execution time).

---

### STEP 18: Update `.env.example`

**Add these variables:**

```env
# --- ECS Agent Orchestration ---
ECS_CLUSTER_ARN=arn:aws:ecs:eu-west-1:ACCOUNT:cluster/corsair
INTERNAL_API_SECRET=generate-a-strong-random-secret-here
INTERNAL_CALLBACK_URL=http://control-plane.corsair.local:8000
DEFAULT_AGENT_TASK_DEFINITION=arn:aws:ecs:eu-west-1:ACCOUNT:task-definition/corsair-agent-default
AWS_REGION=eu-west-1

# --- Local Development ---
USE_LOCAL_AGENT=false
LOCAL_AGENT_IMAGE=corsair-agent:local
```

---

### STEP 19: Update `docker-compose.local.yml`

Replace the single-service file with:

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: corsair
      POSTGRES_USER: corsair
      POSTGRES_PASSWORD: corsair
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U corsair"]
      interval: 5s
      timeout: 3s
      retries: 5

  control-plane:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "${PORT_FRONTEND:-80}:80"
      - "${PORT_BACKEND:-8000}:8000"
    env_file: .env
    environment:
      DATABASE_URL: postgres://corsair:corsair@postgres:5432/corsair
      USE_LOCAL_AGENT: "true"
      LOCAL_AGENT_IMAGE: corsair-agent:local
      INTERNAL_API_SECRET: local-dev-secret
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
      - /var/run/docker.sock:/var/run/docker.sock

volumes:
  pgdata:
```

The Docker socket mount allows the control plane to spawn local agent containers via the Docker SDK.

To build the agent image locally: `docker build -t corsair-agent:local -f agent/Dockerfile agent/`

---

### STEP 20: Terraform infrastructure

**Create directory:** `infra/terraform/`

**Delete:** `infra/ecs-task-definition.json` (replaced by Terraform)

Files to create (see previous artifact for full code — all of it is still valid and should be used verbatim):

1. **`main.tf`** — provider config, S3 backend for state
2. **`variables.tf`** — region, project name, VPC CIDR, instance sizes
3. **`networking.tf`** — VPC, 2 public subnets, 2 private subnets, IGW, NAT gateway, route tables, security groups (alb, control-plane, agent-base, agent-db, rds), Cloud Map service discovery
4. **`ecr.tf`** — two repos (corsair-control-plane, corsair-agent) with lifecycle policies
5. **`iam.tf`** — ECS execution role (shared), control plane task role (ecs:RunTask, iam:PassRole), per-agent-type task roles (default, db, aws, datadog)
6. **`secrets.tf`** — Secrets Manager entries for all credentials
7. **`ecs_cluster.tf`** — cluster with FARGATE + FARGATE_SPOT capacity providers, CloudWatch log groups
8. **`ecs_control_plane.tf`** — task definition (secrets from SM, env vars for ECS config), ECS service with ALB, service discovery registration
9. **`ecs_agent_task_defs.tf`** — one task definition per agent type:
   - `corsair-agent-default` — ANTHROPIC_API_KEY + GITHUB_TOKEN + INTERNAL_API_SECRET
   - `corsair-agent-db` — same + DATABASE_URL
   - `corsair-agent-db-dind` — same as db but with DinD sidecar container (docker:25-dind, privileged=true, health check, dependsOn HEALTHY), 2 vCPU / 4GB
   - `corsair-agent-aws` — default secrets + aws task role with scoped permissions
   - `corsair-agent-datadog` — default secrets + DD_API_KEY + DD_APP_KEY
10. **`alb.tf`** — ALB, target groups for port 80 and 8000, listener with path-based routing (/api/* and /ws/* → 8000, default → 80)
11. **`outputs.tf`** — ALB DNS, ECR URLs, cluster ARN, task definition ARNs

All Terraform code is in the previous artifact. Copy it verbatim.

---

### STEP 21: Create the seed data script

**Create:** `scripts/seed_agent_types.py`

Async script that connects to the database and inserts the default agent types (default, db-agent, db-agent-dind, aws-agent, datadog-agent). Skips if they already exist. Uses the Terraform output values for ARNs (passed as env vars or hardcoded after apply).

See the `SEED_TYPES` list in the previous artifact — use it verbatim, but replace `ACCOUNT` placeholders with actual values from Terraform outputs.

---

### STEP 22: Frontend changes

#### STEP 22.1: Create `frontend/src/api/agentTypes.ts`

Typed API client with methods: `list()`, `get(id)`, `create(data)`, `update(id, data)`, `delete(id)`, `test(id)`. Uses the existing `apiClient` from `frontend/src/api/client.ts`.

TypeScript interfaces: `AgentType`, `AgentTypeCreate`.

#### STEP 22.2: Create `frontend/src/components/AgentTypeBadge.tsx`

Small component that renders the agent type name + colored capability badges. Color map: github=gray, database=blue, aws=orange, datadog=purple, dind=green.

#### STEP 22.3: Create `frontend/src/components/AgentTypeSelector.tsx`

Dropdown component. Fetches agent types on mount. Shows display_name + "(+ Docker)" suffix if enable_dind. Passes `agent_type_id` to parent via `onChange`.

#### STEP 22.4: Create `frontend/src/components/ContainerStatus.tsx`

Shows the current run status (launching → running → completed/failed/cancelled) with a colored label, the truncated ECS task ARN, and a Cancel button for active runs. Polls `GET /api/v1/runs/{run_id}` every 3s while active.

#### STEP 22.5: Modify `frontend/src/components/StageControls.tsx`

Add the `AgentTypeSelector` next to the [Run Plan] / [Run Work] / [Run Review] buttons. Pass the selected `agent_type_id` in the POST body when triggering a stage.

#### STEP 22.6: Modify `frontend/src/components/TaskCard.tsx`

Show the `AgentTypeBadge` if the task has an associated agent type.

#### STEP 22.7: Modify `frontend/src/components/AgentLogViewer.tsx`

Add the `ContainerStatus` component above the log output. Pass `run_id` and `ecs_task_arn` (available in the run data from the API).

#### STEP 22.8: Create `frontend/src/pages/AgentTypes.tsx`

Full CRUD page: list view with table, create/edit modal with form fields, delete confirmation, test button. Route: `/settings/agent-types`.

#### STEP 22.9: Modify `frontend/src/pages/Dashboard.tsx`

Add a "Cost by Agent Type" chart section. Group cost data by agent type and render a bar or pie chart.

#### STEP 22.10: Add route

In the app's router config (likely `App.tsx` or a routes file), add route for `/settings/agent-types` → `AgentTypes` page.

---

### STEP 23: CI/CD pipeline

**Modify:** `.github/workflows/ci.yml`

Add:
- `test-agent` job: `pip install -r agent/requirements.txt && pip install pytest pytest-asyncio`, then `cd agent && pytest tests/`
- In `build-and-deploy`:
  - Build + push `corsair-control-plane` image from root Dockerfile
  - Build + push `corsair-agent` image from `agent/Dockerfile`
  - Deploy: `aws ecs update-service --force-new-deployment` for control plane
  - Agent images are picked up automatically since task defs reference `:latest`

---

### STEP 24: Deploy sequence

Since downtime is acceptable:

1. `terraform apply` — creates all AWS resources
2. Build and push both Docker images to ECR
3. Run database migration (`aerich upgrade`)
4. Run seed script (`python scripts/seed_agent_types.py`)
5. `aws ecs update-service --cluster corsair --service corsair-control-plane --force-new-deployment`
6. Verify: create a task, trigger plan stage, watch logs stream in UI
7. Test DinD: create a task with `db-agent-dind` type, verify Testcontainers work

---

## COMPLETE FILE MANIFEST

### New files (22 files)

```
agent/
├── __init__.py                           # empty
├── Dockerfile
├── requirements.txt
├── config.py
├── log_streamer.py
├── prompt_loader.py
├── harness.py
└── tests/
    ├── __init__.py                       # empty
    └── test_harness.py

backend/app/models/agent_type.py
backend/app/agent/orchestrator.py
backend/app/agent/local_runner.py
backend/app/agent/post_stage.py
backend/app/agent/task_monitor.py
backend/app/api/v1/internal.py
backend/app/api/v1/agent_types.py

scripts/seed_agent_types.py

frontend/src/api/agentTypes.ts
frontend/src/components/AgentTypeBadge.tsx
frontend/src/components/AgentTypeSelector.tsx
frontend/src/components/ContainerStatus.tsx
frontend/src/pages/AgentTypes.tsx

infra/terraform/main.tf
infra/terraform/variables.tf
infra/terraform/networking.tf
infra/terraform/ecr.tf
infra/terraform/iam.tf
infra/terraform/secrets.tf
infra/terraform/ecs_cluster.tf
infra/terraform/ecs_control_plane.tf
infra/terraform/ecs_agent_task_defs.tf
infra/terraform/alb.tf
infra/terraform/outputs.tf
```

### Modified files (15 files)

```
Dockerfile                                # Remove Node.js, Claude Code, JDK, corsair user
backend/requirements.txt                  # Add boto3, docker
backend/app/config.py                     # Add ECS/internal settings
backend/app/main.py                       # Register new routers, create orchestrator, start monitor
backend/app/models/__init__.py            # Export AgentType
backend/app/models/task.py                # Add agent_type FK
backend/app/models/agent_run.py           # Add ecs_task_arn, error_message fields
backend/app/db.py                         # Add AgentType to Tortoise models list
backend/app/api/v1/tasks.py               # Replace subprocess with orchestrator, add cancel endpoint
backend/app/integrations/slack/client.py  # Parse [agent-type] from mentions
.env.example                              # Add new env vars
docker-compose.local.yml                  # Split into postgres + control-plane, mount docker.sock
.github/workflows/ci.yml                  # Add agent test job, dual image build
frontend/src/components/StageControls.tsx  # Add AgentTypeSelector
frontend/src/components/TaskCard.tsx       # Show AgentTypeBadge
frontend/src/components/AgentLogViewer.tsx # Show ContainerStatus
frontend/src/pages/Dashboard.tsx          # Add per-type cost chart
frontend/src/App.tsx                      # Add /settings/agent-types route
```

### Deleted files (1 file)

```
infra/ecs-task-definition.json            # Replaced by Terraform
```

### Files to gut/rewrite (1 file)

```
backend/app/agent/runner.py               # Remove all subprocess logic
```
