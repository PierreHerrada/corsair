# Architecture

This document describes the high-level system design of Corsair for new contributors.

## System Overview

```
┌──────────────┐     ┌──────────────────────────────────────────┐
│              │     │           Docker Container                │
│    Slack     │◀───▶│  ┌─────────────────┐  ┌──────────────┐  │
│   Workspace  │     │  │   FastAPI :8000  │  │  nginx :80   │  │
│              │     │  │  ┌────────────┐  │  │  (React SPA) │  │
└──────────────┘     │  │  │ Slack Bot  │  │  └──────┬───────┘  │
                     │  │  │ (Socket)   │  │         │          │
┌──────────────┐     │  │  └────────────┘  │         │          │
│    Jira      │◀───▶│  │  ┌────────────┐  │◀────────┘          │
│   Cloud      │     │  │  │ REST API   │  │   /api + /ws       │
└──────────────┘     │  │  └────────────┘  │                    │
                     │  │  ┌────────────┐  │                    │
┌──────────────┐     │  │  │ WebSocket  │  │                    │
│   GitHub     │◀───▶│  │  │ Manager    │  │                    │
│   API        │     │  │  └────────────┘  │                    │
└──────────────┘     │  │  ┌────────────┐  │                    │
                     │  │  │ Agent      │  │                    │
┌──────────────┐     │  │  │ Runner     │──┼──▶ Claude Code CLI │
│  PostgreSQL  │◀───▶│  │  └────────────┘  │                    │
│    (RDS)     │     │  └─────────────────┘  │                    │
└──────────────┘     └──────────────────────────────────────────┘
```

## Component Responsibilities

### FastAPI Backend (`backend/app/`)
- **main.py** — App factory, startup/shutdown lifecycle, router registration
- **config.py** — Pydantic settings loaded from environment variables
- **db.py** — Tortoise ORM initialization and Aerich migration config
- **models/** — Database models (Task, AgentRun, AgentLog, Conversation)
- **api/v1/** — REST endpoints and WebSocket handler
- **agent/** — Claude Code subprocess runner, prompt builders, cost calculator
- **integrations/** — Plugin system for Slack, Jira, GitHub (and future integrations)
- **websocket/** — WebSocket connection manager for live log streaming

### React Frontend (`frontend/src/`)
- **pages/** — Board (Kanban), Dashboard (stats/costs), Login
- **components/** — TaskCard, TaskBoard, AgentLogViewer, CostWidget, PRBadge, StageControls
- **api/** — Typed fetch wrappers for all REST endpoints
- **hooks/** — useTasks, useDashboard, useWebSocket

### Infrastructure (`infra/`)
- **nginx.conf** — Serves React static files, proxies /api and /ws to FastAPI
- **supervisord.conf** — Manages uvicorn and nginx processes in single container
- **ecs-task-definition.json** — AWS ECS Fargate task definition

## Data Flow

### Task Creation (Slack → DB → UI)
1. User tags `@corsair` in Slack
2. Slack bot receives `app_mention` event via Socket Mode
3. Bot analyzes the message with Claude, extracts task details
4. Bot creates a Jira ticket via Jira integration
5. Bot creates a Task record in PostgreSQL (status: `backlog`)
6. Bot replies in the Slack thread with the Jira link
7. Task appears in the React Kanban board

### Agent Execution (UI → Agent → GitHub)
1. User clicks **[Run Plan]** / **[Run Work]** / **[Run Review]** in the UI
2. Frontend sends `POST /api/v1/tasks/{id}/{stage}`
3. Backend creates an AgentRun record and spawns Claude Code CLI subprocess
4. Subprocess stdout is read line-by-line, saved as AgentLog records
5. Logs are broadcast via WebSocket to the frontend in real-time
6. On completion, token usage and cost are parsed and saved
7. For the Review stage, a GitHub PR is opened automatically

## Integration Plugin System

All integrations live under `backend/app/integrations/`. Each implements `BaseIntegration`:

```python
class BaseIntegration(ABC):
    name: str
    description: str
    required_env_vars: list[str]

    @abstractmethod
    async def health_check(self) -> bool: ...
```

The `registry.py` module discovers integrations at startup, validates their env vars, and logs which are active. New integrations can be added by creating a new directory — no core code changes required.

## Database Schema

| Table | Description |
|---|---|
| `tasks` | Tracks each engineering task from Slack through completion |
| `agent_runs` | Records each agent execution (plan/work/review) with cost |
| `agent_logs` | Stores individual log lines from Claude Code subprocess |
| `conversations` | Preserves Slack thread messages for context |

See `docs/data-models.md` for full schema with field descriptions and constraints.

## WebSocket Protocol

The frontend connects to `ws://host/ws/runs/{run_id}` to receive live agent logs.

Messages are JSON-encoded `AgentLog` objects:
```json
{
  "id": "uuid",
  "run_id": "uuid",
  "type": "text|tool_use|tool_result|error",
  "content": {},
  "created_at": "ISO 8601"
}
```

## Deployment Topology

```
ECR → corsair:latest

ECS Fargate
└── Cluster: corsair
    └── Service: corsair (single container)
        ├── :80   → ALB → React UI
        └── :8000 → ALB → FastAPI API

RDS PostgreSQL (external, connection via DATABASE_URL)
Secrets Manager (all env vars injected at runtime)
```

See `docs/architecture.md` for detailed deployment documentation.
