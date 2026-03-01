# Corsair

[![CI](https://github.com/PierreHerrada/clipper-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/PierreHerrada/clipper-ai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Corsair** is an open-source AI software engineering platform that bridges Slack, Jira, GitHub, and Claude Code into a unified workflow. Tag `@corsair` in Slack, and it autonomously plans, codes, and opens a PR — with human approval at every stage.

![Screenshot placeholder](docs/screenshot-placeholder.png)

## Features

- **Slack-first workflow** — Tag `@corsair` in any channel to create a task
- **Jira integration** — Automatically creates and tracks Jira tickets
- **Three-stage agent pipeline** — Plan → Work → Review, each manually triggered
- **Live log streaming** — Watch Claude Code work in real-time via WebSocket
- **Cost tracking** — Per-task and per-stage token usage and cost breakdown
- **GitHub PR automation** — Automatically opens PRs with Jira links
- **Kanban board UI** — Visual task management with drag-and-drop
- **Plugin architecture** — Add new integrations without touching core code
- **Single Docker image** — Easy deployment with supervisord + nginx + uvicorn

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Slack Bot  │────▶│  FastAPI API  │────▶│  PostgreSQL  │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                    ┌──────┴───────┐
                    │ Claude Code  │
                    │  Subprocess  │
                    └──────┬───────┘
                           │
                    ┌──────┴───────┐     ┌─────────────┐
                    │  WebSocket   │────▶│  React UI    │
                    └──────────────┘     └─────────────┘
                           │
                    ┌──────┴───────┐
                    │   GitHub     │
                    │   PR API     │
                    └──────────────┘
```

```
Docker Image: corsair
└── supervisord
    ├── uvicorn → FastAPI on :8000 (API + WebSocket + Slack bot)
    └── nginx   → React static build on :80
```

## Quick Start

```bash
# Clone the repository
git clone https://github.com/PierreHerrada/clipper-ai.git
cd clipper-ai

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your credentials

# Start with Docker Compose
docker-compose up --build
```

The UI will be available at `http://localhost` and the API at `http://localhost:8000`.

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `SLACK_BOT_TOKEN` | Slack bot OAuth token (`xoxb-...`) | For Slack |
| `SLACK_APP_TOKEN` | Slack app-level token (`xapp-...`) | For Slack |
| `JIRA_BASE_URL` | Jira instance URL | For Jira |
| `JIRA_EMAIL` | Jira account email | For Jira |
| `JIRA_API_TOKEN` | Jira API token | For Jira |
| `JIRA_PROJECT_KEY` | Jira project key (e.g., `SWE`) | For Jira |
| `GITHUB_TOKEN` | GitHub personal access token | For GitHub |
| `GITHUB_ORG` | GitHub organization name | For GitHub |
| `ADMIN_PASSWORD` | Admin password for the web UI | Yes |
| `ENVIRONMENT` | `development` or `production` | Yes |

## Connecting Integrations

### Slack
1. Create a Slack app at [api.slack.com](https://api.slack.com)
2. Enable Socket Mode and generate an app-level token
3. Add the `app_mentions:read` and `chat:write` scopes
4. Install the app to your workspace
5. Set `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` in your `.env`

### Jira
1. Generate an API token at [id.atlassian.com](https://id.atlassian.com)
2. Set `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, and `JIRA_PROJECT_KEY`

### GitHub
1. Create a personal access token with `repo` scope
2. Set `GITHUB_TOKEN` and `GITHUB_ORG`

Integrations are opt-in: if env vars are missing, the integration is simply inactive — the app still boots.

See [INTEGRATIONS.md](INTEGRATIONS.md) for adding new integrations.

## Development

```bash
# Backend
cd backend
pip install -r requirements.txt
pytest tests/ --cov=app --cov-fail-under=80
ruff check app/ tests/
ruff format app/ tests/

# Frontend
cd frontend
npm ci
npm test -- --coverage
npm run lint
npm run build
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, and PR process.

## Why "Corsair"?

A **corsair** was a privateer that roamed the Mediterranean — fast, autonomous, and lethal effective without a fleet behind it. No admiral on the radio. No convoy required. Just a single ship, a mission, and the skill to get it done.

That's exactly what this project does. You drop a task in Slack, and Corsair sails through plan, code, and PR on its own — no hand-holding, no babysitting.

The name stuck for a few reasons:

- **Autonomous by nature** — corsairs operated independently across open water; this agent operates independently across your entire toolchain.
- **Mediterranean roots** — the project was born in Barcelona, a city built by the sea, where corsair history is part of the harbour walls. The creator loves boats. It fits.
- **Short, sharp, universal** — seven letters, works in every language, no existing dev tool claiming it for this purpose.

Some software needs a fleet. Corsair just needs a heading.

## License

[MIT](LICENSE)
