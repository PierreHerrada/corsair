# --- Default Agent ---
resource "aws_ecs_task_definition" "agent_default" {
  family                   = "${var.project_name}-agent-default"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.agent_default_cpu
  memory                   = var.agent_default_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.agent_default.arn

  container_definitions = jsonencode([{
    name      = "agent"
    image     = "${aws_ecr_repository.agent.repository_url}:latest"
    essential = true

    secrets = [
      { name = "ANTHROPIC_API_KEY", valueFrom = aws_secretsmanager_secret.anthropic_api_key.arn },
      { name = "GITHUB_TOKEN", valueFrom = aws_secretsmanager_secret.github_token.arn },
      { name = "INTERNAL_API_SECRET", valueFrom = aws_secretsmanager_secret.internal_api_secret.arn },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.agent.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "default"
      }
    }
  }])
}

# --- DB Agent ---
resource "aws_ecs_task_definition" "agent_db" {
  family                   = "${var.project_name}-agent-db"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.agent_default_cpu
  memory                   = var.agent_default_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.agent_default.arn

  container_definitions = jsonencode([{
    name      = "agent"
    image     = "${aws_ecr_repository.agent.repository_url}:latest"
    essential = true

    secrets = [
      { name = "ANTHROPIC_API_KEY", valueFrom = aws_secretsmanager_secret.anthropic_api_key.arn },
      { name = "GITHUB_TOKEN", valueFrom = aws_secretsmanager_secret.github_token.arn },
      { name = "INTERNAL_API_SECRET", valueFrom = aws_secretsmanager_secret.internal_api_secret.arn },
      { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.agent.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "db"
      }
    }
  }])
}

# --- DB Agent with DinD (Docker-in-Docker for Testcontainers) ---
resource "aws_ecs_task_definition" "agent_db_dind" {
  family                   = "${var.project_name}-agent-db-dind"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.agent_db_dind_cpu
  memory                   = var.agent_db_dind_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.agent_default.arn

  container_definitions = jsonencode([
    {
      name      = "dind"
      image     = "docker:25-dind"
      essential = true

      privileged = true

      command = ["dockerd", "--host=tcp://0.0.0.0:2375", "--tls=false"]

      portMappings = [{ containerPort = 2375, protocol = "tcp" }]

      healthCheck = {
        command     = ["CMD-SHELL", "docker info || exit 1"]
        interval    = 10
        timeout     = 5
        retries     = 5
        startPeriod = 15
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.agent.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "dind"
        }
      }
    },
    {
      name      = "agent"
      image     = "${aws_ecr_repository.agent.repository_url}:latest"
      essential = true

      dependsOn = [{ containerName = "dind", condition = "HEALTHY" }]

      environment = [
        { name = "DOCKER_HOST", value = "tcp://localhost:2375" },
      ]

      secrets = [
        { name = "ANTHROPIC_API_KEY", valueFrom = aws_secretsmanager_secret.anthropic_api_key.arn },
        { name = "GITHUB_TOKEN", valueFrom = aws_secretsmanager_secret.github_token.arn },
        { name = "INTERNAL_API_SECRET", valueFrom = aws_secretsmanager_secret.internal_api_secret.arn },
        { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.agent.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "db-dind"
        }
      }
    },
  ])
}

# --- AWS Agent ---
resource "aws_ecs_task_definition" "agent_aws" {
  family                   = "${var.project_name}-agent-aws"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.agent_default_cpu
  memory                   = var.agent_default_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.agent_aws.arn

  container_definitions = jsonencode([{
    name      = "agent"
    image     = "${aws_ecr_repository.agent.repository_url}:latest"
    essential = true

    secrets = [
      { name = "ANTHROPIC_API_KEY", valueFrom = aws_secretsmanager_secret.anthropic_api_key.arn },
      { name = "GITHUB_TOKEN", valueFrom = aws_secretsmanager_secret.github_token.arn },
      { name = "INTERNAL_API_SECRET", valueFrom = aws_secretsmanager_secret.internal_api_secret.arn },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.agent.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "aws"
      }
    }
  }])
}

# --- Datadog Agent ---
resource "aws_ecs_task_definition" "agent_datadog" {
  family                   = "${var.project_name}-agent-datadog"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.agent_default_cpu
  memory                   = var.agent_default_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.agent_default.arn

  container_definitions = jsonencode([{
    name      = "agent"
    image     = "${aws_ecr_repository.agent.repository_url}:latest"
    essential = true

    secrets = [
      { name = "ANTHROPIC_API_KEY", valueFrom = aws_secretsmanager_secret.anthropic_api_key.arn },
      { name = "GITHUB_TOKEN", valueFrom = aws_secretsmanager_secret.github_token.arn },
      { name = "INTERNAL_API_SECRET", valueFrom = aws_secretsmanager_secret.internal_api_secret.arn },
      { name = "DD_API_KEY", valueFrom = aws_secretsmanager_secret.dd_api_key.arn },
      { name = "DD_APP_KEY", valueFrom = aws_secretsmanager_secret.dd_app_key.arn },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.agent.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "datadog"
      }
    }
  }])
}
