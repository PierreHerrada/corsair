# Corsair

<p align="center">
  <a href="https://github.com/PierreHerrada/clipper-ai/actions/workflows/ci.yml"><img src="https://github.com/PierreHerrada/clipper-ai/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://codecov.io/gh/PierreHerrada/clipper-ai"><img src="https://codecov.io/gh/PierreHerrada/clipper-ai/branch/main/graph/badge.svg" alt="codecov"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://github.com/PierreHerrada/clipper-ai/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black" alt="React 19">
  <img src="https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/Tailwind_CSS-4.2-06B6D4?logo=tailwindcss&logoColor=white" alt="Tailwind CSS">
  <img src="https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white" alt="Docker">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/code%20style-ruff-261230?logo=ruff&logoColor=white" alt="Ruff">
  <img src="https://img.shields.io/badge/code%20style-prettier-F7B93E?logo=prettier&logoColor=black" alt="Prettier">
  <img src="https://img.shields.io/badge/testing-pytest-0A9EDC?logo=pytest&logoColor=white" alt="pytest">
  <img src="https://img.shields.io/badge/testing-vitest-6E9F18?logo=vitest&logoColor=white" alt="Vitest">
  <img src="https://img.shields.io/badge/coverage-%E2%89%A5%2080%25-success" alt="Coverage >= 80%">
</p>

**Corsair** is an open-source AI software engineering platform that bridges Slack, Jira, GitHub, and Claude Code into a unified workflow. Tag `@Corsair` in Slack, and it autonomously plans, codes, and opens a PR — with human approval at every stage.

![Screenshot placeholder](docs/screenshot-placeholder.png)

## Features

- **Slack-first workflow** — Tag `@Corsair` in any channel to create a task
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
                          ┌───────────────────────────────────────────────────────────┐
                          │                    Docker Image: corsair                  │
                          │                                                           │
                          │  ┌─────────────────────────────────────────────────────┐  │
                          │  │                    supervisord                      │  │
                          │  │                                                     │  │
 ┌───────────┐   :80      │  │  ┌──────────┐    static     ┌──────────────────┐    │  │
 │           │◀───────────┼──┼──│  nginx   │◀──── build ───│  React Frontend  │    │  │
 │  Browser  │            │  │  │          │               │  (TypeScript)    │    │  │
 │  (React   │   :8000    │  │  └──────────┘               └──────────────────┘    │  │
 │   UI)     │◀──── ws ───┼──┼──┐                                                  │  │
 └───────────┘            │  │  │  ┌──────────────────────────────────────────┐    │  │
                          │  │  │  │              FastAPI (uvicorn)           │    │  │
                          │  │  │  │                                          │    │  │
 ┌───────────┐  Socket    │  │  │  │  ┌────────┐  ┌───────────┐  ┌────────┐   │    │  │
 │   Slack   │◀── Mode ───┼──┼──┼──┼──│  REST  │  │ WebSocket │  │ Slack  │   │    │  │
 │ Workspace │            │  │  │  │  │  API   │  │  Server   │  │  Bot   │   │    │  │
 └───────────┘            │  │  │  │  └───┬────┘  └─────┬─────┘  └───┬────┘   │    │  │
                          │  │  │  │      │             │            │        │    │  │
                          │  │  │  │      ▼             ▼             ▼       │    │  │
                          │  │  │  │  ┌──────────────────────────────────┐    │    │  │
                          │  │  │  │  │          Core Services           │    │    │  │
                          │  │  │  │  │                                  │    │    │  │
                          │  │  │  │  │  ┌──────────────────────────┐    │    │    │  │
                          │  │  │  │  │  │   Three-Stage Pipeline   │    │    │    │  │
                          │  │  │  │  │  │   Plan → Work → Review   │    │    │    │  │
                          │  │  │  │  │  └──────────────────────────┘    │    │    │  │
                          │  │  │  │  │  ┌─────────┐  ┌─────────────┐    │    │    │  │
                          │  │  │  │  │  │  Auth   │  │Cost Tracker │    │    │    │  │
                          │  │  │  │  │  └─────────┘  └─────────────┘    │    │    │  │
                          │  │  │  │  └──────────────────────────────────┘    │    │  │
                          │  │  │  │                  │                       │    │  │
                          │  │  │  └──────────────────┼───────────────────────┘    │  │
                          │  │  │                     │                            │  │
                          │  │  └─────────────────────┼────────────────────────────┘  │
                          │  │                        │                               │
                          │  └────────────────────────┼───────────────────────────────┘
                          └───────────────────────────┼────────────────────────────────┘
                                                      │
                          ┌───────────────────────────┼────────────────────────────────┐
                          │            Integrations   │   (plugin architecture)        │
                          │                           │                                │
                          │    ┌──────────┐    ┌──────┴──────┐    ┌──────────────┐     │
                          │    │   Jira   │    │ Claude Code │    │    GitHub    │     │
                          │    │  Client  │    │ Subprocess  │    │   PR API     │     │
                          │    └─────┬────┘    └──────┬──────┘    └──────┬───────┘     │
                          │          │                │                  │             │
                          └──────────┼────────────────┼──────────────────┼─────────────┘
                                     ▼                ▼                  ▼
                              ┌────────────┐  ┌─────────────┐  ┌─────────────┐
                              │ Jira Cloud │  │  Anthropic  │  │   GitHub    │
                              │    API     │  │     API     │  │    API      │
                              └────────────┘  └─────────────┘  └─────────────┘

                          ┌────────────────────────────────────────────────────────────┐
                          │                      PostgreSQL (RDS)                      │
                          │    tasks │ stages │ cost_records │ users │ integrations    │
                          └────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Clone the repository
git clone https://github.com/PierreHerrada/corsair.git
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

## Contributors

<a href="https://github.com/PierreHerrada">
  <img src="https://github.com/PierreHerrada.png" width="50" style="border-radius:50%" alt="Pierre Herrada">
</a>

## License

[MIT](LICENSE)
