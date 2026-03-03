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
| `plan` | TEXT | NOT NULL, default '' | Plan text from the PLAN stage |
| `analysis` | TEXT | NOT NULL, default '' | Auto-generated task analysis |
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
| `workspace_path` | TEXT | NULLABLE | Filesystem path to the cloned workspace |
| `file_tree` | JSONB | NULLABLE | File tree snapshot after run completes |

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

## chat_messages

Persists Slack messages seen by the bot for display in the Chat tab.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, auto-generated | Unique message identifier |
| `channel_id` | TEXT | NOT NULL | Slack channel ID |
| `channel_name` | TEXT | NOT NULL, default '' | Human-readable channel name |
| `user_id` | TEXT | NOT NULL | Slack user ID |
| `user_name` | TEXT | NOT NULL, default '' | Human-readable user name |
| `message` | TEXT | NOT NULL | Message text content |
| `slack_ts` | TEXT | NOT NULL | Slack message timestamp |
| `thread_ts` | TEXT | NULLABLE | Parent thread timestamp (null if top-level) |
| `task_id` | UUID | FK → tasks, NULLABLE, ON DELETE SET NULL | Associated task (if any) |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Record creation time |

### Indexes
- Primary key on `id`
- Index on `created_at` (for ordering)
- Index on `channel_id` (for channel filtering)
- Index on `slack_ts` (for deduplication)
- Index on `task_id` (for task association queries)

---

## datadog_analyses

Stores Datadog log/trace analysis results, triggered manually or via webhook.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, auto-generated | Unique analysis identifier |
| `source` | ENUM | NOT NULL | One of: `webhook`, `manual` |
| `trigger` | TEXT | NOT NULL | URL pasted or monitor name |
| `status` | ENUM | NOT NULL, default 'pending' | One of: `pending`, `analyzing`, `done`, `failed` |
| `query` | TEXT | NOT NULL, default '' | Log search query used |
| `trace_id` | TEXT | NULLABLE | Trace ID if trace-based |
| `log_count` | INT | NOT NULL, default 0 | Number of log entries found |
| `raw_logs` | JSONB | NOT NULL, default [] | Raw log entries (capped at 200) |
| `raw_trace` | JSONB | NOT NULL, default [] | Raw span entries |
| `summary` | TEXT | NOT NULL, default '' | Human-readable analysis |
| `error_message` | TEXT | NULLABLE | Error if analysis failed |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Record creation time |

### Indexes
- Primary key on `id`
- Index on `created_at` (for ordering)

---

## internal_logs

Stores internal application logs from integrations for debugging.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, auto-generated | Unique log entry identifier |
| `source` | TEXT | NOT NULL | Integration source: `jira`, `slack`, `github`, `datadog`, `main` |
| `level` | TEXT | NOT NULL | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `logger_name` | TEXT | NOT NULL | Full Python logger name |
| `message` | TEXT | NOT NULL | Log message content |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Log entry timestamp |

### Indexes
- Primary key on `id`
- Index on `created_at` (for ordering)
- Index on `source` (for filtering)

---

## repositories

Stores GitHub repositories and their enabled/disabled status for agent gating.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, auto-generated | Unique repository identifier |
| `full_name` | VARCHAR(255) | NOT NULL, UNIQUE | Full repo name (e.g., org/repo-name) |
| `name` | VARCHAR(255) | NOT NULL | Short repo name |
| `description` | TEXT | NOT NULL, default '' | Repository description |
| `private` | BOOLEAN | NOT NULL, default false | Whether the repo is private |
| `enabled` | BOOLEAN | NOT NULL, default false | Whether the agent can operate on this repo |
| `default_branch` | VARCHAR(100) | NOT NULL, default 'main' | Default branch name |
| `github_url` | TEXT | NOT NULL, default '' | GitHub URL |
| `last_synced_at` | TIMESTAMPTZ | NULLABLE | Last sync from GitHub |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | Record creation time |
| `updated_at` | TIMESTAMPTZ | NOT NULL, auto-update | Last modification time |

### Indexes
- Primary key on `id`
- Unique index on `full_name` (for upsert lookups)
- Index on `enabled` (for agent gating queries)

---

## setting_history

Tracks changes to settings over time, with source attribution (user or agent).

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, auto-generated | Unique history entry identifier |
| `setting_key` | VARCHAR(255) | NOT NULL | Setting key that was changed |
| `old_value` | TEXT | NOT NULL, default '' | Value before the change |
| `new_value` | TEXT | NOT NULL, default '' | Value after the change |
| `change_source` | VARCHAR(50) | NOT NULL, default 'user' | Who made the change: `user` or `agent` |
| `created_at` | TIMESTAMPTZ | NOT NULL, auto | When the change occurred |

### Indexes
- Primary key on `id`
- Index on `setting_key` (for filtering by setting)
- Index on `created_at` (for chronological ordering)

---

## settings

Stores application-level configuration as key-value pairs.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, auto-generated | Unique setting identifier |
| `key` | TEXT | NOT NULL, UNIQUE | Setting key (e.g., `base_prompt`, `max_active_agents`) |
| `value` | TEXT | NOT NULL, default '' | Setting value |
| `updated_at` | TIMESTAMPTZ | NOT NULL, auto-update | Last modification time |

### Indexes
- Primary key on `id`
- Unique index on `key` (for fast lookup)

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
                "app.models.chat_message",
                "app.models.datadog_analysis",
                "app.models.internal_log",
                "app.models.setting",
                "app.models.setting_history",
                "app.models.repository",
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
