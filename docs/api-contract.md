# API Contract — Corsair

All routes are prefixed `/api/v1/`. The frontend builds exclusively against this contract. Do not deviate from these shapes.

## Authentication

All endpoints except `/health`, `/api/v1/auth/login`, and `/api/v1/webhooks/*` require a valid JWT token in the `Authorization` header:

```
Authorization: Bearer <token>
```

WebSocket connections pass the token as a query parameter: `/ws/runs/{run_id}?token=<token>`

### `POST /api/v1/auth/login`

Authenticate with the admin password and receive a JWT token.

**Request Body:**
```json
{"password": "string"}
```

**Response:** `200 OK`
```json
{
  "access_token": "string",
  "token_type": "bearer"
}
```

**Error:** `401 Unauthorized`
```json
{"detail": "Invalid password"}
```

---

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

#### `GET /api/v1/integrations/health`

Performs real health checks against each configured integration (network calls with 10s timeout each). Unconfigured integrations skip the health check.

**Response:** `200 OK`
```json
[
  {
    "name": "slack",
    "description": "Slack bot for task creation and status updates",
    "configured": true,
    "healthy": true,
    "error": null
  },
  {
    "name": "jira",
    "description": "Jira integration for ticket management",
    "configured": false,
    "healthy": null,
    "error": null
  }
]
```

---

### Chat

#### `GET /api/v1/chat/messages`

Returns paginated chat messages from the Slack listener.

**Query Parameters:**
- `limit` (int, default 50, max 200) — Number of messages to return
- `offset` (int, default 0) — Pagination offset
- `channel_id` (string, optional) — Filter by Slack channel ID

**Response:** `200 OK`
```json
{
  "total": 142,
  "offset": 0,
  "limit": 50,
  "messages": [
    {
      "id": "uuid",
      "channel_id": "C123456",
      "channel_name": "general",
      "user_id": "U123456",
      "user_name": "Jane Doe",
      "message": "Hello world",
      "slack_ts": "1234567890.123456",
      "thread_ts": null,
      "task_id": "uuid|null",
      "created_at": "ISO 8601"
    }
  ]
}
```

---

### Datadog

#### `GET /api/v1/datadog/analyses`

Returns paginated list of Datadog analyses (newest first). Does not include `raw_logs` or `raw_trace` in list responses.

**Query Parameters:**
- `limit` (int, default 20, max 100) — Number of analyses to return
- `offset` (int, default 0) — Pagination offset

**Response:** `200 OK`
```json
{
  "total": 5,
  "offset": 0,
  "limit": 20,
  "analyses": [
    {
      "id": "uuid",
      "source": "webhook|manual",
      "trigger": "string",
      "status": "pending|analyzing|done|failed",
      "query": "string",
      "trace_id": "string|null",
      "log_count": 0,
      "summary": "string",
      "error_message": "string|null",
      "created_at": "ISO 8601"
    }
  ]
}
```

#### `GET /api/v1/datadog/analyses/{id}`

Returns a single analysis with full raw data (logs and trace spans).

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "source": "webhook|manual",
  "trigger": "string",
  "status": "pending|analyzing|done|failed",
  "query": "string",
  "trace_id": "string|null",
  "log_count": 0,
  "raw_logs": [],
  "raw_trace": [],
  "summary": "string",
  "error_message": "string|null",
  "created_at": "ISO 8601"
}
```

**Error:** `404 Not Found`
```json
{"detail": "Analysis not found"}
```

#### `POST /api/v1/datadog/analyze`

Manually trigger a Datadog analysis. At least one of `url`, `query`, or `trace_id` is required.

**Request Body:**
```json
{
  "url": "string|null",
  "query": "string|null",
  "trace_id": "string|null"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "source": "manual",
  "trigger": "string",
  "status": "pending",
  "query": "",
  "trace_id": null,
  "log_count": 0,
  "raw_logs": [],
  "raw_trace": [],
  "summary": "",
  "error_message": null,
  "created_at": "ISO 8601"
}
```

**Error:** `422 Unprocessable Entity`
```json
{"detail": "At least one of url, query, or trace_id is required"}
```

#### `POST /api/v1/webhooks/datadog`

Receives Datadog Monitor webhook payloads. Parses alert metadata and creates an analysis automatically.

**Request Body:** Datadog Monitor webhook JSON (includes `title`, `tags`, `logs_sample`, etc.)

**Response:** `200 OK`
```json
{"status": "ok"}
```

---

### Logs

#### `GET /api/v1/logs`

Returns paginated internal logs from integrations (Jira sync, Slack bot, etc.).

**Query Parameters:**
- `limit` (int, default 100, max 500) — Number of logs to return
- `offset` (int, default 0) — Pagination offset
- `source` (string, optional) — Filter by source: `jira`, `slack`, `github`, `datadog`, `main`
- `level` (string, optional) — Filter by level: `DEBUG`, `INFO`, `WARNING`, `ERROR`

**Response:** `200 OK`
```json
{
  "total": 250,
  "offset": 0,
  "limit": 100,
  "logs": [
    {
      "id": "uuid",
      "source": "jira",
      "level": "INFO",
      "logger_name": "app.integrations.jira.sync",
      "message": "Jira sync: found 3 issues matching label 'corsair'",
      "created_at": "ISO 8601"
    }
  ]
}
```

---

### Settings

#### `GET /api/v1/settings/{key}`

Returns the value of a single setting. Returns empty value if the setting has not been configured yet.

**Response:** `200 OK`
```json
{
  "key": "string",
  "value": "string",
  "updated_at": "ISO 8601|null"
}
```

#### `PUT /api/v1/settings/{key}`

Create or update a setting.

**Request Body:**
```json
{"value": "string"}
```

**Response:** `200 OK`
```json
{
  "key": "string",
  "value": "string",
  "updated_at": "ISO 8601"
}
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

interface IntegrationHealth {
  name: string;
  description: string;
  configured: boolean;
  healthy: boolean | null;
  error: string | null;
}

interface ChatMessage {
  id: string;
  channel_id: string;
  channel_name: string;
  user_id: string;
  user_name: string;
  message: string;
  slack_ts: string;
  thread_ts: string | null;
  task_id: string | null;
  created_at: string;
}

interface ChatMessagesResponse {
  total: number;
  offset: number;
  limit: number;
  messages: ChatMessage[];
}

type AnalysisSource = "webhook" | "manual";
type AnalysisStatus = "pending" | "analyzing" | "done" | "failed";

interface DatadogAnalysis {
  id: string;
  source: AnalysisSource;
  trigger: string;
  status: AnalysisStatus;
  query: string;
  trace_id: string | null;
  log_count: number;
  raw_logs: Record<string, unknown>[];
  raw_trace: Record<string, unknown>[];
  summary: string;
  error_message: string | null;
  created_at: string;
}

interface InternalLogEntry {
  id: string;
  source: string;
  level: string;
  logger_name: string;
  message: string;
  created_at: string;
}

interface InternalLogsResponse {
  total: number;
  offset: number;
  limit: number;
  logs: InternalLogEntry[];
}

interface DatadogAnalysesResponse {
  total: number;
  offset: number;
  limit: number;
  analyses: DatadogAnalysis[];
}

interface SettingResponse {
  key: string;
  value: string;
  updated_at: string | null;
}
```
