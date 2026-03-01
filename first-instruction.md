# Clipper AI — Agent Prompt & Build Instructions

You are an expert software engineering agent. Your mission is to build **Corsair** from scratch — a production-ready, open-source platform that bridges Slack, Jira, GitHub, and Claude Code into a unified AI-powered software engineering workflow.

The product is named **Corsair**. A corsair is an autonomous sailing vessel that operates independently across open waters — a precise metaphor for an agent that takes a task from Slack and sails autonomously through plan → code → PR without constant supervision.

You will work autonomously, potentially for hours. To stay efficient and avoid consuming excessive tokens, you must follow this rule at all times:

> **Work in isolated, focused phases. Complete one phase fully before starting the next. Never work on multiple phases simultaneously.**

At the start of each phase, read only what you need for that phase. Do not load the entire codebase into context unnecessarily.

---

## Agent Setup — Read This First, Before Any Work

Before writing a single file, configure your working environment for maximum performance. These steps are not optional.

### 1. Claude Code Configuration

Create a `CLAUDE.md` file at the root of the repository. Claude Code reads this file automatically at startup. It must contain:

```markdown
# Agent-SWE — Claude Code Instructions

## Project Overview
Agent-SWE is a production-ready, open-source AI software engineering platform.
Single Docker image. FastAPI backend. React frontend. PostgreSQL on RDS.

## Build Phases
Always check LESSONS.md before starting any phase.
Always check docs/api-contract.md before touching any API code.
Always check docs/data-models.md before touching any model code.

## Commands

### Backend
cd backend
pytest tests/ --cov=app --cov-fail-under=80   # run all tests
ruff check app/ tests/                          # lint
ruff format app/ tests/                         # format
aerich migrate                                  # generate migration
aerich upgrade                                  # apply migration

### Frontend
cd frontend
npm test -- --coverage                          # run all tests
npm run lint                                    # ESLint
npm run format                                  # Prettier
npm run build                                   # production build

### Docker
docker-compose up --build                       # full local stack
docker-compose run backend pytest               # tests in container

## Critical Rules
- Never hardcode secrets or URLs
- Never call real external APIs in tests — always mock
- Coverage must be ≥ 80% before moving to the next phase
- Read LESSONS.md before starting any new task
- Update LESSONS.md immediately when you encounter and resolve any error
- Every new integration must have its own directory under backend/app/integrations/
- API shapes must exactly match docs/api-contract.md — do not improvise
```

### 2. Lessons File

Create `LESSONS.md` at the root of the repository immediately. This file is your persistent memory across sessions. Every time you encounter an error, a non-obvious solution, an unexpected behavior, or a better approach — you must record it here before moving on.

Initial structure:

```markdown
# LESSONS — Agent-SWE

This file is maintained by the agent. It records errors encountered, root causes,
and solutions found during the build of Agent-SWE.
Read this file at the start of every phase and every new session.

## Format

### [PHASE X — Short title]
**Error:** what went wrong  
**Root cause:** why it happened  
**Solution:** what fixed it  
**Applies to:** any other areas where this lesson is relevant  

---

## Lessons

(empty — will be filled during build)
```

**Rules for LESSONS.md:**
- Update it immediately when you resolve any error — not at the end of the phase
- Be specific: include file names, line numbers, exact error messages where useful
- If a lesson changes a previous approach, mark the old one as superseded
- This file is version-controlled — it is part of the open-source repo and helps future contributors

### 3. Context Loading Strategy

To avoid consuming excessive tokens, follow this discipline strictly:

| Situation | What to load |
|---|---|
| Starting a phase | Read only: this prompt's phase section + relevant doc file |
| Writing a model | Read only: `docs/data-models.md` |
| Writing an API endpoint | Read only: `docs/api-contract.md` |
| Writing a test | Read only: the module under test + `conftest.py` |
| Hitting an error | Read `LESSONS.md` first before investigating |
| Starting a new session | Read `LESSONS.md` + `CLAUDE.md` + current phase section only |

Never load the full codebase. Never re-read files you already have in context.

---

---

## Brand & Design System

### Name
**Corsair** — lowercase in UI, `corsair` as repo/CLI name, `@corsair` as Slack bot handle.

### Logo
The logo is a minimal SVG: one vertical mast and two triangular sails (one large pointing left, one smaller pointing right). No hull, no wake lines, no decorative elements. Pure geometry.

Save the following as `frontend/public/logo.svg` and `frontend/public/favicon.svg`:

