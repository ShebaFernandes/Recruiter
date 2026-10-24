# Deploying Enter Talent Platform

## Initial low-cost launch: current runbook

Use [deploy/README.md](deploy/README.md) and **compose.production.yaml** for the
approved single-EC2 architecture. Do not deploy the development compose file.
The runbook includes the no-AI mode, legal approval gate, private storage,
subprocess worker, backup/restore and staging acceptance checklist.

The managed ECS/ALB/RDS guidance further below is an alternative for later scale,
not a requirement for the initial launch. Its historical AI-provider requirement
is superseded: production now supports `AI_PROVIDER=disabled` without any key.
No resources have been provisioned by preparing these files.

## Optional hybrid resume understanding (disabled by default)

This is separate from recruiter search. No AI calls are made unless both
`RESUME_AI_ENABLED=true` and `RESUME_AI_EXTERNAL_PROCESSING_APPROVED=true` are set.
Do not enable either on a real-data worker until external processing has been
explicitly authorized and provider/account privacy settings reviewed. For the
first approved synthetic test use an isolated database/storage and one queued
fictional document, not the development database containing real candidates.

```dotenv
RESUME_AI_ENABLED=false
RESUME_AI_EXTERNAL_PROCESSING_APPROVED=false
RESUME_AI_PROVIDER=gemini
RESUME_AI_MODEL=gemini-3.5-flash-lite
RESUME_AI_API_KEY_FILE=
RESUME_AI_ALLOW_PAID=false
RESUME_AI_OPENAI_ZDR_APPROVED=false
RESUME_AI_GEMINI_FREE_TIER_APPROVED=false
RESUME_AI_FALLBACK=rules
RESUME_AI_MAX_ATTEMPTS=1
RESUME_AI_TIMEOUT_SECONDS=60
RESUME_AI_MAX_INPUT_TOKENS=4000
RESUME_AI_MAX_OUTPUT_TOKENS=6000
RESUME_AI_DAILY_BUDGET_USD=0
RESUME_AI_MONTHLY_BUDGET_USD=0
RESUME_AI_INPUT_USD_PER_MILLION=0.30
RESUME_AI_OUTPUT_USD_PER_MILLION=2.50
```

Mount the server-only key through `RESUME_AI_API_KEY_FILE` on the worker service using
`compose.resume-ai.yaml`. Do not put it in `.env.production`, the web/backend container,
frontend variables, an image layer, or Git. Recruiter search configuration is separate.
Restart only the resume worker after an approved resume-AI configuration change.

Pipeline: private upload → scan → existing pypdf/python-docx parser → optional
structured interpretation → shape/evidence/date validation → identity check and
provenance-aware merge → PostgreSQL → My Profile. Names/contact details are locally
parsed and redacted from model input. Work history still identifies people: this
is data minimization, **not anonymization**. Raw text, evidence and provenance stay
in private resume metadata, not recruiter/candidate API responses or logs.

AI facts require document evidence. Employment validation keeps employer evidence
separate from role/date evidence and uses document structure to associate promotions
without borrowing facts from unrelated employers. Unsupported individual fields or
roles are rejected while supported history remains reviewable. Dates preserve their original precision in
`date_label`; normalized month/year dates use the first day for graph placement,
not a claim of exact start day. Experience uses the union of known intervals, so
concurrent roles do not double-count. Incomplete history yields unknown experience.
Strongest skills are ranked by supported use in employment details (maximum five).
Likely directions are conservative local suggestions from supported roles, not
confirmed preferences. Salary, notice and future work setup are never inferred
by AI; the local parser accepts only explicit preference labels.

Gemini resume requests use Google's `v1beta` `generateContent` endpoint with structured JSON
output and the same strict application-side evidence validator. Production requires an active
paid Gemini project, `RESUME_AI_ALLOW_PAID=true`, non-zero daily/monthly budgets, and current
input/output prices. Production startup rejects the Free-tier approval flag because Google's
unpaid-service terms permit product improvement and human review and instruct customers not to
submit personal information. Generate Content request logging/storage must remain disabled,
and no feedback or datasets may be contributed. Implementation and regression tests never make
inference requests. Every live test requires separate authorization, a selected synthetic or
consented resume, a per-call reservation, and a `ResumeAIUsage` record.

