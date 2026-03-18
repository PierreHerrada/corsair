resource "aws_ecs_cluster" "main" {
  name = var.project_name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 3
  }

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
    base              = 1
  }
}

# --- CloudWatch Log Groups ---
resource "aws_cloudwatch_log_group" "control_plane" {
  name              = "/ecs/${var.project_name}/control-plane"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "agent" {
  name              = "/ecs/${var.project_name}/agent"
  retention_in_days = 14
}