```svg
<svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="sail1" x1="18" y1="12" x2="50" y2="68" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#5EC4F0"/>
      <stop offset="100%" stop-color="#1A6FB5" stop-opacity="0.7"/>
    </linearGradient>
    <linearGradient id="sail2" x1="72" y1="28" x2="50" y2="64" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#A8DCF2" stop-opacity="0.7"/>
      <stop offset="100%" stop-color="#2B9ED4" stop-opacity="0.3"/>
    </linearGradient>
  </defs>
  <line x1="50" y1="10" x2="50" y2="72" stroke="#5EC4F0" stroke-width="2" stroke-linecap="round"/>
  <path d="M50 12 L50 68 L18 58 Z" fill="url(#sail1)"/>
  <path d="M50 30 L50 64 L72 50 Z" fill="url(#sail2)"/>
</svg>
```

### Color Palette

Add the following to `frontend/tailwind.config.ts` under `theme.extend.colors`:

```ts
colors: {
  // Backgrounds — darkest to lightest
  deep:    '#020B18',   // page background
  abyss:   '#05152A',   // panels, modals, cards
  navy:    '#0A2444',   // elevated cards, topbar
  ocean:   '#0D3366',   // hover states
  horizon: '#0F4C8A',   // card borders
  // Brand blues
  wave:    '#1A6FB5',   // primary buttons, brand gradient start
  sky:     '#2B9ED4',   // links, interactive elements
  foam:    '#5EC4F0',   // labels, captions, accent text
  mist:    '#A8DCF2',   // secondary / muted text
  white:   '#EEF6FF',   // primary text
  // Semantic
  teal:    '#00D4B4',   // success, done, accent dot
  gold:    '#F0A500',   // warning, running, in-progress
  coral:   '#E8445A',   // error, failed
}
```

