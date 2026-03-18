data "aws_caller_identity" "current" {}

# --- ECS Execution Role (shared) ---
resource "aws_iam_role" "ecs_execution" {
  name = "${var.project_name}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_policy" "ecs_execution_secrets" {
  name = "${var.project_name}-ecs-execution-secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_secrets" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = aws_iam_policy.ecs_execution_secrets.arn
}

# --- Control Plane Task Role ---
resource "aws_iam_role" "control_plane_task" {
  name = "${var.project_name}-control-plane-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_policy" "control_plane_task" {
  name = "${var.project_name}-control-plane-task"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:RunTask",
          "ecs:StopTask",
          "ecs:DescribeTasks",
        ]
        Resource = "*"
        Condition = {
          StringEquals = { "ecs:cluster" = aws_ecs_cluster.main.arn }
        }
      },
      {
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.project_name}-agent-*"
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "control_plane_task" {
  role       = aws_iam_role.control_plane_task.name
  policy_arn = aws_iam_policy.control_plane_task.arn
}

# --- Agent Task Roles ---
resource "aws_iam_role" "agent_default" {
  name = "${var.project_name}-agent-default"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role" "agent_aws" {
  name = "${var.project_name}-agent-aws"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# Scoped AWS permissions for the aws-agent
resource "aws_iam_policy" "agent_aws" {
  name = "${var.project_name}-agent-aws"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket",
        "cloudwatch:GetMetricData",
        "logs:GetLogEvents",
        "logs:FilterLogEvents",
      ]
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "agent_aws" {
  role       = aws_iam_role.agent_aws.name
  policy_arn = aws_iam_policy.agent_aws.arn
}
