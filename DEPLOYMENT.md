# Deploying Enter Talent Platform

## Proposed AWS staging architecture

Use Route 53 and ACM for `app.example.com`. Serve the versioned React build from a private S3 origin through CloudFront and route CloudFront's `/api/*` behavior to an ALB in front of Django. Forward all API methods, the auth/CSRF cookies, `X-CSRFToken`, `Content-Type`, and required query strings; disable caching for authenticated API responses. This same-origin design permits a strict `connect-src 'self'` CSP and avoids cross-site auth cookies. Run separate Django **web** and **resume-worker** ECS/Fargate services in private subnets. Use RDS PostgreSQL Multi-AZ as budget permits, a private S3 resume bucket with Block Public Access, SQS with a dead-letter queue, SES/SMTP for account email, Secrets Manager or SSM Parameter Store for secrets, and CloudWatch for logs, metrics, and alarms.

The browser never receives a permanent resume URL. Django authorizes `/api/v1/resumes/<id>/download/` and reads the private object. Web and worker task roles should be separate and least-privileged. No AWS resources are created by this repository.

### Resource checklist (create only after approval)

- Route 53 DNS record(s), one ACM certificate, and one CloudFront distribution with an Origin Access Control and a response-headers policy mirroring `frontend/nginx.conf`.
- One private S3 frontend-artifact bucket and one separate private resume bucket with Block Public Access and encryption.
- One ECR repository for the backend image; one ECS cluster with web and worker task definitions/services plus a one-off migration task definition.
- One ALB, HTTPS listener, web target group, VPC, public/private subnets, route tables, security groups, and only the endpoints/NAT egress the chosen design requires.
- One RDS PostgreSQL instance/cluster, subnet group, parameter group, credentials secret, automated backups, and deletion protection according to the approved environment tier.
- One encrypted standard SQS queue and one encrypted DLQ with a redrive policy.
- One private ClamAV scanner task/service (or an approved managed scanner integration) and signature-update path.
- SES verified identity/configuration set (or approved SMTP provider), Secrets Manager/SSM parameters, IAM task/execution roles, CloudWatch log groups, metrics/alarms, and an EventBridge schedule for throttle-bucket cleanup.

## Images and services

Build `backend/Dockerfile` once and run it with two commands:

```bash
# Web service
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60

# Worker service
python manage.py run_resume_worker
```

The image collects static files at build time. It intentionally does **not** migrate on startup. Build the frontend with `VITE_API_URL=/api/v1`; deploy its immutable output or `frontend/Dockerfile`. If a separately hosted API is unavoidable, replace the CSP with the exact API origin and configure exact CORS/CSRF origins—never broaden `connect-src` to all HTTPS destinations.

## Required release order and migrations

Before shifting traffic to an image that requires new schema, run exactly one one-off task with the new backend image:

```bash
python manage.py migrate --noinput
python manage.py migrate --check
python manage.py check --deploy
```

Require successful task exit before updating web or worker services. Never run migrations in each Gunicorn replica. Back up RDS before destructive migrations. Prefer additive/backward-compatible schema changes, deploy code, backfill if required, and remove old schema in a later release.

## Resume queue and scanning lifecycle

Uploads enter the private S3 bucket under a `quarantine/` key. Django writes `Resume` and `ResumeProcessingJob` rows transactionally, then publishes `{job_id, idempotency_key}` to SQS. PostgreSQL is the durable outbox: unsent queued jobs are republished by the worker. The worker claims the row under a database lock, scans the object, promotes clean files to `resumes/<candidate>/<resume>/`, extracts PDF/DOCX content, updates the existing profile, and marks the job complete. Duplicate delivery is harmless. Transient failures use bounded exponential retry; stale `PROCESSING` locks are reclaimable. Terminal failures stay private and candidates can safely retry unless the scanner marked the object infected.

