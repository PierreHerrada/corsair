output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "ecr_control_plane_url" {
  value = aws_ecr_repository.control_plane.repository_url
}

output "ecr_agent_url" {
  value = aws_ecr_repository.agent.repository_url
}

output "ecs_cluster_arn" {
  value = aws_ecs_cluster.main.arn
}

output "agent_task_definition_arns" {
  value = {
    default = aws_ecs_task_definition.agent_default.arn
    db      = aws_ecs_task_definition.agent_db.arn
    db_dind = aws_ecs_task_definition.agent_db_dind.arn
    aws     = aws_ecs_task_definition.agent_aws.arn
    datadog = aws_ecs_task_definition.agent_datadog.arn
  }
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "agent_security_group_ids" {
  value = {
    base = aws_security_group.agent_base.id
    db   = aws_security_group.agent_db.id
  }
}
