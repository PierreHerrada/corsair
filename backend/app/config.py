from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgres://corsair:corsair@localhost:5432/corsair"

    # Anthropic
    anthropic_api_key: str = ""

    # Slack
    slack_bot_token: str = ""
    slack_app_token: str = ""

    # Jira
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = "SWE"
    jira_sync_interval_seconds: int = 300
    jira_sync_label: str = "corsair"

    # Datadog
    dd_api_key: str = ""
    dd_app_key: str = ""
    dd_site: str = "datadoghq.com"

    # GitHub
    github_token: str = ""
    github_org: str = ""

    # Workspaces
    workspace_base_dir: str = "/home/corsair/workspaces"

    # App
    admin_password: str = "changeme"
    jwt_secret: str = "change-this-jwt-secret-in-production"
    environment: str = "development"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
