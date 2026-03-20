# Migration Guide: v0.0.11_alpha → v0.1.1_alpha

This guide covers all changes required when upgrading from `v0.0.11_alpha` (or any prior version) to `v0.1.1_alpha`.

## Summary

This release introduces **ECS container orchestration** for running agents in isolated Fargate tasks, a new **Agent Types** system for configuring multiple agent profiles, a **standalone agent container**, and environment variable support for agent runs.

---

## Database Migrations

### New Table: `agent_types`

```sql
CREATE TABLE agent_types (
    id UUID PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    docker_image VARCHAR(500) DEFAULT '',
    ecs_task_definition VARCHAR(500) NOT NULL,
    task_role_arn VARCHAR(500) DEFAULT '',
    secrets_config JSONB DEFAULT '{}',
    capabilities JSONB DEFAULT '[]',
    cpu INT DEFAULT 1024,
    memory INT DEFAULT 2048,
    max_duration_seconds INT DEFAULT 3600,
    security_group_ids JSONB DEFAULT '[]',
    subnet_ids JSONB DEFAULT '[]',
    enable_dind BOOLEAN DEFAULT FALSE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Altered Table: `agent_runs`

```sql
ALTER TABLE agent_runs ADD COLUMN ecs_task_arn VARCHAR(500);
ALTER TABLE agent_runs ADD COLUMN error_message TEXT;
```

The `status` enum now includes a new value:

```sql
-- If using a native ENUM type, add the new value:
ALTER TYPE run_status ADD VALUE IF NOT EXISTS 'launching';
```

### Altered Table: `tasks`

```sql
ALTER TABLE tasks ADD COLUMN agent_type_id UUID REFERENCES agent_types(id) ON DELETE SET NULL;
```

### Seed Default Agent Types

After applying the schema changes, run the seed script to create the default agent types:

```bash
cd backend
python ../scripts/seed_agent_types.py
```

This creates 5 preconfigured agent types: `default`, `db-agent`, `db-agent-dind`, `aws-agent`, and `datadog-agent`. The script is idempotent — it skips types that already exist.

---

## New Environment Variables

| Variable | Description | Default | Required |
|---|---|---|---|
| `AWS_REGION` | AWS region for ECS | `eu-west-1` | For ECS |
| `ECS_CLUSTER_ARN` | ECS cluster ARN | `""` | For ECS |
| `INTERNAL_API_SECRET` | Secret for agent callback authentication | `""` | For ECS |
| `INTERNAL_CALLBACK_URL` | Control plane URL for agent callbacks | `http://control-plane.corsair.local:8000` | For ECS |
| `LOCAL_AGENT_IMAGE` | Docker image for local agent runner | `corsair-agent:local` | For local dev |

Add these to your `.env` file. See `.env.example` for the updated template.

---

## Infrastructure Changes

### Terraform (new)

A full Terraform configuration has been added under `infra/terraform/` for provisioning:

- ECS cluster with Fargate and Fargate Spot capacity providers
- ECR repositories for control plane and agent images
- ECS task definitions for 5 agent types
- ALB with HTTPS listener
- VPC with public/private subnets, NAT gateway
- IAM roles and policies for ECS task execution and agent tasks
- Secrets Manager integration

To deploy:

```bash
cd infra/terraform
terraform init
terraform plan -var-file=your-vars.tfvars
terraform apply -var-file=your-vars.tfvars
```

### Removed

- `infra/ecs-task-definition.json` — Replaced by Terraform-managed task definitions.

### Docker Compose

`docker-compose.local.yml` has been updated with additional services and configuration for local development with the agent container.

---

## API Changes

### New Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/agent-types` | List all agent types |
| `POST` | `/api/v1/agent-types` | Create an agent type |
| `GET` | `/api/v1/agent-types/{id}` | Get a single agent type |
| `PUT` | `/api/v1/agent-types/{id}` | Update an agent type |
| `DELETE` | `/api/v1/agent-types/{id}` | Delete an agent type (cannot delete default) |
| `POST` | `/api/v1/internal/run-complete` | Agent callback on run completion |
| `POST` | `/api/v1/internal/heartbeat` | Agent heartbeat callback |

### Modified Endpoints

- `POST /api/v1/tasks/{id}/trigger` — Now accepts optional `agent_type_id` to select which agent type runs the task. If omitted, the default agent type is used.

### Modified Response Fields

**Task** response now includes:
- `agent_type_id: string | null`

**AgentRun** response now includes:
- `ecs_task_arn: string | null`
- `error_message: string | null`
- `status` can now be `"launching"` in addition to existing values

### New Settings Endpoints

- `GET /api/v1/settings/env-vars` — Retrieve environment variables for agent runs
- `PUT /api/v1/settings/env-vars` — Update environment variables for agent runs

---

## Frontend Changes

- New **Agent Types** management page at `/agent-types`
- **Agent Type Selector** on task cards and stage controls
- **Container Status** badge showing ECS/local container state
- Updated log viewer with container status indicators
- Slack mentions now support `[agent-type]` tag syntax (e.g., `@Corsair [db-agent] fix the migration`)
- Environment variables configuration in Settings page

---

## Standalone Agent Container (new)

A new standalone agent container (`agent/`) can be built and deployed independently:

```bash
cd agent
docker build -t corsair-agent:local .
```

This container runs a single agent task, communicates with the control plane via callbacks, and exits when complete. It is designed for ECS Fargate execution but works locally too.

---

## Step-by-Step Upgrade

1. **Pull the latest code** and check out `v0.1.1_alpha`
2. **Apply database migrations** (SQL statements above)
3. **Update `.env`** with new variables from `.env.example`
4. **Run the seed script**: `python scripts/seed_agent_types.py`
5. **Rebuild Docker images**: `docker-compose up --build`
6. **(Optional)** Deploy Terraform infrastructure if using ECS
7. **Verify** the new Agent Types page loads at `/agent-types`