Create a standard SQS queue with a visibility timeout longer than `RESUME_PROCESSING_TIMEOUT_SECONDS`, long polling, server-side encryption, and a redrive policy to a DLQ. Set `RESUME_SQS_VISIBILITY_TIMEOUT_SECONDS` above the worst expected scan/extraction time. Alarm on oldest-message age, DLQ depth, terminal job count, and workers with no healthy tasks. Scale workers from SQS backlog/age; begin with one task and conservative CPU/memory, then validate extraction throughput before increasing concurrency.

`RESUME_SCANNER_BACKEND=clamav` uses the ClamAV INSTREAM protocol. Run the scanner as a private sidecar/service reachable only from workers, update signatures continuously, and fail closed if unavailable. The local `development` scanner only exercises state transitions and is rejected when `DEBUG=false`; it is not malware protection.

## Data and secrets

Start from `.env.example`; inject values at runtime, never into images or frontend variables.

- `DATABASE_URL`: TLS RDS PostgreSQL endpoint; restrict security-group ingress to tasks.
- `AWS_STORAGE_BUCKET_NAME`, region: private S3 bucket. Prefer IAM task roles and omit static access keys on ECS.
- `RESUME_QUEUE_BACKEND=sqs`, `RESUME_SQS_QUEUE_URL`, region: encrypted queue and task-role permissions.
- `RESUME_SCANNER_BACKEND=clamav`, host/port: private scanner endpoint.
- `DJANGO_SECRET_KEY`, SMTP credentials: Secrets Manager/SSM references.
- `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL`: the exact public HTTPS app origin/host only.
- `AUTH_COOKIE_SECURE=true`, `AUTH_COOKIE_SAMESITE=Lax`, `SECURE_SSL_REDIRECT=true`, and HSTS after HTTPS is verified.
- `RATE_LIMIT_TRUST_X_FORWARDED_FOR=true` only when the ALB is configured in append mode; the application uses the right-most observed address and ignores spoofable left-most values.
- SMTP/SES variables and a verified `DEFAULT_FROM_EMAIL`; production signup depends on email delivery.
- `AI_PROVIDER=openai|openrouter`, the selected provider's API key, and an approved
  structured-output-capable model. Store the key in Secrets Manager/SSM, never the frontend.
- OpenAI uses `OPENAI_API_KEY`, `OPENAI_SEARCH_MODEL`, and `OPENAI_API_BASE_URL`.
- OpenRouter uses `OPENROUTER_API_KEY`, `OPENROUTER_SEARCH_MODEL`,
  `OPENROUTER_API_BASE_URL`, `OPENROUTER_HTTP_REFERER`, and `OPENROUTER_APP_TITLE`.
- `AI_ALLOW_DETERMINISTIC_FALLBACK=false`: staging/production fails clearly when the
  selected provider is unavailable instead of silently presenting deterministic parsing as AI.

Keep S3 Block Public Access enabled, use SSE-S3 or SSE-KMS, disable ACLs, and grant web read only if downloads remain web-served. Grant workers quarantine read/delete and promoted-object read/write. Add a reviewed lifecycle rule only after the retention policy exists. RDS backups, point-in-time recovery, backup retention, restore testing, and deletion protection are product decisions, not repository defaults.

Recruiter queries are interpreted server-side through a provider adapter. OpenAI uses the
Responses API; OpenRouter uses Chat Completions with `response_format=json_schema` and
`require_parameters=true`. Both responses pass through the same strict application validator
before reaching Django search logic. Only the recruiter's search sentence and clarification
context are sent; candidate profiles and resumes are not sent to either integration. Restrict
and rotate provider keys, monitor latency/error/cost, and give ECS tasks controlled outbound
HTTPS access. Local development may explicitly opt into the named deterministic fallback; it
is recorded as `understanding_source=deterministic_fallback` and is disabled by default.
Production configuration rejects fallback mode so the product never presents fixed parsing
as AI.

Successful real requests emit a redacted log event such as
`ai_search_provider_success provider=openrouter model=<model> request_id=<id>`. Fallbacks emit
`ai_search_provider_fallback provider=openrouter error=<category>`. No prompt, candidate data,
or API key is included in either event.

