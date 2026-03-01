# Integrations

Corsair uses a plugin-based integration system. Each integration is a self-contained module under `backend/app/integrations/` that implements the `BaseIntegration` interface.

## Current Integrations

| Integration | Status | Required Env Vars | Description |
|---|---|---|---|
| **Slack** | Active | `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` | Receives task requests via `@corsair` mentions, posts status updates to threads |
| **Jira** | Active | `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY` | Creates and tracks Jira tickets for each task |
| **GitHub** | Active | `GITHUB_TOKEN`, `GITHUB_ORG` | Opens pull requests after the review stage completes |

Integrations are **opt-in via environment variables**. If the required env vars for an integration are not set, the integration is simply marked as inactive — the app still boots and all other integrations continue to work.

## Adding a New Integration

### Step 1: Create the integration directory

```
backend/app/integrations/{name}/
├── __init__.py
├── client.py
└── tests/
    ├── __init__.py
    └── test_{name}.py
```

### Step 2: Implement `BaseIntegration`

```python
# backend/app/integrations/{name}/client.py
from app.integrations.base import BaseIntegration

class MyIntegration(BaseIntegration):
    name = "my-integration"
    description = "Short description of what it does"
    required_env_vars = ["MY_INTEGRATION_API_KEY", "MY_INTEGRATION_URL"]

    async def health_check(self) -> bool:
        # Return True if the integration is reachable
        ...
```

### Step 3: Declare `required_env_vars`

List every environment variable the integration needs. The registry will check these at startup and mark the integration as inactive if any are missing.

### Step 4: Register in `registry.py`

Import your integration class in the registry so it is discovered at startup:

```python
# backend/app/integrations/registry.py
from app.integrations.{name}.client import MyIntegration

INTEGRATIONS = [
    # ... existing integrations
    MyIntegration,
]
```

### Step 5: Write tests

Place tests under `integrations/{name}/tests/`. Mock all external API calls — never hit real services in tests.

### Step 6: Update this table

Add your integration to the table at the top of this file with its status, required env vars, and description.

## Architecture

The integration system is designed around three principles:

1. **Self-contained** — Each integration is a standalone directory. No integration logic leaks into core code.
2. **Opt-in** — Missing env vars = inactive integration. The app always boots.
3. **Discoverable** — The registry auto-detects integrations and exposes their status via `GET /api/v1/integrations`.