Deterministic history that passes the completeness heuristic makes no model call.
The durable per-resume attempt cap applies across worker retries; this prepared Gemini
release sets it to one, so no provider failure triggers another paid request. Rate limits,
outages, timeouts and malformed output fall back to rules. Input and output are capped at the configured
token limits; oversized input uses rules rather than silently sending a
truncated document. Failed/expired attempt owners cannot update or fail a newer
attempt. Lease recovery respects the job attempt cap. SQS busy/superseded receipts
are not acknowledged prematurely. Socket timeouts are not a hard CPU limit on
local PDF parsing; container/process supervision is still needed in production.

`ResumeAIUsage` records provider, exact returned model, token counts, latency,
estimated cost, outcome and failure category, but never resume text. Paid calls
reserve their maximum configured cost under a database lock before sending and
are refused when either budget would be exceeded. A validated result is cached
durably before the worker merge, so a process/SQS retry can reuse it without a
second charge. Paid mode refuses to start unless both budgets and current token
prices are configured.

Inspect `Resume.extracted_data['_interpretation']` locally for `source=ai` with
provider/model, or `source=rules` with the fallback reason. `_ai_requests` is the
durable attempt count. Do not print raw text/evidence or credentials to verify it.
Warnings record only an error category. `RESUME_AI_FALLBACK=fail` opts out of rule
fallback; the existing bounded job failure/retry UI then applies.

Same-person replacement updates only fields still matching their automatic
baseline. Manual edits, explicit clears and Beyond the CV remain protected.
Legacy uploads without a baseline stay pending in the compact Resume updates
control; they are not assumed safe or silently backfilled. Different/unknown
replacement names block the entire merge and prompt the candidate to upload the
correct document. The owner can preview that original file; recruiters cannot
download identity-blocked files. Names are a conservative warning heuristic, not
identity verification; initials, name changes and parser mistakes may require a
corrected document/profile name. No existing profiles are silently repaired.

For a later, separately approved paid OpenAI rollout, use `RESUME_AI_PROVIDER=openai`,
an explicitly selected structured-output-capable `RESUME_AI_MODEL`, a server-only
`OPENAI_API_KEY`, and `RESUME_AI_ALLOW_PAID=true`. Configure approved OpenAI ZDR first,
then set `RESUME_AI_OPENAI_ZDR_APPROVED=true` and the external-processing approval
flag. Requests use Responses with `store=false`; that flag alone is **not** ZDR.
Review [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data)
and current model pricing before approving paid requests. No pipeline rebuild is needed.

Gemini uses the same pipeline with `RESUME_AI_PROVIDER=gemini`, the exact verified
`gemini-3.5-flash-lite` model ID, and a worker-only `RESUME_AI_API_KEY_FILE`.
`RESUME_AI_GEMINI_FREE_TIER_APPROVED=true` is limited to explicitly authorized
synthetic local tests and is rejected when `APP_ENV=production`. Real candidate
resumes require separately approved paid-service data handling, legal text, the
explicit paid flag, budgets, and rechecked current prices. Never attach billing or
upgrade automatically.

Limitations: evidence checks prove text support, not the truth of a CV or perfect
employer association. Complex columns, scanned/image-only documents (no OCR),
ambiguous promotions and truncated documents can still need candidate correction.
Free models have variable availability, quality and rate limits; benchmark with
consented synthetic fixtures before any public rollout. AI remains optional and
the application must not be described as fully AI-powered while using rules.

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
- `AI_PROVIDER=anthropic|openai`, the selected provider's API key, and an approved
  structured-output-capable model. Store the key in Secrets Manager/SSM, never the frontend.
- OpenAI uses `OPENAI_API_KEY`, `OPENAI_SEARCH_MODEL`, and `OPENAI_API_BASE_URL`.
- Anthropic uses `ANTHROPIC_API_KEY`, `ANTHROPIC_SEARCH_MODEL`,
  `ANTHROPIC_API_BASE_URL`, `ANTHROPIC_API_VERSION`, and
  `ANTHROPIC_SEARCH_MAX_OUTPUT_TOKENS`.
- Resume extraction uses a Docker secret mounted only into the worker at
  `RESUME_AI_API_KEY_FILE`; for the prepared Gemini release, the secret source is
  `ENTER_GEMINI_SECRET_FILE` outside the repository.
- `AI_ALLOW_DETERMINISTIC_FALLBACK=false`: staging/production fails clearly when the
  selected provider is unavailable instead of silently presenting deterministic parsing as AI.

