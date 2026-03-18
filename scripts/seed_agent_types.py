"""Seed the database with default agent types.

Usage:
    DATABASE_URL=postgres://... python scripts/seed_agent_types.py

Set the following env vars for real ARNs (or leave defaults for dev):
    ECS_CLUSTER_ARN, AWS_ACCOUNT_ID, AWS_REGION
"""

from __future__ import annotations

import asyncio
import os

from tortoise import Tortoise

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://corsair:corsair@localhost:5432/corsair")
ACCOUNT = os.environ.get("AWS_ACCOUNT_ID", "ACCOUNT")
REGION = os.environ.get("AWS_REGION", "eu-west-1")


SEED_TYPES = [
    {
        "name": "default",
        "display_name": "Default Agent",
        "description": "General-purpose software engineering agent",
        "ecs_task_definition": f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/corsair-agent-default",
        "capabilities": ["github"],
        "cpu": 1024,
        "memory": 2048,
        "max_duration_seconds": 3600,
        "is_default": True,
    },
    {
        "name": "db-agent",
        "display_name": "Database Agent",
        "description": "Agent with database access for migrations and queries",
        "ecs_task_definition": f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/corsair-agent-db",
        "capabilities": ["github", "database"],
        "cpu": 1024,
        "memory": 2048,
        "max_duration_seconds": 3600,
    },
    {
        "name": "db-agent-dind",
        "display_name": "Database Agent (Docker)",
        "description": "Database agent with Docker-in-Docker for Testcontainers",
        "ecs_task_definition": f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/corsair-agent-db-dind",
        "capabilities": ["github", "database", "dind"],
        "cpu": 2048,
        "memory": 4096,
        "max_duration_seconds": 3600,
        "enable_dind": True,
    },
    {
        "name": "aws-agent",
        "display_name": "AWS Agent",
        "description": "Agent with scoped AWS permissions",
        "ecs_task_definition": f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/corsair-agent-aws",
        "task_role_arn": f"arn:aws:iam::{ACCOUNT}:role/corsair-agent-aws",
        "capabilities": ["github", "aws"],
        "cpu": 1024,
        "memory": 2048,
        "max_duration_seconds": 3600,
    },
    {
        "name": "datadog-agent",
        "display_name": "Datadog Agent",
        "description": "Agent with Datadog API access for incident investigation",
        "ecs_task_definition": f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/corsair-agent-datadog",
        "capabilities": ["github", "datadog"],
        "cpu": 1024,
        "memory": 2048,
        "max_duration_seconds": 3600,
    },
]


async def seed() -> None:
    await Tortoise.init(
        db_url=DATABASE_URL,
        modules={"models": ["app.models.agent_type"]},
    )
    await Tortoise.generate_schemas()

    from app.models.agent_type import AgentType

    for data in SEED_TYPES:
        existing = await AgentType.filter(name=data["name"]).first()
        if existing:
            print(f"  Skipping '{data['name']}' (already exists)")
            continue
        await AgentType.create(**data)
        print(f"  Created '{data['name']}'")

    await Tortoise.close_connections()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(seed())
