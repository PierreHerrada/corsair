# Secrets Manager entries — values are set manually or via CI
# Terraform only manages the secret resource, not the secret value

resource "aws_secretsmanager_secret" "database_url" {
  name = "${var.project_name}/database-url"
}

resource "aws_secretsmanager_secret" "anthropic_api_key" {
  name = "${var.project_name}/anthropic-api-key"
}

resource "aws_secretsmanager_secret" "github_token" {
  name = "${var.project_name}/github-token"
}

resource "aws_secretsmanager_secret" "slack_bot_token" {
  name = "${var.project_name}/slack-bot-token"
}

resource "aws_secretsmanager_secret" "slack_app_token" {
  name = "${var.project_name}/slack-app-token"
}

resource "aws_secretsmanager_secret" "jira_base_url" {
  name = "${var.project_name}/jira-base-url"
}

resource "aws_secretsmanager_secret" "jira_email" {
  name = "${var.project_name}/jira-email"
}

resource "aws_secretsmanager_secret" "jira_api_token" {
  name = "${var.project_name}/jira-api-token"
}

resource "aws_secretsmanager_secret" "admin_password" {
  name = "${var.project_name}/admin-password"
}

resource "aws_secretsmanager_secret" "internal_api_secret" {
  name = "${var.project_name}/internal-api-secret"
}

resource "aws_secretsmanager_secret" "dd_api_key" {
  name = "${var.project_name}/dd-api-key"
}

resource "aws_secretsmanager_secret" "dd_app_key" {
  name = "${var.project_name}/dd-app-key"
}
