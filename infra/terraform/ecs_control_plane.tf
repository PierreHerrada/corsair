resource "aws_ecs_task_definition" "control_plane" {
  family                   = "${var.project_name}-control-plane"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.control_plane_cpu
  memory                   = var.control_plane_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.control_plane_task.arn

  container_definitions = jsonencode([{
    name      = "control-plane"
    image     = "${aws_ecr_repository.control_plane.repository_url}:latest"
    essential = true

    portMappings = [
      { containerPort = 80, protocol = "tcp" },
      { containerPort = 8000, protocol = "tcp" },
    ]

    secrets = [
      { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn },
      { name = "ANTHROPIC_API_KEY", valueFrom = aws_secretsmanager_secret.anthropic_api_key.arn },
      { name = "SLACK_BOT_TOKEN", valueFrom = aws_secretsmanager_secret.slack_bot_token.arn },
      { name = "SLACK_APP_TOKEN", valueFrom = aws_secretsmanager_secret.slack_app_token.arn },
      { name = "GITHUB_TOKEN", valueFrom = aws_secretsmanager_secret.github_token.arn },
      { name = "JIRA_BASE_URL", valueFrom = aws_secretsmanager_secret.jira_base_url.arn },
      { name = "JIRA_EMAIL", valueFrom = aws_secretsmanager_secret.jira_email.arn },
      { name = "JIRA_API_TOKEN", valueFrom = aws_secretsmanager_secret.jira_api_token.arn },
      { name = "ADMIN_PASSWORD", valueFrom = aws_secretsmanager_secret.admin_password.arn },
      { name = "INTERNAL_API_SECRET", valueFrom = aws_secretsmanager_secret.internal_api_secret.arn },
    ]

    environment = [
      { name = "ECS_CLUSTER_ARN", value = aws_ecs_cluster.main.arn },
      { name = "INTERNAL_CALLBACK_URL", value = "http://control-plane.${var.project_name}.local:8000" },
      { name = "AWS_REGION", value = var.aws_region },
      { name = "ENVIRONMENT", value = "production" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.control_plane.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])
}

resource "aws_ecs_service" "control_plane" {
  name            = "${var.project_name}-control-plane"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.control_plane.arn
  desired_count   = 1

  capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
    base              = 1
  }

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.control_plane.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "control-plane"
    container_port   = 80
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "control-plane"
    container_port   = 8000
  }

  service_registries {
    registry_arn = aws_service_discovery_service.control_plane.arn
  }
}
