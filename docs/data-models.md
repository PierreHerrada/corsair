# Data Models — Corsair

All models use UUID primary keys and timezone-aware timestamps.
ORM: Tortoise ORM with Aerich for migrations. Database: PostgreSQL.

## tasks

Tracks each engineering task from Slack through completion.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, auto-generated | Unique task identifier |
| `title` | TEXT | NOT NULL | Task title (extracted from Slack message) |
| `description` | TEXT | NOT NULL, default '' | Detailed description |
| `acceptance` | TEXT | NOT NULL, default '' | Acceptance criteria |
| `status` | ENUM | NOT NULL, default 'backlog' | One of: `backlog`, `planned`, `working`, `reviewing`, `done`, `failed` |
| `jira_key` | TEXT | NULLABLE | Jira issue key (e.g., SWE-123) |
| `jira_url` | TEXT | NULLABLE | Full URL to Jira issue |
| `slack_channel` | TEXT | NOT NULL | Slack channel ID where task was created |
| `slack_thread_ts` | TEXT | NOT NULL | Slack thread timestamp for reply tracking |
| `slack_user_id` | TEXT | NOT NULL | Slack user who created the task |
| `pr_url` | TEXT | NULLABLE | GitHub PR URL (set after Review stage) |
| `pr_number` | INT | NULLABLE | GitHub PR number |
| `repo` | TEXT | NULLABLE | GitHub repository (e.g., org/repo-name) |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Record creation time |
| `updated_at` | TIMESTAMPTZ | NOT NULL, auto-update | Last modification time |

### Indexes
- Primary key on `id`
- Index on `status` (for board filtering)
- Index on `slack_thread_ts` (for Slack message matching)
- Index on `created_at` (for ordering)

### Status Transitions
```
backlog → planned (after Plan stage completes)
planned → working (after Work stage starts)
working → reviewing (after Review stage starts)
reviewing → done (after PR is merged)
any → failed (if a stage fails)
```

---

## agent_runs

Records each agent execution (plan/work/review) with cost tracking.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, auto-generated | Unique run identifier |
| `task_id` | UUID | FK → tasks, NOT NULL | Associated task |
| `stage` | ENUM | NOT NULL | One of: `plan`, `work`, `review` |
| `status` | ENUM | NOT NULL, default 'running' | One of: `running`, `done`, `failed` |
| `tokens_in` | INT | NOT NULL, default 0 | Input tokens consumed |
| `tokens_out` | INT | NOT NULL, default 0 | Output tokens generated |
| `cost_usd` | DECIMAL(10,6) | NOT NULL, default 0 | Total cost in USD |
| `started_at` | TIMESTAMPTZ | NOT NULL, auto | Run start time |
| `finished_at` | TIMESTAMPTZ | NULLABLE | Run completion time |

### Indexes
- Primary key on `id`
- Index on `task_id` (for task detail queries)
- Index on `status` (for active run queries)
- Index on `started_at` (for dashboard queries)

### Relationships
- Many-to-one with `tasks` (a task can have multiple runs)
- One-to-many with `agent_logs` (a run has many log entries)

---

## agent_logs

Stores individual log lines from the Claude Code subprocess.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, auto-generated | Unique log entry identifier |
| `run_id` | UUID | FK → agent_runs, NOT NULL | Associated run |
| `type` | ENUM | NOT NULL | One of: `text`, `tool_use`, `tool_result`, `error` |
| `content` | JSONB | NOT NULL | Structured log content |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Log entry timestamp |

### Indexes
- Primary key on `id`
- Index on `run_id` (for log retrieval)
- Index on `created_at` (for chronological ordering)

### Content Schema

**type: text**
```json
{"message": "Analyzing the codebase..."}
```

**type: tool_use**
```json
{"tool": "Read", "input": {"file_path": "/src/main.py"}}
```

**type: tool_result**
```json
{"tool": "Read", "output": "file contents..."}
```

**type: error**
```json
{"message": "Process exited with code 1", "details": "..."}
```

---

## conversations

Preserves Slack thread messages for context tracking.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, auto-generated | Unique message identifier |
| `task_id` | UUID | FK → tasks, NOT NULL | Associated task |
| `role` | ENUM | NOT NULL | One of: `user`, `assistant` |
| `message` | TEXT | NOT NULL | Message content |
| `slack_ts` | TEXT | NULLABLE | Slack message timestamp |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Message timestamp |

### Indexes
- Primary key on `id`
- Index on `task_id` (for conversation retrieval)
- Index on `created_at` (for chronological ordering)

---

## Tortoise ORM Configuration

```python
TORTOISE_ORM = {
    "connections": {
        "default": settings.database_url,
    },
    "apps": {
        "models": {
            "models": [
                "app.models.task",
                "app.models.agent_run",
                "app.models.agent_log",
                "app.models.conversation",
                "aerich.models",
            ],
            "default_connection": "default",
        },
    },
}
```

## Aerich Configuration

```python
AERICH_CONFIG = {
    "connections": TORTOISE_ORM["connections"],
    "apps": TORTOISE_ORM["apps"],
}
```