Keep S3 Block Public Access enabled, use SSE-S3 or SSE-KMS, disable ACLs, and grant web read only if downloads remain web-served. Grant workers quarantine read/delete and promoted-object read/write. Add a reviewed lifecycle rule only after the retention policy exists. RDS backups, point-in-time recovery, backup retention, restore testing, and deletion protection are product decisions, not repository defaults.

Recruiter queries are interpreted server-side through a provider adapter. OpenAI uses the
Responses API; Anthropic uses Messages with `output_config.format=json_schema`. Both responses
pass through the same strict application validator
before reaching Django search logic. Only the recruiter's search sentence and clarification
context are sent; candidate profiles and resumes are not sent to either integration. Restrict
and rotate provider keys, monitor latency/error/cost, and give ECS tasks controlled outbound
HTTPS access. Local development may explicitly opt into the named deterministic fallback; it
is recorded as `understanding_source=deterministic_fallback` and is disabled by default.
Production configuration rejects fallback mode so the product never presents fixed parsing
as AI.

Successful real requests emit a redacted log event such as
`ai_search_provider_success provider=anthropic model=<model> request_id=<id>`. Fallbacks emit
`ai_search_provider_fallback provider=anthropic error=<category>`. No prompt, candidate data,
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

## ENTER recruiter access administration

The public landing page and candidate registration remain open. Recruiter signup
is closed. `/recruiter` and the legacy `/recruiter/account` show password login;
a valid approved recruiter session opens the existing workspace. Guest-search
routes have been removed: old guest tokens and `GUEST_SEARCH_*` settings grant
no access. No passwordless invitation flow is implemented.

A recruiter must have an active Django user, recruiter role/profile, no candidate
profile, and explicit administrator approval. Django checks this on every API
request (including existing tokens/cookies), and again for candidate/resume
authorization. Candidate consent, submission, visibility and matching-search rules
still apply. Only active superusers can manage recruiter approval, users, groups,
and roles in Django Admin. Ordinary staff/model permissions cannot grant approval.
Normal recruiters must NOT be given staff or superuser status.

### Local rollout and existing accounts

Migration `0012_recruiter_administrator_approval` adds only approval fields.
Existing profiles default to unapproved; IDs, projects, stages and searches remain
unchanged. Review each existing recruiter before approving them; never bulk-approve
accounts based on email domain. Applying this migration intentionally blocks
existing recruiter sessions until review. Do not delete/recreate accounts.

Commands below explicitly load the root `.env`; do not paste secrets into commands
or logs. From the repository root:

```bash
uv run --env-file .env python backend/manage.py migrate
uv run --env-file .env python backend/manage.py runserver 127.0.0.1:8010
```

For future deployments, migrations remain an explicit one-off release operation,
not web replica startup. Never roll back to a version allowing public signup or
guest search; forward-fix security regressions.

### Create an ENTER recruiter

1. Sign in to `http://127.0.0.1:8010/admin/` with a designated superuser.
2. Open **Talent → Recruiter profiles → Add**.
3. Leave **User** empty for a new account. Enter the employee's email, a strong
   initial password, full name and optional company. For an existing user, select
   **User** and leave new-email/password fields blank. Candidate accounts cannot
   be converted to recruiters.
4. Confirm employment/authorization outside the app; only then select
   **Is approved** and save. The form atomically creates the user, role and profile.
   New users are active but not staff/superusers. To create a pending account,
   leave approval unchecked.
5. Have the recruiter use **For recruiters → Forgot password?** to set their own
   password through the existing reset flow (working email delivery required),
   or securely provide the initial password through an approved channel.
   Never email plaintext passwords. Password reset does not approve an account.

### Approve or revoke an existing recruiter

- **Approve:** open the existing recruiter profile, check **Is approved**, save.
  Ensure the related user is **Active** under **Authentication and Authorization →
  Users**. The approver and timestamp are recorded; Django Admin logs changes.
- **Revoke:** uncheck **Is approved**, save. Tokens are deleted, and every new API
  request checks current approval. A page already open may retain previously
  rendered information, but cannot fetch private data or perform actions.
  Projects, searches and stages are retained. Inactivation also blocks access.
- **Log in:** visit the public website, select **For recruiters**, and enter the
  approved account's email/password. An existing valid session opens Search.
  Approval never bypasses candidate visibility or resume authorization.

### Administrator recovery

Use another designated superuser to restore access where possible. Otherwise an
authorized operator with access to the correct server/environment may run:

```bash
uv run --env-file .env python backend/manage.py changepassword ADMIN_USERNAME
# Only if no usable administrator exists:
uv run --env-file .env python backend/manage.py createsuperuser
```

