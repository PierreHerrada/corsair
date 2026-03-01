# API Contract — Corsair

All routes are prefixed `/api/v1/`. The frontend builds exclusively against this contract. Do not deviate from these shapes.

## REST Endpoints

### Tasks

#### `GET /api/v1/tasks`

Returns all tasks ordered by `created_at` descending.

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "title": "string",
    "description": "string",
    "acceptance": "string",
    "status": "backlog|planned|working|reviewing|done|failed",
    "jira_key": "string|null",
    "jira_url": "string|null",
    "slack_thread_ts": "string",
    "pr_url": "string|null",
    "pr_number": 0,
    "repo": "string|null",
    "created_at": "ISO 8601",
    "latest_run": null
  }
]
```

#### `GET /api/v1/tasks/{id}`

Returns a single task with its latest agent run and recent logs.

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "title": "string",
  "description": "string",
  "acceptance": "string",
  "status": "backlog|planned|working|reviewing|done|failed",
  "jira_key": "string|null",
  "jira_url": "string|null",
  "slack_thread_ts": "string",
  "pr_url": "string|null",
  "pr_number": 0,
  "repo": "string|null",
  "created_at": "ISO 8601",
  "latest_run": {
    "id": "uuid",
    "task_id": "uuid",
    "stage": "plan|work|review",
    "status": "running|done|failed",
    "tokens_in": 0,
    "tokens_out": 0,
    "cost_usd": 0.000000,
    "started_at": "ISO 8601",
    "finished_at": "ISO 8601|null"
  }
}
```

**Error:** `404 Not Found`
```json
{"detail": "Task not found"}
```

#### `PATCH /api/v1/tasks/{id}`

Update task status.

**Request Body:**
```json
{"status": "backlog|planned|working|reviewing|done|failed"}
```

**Response:** `200 OK` — Updated task object (same shape as GET)

**Error:** `404 Not Found`, `422 Unprocessable Entity`

#### `POST /api/v1/tasks/{id}/plan`

Trigger the Plan stage for a task. Creates an AgentRun and starts Claude Code subprocess.

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "task_id": "uuid",
  "stage": "plan",
  "status": "running",
  "tokens_in": 0,
  "tokens_out": 0,
  "cost_usd": 0.000000,
  "started_at": "ISO 8601",
  "finished_at": null
}
```

**Error:** `404 Not Found`, `409 Conflict` (if a run is already active)

#### `POST /api/v1/tasks/{id}/work`

Trigger the Work stage. Same response shape as Plan.

#### `POST /api/v1/tasks/{id}/review`

Trigger the Review stage. Same response shape as Plan.

---

### Dashboard

#### `GET /api/v1/dashboard/stats`

Returns aggregate statistics.

**Response:** `200 OK`
```json
{
  "total_cost_usd": 0.00,
  "active_runs": 0,
  "tasks_by_status": {
    "backlog": 0,
    "planned": 0,
    "working": 0,
    "reviewing": 0,
    "done": 0,
    "failed": 0
  },
  "cost_by_stage": {
    "plan": 0.00,
    "work": 0.00,
    "review": 0.00
  }
}
```

#### `GET /api/v1/dashboard/costs`

Returns cost breakdown per task.

**Response:** `200 OK`
```json
[
  {
    "task_id": "uuid",
    "task_title": "string",
    "total_cost_usd": 0.00,
    "cost_by_stage": {
      "plan": 0.00,
      "work": 0.00,
      "review": 0.00
    }
  }
]
```

---

### Webhooks

#### `POST /api/v1/webhooks/{integration_name}`

Generic webhook endpoint for future integrations.

**Response:** `200 OK`
```json
{"status": "ok"}
```

---

### Integrations

#### `GET /api/v1/integrations`

Returns status of all registered integrations.

**Response:** `200 OK`
```json
[
  {
    "name": "slack",
    "description": "Slack bot for task creation and status updates",
    "active": true,
    "missing_env_vars": []
  },
  {
    "name": "jira",
    "description": "Jira integration for ticket management",
    "active": false,
    "missing_env_vars": ["JIRA_API_TOKEN"]
  }
]
```

---

## WebSocket

### `WS /ws/runs/{run_id}`

Streams agent log messages for a specific run in real-time.

**Connection:** Client opens WebSocket to `/ws/runs/{run_id}`

**Server → Client messages:**

Each message is a JSON-encoded AgentLog:
```json
{
  "id": "uuid",
  "run_id": "uuid",
  "type": "text|tool_use|tool_result|error",
  "content": {},
  "created_at": "ISO 8601"
}
```

**Connection lifecycle:**
1. Client connects
2. Server sends all existing logs for the run as individual messages
3. Server streams new logs as they arrive
4. When the run completes/fails, server sends a close frame

---

## TypeScript Types

```typescript
type TaskStatus = "backlog" | "planned" | "working" | "reviewing" | "done" | "failed";
type RunStage = "plan" | "work" | "review";
type RunStatus = "running" | "done" | "failed";
type LogType = "text" | "tool_use" | "tool_result" | "error";

interface Task {
  id: string;
  title: string;
  description: string;
  acceptance: string;
  status: TaskStatus;
  jira_key: string | null;
  jira_url: string | null;
  slack_thread_ts: string;
  pr_url: string | null;
  pr_number: number | null;
  repo: string | null;
  created_at: string;
  latest_run: AgentRun | null;
}

interface AgentRun {
  id: string;
  task_id: string;
  stage: RunStage;
  status: RunStatus;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  started_at: string;
  finished_at: string | null;
}

interface AgentLog {
  id: string;
  run_id: string;
  type: LogType;
  content: Record<string, unknown>;
  created_at: string;
}

interface DashboardStats {
  total_cost_usd: number;
  active_runs: number;
  tasks_by_status: Record<TaskStatus, number>;
  cost_by_stage: Record<RunStage, number>;
}

interface CostBreakdown {
  task_id: string;
  task_title: string;
  total_cost_usd: number;
  cost_by_stage: Record<RunStage, number>;
}

interface IntegrationStatus {
  name: string;
  description: string;
  active: boolean;
  missing_env_vars: string[];
}
```
