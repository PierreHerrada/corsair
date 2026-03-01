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

    # GitHub
    github_token: str = ""
    github_org: str = ""

    # App
    admin_password: str = "changeme"
    environment: str = "development"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
