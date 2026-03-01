# Corsair — Claude Code Instructions

## Project Overview
Corsair is a production-ready, open-source AI software engineering platform.
Single Docker image. FastAPI backend. React frontend. PostgreSQL on RDS.

## Build Phases
Always check LESSONS.md before starting any phase.
Always check docs/api-contract.md before touching any API code.
Always check docs/data-models.md before touching any model code.

## Commands

### Backend
cd backend
pytest tests/ --cov=app --cov-fail-under=80   # run all tests
ruff check app/ tests/                          # lint
ruff format app/ tests/                         # format
aerich migrate                                  # generate migration
aerich upgrade                                  # apply migration

### Frontend
cd frontend
npm test -- --coverage                          # run all tests
npm run lint                                    # ESLint
npm run format                                  # Prettier
npm run build                                   # production build

### Docker
docker-compose up --build                       # full local stack
docker-compose run backend pytest               # tests in container

## Critical Rules
- Never hardcode secrets or URLs
- Never call real external APIs in tests — always mock
- Coverage must be ≥ 80% before moving to the next phase
- Read LESSONS.md before starting any new task
- Update LESSONS.md immediately when you encounter and resolve any error
- Every new integration must have its own directory under backend/app/integrations/
- API shapes must exactly match docs/api-contract.md — do not improvise
