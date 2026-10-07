# Repository Guidelines

## Project Structure & Module Organization

`frontend/` contains the Vite, React, and TypeScript client. Product UI is in `frontend/src/App.tsx`, shared API/types live beside it, browser acceptance tests are in `frontend/tests/`, and static assets are in `frontend/public/`. `backend/` contains the Django project (`config/`) and the `talent` application. Models, serializers, business parsers/search scoring, API views, migrations, and tests live under `backend/talent/` and `backend/tests/`. Root configuration includes `pyproject.toml`, `compose.yaml`, `.env.example`, and `DEPLOYMENT.md`.

## Build, Test, and Development Commands

- `uv sync` installs Python dependencies; `cd frontend && npm install` installs UI dependencies.
- `docker compose up -d db` starts PostgreSQL on port 5433.
- `DATABASE_URL=postgresql://enter:enter@127.0.0.1:5433/enter uv run python backend/manage.py migrate` applies migrations.
- `uv run python backend/manage.py runserver 127.0.0.1:8010` starts Django.
- `uv run python backend/manage.py run_resume_worker` starts the durable local/SQS resume worker.
- `cd frontend && VITE_API_URL=http://127.0.0.1:8010/api/v1 npm run dev` starts React.
- `uv run pytest -q`, `uv run ruff check .`, `cd frontend && npm run test`, `npm run lint`, and `npm run build` verify changes.
- With both servers running, `cd frontend && npm run test:e2e` runs browser flows.

## Coding Style & Naming Conventions

Use Ruff’s 100-character Python line length and Django conventions: snake_case functions, PascalCase models, and thin API views backed by service functions. TypeScript is strict. React components and types use PascalCase; functions and state use camelCase. Extend the existing CSS variables and reusable UI patterns before introducing new styling systems.

## Testing Guidelines

Pytest-django tests are named `test_*.py` under `backend/tests/`. Vitest covers components; Playwright specs end in `.spec.ts`. Test authorization, persistence, errors, and the complete user path—not only happy-path rendering.

## Commit & Pull Request Guidelines

No Git history is included in this snapshot. Use concise imperative commits (for example, `Add recruiter status persistence`). PRs should explain scope, linked issues, migrations/configuration, test evidence, and include screenshots for UI changes.

## Security & Agent-Specific Instructions

Copy `.env.example`; never commit secrets or resume contents. Production requires private S3-compatible storage. Inspect existing code before replacing it, extend reusable components, run relevant tests, visually verify frontend work, exercise backend APIs, and never claim untested behavior works.