### Design Rules
- **Background:** always `deep` (#020B18) — never pure black
- **Cards:** `abyss` with a `1px` border at `foam/8` opacity
- **Primary button:** gradient from `wave` → `horizon`
- **Brand gradient:** `linear-gradient(135deg, #1A6FB5, #0F4C8A)`
- **Typography:** Inter for UI, JetBrains Mono for code/logs
- **Status colors:** `teal` = done, `gold` = running, `coral` = failed, `foam` = backlog
- **Dark mode only** — no light mode needed for this internal tool

---

You are in charge of everything:
- Creating the full repository structure
- Writing all application code (backend + frontend)
- Writing all tests
- Setting up CI/CD with GitHub Actions
- Preparing the repository for open source release
- Verifying your own work at every step before proceeding

---

## Product Overview

Agent-SWE is an internal developer tool that works as follows:

1. An engineer tags `@agent-swe` in Slack with a request
2. The bot analyzes the message with Claude → creates a Jira ticket → replies in thread
3. The ticket appears in a web UI board (Backlog column)
4. The engineer manually clicks **[Run Plan]** → Claude Code writes an implementation plan
5. The engineer manually clicks **[Run Work]** → Claude Code writes the code and commits
6. The engineer manually clicks **[Run Review]** → Claude Code reviews the code and opens a GitHub PR
7. The bot posts the PR link back to the original Slack thread
8. The UI shows live logs, costs, and PR links throughout

Every stage transition is **manually triggered** from the UI. No automatic progression.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Python 3.12 |
| Agent execution | Claude Code CLI (asyncio subprocess) |
| Slack bot | slack-bolt[async] — Socket Mode |
| ORM | Tortoise ORM + Aerich (migrations) |
| Database | PostgreSQL on AWS RDS (external) |
| Git platform | GitHub API (PyGithub) |
| Issue tracking | Jira REST API v3 |
| Frontend | React 18 + Vite + Tailwind CSS |
| Realtime | WebSocket (FastAPI native) |
| Container | Single Docker image (supervisord + uvicorn + nginx) |
| Deployment | AWS ECS Fargate + ECR |
| Secrets | AWS Secrets Manager |
| CI/CD | GitHub Actions |

---

## Architecture

### Single Docker Image

```
Docker Image: agent-swe
└── supervisord
    ├── uvicorn → FastAPI on :8000 (API + WebSocket + Slack bot background task)
    └── nginx   → React static build on :80
```

The Slack bot runs as an async background task inside FastAPI. Socket Mode opens an outbound WebSocket to Slack — no inbound port or public URL required. Works identically in local and production.

### AWS Infrastructure

```
ECR → agent-swe:latest

ECS Fargate
└── Cluster: agent-swe
    └── Service: agent-swe (single container)
        ├── :80   → ALB → React UI (users)
        └── :8000 → ALB → FastAPI (React API calls)

RDS PostgreSQL (external, connection via DATABASE_URL)
Secrets Manager (all env vars injected at runtime)
```

### Realtime Log Flow

```
Claude Code CLI subprocess
    ↓ stdout (line by line)
FastAPI async reader
    ↓
agent_logs table (PostgreSQL)
    ↓
WebSocket broadcast
    ↓
React UI — Live Log Viewer
```

---

## Open Source Foundation

Agent-SWE is designed to be extended by the community. The architecture must anticipate a wide range of integrations beyond the initial set (Jira, GitHub, Slack). Every structural decision must support this.

### Integration Plugin System

All integrations live under `backend/app/integrations/`. Each integration is a self-contained module with a standard interface:

```
backend/app/integrations/
├── base.py                  # Abstract base class all integrations implement
├── registry.py              # Integration registry — discover and load integrations
├── slack/
│   ├── __init__.py
│   ├── bot.py
│   └── tests/
├── jira/
│   ├── __init__.py
│   ├── client.py
│   └── tests/
├── github/
│   ├── __init__.py
│   ├── client.py
│   └── tests/
└── README.md                # How to build a new integration
```

`base.py` defines the contract every integration must fulfill:

```python
class BaseIntegration(ABC):
    name: str                        # e.g. "github", "linear", "gitlab"
    description: str
    required_env_vars: list[str]     # validated at startup

    @abstractmethod
    async def health_check(self) -> bool: ...
```

`registry.py` discovers all integrations, validates their env vars on startup, and logs which ones are active. This means contributors can add a new integration by creating a new directory — no changes to core code required.

### Extensibility Rules

- **No integration logic in core code.** `runner.py`, `api/`, and models must never import directly from an integration. Always go through the registry.
- **Feature flags via env vars.** If `GITHUB_TOKEN` is not set, the GitHub integration is simply inactive. The app still boots.
- **Versioned API.** All REST endpoints are prefixed `/api/v1/`. This ensures future breaking changes can be introduced under `/api/v2/` without disrupting existing integrations.
- **Webhook-ready.** Even if not used initially, the routing structure must support `POST /api/v1/webhooks/{integration_name}` for any integration to receive inbound events.

### Community Files

Beyond the standard open source files, create:

```
agent-swe/
├── INTEGRATIONS.md          # List of supported integrations + how to add one
├── ARCHITECTURE.md          # High-level system design for new contributors
├── SECURITY.md              # How to report vulnerabilities
├── CHANGELOG.md             # Keep a Changelog format (unreleased section ready)
└── .github/
    ├── CODEOWNERS           # Define ownership of critical paths
    └── workflows/
        └── stale.yml        # Auto-label stale issues and PRs
```

---

## Repository Structure

Create this structure exactly:

```
agent-swe/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml               # Run all tests + coverage on every push/PR
│   │   ├── deploy.yml           # Build + push ECR + update ECS on main merge
│   │   ├── badges.yml           # Update coverage badge on main
│   │   └── stale.yml            # Auto-label stale issues/PRs
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   ├── feature_request.md
│   │   └── new_integration.md   # Template for proposing a new integration
│   ├── CODEOWNERS
│   └── PULL_REQUEST_TEMPLATE.md
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── task.py
│   │   │   ├── agent_run.py
│   │   │   ├── agent_log.py
│   │   │   └── conversation.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── v1/              # All routes versioned under /api/v1/
│   │   │   │   ├── tasks.py
│   │   │   │   ├── agent.py
│   │   │   │   ├── dashboard.py
│   │   │   │   └── webhooks.py  # POST /webhooks/{integration_name}
│   │   ├── agent/
│   │   │   ├── __init__.py
│   │   │   ├── runner.py
│   │   │   ├── prompts.py
│   │   │   └── cost.py
│   │   ├── integrations/
│   │   │   ├── base.py          # Abstract base class
│   │   │   ├── registry.py      # Integration discovery + health checks
│   │   │   ├── README.md        # How to add a new integration
│   │   │   ├── slack/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── bot.py
│   │   │   │   └── tests/
│   │   │   ├── jira/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── client.py
│   │   │   │   └── tests/
│   │   │   └── github/
│   │   │       ├── __init__.py
│   │   │       ├── client.py
│   │   │       └── tests/
│   │   └── websocket/
│   │       ├── __init__.py
│   │       └── manager.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_models.py
│   │   ├── test_agent.py
│   │   └── test_api.py
│   ├── migrations/
│   ├── pyproject.toml
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/
│   │   │   ├── tasks.ts
│   │   │   ├── agent.ts
│   │   │   └── dashboard.ts
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useTasks.ts
│   │   │   └── useDashboard.ts
│   │   ├── pages/
│   │   │   ├── Board.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   └── Login.tsx
│   │   ├── components/
│   │   │   ├── TaskCard.tsx
│   │   │   ├── TaskBoard.tsx
│   │   │   ├── AgentLogViewer.tsx
│   │   │   ├── CostWidget.tsx
│   │   │   ├── PRBadge.tsx
│   │   │   └── StageControls.tsx
│   │   └── types/
│   │       └── index.ts
│   ├── tests/
│   │   ├── Board.test.tsx
│   │   ├── AgentLogViewer.test.tsx
│   │   └── CostWidget.test.tsx
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── package.json
│
├── infra/
│   ├── ecs-task-definition.json
│   ├── nginx.conf
│   └── supervisord.conf
│
├── docs/
│   ├── architecture.md
│   ├── api-contract.md
│   ├── data-models.md
│   └── agent-prompts.md
│
├── CLAUDE.md                    # Claude Code auto-reads this on startup
├── LESSONS.md                   # Agent error log — persistent memory across sessions
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── LICENSE                      # MIT
├── README.md
├── CONTRIBUTING.md
├── INTEGRATIONS.md              # Supported integrations + how to add one
├── ARCHITECTURE.md              # System design for new contributors
├── SECURITY.md                  # Vulnerability reporting policy
└── CHANGELOG.md                 # Keep a Changelog format
```

---

## Environment Variables

```bash
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# PostgreSQL
DATABASE_URL=postgres://user:pass@rds-host:5432/agentswe

# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...

# Jira
JIRA_BASE_URL=https://company.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=...
JIRA_PROJECT_KEY=SWE

# GitHub
GITHUB_TOKEN=ghp_...
GITHUB_ORG=your-org

# App
ADMIN_PASSWORD=...
ENVIRONMENT=production
```

---

## Data Models

### tasks
```
id              UUID PK
title           TEXT
description     TEXT
acceptance      TEXT
status          ENUM(backlog, planned, working, reviewing, done, failed)
jira_key        TEXT nullable
jira_url        TEXT nullable
slack_channel   TEXT
slack_thread_ts TEXT
slack_user_id   TEXT
pr_url          TEXT nullable
pr_number       INT nullable
repo            TEXT nullable
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

### agent_runs
```
id              UUID PK
task_id         UUID FK → tasks
stage           ENUM(plan, work, review)
status          ENUM(running, done, failed)
tokens_in       INT default 0
tokens_out      INT default 0
cost_usd        DECIMAL(10,6) default 0
started_at      TIMESTAMPTZ
finished_at     TIMESTAMPTZ nullable
```

### agent_logs
```
id              UUID PK
run_id          UUID FK → agent_runs
type            ENUM(text, tool_use, tool_result, error)
content         JSONB
created_at      TIMESTAMPTZ
```

### conversations
```
id              UUID PK
task_id         UUID FK → tasks
role            ENUM(user, assistant)
message         TEXT
slack_ts        TEXT nullable
created_at      TIMESTAMPTZ
```

---

## API Contract

The frontend builds exclusively against this contract. All routes are prefixed `/api/v1/`. Do not deviate from these shapes.

### REST Endpoints

```
GET    /api/v1/tasks                  → Task[]
GET    /api/v1/tasks/{id}             → TaskDetail (task + latest_run + recent logs)
PATCH  /api/v1/tasks/{id}            → Task  (body: { status })
POST   /api/v1/tasks/{id}/plan       → AgentRun
POST   /api/v1/tasks/{id}/work       → AgentRun
POST   /api/v1/tasks/{id}/review     → AgentRun
GET    /api/v1/dashboard/stats       → DashboardStats
GET    /api/v1/dashboard/costs       → CostBreakdown[]
POST   /api/v1/webhooks/{integration} → 200 OK (future integrations)
GET    /api/v1/integrations          → IntegrationStatus[] (which are active)

WS     /ws/runs/{run_id}             → streams AgentLog messages
```

### TypeScript Types

```typescript
type TaskStatus = "backlog"|"planned"|"working"|"reviewing"|"done"|"failed"
type RunStage   = "plan"|"work"|"review"
type RunStatus  = "running"|"done"|"failed"
type LogType    = "text"|"tool_use"|"tool_result"|"error"

interface Task {
  id: string
  title: string
  description: string
  acceptance: string
  status: TaskStatus
  jira_key: string | null
  jira_url: string | null
  slack_thread_ts: string
  pr_url: string | null
  pr_number: number | null
  repo: string | null
  created_at: string
  latest_run: AgentRun | null
}

interface AgentRun {
  id: string
  task_id: string
  stage: RunStage
  status: RunStatus
  tokens_in: number
  tokens_out: number
  cost_usd: number
  started_at: string
  finished_at: string | null
}

interface AgentLog {
  id: string
  run_id: string
  type: LogType
  content: Record<string, unknown>
  created_at: string
}

interface DashboardStats {
  total_cost_usd: number
  active_runs: number
  tasks_by_status: Record<TaskStatus, number>
  cost_by_stage: Record<RunStage, number>
}

interface CostBreakdown {
  task_id: string
  task_title: string
  total_cost_usd: number
  cost_by_stage: Record<RunStage, number>
}

interface IntegrationStatus {
  name: string
  description: string
  active: boolean
  missing_env_vars: string[]   // empty if active
}
```

---

## Agent — Claude Code CLI

### Invocation

```python
process = await asyncio.create_subprocess_exec(
    "claude", "--print", "--dangerously-skip-permissions",
    prompt,
    cwd=repo_local_path,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    env={**os.environ, "ANTHROPIC_API_KEY": settings.anthropic_api_key}
)

async for line in process.stdout:
    await save_log(run_id, line)
    await ws_manager.broadcast(run_id, line)

await process.wait()
usage = parse_claude_code_usage(await process.stderr.read())
await update_run_cost(run_id, usage)
```

### Stage Prompts

**Plan:**
```
You are a senior software engineer.
Analyze the following ticket and write a detailed, step-by-step implementation plan.
Save it as PLAN.md at the root of the repository.

Title: {title}
Description: {description}
Acceptance criteria: {acceptance}
```

**Work:**
```
You are a senior software engineer.
Implement the plan in PLAN.md exactly.
Write clean, well-tested code.
Commit your changes with descriptive commit messages.
Do not open a PR yet.
```

**Review:**
```
You are a senior software engineer reviewing your own work.
Review all changes since the base branch.
Fix any issues found.
Then open a Pull Request on GitHub with:
- Title: {jira_key} — {title}
- Body: summary of changes, link to Jira ticket ({jira_url}), test results
- Base branch: main
```

### Cost Calculation

```python
INPUT_PRICE_PER_M  = 3.00   # USD per million tokens (claude-sonnet-4)
OUTPUT_PRICE_PER_M = 15.00

cost = (tokens_in  / 1_000_000 * INPUT_PRICE_PER_M) + \
       (tokens_out / 1_000_000 * OUTPUT_PRICE_PER_M)
```

---

## Slack Bot

### Events

```python
@app.event("app_mention")
# → analyze message with Claude
# → create Jira ticket
# → create task in DB (status: backlog)
# → reply in thread

@app.event("message")
# → if thread_ts matches a task: save to conversations table
```

### Thread Messages

| Event | Message |
|---|---|
| Ticket created | `✅ Ticket created: *{jira_key}* — {title}\n{jira_url}` |
| Plan complete | `📋 Plan ready. Review it in the board and trigger Work when ready.` |
| Work complete | `⚙️ Code written and committed. Trigger Review when ready.` |
| PR opened | `🚀 PR ready: {pr_url}` |
| Stage failed | `❌ {stage} failed. Check the dashboard for logs.` |

---

## GitHub Integration

After Review stage completes successfully:

```python
gh   = Github(settings.github_token)
repo = gh.get_repo(task.repo)
pr   = repo.create_pull(
    title=f"{task.jira_key} — {task.title}",
    body=f"## Summary\n\n**Jira:** {task.jira_url}\n\n{summary}",
    head=f"feature/{task.jira_key.lower()}",
    base="main"
)
await Task.filter(id=task.id).update(pr_url=pr.html_url, pr_number=pr.number)
```

---

## CI/CD — GitHub Actions

### ci.yml — Runs on every push and pull request

```yaml
name: CI
on:
  push:
  pull_request:

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: agentswe_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r backend/requirements.txt
      - run: pytest backend/tests/ --cov=app --cov-report=xml --cov-fail-under=80
      - uses: codecov/codecov-action@v4

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd frontend && npm ci
      - run: cd frontend && npm test -- --coverage --coverageThreshold='{"global":{"lines":80}}'
```

### deploy.yml — Runs on push to main (after CI passes)

```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    needs: [backend-tests, frontend-tests]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - uses: aws-actions/amazon-ecr-login@v2
      - run: |
          docker build -t $ECR_REGISTRY/agent-swe:$GITHUB_SHA .
          docker push $ECR_REGISTRY/agent-swe:$GITHUB_SHA
          docker tag $ECR_REGISTRY/agent-swe:$GITHUB_SHA $ECR_REGISTRY/agent-swe:latest
          docker push $ECR_REGISTRY/agent-swe:latest
      - run: |
          aws ecs update-service \
            --cluster agent-swe \
            --service agent-swe \
            --force-new-deployment
```

### badges.yml — Updates README coverage badge on main

```yaml
name: Update Badges
on:
  push:
    branches: [main]

jobs:
  badge:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r backend/requirements.txt
      - run: pytest backend/tests/ --cov=app --cov-report=json
      - name: Update coverage badge
        uses: schneegans/dynamic-badges-action@v1.7.0
        with:
          auth: ${{ secrets.GIST_TOKEN }}
          gistID: ${{ secrets.GIST_ID }}
          filename: coverage.json
          label: coverage
          message: ${{ env.COVERAGE }}%
          color: ${{ env.COVERAGE >= 80 && 'green' || 'red' }}
```

---

## Open Source Setup

You must create all of the following files with complete, non-placeholder content:

### README.md
Must include:
- Project description and screenshot placeholder
- Coverage badge (pointing to the Gist badge from badges.yml)
- CI badge (GitHub Actions status)
- Feature list
- Architecture diagram (ASCII)
- Quick start (docker-compose)
- Environment variables table
- How to connect Slack, Jira, GitHub
- Link to `INTEGRATIONS.md` for adding new integrations
- Contributing link
- License badge

### LICENSE
MIT License.

### CONTRIBUTING.md
Must include:
- How to set up local dev environment
- How to run tests
- Branch naming: `feature/`, `fix/`, `chore/`, `integration/`
- PR process
- Code style (ruff for Python, ESLint + Prettier for TypeScript)
- Coverage requirement (80% minimum)
- Link to `INTEGRATIONS.md` for integration contributors

### INTEGRATIONS.md
Must include:
- Table of current integrations (Slack, Jira, GitHub) with status and required env vars
- Step-by-step guide for adding a new integration:
    1. Create `backend/app/integrations/{name}/`
    2. Implement `BaseIntegration`
    3. Declare `required_env_vars`
    4. Register in `registry.py`
    5. Write tests in `integrations/{name}/tests/`
    6. Add to this table
- Note that integrations are opt-in via env vars — missing vars = integration inactive, app still boots

### ARCHITECTURE.md
Must include:
- System overview diagram
- Component responsibilities
- Data flow (Slack → Bot → DB → UI → Agent → GitHub)
- Integration plugin system explanation
- Database schema overview
- WebSocket protocol description
- Deployment topology

### SECURITY.md
Must include:
- How to report a vulnerability (private disclosure via GitHub Security Advisories)
- What is in scope
- Response time commitment
- Note that secrets must never be committed — refer to `.env.example`

### CHANGELOG.md
Keep a Changelog format. Start with an `[Unreleased]` section ready for first entries.

### .github/ISSUE_TEMPLATE/new_integration.md
Template for proposing a new integration. Must ask for:
- Integration name and service URL
- Use case description
- Required env vars
- Proposed API surface (what methods it would expose)

### CODEOWNERS
```
# Core maintainers own everything by default
*                          @your-org/maintainers

# Integration-specific ownership (community contributors)
backend/app/integrations/slack/   @your-org/maintainers
backend/app/integrations/jira/    @your-org/maintainers
backend/app/integrations/github/  @your-org/maintainers
```

### .gitignore
Cover Python, Node, Docker, macOS, JetBrains, VSCode, `.env` files, `LESSONS.md` private entries (note: LESSONS.md itself is tracked).

### .env.example
All variables from the Environment Variables section above with placeholder values and inline comments explaining each one. Group by integration.

---

## Testing Standards

- **Backend:** pytest + pytest-asyncio. Every module has a test file in `backend/tests/`.
- **Frontend:** Vitest + React Testing Library. Every component has a test.
- **Minimum coverage:** 80% — enforced by CI (build fails below this).
- **Mocking:** never call real external APIs in tests. Mock Jira, GitHub, Slack, Anthropic.
- **conftest.py:** shared fixtures for DB setup, mock clients, test task/run factories.

---

## Build Phases — Execution Order

Follow these phases strictly. **Finish and verify each phase before starting the next.**
Each phase is designed to be small enough to execute without overloading context.

---

### PHASE 0 — Repository Scaffold & Claude Code Setup
**Goal:** Empty but complete repo, open source files, CI skeletons, agent tooling configured.

Tasks:
1. Create `CLAUDE.md` with full Claude Code configuration (commands, rules, context strategy)
2. Create `LESSONS.md` with initial structure (empty lessons section)
3. Create all directories and empty placeholder files per the repo structure
4. Write `README.md`, `LICENSE`, `CONTRIBUTING.md`, `INTEGRATIONS.md`, `ARCHITECTURE.md`, `SECURITY.md`, `CHANGELOG.md`
5. Write `.gitignore`, `.env.example`
6. Write GitHub issue templates (bug, feature, new integration), PR template, CODEOWNERS
7. Write GitHub Actions workflow files (`ci.yml`, `deploy.yml`, `badges.yml`, `stale.yml`)
8. Write `docker-compose.yml` and `Dockerfile` shells (not yet functional)

Verify: `git status` shows clean tree with all files present. `CLAUDE.md` and `LESSONS.md` exist at root.

---

### PHASE 1 — Documentation
**Goal:** All four contract docs written. These are the source of truth for all future phases.

Tasks:
1. Write `docs/architecture.md` — diagrams, component responsibilities, data flow
2. Write `docs/api-contract.md` — all endpoints, request/response shapes, WebSocket protocol, TypeScript types
3. Write `docs/data-models.md` — full schema with field descriptions, constraints, indexes
4. Write `docs/agent-prompts.md` — all Claude Code prompts per stage with variable descriptions

Verify: All four docs are complete, consistent with each other, and match this spec.

---

### PHASE 2 — Backend: Foundation
**Goal:** FastAPI app boots, connects to DB, models exist, migrations run, integration registry initializes.

Tasks:
1. Write `backend/pyproject.toml` and `backend/requirements.txt`
2. Write `app/config.py` (Pydantic settings from env vars)
3. Write `app/db.py` (Tortoise ORM init + Aerich config)
4. Write all Tortoise models (`task.py`, `agent_run.py`, `agent_log.py`, `conversation.py`)
5. Generate and run Aerich migrations
6. Write `integrations/base.py` (abstract base class) and `integrations/registry.py`
7. Write `app/main.py` (FastAPI app, startup/shutdown, include routers, initialize registry)
8. Write `tests/conftest.py` (test DB setup, fixtures)
9. Write `tests/test_models.py`

Verify: `pytest backend/tests/test_models.py` passes 100%. App boots and logs which integrations are active.

---

### PHASE 3 — Backend: Integrations
**Goal:** Jira, GitHub, and Slack integrations implement `BaseIntegration`, work independently, and are tested with mocks.

Tasks:
1. Write `integrations/jira/client.py` — implements `BaseIntegration`, exposes `create_issue()`, `update_status()`
2. Write `integrations/jira/tests/` — mock HTTP, verify payloads
3. Write `integrations/github/client.py` — implements `BaseIntegration`, exposes `create_pr()`
4. Write `integrations/github/tests/` — mock PyGithub
5. Write `integrations/slack/bot.py` — implements `BaseIntegration`, handles `app_mention`, `message`, exposes `post_thread_update()`
6. Write `integrations/slack/tests/` — mock slack-bolt
7. Register all three in `registry.py`
8. Write `integrations/README.md` — how to build a new integration

Verify: all integration tests pass 100%. Registry correctly reports active/inactive integrations based on env vars.

---

### PHASE 4 — Backend: Agent Runner
**Goal:** Claude Code CLI subprocess runs, logs stream, costs are captured.

Tasks:
1. Write `agent/cost.py` — token parser, cost calculator
2. Write `agent/prompts.py` — prompt builders for each stage
3. Write `agent/runner.py` — subprocess execution, log streaming, DB saving
4. Write `websocket/manager.py` — WebSocket connection manager + broadcast
5. Write `tests/test_agent.py` — mock subprocess, verify log saving and cost

Verify: `pytest backend/tests/test_agent.py` passes 100%.

---

### PHASE 5 — Backend: API Layer
**Goal:** All REST endpoints and WebSocket work correctly.

Tasks:
1. Write `api/tasks.py` — GET list, GET detail, PATCH status, POST plan/work/review
2. Write `api/agent.py` — WebSocket endpoint `/ws/runs/{run_id}`
3. Write `api/dashboard.py` — stats and cost breakdown endpoints
4. Write `tests/test_api.py` — integration test every endpoint

Verify: `pytest backend/tests/test_api.py` passes 100%. Full backend coverage ≥ 80%.

---

### PHASE 6 — Frontend: Foundation
**Goal:** Vite + React app runs, routing works, API client layer is typed.

Tasks:
1. Scaffold Vite + React + TypeScript + Tailwind + React Router
2. Write `src/types/index.ts` — all types from the API contract
3. Write `src/api/` — typed fetch wrappers for every endpoint
4. Write `src/hooks/` — `useTasks`, `useDashboard`, `useWebSocket`
5. Write login page with admin password auth

Verify: `npm run dev` starts without errors.

---

### PHASE 7 — Frontend: Components
**Goal:** All UI components built, tested with mocked data.

Tasks:
1. Write `TaskBoard.tsx` + `TaskCard.tsx` — Kanban columns, drag between columns
2. Write `StageControls.tsx` — Plan / Work / Review buttons with loading states
3. Write `AgentLogViewer.tsx` — WebSocket log stream with color-coded entries
4. Write `PRBadge.tsx` — PR link badge on task card
5. Write `CostWidget.tsx` — total cost, cost per task table, cost per stage
6. Write `Dashboard.tsx` — active runs + cost widgets
7. Write component tests for each

Verify: `npm test` passes 100%. Frontend coverage ≥ 80%.

---

### PHASE 8 — Docker
**Goal:** Single image builds and full flow runs in container.

Tasks:
1. Write `Dockerfile` — multi-stage build (Python deps + React build + final image with nginx + supervisord)
2. Write `infra/nginx.conf` — serve React static on :80, proxy `/api` and `/ws` to :8000
3. Write `infra/supervisord.conf` — manage uvicorn and nginx processes
4. Write `docker-compose.yml` — single service, env from `.env` file
5. Build image locally and run full flow

Verify: `docker-compose up` starts cleanly. UI loads. API responds. WebSocket connects.

---

### PHASE 9 — AWS Infrastructure
**Goal:** Deployed and running on ECS Fargate.

Tasks:
1. Write `infra/ecs-task-definition.json` — Fargate task, ECR image, port mappings, Secrets Manager env vars
2. Write `infra/deploy.sh` — ECR login, build, tag, push, ECS update
3. Confirm GitHub Actions secrets needed: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `ECR_REGISTRY`, `GIST_TOKEN`, `GIST_ID`
4. Document RDS setup steps in `docs/architecture.md`

Verify: `deploy.sh` runs without errors. ECS service shows running task. Full flow works on production URL.

---

## Definition of Done

A phase is complete only when **all** of the following are true:

- [ ] All files for the phase are created with real, working code (no placeholders)
- [ ] All tests for the phase pass
- [ ] Coverage for new code is ≥ 80%
- [ ] No hardcoded secrets, API keys, or environment-specific URLs
- [ ] Code follows style conventions (ruff for Python, ESLint + Prettier for TypeScript)
- [ ] Any errors encountered and resolved are recorded in `LESSONS.md`
- [ ] The verify command at the end of the phase succeeds cleanly

A feature is done when:

- [ ] It matches the API contract in `docs/api-contract.md`
- [ ] It has tests
- [ ] It runs correctly inside Docker
- [ ] README or INTEGRATIONS.md is updated if the feature affects setup or usage

---

## Final Reminder

> You are working autonomously and may run for hours.
> Read `CLAUDE.md` and `LESSONS.md` at the start of every session and every phase.
> Stay focused on one phase at a time.
> Complete it fully. Verify it. Then move to the next.
> When you hit an error — check `LESSONS.md` first, then investigate.
> When you resolve an error — update `LESSONS.md` immediately, before moving on.
> Do not skip the verify step.
> Do not start the next phase if the current one is not passing.