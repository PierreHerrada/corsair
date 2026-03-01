# Architecture — Corsair

## System Overview

Corsair is a single Docker image that bundles a FastAPI backend, a React frontend, and an nginx reverse proxy — all managed by supervisord.

```
┌────────────────────────────────────────────────────────────┐
│                    Docker Container                         │
│  ┌──────────────────────────────┐  ┌────────────────────┐  │
│  │       FastAPI :8000          │  │    nginx :80       │  │
│  │  ┌────────────────────────┐  │  │  (React SPA)      │  │
│  │  │ Slack Bot (Socket Mode)│  │  └────────┬───────────┘  │
│  │  │ REST API (/api/v1/)    │  │           │              │
│  │  │ WebSocket (/ws/)       │  │◀──────────┘              │
│  │  │ Agent Runner           │  │   /api + /ws proxy       │
│  │  └────────────────────────┘  │                          │
│  └──────────────┬───────────────┘                          │
│                 │                                           │
│    supervisord (process manager)                           │
└────────────────────────────────────────────────────────────┘
         │              │              │
    ┌────┴────┐    ┌───┴───┐    ┌────┴────┐
    │PostgreSQL│    │ Slack │    │ GitHub  │
    │  (RDS)   │    │  API  │    │  API    │
    └─────────┘    └───────┘    └─────────┘
         │
    ┌────┴────┐
    │  Jira   │
    │  API    │
    └─────────┘
```

## Component Responsibilities

### Backend (`backend/app/`)

| Component | Path | Responsibility |
|---|---|---|
| **App Factory** | `main.py` | FastAPI app, startup/shutdown lifecycle, router registration |
| **Config** | `config.py` | Pydantic settings loaded from environment variables |
| **Database** | `db.py` | Tortoise ORM initialization and Aerich migration config |
| **Models** | `models/` | Database models — Task, AgentRun, AgentLog, Conversation |
| **API** | `api/v1/` | REST endpoints (tasks, dashboard, webhooks) + WebSocket |
| **Agent** | `agent/` | Claude Code subprocess runner, prompt builders, cost calculator |
| **Integrations** | `integrations/` | Plugin system — Slack, Jira, GitHub |
| **WebSocket** | `websocket/` | Connection manager for live log streaming |

### Frontend (`frontend/src/`)

| Component | Path | Responsibility |
|---|---|---|
| **Pages** | `pages/` | Board (Kanban), Dashboard (stats/costs), Login |
| **Components** | `components/` | TaskCard, TaskBoard, AgentLogViewer, CostWidget, PRBadge, StageControls |
| **API Layer** | `api/` | Typed fetch wrappers for all REST endpoints |
| **Hooks** | `hooks/` | useTasks, useDashboard, useWebSocket |
| **Types** | `types/` | TypeScript types matching the API contract |

### Infrastructure (`infra/`)

| File | Responsibility |
|---|---|
| `nginx.conf` | Serve React static files on :80, proxy /api and /ws to :8000 |
| `supervisord.conf` | Manage uvicorn and nginx processes in single container |
| `ecs-task-definition.json` | AWS ECS Fargate task definition |

## Data Flow

### 1. Task Creation (Slack → DB → UI)

```
User tags @Corsair in Slack
    ↓
Slack Bot receives app_mention event (Socket Mode)
    ↓
Bot analyzes message with Claude → extracts title, description, acceptance criteria
    ↓
Bot creates Jira ticket via Jira integration
    ↓
Bot creates Task record in PostgreSQL (status: backlog)
    ↓
Bot replies in Slack thread: "✅ Ticket created: SWE-123 — Title"
    ↓
Task appears in React Kanban board (Backlog column)
```

### 2. Agent Execution (UI → Agent → GitHub)

```
User clicks [Run Plan] / [Run Work] / [Run Review] in UI
    ↓
Frontend sends POST /api/v1/tasks/{id}/{stage}
    ↓
Backend creates AgentRun record (status: running)
    ↓
Backend spawns Claude Code CLI subprocess
    ↓
Subprocess stdout read line-by-line → saved as AgentLog records
    ↓
Logs broadcast via WebSocket → React shows live log viewer
    ↓
On completion: parse token usage → calculate cost → update AgentRun
    ↓
(Review stage only) → Open GitHub PR → save PR URL to Task
    ↓
Post status update to Slack thread
```

