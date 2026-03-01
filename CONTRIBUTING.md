# Contributing to Corsair

Thank you for your interest in contributing to Corsair! This guide will help you get set up and understand our development workflow.

## Local Development Setup

### Prerequisites
- Python 3.12+
- Node.js 20+
- PostgreSQL 15+
- Docker and Docker Compose (optional, for containerized development)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest tests/ --cov=app --cov-fail-under=80

# Lint and format
ruff check app/ tests/
ruff format app/ tests/

# Run migrations
aerich upgrade
```

### Frontend

```bash
cd frontend
npm ci

# Run tests
npm test -- --coverage

# Lint and format
npm run lint
npm run format

# Development server
npm run dev

# Production build
npm run build
```

### Docker (full stack)

```bash
cp .env.example .env
# Edit .env with your credentials
docker-compose up --build
```

## Branch Naming

Use the following prefixes:
- `feature/` — New features
- `fix/` — Bug fixes
- `chore/` — Maintenance tasks (deps, CI, docs)
- `integration/` — New integrations

Examples: `feature/dark-mode`, `fix/websocket-reconnect`, `integration/linear`

## Pull Request Process

1. Fork the repository and create your branch from `main`
2. Write tests for any new functionality
3. Ensure all tests pass and coverage is >= 80%
4. Run linting (`ruff check` for Python, `npm run lint` for TypeScript)
5. Update documentation if your change affects setup or usage
6. Open a PR with a clear title and description
7. Link any related issues

## Code Style

### Python (Backend)
- **Formatter:** ruff format
- **Linter:** ruff check
- Follow PEP 8 conventions
- Use type hints for function signatures
- Use `async`/`await` consistently

### TypeScript (Frontend)
- **Formatter:** Prettier
- **Linter:** ESLint
- Use functional components with hooks
- Use TypeScript strict mode
- Import types explicitly

## Testing

- **Backend:** pytest + pytest-asyncio
- **Frontend:** Vitest + React Testing Library
- **Coverage minimum:** 80% (enforced by CI)
- **Mocking:** Never call real external APIs in tests — always mock

## Adding Integrations

See [INTEGRATIONS.md](INTEGRATIONS.md) for a step-by-step guide on adding new integrations. The plugin system makes it possible to add integrations without modifying core code.

## Reporting Issues

- **Bugs:** Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md)
- **Features:** Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md)
- **New integrations:** Use the [integration template](.github/ISSUE_TEMPLATE/new_integration.md)

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting.
