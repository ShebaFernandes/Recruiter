# Deploying Enter Talent Platform

## Recommended architecture

Deploy the React build behind a CDN or HTTPS web server, Django/Gunicorn as a private application service, PostgreSQL as a managed database, and resumes in a private S3-compatible bucket (Amazon S3, Cloudflare R2, or equivalent). Route a public API hostname to Django and a separate application hostname to React. Keep the database and object store off the public network.

## Environment

Start from `.env.example`. Set a long, random `DJANGO_SECRET_KEY`, `DEBUG=false`, a TLS-enabled PostgreSQL `DATABASE_URL`, the public `FRONTEND_URL`, exact `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, and `CSRF_TRUSTED_ORIGINS`. Build React with `VITE_API_URL=https://api.example.com/api/v1`.

Production startup intentionally fails without `AWS_STORAGE_BUCKET_NAME`. Configure the bucket, region, optional S3-compatible endpoint, access key, and secret key. The bucket must block public access; Django generates short-lived signed access internally and serves downloads only after authorization. Use a narrowly scoped service credential. Configure the SMTP variables for transactional email groundwork. Never place credentials in images, source control, or frontend variables.

Candidate signup requires transactional email. Configure a verified `DEFAULT_FROM_EMAIL` and a production SMTP backend before beta. Verification links expire after `EMAIL_VERIFICATION_TOKEN_TTL_SECONDS` (24 hours by default), password-reset links after `PASSWORD_RESET_TOKEN_TTL_SECONDS` (one hour), and authenticated API sessions after `AUTH_TOKEN_TTL_SECONDS` (seven days). Tokens are random, stored only as hashes, single-use, and invalidated when replaced. Update `SUBMISSION_CONSENT_VERSION` only after legal review when the consent language materially changes.

The `/privacy` and `/terms` frontend routes are explicitly marked placeholders. Replace them with counsel-reviewed policies before public launch.

Candidate account deletion is a hard deletion. After password and typed confirmation, Django deletes every stored resume object first and then cascades deletion through the candidate user, profile, work history, recruiter signals, notifications, tokens, and related database records. If object-storage deletion fails, the endpoint returns an error and retains the database account so the candidate can retry or support can intervene. Production storage credentials therefore require object-delete permission in addition to private read/write access.

## Backend

Build `backend/Dockerfile` from the repository root. Before serving traffic, run:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60
```

The container entrypoint performs these steps. In orchestrated production, prefer a one-off migration job before rolling out web instances. Mount no resume volume in production; private object storage is required. Check `/api/v1/health/` from the load balancer. Scale Gunicorn horizontally and send application logs to the platform without logging tokens, resume text, or candidate contact details.

## Frontend

Build `frontend/Dockerfile` with the public API URL:

```bash
docker build -f frontend/Dockerfile \
  --build-arg VITE_API_URL=https://api.example.com/api/v1 \
  -t enter-frontend frontend
```

The final image serves the static Vite build through Nginx with history fallback and baseline security headers. Terminate HTTPS at the CDN/load balancer, redirect HTTP to HTTPS, and add the production content-security policy at that edge after confirming allowed analytics/font origins.

## Database, domains, and rollout

Provision PostgreSQL 15+ with automated backups, point `DATABASE_URL` at it, and restrict ingress to Django. Create DNS records for the app and API, issue certificates, and set `SECURE_SSL_REDIRECT=true` plus an appropriate `SECURE_HSTS_SECONDS`. Run backend tests, frontend tests/lint/build, and Playwright against a staging domain. Then migrate, deploy the backend, deploy the frontend, verify signup and a private resume download, and monitor errors. Roll back application images independently; never roll back a destructive migration without a reviewed reverse-data plan.

`compose.yaml` is a reproducible local stack, not the recommended public production topology. It exposes PostgreSQL on local port 5433, Django on 8010, and the frontend on 5173.
