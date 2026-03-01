---
name: New Integration
about: Propose a new integration for Corsair
title: "[INTEGRATION] "
labels: integration
assignees: ''
---

## Integration Name
Name of the service (e.g., Linear, GitLab, Discord).

## Service URL
Link to the service's website and API documentation.

## Use Case
How would this integration be used within Corsair? What workflow does it enable?

## Required Environment Variables
List the env vars this integration would need:
- `SERVICE_API_KEY` — API key for authentication
- `SERVICE_URL` — Base URL of the service

## Proposed API Surface
What methods would this integration expose?

```python
class MyIntegration(BaseIntegration):
    name = "my-service"
    description = "..."
    required_env_vars = ["SERVICE_API_KEY", "SERVICE_URL"]

    async def health_check(self) -> bool: ...
    # What other methods?
```

## Willingness to Implement
- [ ] I am willing to submit a PR for this integration
- [ ] I need help implementing this

## Additional Context
Any relevant links, screenshots, or notes.