Both commands prompt interactively; do not pass passwords on the command line.
If the old administrator is inactive, another designated superuser must restore
its Active status, or use the new recovery superuser. Do not grant superuser
privileges to a normal recruiter or weaken application permissions as a workaround.
Review/audit recovery access and disable temporary administrators afterward.

### Authentication security and verification

Public auth POSTs explicitly enforce CSRF, even before login. Clients must first
GET `/api/v1/auth/csrf/`, retain its cookie, and send `X-CSRFToken` with mutations.
The React client already does this. Existing cookie security, expiry, password
reset/verification limits and database-backed rate limits are retained.
The Django Admin login also enforces CSRF and shares the existing login quota;
switching between admin and API login cannot evade the limit.

Browser fixtures provision approved test recruiters using the same admin form,
not a public bypass. Run browser tests against an isolated local PostgreSQL
database with `_e2e` in its name, plus a matching backend, worker and frontend.
Set `DATABASE_URL`, `PLAYWRIGHT_API_URL`, `PLAYWRIGHT_BASE_URL`, and
`RUN_CONNECTION_AUDIT=1`. Use `TESTING=true AI_PROVIDER=deterministic` on that
test server only; keep real provider configuration untouched. Candidate tests
still register, verify, upload, process and submit through the real APIs.

### Candidate verification and transactional email

Candidate signup stays public and requires no administrator approval. Candidate
login and every authenticated request require an active user and a non-null
`email_verified_at`. Existing profiles are not automatically marked verified.
Verification/resend only operate on unverified candidates; an already-verified
account disabled by an administrator cannot reactivate itself with verification
or password reset. The existing schema represents both a pending signup and an
inactive unverified account identically: do not use the already-false Active
checkbox alone to distinguish suspension of a never-verified signup. A separate
suspension state would require a separately approved schema change.

Set `APP_ENV=staging` or `APP_ENV=production`, `DEBUG=false`, `TESTING=false`, and
`EXPOSE_LOCAL_EMAIL_LINKS=false` for deployments. Startup rejects DEBUG, TESTING,
or local-email opt-in in these environments. Development defaults to local when
DEBUG is true; deployment configuration must explicitly declare its environment.
Local shortcuts default off and both the signup link and `issue_local_account_token`
command require explicit local/test opt-in, DEBUG, and a non-delivering local
email backend. Browser tests must use `APP_ENV=test DEBUG=true
EXPOSE_LOCAL_EMAIL_LINKS=true EMAIL_BACKEND=django.core.mail.backends.locmem.EmailBackend`
on their isolated test server and token-helper process. Never apply that test
configuration to staging or production.

For real delivery, configure these existing server-side SMTP variables (no
credentials belong in React or any `VITE_` variable):

```dotenv
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=<transactional-provider-SMTP-host>
EMAIL_PORT=587
EMAIL_HOST_USER=<SMTP-username>
EMAIL_HOST_PASSWORD=<SMTP-password>
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_TIMEOUT=10
DEFAULT_FROM_EMAIL=ENTER <noreply@verified-sending-domain>
FRONTEND_URL=https://your-frontend-domain
EMAIL_VERIFICATION_TOKEN_TTL_SECONDS=86400
PASSWORD_RESET_TOKEN_TTL_SECONDS=3600
ACCOUNT_EMAIL_RESEND_COOLDOWN_SECONDS=60
```

Production SMTP requires credentials, a sender, and either STARTTLS or implicit
SSL (not both). Implicit SSL typically uses port 465 with TLS false and SSL true.
The SMTP socket timeout is bounded to 1–60 seconds; it is not a total request
deadline. Mail remains synchronous. Expiry wording uses the configured positive
token lifetimes. Failed delivery logs only purpose and a fixed error category,
never exception details, recipient addresses, credentials, or token-bearing URLs.
Password-reset/resend responses stay generic even on delivery failure. Monitor
`account_email_delivery_failed` and the provider's delivery/bounce dashboard.
A failed send still consumes the resend cooldown; retry after it expires.

Before enabling real email: obtain provider credentials, verify the sender/domain
and provider-required DNS records (including DKIM and appropriate SPF/DMARC),
configure HTTPS origins and deployment secrets, then restart with the production
settings. With approval, test actual delivery, spam placement, expiry, resend,
reset, and bounce handling. No provider connectivity or delivery is implied by
configuration/unit tests. An email queue is a follow-up scaling improvement.

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
