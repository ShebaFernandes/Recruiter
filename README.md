# Enter Talent Platform

A connected Django REST Framework and React recruiting platform for candidates and recruiters. Candidate profiles and recruiter signals persist in PostgreSQL; resumes are extracted from real PDF/DOCX uploads and are accessed through authorized downloads.

## Local development

```bash
cp .env.example .env
uv sync
cd frontend && npm install && cd ..
docker compose up -d db
DATABASE_URL=postgresql://enter:enter@127.0.0.1:5433/enter uv run python backend/manage.py migrate
uv run python scripts/run_local.py
```

The local launcher starts Django, the frontend and the durable resume worker together.
It uses the local PostgreSQL queue and private files, disables external AI calls, and
restarts a stopped worker with bounded backoff. Keep this terminal open. Ctrl+C stops
the services started by the launcher. Apply pending local migrations first; ports
8010 and 5173 must be free. It does not deploy or change production configuration.

If the local UI and Django are already running and only the worker is missing:

```bash
uv run python scripts/run_local.py --worker-only
```

Direct local Django and worker commands load the repository `.env` without overriding values
already exported by the shell. Tests and staging/production do not load this local file.

For separate manual service terminals, start Django, the worker and frontend (all three
are required for asynchronous uploads). These direct commands use your `.env` AI settings:

```bash
DATABASE_URL=postgresql://enter:enter@127.0.0.1:5433/enter uv run python backend/manage.py runserver 127.0.0.1:8010
DATABASE_URL=postgresql://enter:enter@127.0.0.1:5433/enter uv run python backend/manage.py run_resume_worker
```

Run the frontend in a third terminal:

```bash
cd frontend
VITE_API_URL=http://127.0.0.1:8010/api/v1 npm run dev
```

Open `http://127.0.0.1:5173`. See `AGENTS.md` for verification commands and `DEPLOYMENT.md` for production configuration.

For a beginner-friendly explanation of the candidate backend, resume parsing, filters, security,
AI status and production limits, see [ENTER Candidate Backend Guide](docs/ENTER_CANDIDATE_BACKEND_GUIDE.md).