### 3. Real-time Log Streaming

```
Claude Code CLI subprocess
    ↓ stdout (line by line)
FastAPI async reader
    ↓
agent_logs table (PostgreSQL)
    ↓
WebSocket broadcast
    ↓
React UI — AgentLogViewer component
```

## Integration Plugin System

All integrations live under `backend/app/integrations/`. Each implements `BaseIntegration`:

```python
class BaseIntegration(ABC):
    name: str                        # e.g. "github", "linear", "gitlab"
    description: str
    required_env_vars: list[str]     # validated at startup

    @abstractmethod
    async def health_check(self) -> bool: ...
```

### Discovery Flow

1. On startup, `registry.py` imports all integration classes
2. For each integration, checks if all `required_env_vars` are set
3. Active integrations are initialized; inactive ones are logged
4. `GET /api/v1/integrations` returns status of all integrations

### Rules

- No integration logic in core code — always go through the registry
- Missing env vars = inactive integration, app still boots
- All REST endpoints prefixed `/api/v1/` for future versioning
- Webhook-ready: `POST /api/v1/webhooks/{integration_name}` for inbound events

## Database Schema

| Table | Description |
|---|---|
| `tasks` | Each engineering task from Slack through completion |
| `agent_runs` | Each agent execution (plan/work/review) with token usage and cost |
| `agent_logs` | Individual log lines from Claude Code subprocess |
| `conversations` | Slack thread messages for context preservation |

See `docs/data-models.md` for full schema.

## WebSocket Protocol

The frontend connects to `ws://host/ws/runs/{run_id}` to receive live agent logs.

Messages are JSON-encoded `AgentLog` objects:

```json
{
  "id": "uuid",
  "run_id": "uuid",
  "type": "text|tool_use|tool_result|error",
  "content": {},
  "created_at": "2026-01-15T10:30:00Z"
}
```

Connection lifecycle:
1. Client opens WebSocket to `/ws/runs/{run_id}`
2. Server sends all existing logs for the run as a batch
3. Server streams new logs as they arrive in real-time
4. When the run finishes, server sends a final status message and closes

## Deployment Topology

### Local Development

```
docker-compose up --build
├── corsair (app container, ports 80 + 8000)
└── postgres (database, port 5432)
```

### Production (AWS)

```
ECR → corsair:latest

ECS Fargate
└── Cluster: corsair
    └── Service: corsair (single task)
        ├── :80   → ALB → React UI (users)
        └── :8000 → ALB → FastAPI (API calls)

RDS PostgreSQL (external, connection via DATABASE_URL)
Secrets Manager (all env vars injected at runtime)
```

### RDS Setup

1. **Create RDS Instance**
   - Engine: PostgreSQL 15
   - Instance class: `db.t3.micro` (dev) or `db.t3.medium` (prod)
   - Storage: 20 GB gp3
   - Database name: `corsair`
   - Master username: `corsair`
   - Enable encryption at rest
   - Disable public access

2. **Configure Security Groups**
   - Create an RDS security group allowing inbound PostgreSQL (port 5432) from the ECS task security group
   - The ECS task security group should allow outbound to RDS on port 5432

3. **Store Connection String in Secrets Manager**
   - Secret name: `corsair/database-url`
   - Value: `postgres://corsair:<password>@<rds-endpoint>:5432/corsair`

4. **Verify Connectivity**
   - Deploy the ECS task and check logs for successful database connection
   - Aerich will apply migrations automatically on startup

### Required GitHub Actions Secrets

| Secret | Description |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM access key for ECR push and ECS deploy |
| `AWS_SECRET_ACCESS_KEY` | IAM secret key |
| `ECR_REGISTRY` | ECR registry URL (e.g., `123456789.dkr.ecr.us-east-1.amazonaws.com`) |
| `GIST_TOKEN` | GitHub token with gist scope (for badges workflow) |
| `GIST_ID` | Gist ID for coverage badge JSON |
