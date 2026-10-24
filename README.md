# Enter Talent Platform

A connected Django REST Framework and React recruiting platform for candidates and recruiters. Candidate profiles and recruiter signals persist in PostgreSQL; resumes are extracted from real PDF/DOCX uploads and are accessed through authorized downloads.

## Local development

```bash
cp .env.example .env
uv sync
cd frontend && npm install && cd ..
docker compose up -d db
DATABASE_URL=postgresql://enter:enter@127.0.0.1:5433/enter uv run python backend/manage.py migrate
DATABASE_URL=postgresql://enter:enter@127.0.0.1:5433/enter uv run python backend/manage.py runserver 127.0.0.1:8010
```

Direct local Django and worker commands load the repository `.env` without overriding values
already exported by the shell. Tests and staging/production do not load this local file.

Run the durable local resume worker in another terminal:

```bash
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
