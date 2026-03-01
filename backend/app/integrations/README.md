# Integrations

This directory contains all Corsair integrations. Each integration is a self-contained module that implements `BaseIntegration`.

## Structure

```
integrations/
├── base.py          # Abstract base class
├── registry.py      # Discovery + initialization
├── slack/           # Slack bot integration
├── jira/            # Jira ticket management
└── github/          # GitHub PR creation
```

## Adding a New Integration

1. Create a new directory: `integrations/{name}/`
2. Add `__init__.py`, `client.py`, and `tests/` directory
3. Implement `BaseIntegration` in `client.py`:

```python
from app.integrations.base import BaseIntegration

class MyIntegration(BaseIntegration):
    name = "my-service"
    description = "What it does"
    required_env_vars = ["MY_SERVICE_API_KEY"]

    async def health_check(self) -> bool:
        # Check connectivity
        ...
```

4. Import and add to `_DEFAULT_INTEGRATIONS` in `registry.py`
5. Write tests in `integrations/{name}/tests/` — always mock external APIs
6. Update `INTEGRATIONS.md` at the repo root

## Rules

- Never call real external APIs in tests
- All integrations are opt-in via env vars
- Missing env vars = inactive, app still boots
- Each integration must implement `health_check()`
