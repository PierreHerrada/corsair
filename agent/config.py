from pydantic_settings import BaseSettings


class AgentConfig(BaseSettings):
    task_id: str
    agent_run_id: str
    stage: str
    repo_url: str
    branch: str = "main"
    callback_url: str
    internal_api_secret: str
    anthropic_api_key: str
    max_duration_seconds: int = 3600
    github_token: str = ""
    work_dir: str = "/home/corsair/workspaces"
    prompt_override: str = ""
    docker_host: str = ""
    task_description: str = ""
    plan_output: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}