## Health, logging, and monitoring

Use `/api/v1/health/` for ALB liveness and `/api/v1/health/ready/` for database/config readiness. ECS process health supervises the worker; queue-age and job-state alarms verify useful worker progress. Logs go to stdout for CloudWatch and pass through a credential redaction filter. Do not log request bodies, resume text, auth cookies, tokens, or candidate contact fields. Configure alarms for 5xx rate, latency, task restarts, database capacity/connections, SQS age/DLQ, email failures, scan failures, and terminal resume jobs.

Run `python manage.py purge_rate_limit_buckets --older-than-hours 48` daily as an EventBridge-scheduled one-off ECS task so fixed-window throttle rows do not grow indefinitely.

## Search scale boundary

Discovery eligibility, scalar filters, skills/work-preference JSON checks, and recruiter stage/view filters now execute in PostgreSQL; scalar and recruiter-state paths have targeted B-tree indexes, with GIN indexes available for exact JSON containment paths. The current case-insensitive JSON membership query may still scan filtered JSON values, relevance scoring/final sorting run in Python, and the response is not paginated. This is appropriate for staging and a controlled beta, not an unbounded corpus. Before large-scale acquisition, add normalized searchable skill/preference columns plus cursor pagination, measure real query plans with `EXPLAIN (ANALYZE, BUFFERS)`, cap broad searches, and move ranking to PostgreSQL full-text/vector search or a dedicated search service only when measured volume requires it.

## Rollout, rollback, backups, and cost control

Deploy to staging with isolated RDS, buckets, queues, email sandbox, and secrets. Run smoke tests through CloudFront/ALB, including cookie+CSRF login, PDF/DOCX processing, submission/discovery, and authorized download. Then test restoration from an RDS snapshot and a private-object backup before beta.

Rollback by returning ECS services and frontend/CDN to the prior immutable image/artifact. Do not reverse a data migration unless its reverse path was reviewed and tested. Forward-fix additive migrations where possible. If a worker release is faulty, scale workers to zero without stopping web traffic, preserve SQS messages, deploy the prior worker, and resume processing.

For a dormant staging environment, set web/worker desired count to zero, stop nonessential scanner tasks, shorten noncritical log retention, and use a single-AZ/small RDS instance only if the staging recovery tradeoff is accepted. RDS continues charging while running; snapshot then delete it only through an approved teardown procedure. S3 data, snapshots, NAT gateways, ALBs, public IPv4 addresses, CloudWatch retention, and KMS keys can continue to incur cost. Prefer VPC endpoints or carefully evaluate NAT cost, Fargate Spot for noncritical workers, SQS long polling, autoscaling-to-zero workers, and CloudFront/S3 static hosting.

## Required external decisions before real users

Counsel must replace the clearly marked Privacy Policy and Terms placeholders. Owners must approve a data-retention/deletion policy, backup/restore policy with tested RPO/RTO, and incident-response policy with breach escalation. Malware signatures/scanner operations, SES production access, domain/HTTPS, alert destinations, on-call ownership, and a production restore exercise also remain external requirements. Do not represent these as completed by application code.

## Verification commands

```bash
uv run ruff check .
DATABASE_URL=postgresql://enter:enter@127.0.0.1:5433/enter uv run pytest -q
DATABASE_URL=postgresql://enter:enter@127.0.0.1:5433/enter uv run python backend/manage.py makemigrations --check --dry-run
DATABASE_URL=postgresql://enter:enter@127.0.0.1:5433/enter uv run python backend/manage.py check
cd frontend && npm run lint && npm run test && npm run build && npm run test:e2e
```

For a production-settings check, provide non-secret placeholder/test endpoints for every required environment variable, then run `python manage.py check --deploy`. This validates configuration shape; it does not prove RDS, S3, SQS, SMTP, ClamAV, DNS, or TLS connectivity.
