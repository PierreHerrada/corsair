from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "tasks" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "title" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "acceptance" TEXT NOT NULL,
    "status" VARCHAR(20) NOT NULL  DEFAULT 'backlog',
    "jira_key" TEXT,
    "jira_url" TEXT,
    "slack_channel" TEXT NOT NULL,
    "slack_thread_ts" TEXT NOT NULL,
    "slack_user_id" TEXT NOT NULL,
    "pr_url" TEXT,
    "pr_number" INT,
    "repo" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON COLUMN "tasks"."status" IS 'BACKLOG: backlog\nPLANNED: planned\nWORKING: working\nREVIEWING: reviewing\nDONE: done\nFAILED: failed';
CREATE TABLE IF NOT EXISTS "agent_runs" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "stage" VARCHAR(10) NOT NULL,
    "status" VARCHAR(10) NOT NULL  DEFAULT 'running',
    "tokens_in" INT NOT NULL  DEFAULT 0,
    "tokens_out" INT NOT NULL  DEFAULT 0,
    "cost_usd" DECIMAL(10,6) NOT NULL  DEFAULT 0,
    "started_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "finished_at" TIMESTAMPTZ,
    "task_id" UUID NOT NULL REFERENCES "tasks" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "agent_runs"."stage" IS 'PLAN: plan\nWORK: work\nREVIEW: review';
COMMENT ON COLUMN "agent_runs"."status" IS 'RUNNING: running\nDONE: done\nFAILED: failed';
CREATE TABLE IF NOT EXISTS "agent_logs" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "type" VARCHAR(15) NOT NULL,
    "content" JSONB NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "run_id" UUID NOT NULL REFERENCES "agent_runs" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "agent_logs"."type" IS 'TEXT: text\nTOOL_USE: tool_use\nTOOL_RESULT: tool_result\nERROR: error';
CREATE TABLE IF NOT EXISTS "conversations" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "role" VARCHAR(10) NOT NULL,
    "message" TEXT NOT NULL,
    "slack_ts" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "task_id" UUID NOT NULL REFERENCES "tasks" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "conversations"."role" IS 'USER: user\nASSISTANT: assistant';
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
