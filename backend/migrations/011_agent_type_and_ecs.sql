-- 011_agent_type_and_ecs.sql
-- Adds agent type configuration and ECS container orchestration support.

-- Agent types table — configurable agent profiles with ECS task definitions
CREATE TABLE IF NOT EXISTS agent_types (
    id                   UUID            NOT NULL PRIMARY KEY,
    name                 VARCHAR(100)    NOT NULL UNIQUE,
    display_name         VARCHAR(200)    NOT NULL,
    description          TEXT,
    docker_image         VARCHAR(500)    NOT NULL DEFAULT '',
    ecs_task_definition  VARCHAR(500)    NOT NULL DEFAULT '',
    task_role_arn        VARCHAR(500)    NOT NULL DEFAULT '',
    secrets_config       JSONB           NOT NULL DEFAULT '{}',
    capabilities         JSONB           NOT NULL DEFAULT '[]',
    cpu                  INT             NOT NULL DEFAULT 1024,
    memory               INT             NOT NULL DEFAULT 2048,
    max_duration_seconds INT             NOT NULL DEFAULT 3600,
    security_group_ids   JSONB           NOT NULL DEFAULT '[]',
    subnet_ids           JSONB           NOT NULL DEFAULT '[]',
    enable_dind          BOOLEAN         NOT NULL DEFAULT FALSE,
    is_default           BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_types_name       ON agent_types (name);
CREATE INDEX IF NOT EXISTS idx_agent_types_is_default ON agent_types (is_default) WHERE is_default = TRUE;

-- Link tasks to agent types
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS agent_type_id UUID REFERENCES agent_types (id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_agent_type_id ON tasks (agent_type_id);

-- Extend agent_runs for ECS container tracking
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS ecs_task_arn  VARCHAR(500);
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS error_message TEXT;

CREATE INDEX IF NOT EXISTS idx_runs_ecs_task_arn ON agent_runs (ecs_task_arn) WHERE ecs_task_arn IS NOT NULL;
