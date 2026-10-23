# ENTER: low-cost EC2 launch runbook

> **Current candidate-only launch control:** the single authoritative launch path
> is at the top of `CANDIDATE_ONLY_SAFETY_RELEASE.txt`. The longer staging,
> infrastructure, image, and historical review sections in this runbook preserve
> evidence and operating detail; they are not separate publication approvals.
> Candidate launch remains fail closed on the approved legal-copy status and
> hashes, and registration stays paused until the consolidated check passes and
> final authorization is given.

## Caddy and PostgreSQL remediation — 15 October 2026

### Decision and scope

GO for **restricted AWS staging with fictional data only**, subject to the owner
approving the infrastructure/budget and image maintenance approach below.
NO-GO for public candidate uploads until live AWS gates pass. No AWS resources,
real emails or external AI requests were made. No development data was reset or
migrated. All integration data was disposable under /tmp/enter-stack.Uspnwf83.

### Why vendor-patched rebuilds were needed

- Official Caddy 2.11.7 on Alpine 3.23.6 still shipped Go 1.26.8 and x/net 0.59.0.
  The latest supported Caddy release was retained and rebuilt with Go 1.26.9
  and x/net 0.60.0, using standard modules only. The final Alpine 3.23 runtime
  includes zlib 1.3.2-r1 and OpenSSL 3.5.9-r0.
- Official postgres:17-alpine (PostgreSQL 17.11, image index
  b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24)
  used Alpine 3.24.2, libxml2 2.13.9-r2,
  zlib 1.3.2-r0 and the Go 1.24.6 gosu helper (4 critical / 31 high findings).
  Switching to the current official Debian image alone did not solve it:
  postgres:17, Debian 13.7, PG 17.11, libxml2
  2.12.7+dfsg+really2.9.14-2.1+deb13u3 and zlib
  1:1.3.dfsg+really1.3.1-1+b1 still reported 4 critical / 32 high findings.
  Its additional CVE-2026-74860 concerns libxml2 Python bindings; ENTER does not
  use these bindings, but that is not an exemption for the other libxml2 defects.
- The replacement keeps **PostgreSQL major 17**, using the PostgreSQL project's
  signed Ubuntu noble repository: 17.11-1.pgdg24.04+2, Ubuntu 24.04.5 LTS,
  libxml2 2.9.14+dfsg-1.3ubuntu3.10, zlib1g 1:1.3.dfsg-3.1ubuntu2.2.
  libpq5 is the vendor-provided backward-compatible client library 18.6;
  the actual server and pg_dump/pg_restore remain 17.11. No mixed Debian/Ubuntu
  or unsupported distribution packages were installed.
- The pinned official PostgreSQL entrypoint is reused with one scoped change:
  gosu is replaced with Ubuntu util-linux setpriv 2.39.3-9ubuntu6.6, dropping to
  postgres with initialized groups. Initialization, persistence and authentication
  were tested. No Go helper remains in the replacement database runtime.
- These are maintained build recipes, **not official Docker Hub Caddy/Postgres
  release images**. Prefer returning to official images when their vendor fixes
  are available, after repeating the same integration/scan gates.

Sources: [Caddy supported source builds](https://caddyserver.com/docs/build),
[PostgreSQL supported Ubuntu repository](https://www.postgresql.org/download/linux/ubuntu/),
[Ubuntu libxml2 advisory](https://ubuntu.com/security/CVE-2026-86140),
[Debian libxml2 tracker](https://security-tracker.debian.org/tracker/CVE-2026-86140).

### Reachability and scanner interpretation

Caddy's old Go TLS/HTTP/network dependencies are on the public-facing edge;
they were treated as genuine blockers, not assumed unreachable. Exact exploit
reachability for every CVE was not proven, and no exception was taken.
The original database image's Go findings belong to its startup identity-switch
helper, not the PostgreSQL network server. Network/certificate attack paths in
that helper are not demonstrated in ENTER; nevertheless the helper was replaced,
rather than suppressing those findings. libxml2/zlib are real native dependencies:
PostgreSQL XML/compression functionality exists, even though ENTER does not expose
arbitrary SQL/XML operations to candidates. Lower exposure is not proof of safety.

The first rebuilt Caddy layered over the official image still yielded findings
against the superseded binary in layer f65067307924..., while live build-info
reported Go 1.26.9/x/net 0.60.0. Its SBOM contained both old and new versions.
The final clean Alpine runtime contains only the patched executable; the fresh
scan then cleared. No ignore-base, CVE suppression, VEX exclusion, or security
feature disabling was used. Ubuntu backported fixes were assessed using vendor
package revisions rather than comparing the upstream libxml2 version alone.

### Final scan artifacts

Docker Scout 1.24.0, fresh advisory evaluation on 15 October 2026, linux/amd64.
All five images were rebuilt and scanned; **0 high / 0 critical** in each.
This statement does not cover medium/low findings or future advisory updates.

| Image | Reviewed image index ID |
| --- | --- |
| enter-edge:stack-review-20261015 | sha256:f749dcd82e96d6429fbb9043cd0c430d3b4263774b7a914882a1e1ebcafd385e |
| enter-postgres:stack-review-20261015 | sha256:b7bb9910dfc02354f26b85499ed96a2d2e4a2c8b8a90f1d08c701121561eca30 |
| enter-backend:scanner-review-20261014 | sha256:60fe70cb1b12b19153eb2334df50fed9500829797efb0a872f61c672c6b7a1f7 |
| enter-frontend:scanner-review-20261014 | sha256:18d57d4e80f1428ce979552e6681b043fafcb033a95f05a52bb7bb5f25c50da5 |
| enter-scanner:scanner-review-20261014 | sha256:5ee58942a41326075a9935fe5879cc6a610e0dd4aae8f7c417c574bf1ac64a4d |

Raw original/final SARIF reports remain in /tmp/enter-stack.Uspnwf83:
caddy-scan.json, postgres-scan.json, edge-clean-final-scan.json,
postgres-final-scan.json, backend-final-scan.json, frontend-final-scan.json,
scanner-final-scan.json. Preserve release scan evidence outside temporary storage
before deployment. Rebuilds refresh vendor packages and may have different IDs;
scan the **actual release**, not a prior tag.

### Verified locally

- Backend: 205 tests passed against the replacement PostgreSQL in a separate test
  database, including candidate isolation/recruiter authorization and worker regressions.
- Frontend: 68 tests; TypeScript, ESLint and production build passed.
- Ruff and Django deployment checks passed (zero silenced checks).
- Real HTTP stack passed: Caddy TLS, Gunicorn DEBUG=false, AI disabled, local
  SMTP STARTTLS sink, verification/login/cookies, SQS queued recovery, clean PDF
  and DOCX scanning/extraction, private previews/ownership, JPG/PNG/WebP handling,
  settings/persistence/submission, account deletion, worker crash recovery,
  scanner outage fail-closed behavior, embedded EICAR rejection, and updater restart.
- Playwright: signup, mailbox verification, upload, profile/timeline, preview,
  Beyond the CV, settings, submission, refresh and deletion passed through Caddy.
- PostgreSQL: SCRAM rejects wrong passwords on the Docker network; only plpgsql
  is required/installed by ENTER. Complete schema/data dump and restore equality
  verified with writes quiesced. Persistent volume survives container recreation.
  The recovery script also checks forced SIGKILL/start and WAL replay.
- Production Caddyfile validates, HTTP redirects with 308, HTTPS headers remain,
  /admin is blocked, unauthenticated profile access denied. Local TLS used a
  test certificate; real ACME issuance/renewal was **not** tested.
- Rehearsal S3/SQS APIs ran inside an internal Docker network. LocalStack's stock
  health probe cannot resolve localhost.localstack.cloud there; direct
  127.0.0.1:4566/_localstack/health reports both services running and real API
  operations passed. This is an emulator DNS limitation, not an AWS health check.

The first host-side backend run could not reach the internal Docker database
(83 non-DB tests passed, 122 setup errors); rerunning inside that network passed
all 205. A first frontend image build used the wrong context and failed; the
repository-root build succeeded. The initial recovery harness was strengthened
to quiesce heartbeat writes and assert an actual crash rather than merely sending
a signal inside a PID namespace. These failures are not omitted from the evidence.
Repeated test signups also hit the expected HTTP 429 rate limit; only disposable
rehearsal throttle counters were cleared before rerunning. No production limits
were disabled. The forced database crash was initiated using Docker SIGKILL,
followed by an explicit start (Docker regards docker kill as a manual stop).
WAL replay and exit 137 were asserted; this is not a claim that Docker automatically
restarts a manually stopped container. The production restart policy remains
unless-stopped; worker and scanner automatic failure recovery were tested separately.

### Deployment safety and exact next steps

1. Approve a restricted **synthetic-only** staging environment and the maintenance
   obligation for the two scoped image rebuilds. Check AWS account plan, credit
   eligibility/expiry and budgets first. Alerts are not hard spending caps.
2. Choose one region and x86-64 EC2 (initial 8 GiB evaluation), encrypted EBS,
   SSM access and least-privilege instance role. No database/scanner/API ports
   in security-group ingress. Restrict application access to tester IPs or a VPN.
3. Create private S3 and backup buckets (Block Public Access, encryption,
   retention/lifecycle); SQS plus DLQ; least-privilege IAM. Keep AI disabled.
4. Configure SES verified sender/domain, SPF/DKIM/DMARC and approved test
   recipients. Never transfer local resumes or development records.
5. Prepare staging DNS and HTTPS. If using an IP allowlist, arrange ACME challenge
   access deliberately (or use a tested DNS challenge flow); do not make the
   application public just to issue a certificate.
6. Copy production.env.example into a private staging environment file, replace
   placeholders, set a unique ENTER_RELEASE and ENTER_PLATFORM=linux/amd64.
   Build with the production Compose file (all five image recipes), then scan:
   `docker scout cves --only-severity critical,high --exit-code IMAGE`.
   Retain image IDs/digests and scan evidence. Validate Compose before startup.
7. Start a **new empty** PostgreSQL volume; run migrations once. Do not mount an
   Alpine database directory directly into the Ubuntu image: UID, libc/locale
   and collation differences require logical dump/restore into a new directory,
   compatibility checks and preserved original volume. No in-place major upgrade.
8. Start scanner; wait for current signatures and healthy clamd/FreshClam.
   Start API and worker using identical DB/S3/SQS settings, then frontend/Caddy.
   Verify readiness, heartbeat, queued-job alerts and DLQ visibility.
9. Run the complete fictional staging journey over real HTTPS/SES/S3/SQS.
   Explicitly deny anonymous S3 access and other-candidate/unapproved-recruiter
   access. LocalStack is not proof of AWS IAM/privacy enforcement.
10. Test worker/scanner outage recovery, native EC2 resource use and upload bursts.
    Idle emulator observations are not a capacity guarantee. Configure host
    monitoring, disk/queue/worker alarms, backups and an actual S3 restore drill.
11. Rollback: preserve prior image digests, env/config and verified logical backup.
    Stop writers; restore into a new volume/database and verify before routing
    traffic. Never overwrite the only database copy or use down -v on real data.
12. Stay restricted until HTTPS renewal, IAM, storage privacy, email delivery,
    monitoring, restore/recovery, legal/privacy approval and end-to-end staging
    have passed. Public candidate uploads require a separate explicit approval.

No application UI, authentication logic, consent text or resume extraction
behavior was modified by this Caddy/PostgreSQL remediation.


### Original high/critical finding inventory

These are all findings from the original amd64 image scans, not suppressed exceptions.
Multiple affected packages can share one CVE; package-finding counts therefore exceed unique CVEs.

#### Original Caddy

| CVE | Severity | Affected package |
| --- | --- | --- |
| CVE-2026-56866 | HIGH | pkg:golang/stdlib@1.26.8 |
| CVE-2026-78659 | HIGH | pkg:golang/golang.org/x/net@0.59.0; pkg:golang/stdlib@1.26.8 |
| CVE-2026-78660 | HIGH | pkg:golang/golang.org/x/net@0.59.0; pkg:golang/stdlib@1.26.8 |
| CVE-2026-78667 | HIGH | pkg:golang/stdlib@1.26.8 |
| CVE-2026-78669 | HIGH | pkg:golang/golang.org/x/net@0.59.0; pkg:golang/stdlib@1.26.8 |
| CVE-2026-94439 | HIGH | pkg:golang/stdlib@1.26.8 |
| CVE-2026-94440 | HIGH | pkg:golang/stdlib@1.26.8 |
| CVE-2026-97031 | HIGH | pkg:golang/stdlib@1.26.8 |
| CVE-2026-85091 | HIGH | pkg:apk/alpine/zlib@1.3.2-r0?os_name=alpine&os_version=3.23 |
| CVE-2026-78663 | CRITICAL | pkg:golang/golang.org/x/net@0.59.0; pkg:golang/stdlib@1.26.8 |
| CVE-2026-56857 | CRITICAL | pkg:golang/stdlib@1.26.8 |

#### Original PostgreSQL Alpine

| CVE | Severity | Affected package |
| --- | --- | --- |
| CVE-2025-58187 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2025-58188 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2025-61723 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2025-61725 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2025-61726 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2025-61729 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-25679 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-32280 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-32281 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-32283 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-33811 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-33814 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-33818 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-39820 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-39836 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-42499 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-42504 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-56853 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-56859 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-56862 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-56866 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-78659 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-78660 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-78667 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-78669 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-94439 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-94440 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-97031 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-39822 | HIGH | pkg:golang/stdlib@1.24.6 |
| CVE-2026-86140 | HIGH | pkg:apk/alpine/libxml2@2.13.9-r2?os_name=alpine&os_version=3.24 |
| CVE-2026-85091 | HIGH | pkg:apk/alpine/zlib@1.3.2-r0?os_name=alpine&os_version=3.24 |
| CVE-2026-78663 | CRITICAL | pkg:golang/stdlib@1.24.6 |
| CVE-2026-39821 | CRITICAL | pkg:golang/stdlib@1.24.6 |
| CVE-2026-56857 | CRITICAL | pkg:golang/stdlib@1.24.6 |
| CVE-2025-68121 | CRITICAL | pkg:golang/stdlib@1.24.6 |



**Status: deployment preparation, not a production certification.** Do not admit
real candidates until every staging gate below passes. No AWS resources are
created by the repository changes. All commands in this document are for the
owner to execute AFTER approving provisioning/deployment.

**Latest decision:** see [Caddy and PostgreSQL remediation](#caddy-and-postgresql-remediation--15-october-2026).
GO for restricted, synthetic-data AWS staging preparation; NO-GO for public candidate
uploads until the live staging gates pass. All five reviewed linux/amd64 runtime
images have zero reported high/critical findings. This is point-in-time evidence,
not a claim that the images have no vulnerabilities. Development Dockerfiles and
the development database were not changed in this review. Earlier reviews below
are historical and superseded where they conflict with the latest review.

## Architecture and cost decision

One Linux EC2 instance: Caddy (HTTPS), nginx (static React), Gunicorn/Django,
PostgreSQL 17, one resume-worker supervisor, ClamAV. Private S3 for documents;
SQS standard queue + dead-letter queue; SES SMTP. No NAT, ALB, ECS or RDS required.
Only ports 80 and 443 are published. The Django API, database and scanner are
private to the Docker network. The public Caddy route explicitly blocks /admin.
Use SSM and management commands for controlled administration.

Start evaluation at 8 GB RAM (for example t3a.large/t3.large); the configuration
limits individual containers but requires measurement under campaign load.
Do not assume a 1 GB server can run a malware scanner alongside the application.
One server is a single point of failure: accept downtime/recovery responsibility
or approve a higher-cost managed architecture.

Illustrative monthly budget (730 hours, US pricing baseline, low traffic,
1,000 initial resumes, no AI, no premium support): 4 GB pilot $45–60 ONLY after
memory validation; 8 GB beta $75–95; larger workload $130–200+. Recalculate for
Mumbai if most candidates are in India. $100 credits are roughly one month of
comfortable runway, not a lasting spending limit. Taxes/domain registration,
credit expiry/exclusions, data transfer, public IPv4, EBS/snapshots, logs and CPU
surplus charges can add cost. Do not enable paid SES plans or dedicated IPs.
Pricing references: [EC2 T3/T3a](https://aws.amazon.com/ec2/instance-types/t3/)
and [public IPv4](https://aws.amazon.com/vpc/pricing/). These are estimates, not
a quote or guarantee that promotional credits cover every charge.

Verify Billing → account plan, Credits → balance/expiry/eligible services, support
plan and resources in every region. Set actual/forecast Budgets and anomaly
notifications, checking gross spend as well as charges after credits. Alerts are
NOT hard caps. A Paid account can charge beyond credits; a Free plan can expire
and interrupt service. Check https://aws.amazon.com/awscredits/ and
https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html.

## 1. Approvals and account safety

- [ ] Confirm region, domain ownership, monthly spending ceiling and beta limits.
- [ ] Root MFA; separate administrator identity; no root access keys.
- [ ] Decide who receives and acts on billing/operational alerts.
- [ ] Publish APPROVED privacy and terms content in place of App.tsx placeholders.
- [ ] Approve the EXISTING consent wording/version, visibility and retention rules.
- [ ] Approve a real support destination. Do not invent an address or legal policy.

`LEGAL_CONTENT_APPROVED=false` blocks APP_ENV=production startup. Approval also
requires the effective date and exact Privacy, Terms, age-confirmation and
submission-confirmation SHA-256 values. The backend refuses internal review
markers or mismatched files, and the frontend must be built with
`VITE_LEGAL_CONTENT_APPROVED=true`. Keep staging private/restricted to testers;
do not bypass the gate by using staging mode for public candidates.

## 2. Provision resources manually after approval

1. Select one region for EC2, S3, SQS and SES. Use encrypted gp3 EBS and persistent
   storage mounted at /srv/enter-data. Confirm encryption in the EC2/EBS console;
   Compose cannot enforce cloud disk encryption. Do not use ephemeral instance
   storage for PostgreSQL. Choose CPU credit mode deliberately (Standard avoids
   surplus charges but can throttle); monitor CPU credit balance.
2. Security group: public 80/443 only; restrict staging to tester IPs if possible.
   No 5432/8000/3310 exposure. Use SSM Session Manager instead of public SSH.
3. Attach a least-privilege EC2 instance role. Require IMDSv2; Docker bridge
   access generally needs the instance metadata response hop limit set to 2.
   Verify the role works inside API/worker containers. Never bake access keys.
4. Create a dedicated resume bucket: Block Public Access all ON, Bucket owner
   enforced (ACLs disabled), default SSE-S3 encryption, deny non-TLS access.
   The app sends AES256 encryption and NO ACL; it streams authorized downloads,
   never emits public resume URLs. No S3 website hosting on this bucket.
5. Initial resume bucket: leave versioning OFF unless deletion of all versions is
   implemented and approved. Backup bucket may be versioned with an explicit
   lifecycle. No Object Lock or legal holds without a retention decision.
6. Create a standard SQS queue, visibility 360 seconds, long poll 20 seconds,
   encrypted with SSE-SQS; DLQ redrive maxReceiveCount 5 and DLQ retention 14 days.
   Set queue retention appropriate to recovery (e.g. 4 days); retain alarm coverage.
   PostgreSQL is the durable job record; never purge queues as a recovery shortcut.
7. Create a separate encrypted backup bucket. Approve lifecycle retention before
   enabling automatic expiration. Example to approve: hourly dumps retained
   seven days, selected weekly dumps four weeks. The script itself does not
   expire objects, so retention MUST be configured to prevent unbounded cost.
8. Enable Docker at boot; install Docker Compose and official AWS CLI on the host.
   Keep the operating system patched. Docker health checks report status; they
   do not themselves restart an unhealthy running process. Worker hard timeouts
   and restart-on-exit cover crashes; alarms require an operator response.

Role permissions must be scoped to YOUR exact bucket/queue ARNs: resume object
GetObject/PutObject/DeleteObject and necessary ListBucket; SQS SendMessage,
ReceiveMessage, DeleteMessage, ChangeMessageVisibility/GetQueueAttributes;
backup PutObject and GetObject/ListBucket for restore; SSM managed-instance
permissions. Optional alert topic: sns:Publish only to the operator topic.
The role does not need bucket creation, ACL changes, administrator access, or
access to other buckets. A shared host role is an initial compromise; separate
API/worker roles when splitting services later.

## 3. Configure real email (no email sent during local implementation)

- Verify the sender domain in SES in the chosen region.
- Add SES DKIM records, SPF for the selected MAIL FROM configuration, and DMARC
  aligned to your domain's approved policy. Do not overwrite existing SPF records.
- Request SES production access; sandbox recipients/limits are unsuitable for
  public signup. Choose the low-cost Essentials/appropriate pay-as-you-go plan,
  not Pro/Enterprise, dedicated IPs or unnecessary add-ons.
- Create SES SMTP credentials (not ordinary AWS access-key credentials).
- Configure TLS on port 587. Store credentials only in a root-protected backend
  configuration file or provision them from a secure parameter store.
- Enable SES account-level suppression for bounces/complaints; configure SES
  delivery/bounce/complaint monitoring and alarms to a real operator. The app
  sanitizes synchronous SMTP errors but does NOT receive SES bounce webhooks.
- Test verification, resend, expiry, reset and provider rejection with synthetic
  accounts. Failed sends must not reveal whether an address is registered.

## 4. Prepare and validate a release

Work from the reviewed feature/candidate-platform-redesign commit. Do not copy
development databases, media or .env. A fresh production database is mandatory.

```sh
cp deploy/production.env.example .env.production
chmod 600 .env.production
```

Fill every placeholder. Generate a random Django secret of at least 50 characters
and a DIFFERENT database password (hex avoids URL escaping mistakes). Both
POSTGRES_PASSWORD and DATABASE_URL must agree. Set exact HTTPS origins. Retain
AI_PROVIDER=disabled; production Compose also clears provider keys and explicitly
disables resume AI. A future paid provider requires an intentional reviewed
configuration change; no frontend key is needed.

Use APP_ENV=staging for restricted synthetic testing. Production requires legal
approval. Do not paste `docker compose config` output into tickets: it contains
resolved secrets. Use `config --quiet` instead.

**Before running the start commands below:** resolve the Caddy/PostgreSQL release
image findings in the latest review. Building/scanning locally does not authorize
provisioning or exposing this stack publicly.

```sh
docker compose --env-file .env.production -f compose.production.yaml config --quiet
docker compose --env-file .env.production -f compose.production.yaml build --pull
docker compose --env-file .env.production -f compose.production.yaml up -d db
docker compose --env-file .env.production -f compose.production.yaml run --rm migrate
docker compose --env-file .env.production -f compose.production.yaml run --rm migrate python manage.py check --deploy
docker compose --env-file .env.production -f compose.production.yaml up -d backend scanner worker frontend edge
```

Never run `down -v`, prune volumes, or restore a development dump here. Migration
0015 adds only cleanup jobs and worker heartbeats; it does not delete candidate
records. Migrations run as an explicit release step, not on every API restart.
Pin reviewed container image digests before the actual launch; mutable base tags
are not a substitute for a release image scan. Keep the previous image tag.

Point DNS at EC2 and verify Caddy obtains/renews a public certificate. There must
be no extra public proxy in front unless trusted proxy/IP settings are reviewed.
Caddy sets forwarding headers; do not publish nginx or Gunicorn directly.
Access logs are intentionally off to avoid query-string verification/reset tokens.

## 5. Worker, cleanup and failure operation

The supervisor and API inherit the SAME .env.production (database, bucket, queue).
ClamAV must become healthy before the worker starts. Each job is claimed in
PostgreSQL, then processed in a child with a 240-second hard wall timeout,
240-second CPU limit and Linux 768 MB address-space limit. The lease is 300 seconds,
SQS visibility 360 seconds; never shorten these independently. Container limits
add a second boundary. Timeout/crash retries preserve existing attempt ownership.
ClamAV failure never proceeds to parsing. Infected documents cannot be downloaded.

File deletions use a transactional outbox. Account access is revoked immediately;
the worker retries storage deletion, with backoff, during S3 outages. Upload keys
are journaled before writing to storage so a failed DB transaction can be cleaned
later. Unreferenced new objects wait 24 hours; linked objects are never removed by
cleanup. Monitoring alerts on cleanup older than 24 hours. Document retention in
backups still requires the approved policy; do not promise instantaneous erasure
from backup archives.

```sh
docker compose --env-file .env.production -f compose.production.yaml ps
docker compose --env-file .env.production -f compose.production.yaml exec -T backend python manage.py check_resume_operations
```

The operational command emits counts only (no resume content, addresses or keys)
and exits nonzero for no recent worker, overdue jobs, failed jobs or old cleanup.
Failed counts intentionally remain visible until investigated. Candidate status
polling is owner-only, no-store, lightweight and backs off; worker outages show
a truthful delay, not fake completion. If all workers stop, only supervision and
operator recovery can resume processing—there is no claim of zero downtime.

Set CloudWatch/SQS alarms: oldest message >600s, DLQ visible >0, EC2 status checks,
memory/disk utilization (agent required), CPU credits, SES bounce/complaint rates.
Use short log retention, no request bodies, no secrets. Confirm alarm delivery.
Inspect DLQ reasons before redrive; retries are bounded and duplicate-safe.

## 6. Backups, monitoring and restore rehearsal

Copy deploy/ops.env.example to /etc/enter/ops.env and fill non-secret paths/bucket
and optional confirmed operator SNS topic. Restrict ownership/permissions. Install
the four .service/.timer files under /etc/systemd/system, then:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now enter-backup.timer enter-monitor.timer
sudo systemctl start enter-backup.service
sudo systemctl status enter-backup.service enter-monitor.timer
```

The backup script uses the database container's matching pg_dump version, validates
the archive and uploads encrypted to the backup bucket using the instance role.
It never copies local development data. Verify a backup actually exists before
launch. Monitor service failures; CloudWatch/alarms should also cover missing or
disabled timers. Configure retention in S3; budget for snapshots and old versions.

Restore drill: set ENTER_REPO_DIR, ENTER_BACKUP_BUCKET, ENTER_BACKUP_KEY and a NEW
ENTER_RESTORE_DB=restore_check_YYYYMMDD value, then run `bash deploy/restore-test.sh`.
It refuses normal production database names and refuses an existing target. It
does NOT use --clean or overwrite enter. Validate record counts and isolated app
access, then arrange deletion of that scratch database separately. Never expose
restored personal data through a public test application.

Target (not a proven SLA): RPO about one hour, RTO 2–4 hours after rehearsal.
Hourly dumps do not provide continuous point-in-time recovery. Move to managed
PostgreSQL/PITR when data value or uptime requirements justify the cost.

## 7. Mandatory staging launch gates

- [ ] No external AI traffic; no paid-model fallback; disabled AI search is explicit.
- [ ] Signup, actual verification delivery, one-time links, login/logout, reset.
- [ ] PDF/DOCX upload including a valid 5 MB boundary file through HTTPS proxy.
- [ ] Private S3 blocks anonymous reads; unrelated candidates/recruiters denied.
- [ ] Malware scanner real clean/infected/failure tests with safe synthetic fixtures.
- [ ] Hard timeout, killed worker, database/SQS/S3 outage and retry/DLQ recovery.
- [ ] Profile, seven-role journey, photos, skills, editing and private preview.
- [ ] Beyond the CV, settings, consent, final success, logout/login persistence.
- [ ] Safe replacement and protected corrections; new and old resume access rules.
- [ ] Account deletion during simulated storage failure; eventual object removal.
- [ ] Recruiter approval/search-disabled behavior, projects and permission regression.
- [ ] Mobile/tablet/desktop at 390/768/1024/1440; no UI redesign required.
- [ ] Container/dependency scans reviewed; production Django checks pass.
- [ ] Actual backup restore and operational/billing alerts demonstrated.
- [ ] Published legal text approved; only then APP_ENV=production and approval=true.

Load-test on this exact AWS size with fictional documents, real scanner/S3/SQS and
HTTP concurrency. Local microbenchmarks cannot justify 1,000 simultaneous uploads.
For example, 1,000 jobs at 2–10 seconds each take 33–167 minutes with one worker.
Begin with a small cohort; monitor queue age before promoting a large campaign.

## 8. Rollback

Record image tags/digests and back up BEFORE migration. If code fails, stop new
submissions/uploads, keep private data intact and restore the previous compatible
application image. Do not reverse additive migrations unnecessarily. For database
recovery restore into a fresh isolated database, validate, then explicitly switch
DATABASE_URL for BOTH API and worker. Reconcile queued jobs and storage references.
Never overwrite new candidate registrations with an old dump casually. Never
delete volumes as a rollback technique. Keep public launch paused until smoke
tests pass again.

## Local verification commands

```sh
DATABASE_URL=postgresql://enter:enter@127.0.0.1:5433/enter .venv/bin/python scripts/test_isolated.py
uv run ruff check .
cd frontend
npm run lint
npm run test
npm run build
```

The test wrapper assigns a unique test database and temporary media, clears AI
keys and uses an in-memory email backend. The development database is not reset.
Staging verification and AWS policy checks remain separate from local tests.

Browser tests also have an isolated runner (never point ordinary browser seed
helpers at production). Run the recruiter workflow separately so its global
test worker cannot consume the candidate test's deliberately queued fixture:

```sh
DATABASE_URL=postgresql://enter:enter@127.0.0.1:5433/enter .venv/bin/python scripts/e2e_isolated.py auth-ui.spec.ts candidate-flow.spec.ts recruiter-approval.spec.ts
E2E_START_WORKER=1 DATABASE_URL=postgresql://enter:enter@127.0.0.1:5433/enter .venv/bin/python scripts/e2e_isolated.py recruiter-flow.spec.ts
.venv/bin/python scripts/check_deploy.py
```

## Outstanding release-security gate (local review, 14 October 2026)

Local verification results:

- Backend: 205 passed on a disposable PostgreSQL database.
- Frontend unit tests: 68 passed; TypeScript, ESLint and production build passed.
- Ruff, migration-drift check, shell syntax, Compose parsing and configuration-only
  Django deployment checks passed.
- Targeted Playwright: 23 distinct tests passed across the final targeted runs;
  one external-original-HTML comparison skipped because ENTER_MOCKUP_PATH was
  not supplied. Initial stale selectors/timing/isolation failures were corrected
  and rerun. Coverage includes candidate authentication, real local PDF/DOCX
  processing/replacement, failure/retry, preview, settings, submission, deletion,
  recruiter approval/login/search/projects, mobile and reduced motion.
- Browser tests use fictional documents, a development scanner and local email;
  these are NOT evidence of real ClamAV/SES/S3/SQS operation.
- Backend and frontend container builds passed locally; frontend nginx syntax
  check passed. Backup/restore scripts passed syntax checks, not an AWS restore.
- The additive migration has NOT been applied to the existing development DB.
  Apply it as an explicit approved migration step before running updated code
  against an existing database; never reset that database.

The Python dependency audit and npm audit reported no known vulnerabilities.
The frontend image was rebuilt with patched Alpine packages and unused nginx
XML/image/ACME modules removed; nginx configuration validation and the final
Docker Scout high/critical scan passed. The backend image still reports one
HIGH finding: **CVE-2026-85091, Debian zlib**. The scanned Debian package has no
vendor fix available in that scan. Do not suppress it or interpret passing Python
tests as resolution. Review the [Debian security tracker](https://security-tracker.debian.org/tracker/CVE-2026-85091),
rebuild using a reviewed patched base when available, and rerun the scan before
public launch. Any applicability exception needs explicit security review.

Local image builds/scans were linux/arm64. Build and scan the actual target EC2
architecture before release; also scan PostgreSQL, ClamAV and Caddy images.
The production stack, real ClamAV signatures, AWS permissions, SES delivery,
TLS, backup restore and campaign throughput remain staging acceptance gates.
No production credentials or infrastructure were used in local verification.

## Implementation file inventory

Paths are relative to the repository root. Changes include production code,
isolated test runners/regressions, configuration and this runbook.

```text
.dockerignore
.gitignore
DEPLOYMENT.md
backend/config/settings.py
backend/talent/candidate_views.py
backend/talent/management/commands/check_resume_operations.py
backend/talent/management/commands/process_resume_job.py
backend/talent/management/commands/run_resume_worker.py
backend/talent/migrations/0015_filecleanupjob_workerheartbeat.py
backend/talent/models.py
backend/talent/resume_processing.py
backend/talent/search_understanding.py
backend/talent/services.py
backend/talent/storage_cleanup.py
backend/talent/throttling.py
backend/talent/urls.py
backend/talent/views.py
backend/talent/worker_runtime.py
backend/tests/test_account_security.py
backend/tests/test_candidate_email_hardening.py
backend/tests/test_candidate_photo_and_spectrum.py
backend/tests/test_launch_blockers.py
compose.production.yaml
compose.yaml
deploy/Caddyfile
deploy/README.md
deploy/backup.sh
deploy/enter-backup.service
deploy/enter-backup.timer
deploy/enter-monitor.service
deploy/enter-monitor.timer
deploy/monitor.sh
deploy/ops.env.example
deploy/production.env.example
deploy/restore-test.sh
frontend/Dockerfile
frontend/nginx.conf
frontend/src/App.tsx
frontend/src/api.ts
frontend/src/components/CandidateExperience.tsx
frontend/src/components/CandidatePresentation.tsx
frontend/src/components/CandidateProcessingFlow.test.tsx
frontend/tests/candidate-flow.spec.ts
frontend/tests/recruiter-flow.spec.ts
frontend/tests/resume-processing-ui.spec.ts
pyproject.toml
scripts/check_deploy.py
scripts/e2e_isolated.py
scripts/production_logic_smoke.py
scripts/test_isolated.py
uv.lock
```

## Historical pre-AWS review (14 October 2026, before Alpine approval)

This section records the earlier review. Its migration and default-image status
is superseded by the Alpine rehearsal below; do not rerun migration instructions
as though development were still at 0014.

### Container finding: alternative verified, default NOT switched

The current backend Dockerfile still uses `python:3.12-slim`. The locally built
`enter-backend:launch-check` is Debian 13.7 (trixie), with
`zlib1g 1:1.3.dfsg+really1.3.1-1+b1` and Python runtime zlib 1.3.1.
The Debian tracker still marks CVE-2026-85091 vulnerable without a fixed package.
Switching between affected Debian releases is not a demonstrated remediation.

The advisory concerns the native gzwrite/nonblocking-buffer/gzprintf path.
ENTER has no direct calls to these C APIs; its document compression uses Python
zlib/zipfile. This reduces apparent direct reachability but is NOT proof that all
native dependency paths are unreachable. The affected-version range is disputed:
the upstream issue contains both a source-based false-positive argument for 1.3.1
and a Debian maintainer report of older-version reproductions. No suppression or
false-positive exception has been applied.

Sources: [Debian tracker](https://security-tracker.debian.org/tracker/CVE-2026-85091),
[upstream discussion](https://github.com/madler/zlib/issues/1310),
[upstream fix](https://github.com/madler/zlib/commit/df84af25dc1942490e1d1c899a07619152a46148).

A temporary review build using `python:3.12-alpine` plus `apk upgrade --no-cache`
installed Alpine 3.24.2 with zlib **1.3.2-r1**. Its ARM64 image is
`enter-backend:alpine-review`, digest
`sha256:c4247f6b113b1ec30b50b6912c82b7b5a1a00810ee34caf0315f536d1e711d7b`.
The fresh Docker Scout high/critical scan found no vulnerable packages in that
selection. Network-disabled PDF/DOCX/WebP native-library smoke checks passed.
This does NOT certify all severities or full runtime compatibility. Alpine uses
musl instead of glibc. Approve this base change, then run the complete production
stack on the intended EC2 architecture and scan every final image before release.
The default Debian release remains blocked; this review did not change it silently.

### Migration and backup

The verified development target is PostgreSQL 17.11 at 127.0.0.1:5433, database
`enter`, user `enter`, container `recruiter-db-1`. Its latest talent migration is
0014. The 0015 plan contains only CreateModel(FileCleanupJob) and
CreateModel(WorkerHeartbeat); no candidate/recruiter updates or destructive SQL.
It is additive and suitable for an explicitly approved migration window.

Backup: `backups/development-before-0015-20261014.dump`, 395115 bytes, mode 0600.
SHA256: `4cec745a4c2771dbd6afeee05d04df7c1df88435468f0a7db129471fef1f2ec0`.
The PostgreSQL archive catalog validated. A restore drill has NOT been performed.
The backup contains private development data: do not commit, upload to production,
or share it. Git and Docker both exclude it. Recreate a fresh backup if development
data changes before migration. Secure local disk encryption remains the owner's duty.

ONLY AFTER owner approval, from the repository root:

```sh
DATABASE_URL=postgresql://enter:enter@127.0.0.1:5433/enter .venv/bin/python backend/manage.py migrate talent 0015 --plan
DATABASE_URL=postgresql://enter:enter@127.0.0.1:5433/enter .venv/bin/python backend/manage.py migrate talent 0015 --noinput
```

The second command has NOT been run on the existing development database.

### Verification boundaries

- Fresh PostgreSQL regressions: 205 passed. The first attempt accidentally omitted
  DATABASE_URL and used SQLite: 202 passed, 3 failed. The runner now rejects that
  configuration; the corrected PostgreSQL run passed. No development migration occurred.
- Fresh frontend: 68 passed, ESLint and TypeScript/production build passed.
- Fresh Playwright run: all 13 auth-ui, candidate-flow and recruiter-approval
  tests passed in 5.9 minutes, including real retry backoff and replacement.
  The isolated API used port 8035 to avoid another application's port 8025.
  This browser run used development-mode services, not the production container stack.
- Ruff, diff whitespace, backup/restore/monitor shell syntax and strict production
  Django deployment checks passed.
- Production Compose parses with the example environment; use
  `ENTER_ENV_FILE=deploy/production.env.example docker compose --env-file deploy/production.env.example -f compose.production.yaml config --quiet`.
  Real configuration must use a protected populated .env.production instead.
- `scripts/production_logic_smoke.py` passed with DEBUG=false, TESTING=false,
  AI disabled and no provider key. It exercises signup/verification/cookie login,
  DOCX processing, career-history data, private preview, preferences, consent,
  submission, candidate-to-recruiter denial and account/file cleanup.
  SMTP/SQS/ClamAV are mocked and private local files substitute for S3. It is an
  application smoke, NOT a real-service integration or full container simulation.
- Real supervisor-child and timeout/retry tests are in the backend regressions;
  an actual container kill/restart with real ClamAV and queue is still unverified.
- Full local production-stack rehearsal, fresh-signature malware tests, backup
  restore, target-architecture scans and actual AWS/SES/HTTPS tests remain gates.
  Do not infer public readiness from these passing application checks.

Run the strict-settings smoke without sending mail or calling AWS/AI:

```sh
DATABASE_URL=postgresql://enter:enter@127.0.0.1:5433/enter .venv/bin/python scripts/production_logic_smoke.py
```

### Git handoff (owner commands only)

Branch verified: feature/candidate-platform-redesign; HEAD 13b2a50. Cached remote
comparison was 0 ahead / 0 behind; no live fetch or push was performed. The file
inventory above describes the current pending hardening changes, but attribution
to an earlier author cannot be proven from an uncommitted tree alone.
High-confidence AWS/provider/private-key pattern scan found no matches in tracked
and proposed files. None exceeded 5 MiB. The only tracked resume document is the
fictional test fixture. This is not a full historical secret audit.

After reviewing all diffs and resolving the release gates, run:

```sh
git branch --show-current
git fetch origin
git rev-list --left-right --count HEAD...origin/feature/candidate-platform-redesign
git diff --check
git diff
git status --short
```

If the remote is ahead or diverged, STOP and review; do not force-push or blindly
pull. If the tracked diff contains only the reviewed inventory, stage it with
`git add -u`. Stage the reviewed new files explicitly:

```sh
git add -- backend/talent/management/commands/check_resume_operations.py backend/talent/management/commands/process_resume_job.py backend/talent/migrations/0015_filecleanupjob_workerheartbeat.py backend/talent/storage_cleanup.py backend/talent/worker_runtime.py backend/tests/test_launch_blockers.py compose.production.yaml
git add -- deploy/Caddyfile deploy/README.md deploy/backup.sh deploy/enter-backup.service deploy/enter-backup.timer deploy/enter-monitor.service deploy/enter-monitor.timer deploy/monitor.sh deploy/ops.env.example deploy/production.env.example deploy/restore-test.sh
git add -- scripts/check_deploy.py scripts/e2e_isolated.py scripts/production_logic_smoke.py scripts/test_isolated.py scripts/container_stack_smoke.py
git add -- backend/Dockerfile.production frontend/tests/container-stack.spec.ts
git add -- deploy/scanner/Dockerfile deploy/scanner/clamd.conf deploy/scanner/freshclam.conf deploy/scanner/entrypoint.sh
git diff --cached --check
git diff --cached --stat
git diff --cached
git commit -m "Harden candidate launch configuration and document staging gates"
git push origin HEAD:feature/candidate-platform-redesign
```

Never stage .env.production, backups, local resumes, videos or databases. These
commands are instructions, not actions performed by the assistant. A successful
future push, not a cached branch comparison, proves remote transport works.

### AWS setup order and approval gates

1. Review the scanner remediation below and resolve the remaining proxy/database image gates.
2. In Billing, check account plan, credit balance/expiry/eligible services and support
   plan. Configure actual/forecast budgets and an accountable alert recipient.
   Alerts are NOT hard spending caps. AWS Free-plan terms say evaluation accounts
   should not process sensitive data; real resumes require an appropriate approved
   account plan. Do not upgrade automatically without accepting billing exposure.
   See [AWS plan documentation](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)
   and [Free Tier terms](https://aws.amazon.com/free/terms/).
3. Approve region and a current Pricing Calculator estimate. Choose EC2 architecture
   before building final images; backend/frontend evidence now covers linux/amd64
   for t3/t3a. Evaluate 8 GiB RAM for this combined scanner/database/worker host.
4. Configure root MFA, operator IAM and least-privilege instance role; then EC2,
   encrypted persistent gp3 storage, restricted security groups and SSM access.
5. Create private ACL-disabled resume S3 and separate backup bucket, encryption,
   TLS-only policies, approved retention and least-privilege role permissions.
6. Create encrypted SQS + DLQ with the timeout/redrive settings in section 2.
7. Verify SES domain/DKIM/SPF/DMARC, production sending permission and SMTP credentials;
   configure bounce/complaint handling. No dedicated IP or paid add-on by default.
8. Configure staging DNS, protected environment file, AI disabled, exact HTTPS hosts,
   origins, database password, buckets/queue and sender. Build/pin/scan release images.
9. Start fresh PostgreSQL on encrypted storage, run explicit migrations and deployment
   checks, then scanner, API, worker, frontend and Caddy. Verify certificates and that
   database/scanner/API ports are not publicly exposed.
10. Enable backup/monitor timers and alarms; prove an encrypted backup restore into a
    new scratch database. Test worker/scanner failure alerts and queue/DLQ alarms.
11. Keep staging restricted; execute every section-7 gate with fictional candidates,
    real email to approved testers and all actual services. Measure burst capacity.
12. Approve legal text, support contact, consent, retention, operating budget and test
    evidence before admitting real candidates. Record previous image digests and
    rehearse section-8 rollback. No volume deletion or destructive database reset.

## Alpine full-stack rehearsal — 14 October 2026

### Decision and production-only changes

Alpine is suitable as the **backend candidate for restricted AWS staging**, not
public launch certification. `backend/Dockerfile.production` pins the reviewed
Python 3.12 Alpine base and upgrades vendor packages, including zlib 1.3.2-r1.
`compose.production.yaml` uses that file and defaults ENTER_PLATFORM=linux/amd64
for the proposed t3/t3a EC2 host. `deploy/production.env.example` documents it.
The development backend Dockerfile was not changed during this rehearsal.
New test coverage is in `scripts/container_stack_smoke.py` and the opt-in
`frontend/tests/container-stack.spec.ts`; the isolated pytest runner explicitly
sets test origins/cookies rather than inheriting production HTTPS settings.
No UI, application schema or submission behavior was changed in this rehearsal.

### Actual integration evidence

A separate Compose project, `enter-alpine-rehearsal`, used a disposable PostgreSQL
database, LocalStack S3/SQS with a DLQ, actual ClamAV, Gunicorn, the real resume
worker, nginx HTTPS and a local Mailpit STARTTLS mail sink. API/worker services
were on an internal Docker network without internet egress. DEBUG=false,
TESTING=false, AI_PROVIDER=disabled and blank AI keys were used. Only fictional
accounts/documents entered this stack. No AWS resources, external AI requests or
external email deliveries occurred. A self-signed local test certificate was
trusted for this rehearsal; this does not verify public ACME issuance.

Both Alpine and Debian passed the same real-service HTTP test:

- Signup, actual verification-email generation into Mailpit, verification and
  secure-cookie login; no bearer token or development verification link leaked.
- PDF upload while the worker was stopped, SQS queueing, worker startup and
  successful extraction; original private PDF retrieval and career-history roles.
- Actual worker-process SIGKILL, Docker restart count increase and recovery.
- DOCX upload with ClamAV stopped: scanning failed closed, job retried, scanner
  restart recovered processing, and DOCX preview succeeded.
- JPG, PNG and WebP processing; invalid images rejected; cross-candidate and
  anonymous resume requests rejected; candidate access to recruiter API rejected.
- Beyond-the-CV/settings/spectrum persistence, consent and final submission,
  fresh-login persistence, account deletion and cleanup processing.
- A separate direct scanner check accepted harmless bytes and rejected EICAR.

The final Alpine production build also passed a real browser journey through
verification, DOCX upload/extraction, Career Journey, resume preview, Beyond the
CV, Career Settings, submission, reload and deletion. Desktop 1440px and mobile
390px screenshots were captured without horizontal overflow.

Limits: local S3/SQS emulation is not AWS IAM, KMS or delivery certification.
LocalStack returned 200 to an unsigned object GET despite public-access-block
settings and owner-only ACL. Object metadata showed AES256 encryption, but
**actual S3 anonymous GET=403 and ACL-disabled/IAM tests remain mandatory**.
The scanner used cached signatures (28136, dated 27 September); freshclam
network updates and signature freshness must be verified in AWS. The stopped
SQS consumer can retain a message until its 360-second visibility timeout;
this is recovery latency, not a promise of few-second processing after crashes.

### Fresh scan and compatibility comparison

The backend and frontend were built/scanned for linux/amd64, executed under
Docker emulation on an ARM64 Mac. This validates binary compatibility in this
test environment, **not native EC2 throughput or campaign capacity**.

| Image | High/critical scan result | Reported image size |
| --- | --- | --- |
| Final Alpine `enter-backend:staging-amd64` | 0 high, 0 critical | 88 MB |
| Fresh Debian `enter-backend:debian-amd64-review` | 1 high: CVE-2026-85091 | 111 MB |
| Frontend `enter-frontend:staging-amd64` | 0 high, 0 critical | 33 MB |
| Current ClamAV upstream | 3 high, 0 critical | not used for comparison |
| Temporary ClamAV plus apk upgrade | 1 high, 0 critical | 159 MB |

Final backend image ID:
`sha256:a39082046bd3b03a35cafec2956a0ac2c5a818224aa10a164a9a32e37cd472dc`.
Rebuilds can receive newer package updates; rescan each final release, pin its
digest, and do not treat these results as a permanent security guarantee.

Alpine uses musl, Debian glibc. Python 3.12, psycopg, Pillow image formats,
PDF/DOCX extraction, TLS, Gunicorn and subprocess-worker behavior passed on
Alpine. Future native-library upgrades still need this regression coverage.
Both bases passed the workload; a short rehearsal cannot establish long-term
reliability. Alpine's smaller image did not demonstrate a material RAM saving:
observed warmed API approximately 250–271 MiB / worker 97–127 MiB on Alpine;
Debian approximately 273 MiB / 125 MiB. These are snapshots, not controlled
peak benchmarks. ClamAV was approximately 940–970 MiB. Keep the 8-GiB host
evaluation and measure native memory/CPU/backlog before any campaign.

**Unresolved scanner blocker:** upstream ClamAV carried zlib CVE-2026-85091,
pcre2 CVE-2026-103111 and libxml2 CVE-2026-86140. A temporary `apk upgrade`
build removed the first two but retained libxml2 2.13.9-r2 with no fixed package
reported by Scout. No suppression, unsupported XML removal or risk acceptance
was applied. The production scanner remains unchanged and explicitly marked
as a release gate. Approve investigation of a supported patched scanner image
before using it for untrusted public uploads. Its document-parser reachability
has not been proven absent. PostgreSQL/Caddy final x86 release-image scans,
fresh signature delivery and all AWS service checks remain staging gates.

### Test results

- Backend: 205 passed locally against isolated PostgreSQL; all 205 also passed
  inside an x86 Alpine test image built from the candidate runtime (103.97s).
  Unit tests use explicit test-mode service adapters; the separate real stack
  above verifies production settings and external-service integration.
- Frontend: 68 passed; TypeScript, ESLint and production build passed.
- Playwright: 13 auth/candidate/approval journeys plus 1 recruiter journey passed
  in disposable development-mode services; 1 additional strict-container browser
  journey passed (final repeat 13.9s). Do not conflate the two environments.
- Ruff, git whitespace checks, production Compose parsing and Django
  `check --deploy` passed. Early harness attempts failed on test-only setup
  (origins, password similarity, process targeting and SQS timing); corrected
  runs above passed. They were not ignored as application successes.

### Development backup and approved migration

Created a fresh private custom-format backup before touching development:
`backups/development-before-alpine-migration-20261014.dump`.
SHA256: `04216c5802e9b83196da947e5fafefe7526065c3b6867b43336c1de0ff188a76`.
The archive restored successfully to a separately named disposable database.
All table row counts and sorted row-content fingerprints matched development.
Migration 0015 first passed there; all original rows remained unchanged (only
the expected new model content types/permissions were added).

After a second unchanged-source check and the owner's explicit approval,
`migrate talent 0015 --noinput` was applied to development `enter` on port 5433.
Its resulting fingerprints matched the migrated restored database. Preserved:
456 users, 369 candidate profiles, 86 recruiter profiles, 359 resume records and
796 work-experience records. No development data was reset or copied to staging.
The backup contains private data: keep it access-restricted, excluded from Git
and Docker, and never upload it into production. Production starts with a fresh
database and runs all migrations independently.

The disposable restore database and fictional-data rehearsal containers were
removed after verification; the private backup was retained. Existing development
services were not stopped. A final post-test fingerprint comparison found no
changes to development records after the approved migration.

### Remaining approval gates

Resolve the scanner image; approve native EC2 sizing/budget and provisioning;
verify AWS private S3/IAM, SQS/DLQ recovery, SES delivery, freshclam, HTTPS,
monitoring/alerts, persistent encrypted storage and off-host backup restoration.
Run restricted AWS staging smoke/load tests with fictional data and approved
email recipients. Legal/privacy content approval remains required. No public
candidate uploads are authorized by the local test results.

## Scanner remediation review — 15 October 2026

### CVE-2026-86140: resolved in the ENTER scanner, not in upstream Alpine

The prior upstream image was `clamav/clamav:stable` at
`sha256:ebec5bc138401b36ae987caa1a3fa3c3b2a21ed3d51f0bfa5852825e663e67b0`.
A fresh pull returned index
`sha256:638d90201ee7ee6a82d249a2fc23b132e578673b5f1f2766852b127676ca1ef6`
(x86 manifest starts `705e0723f02f`). It still contains Alpine 3.24.2
`libxml2 2.13.9-r2`; `apk update`/`apk policy` offered no patched version.
The fresh upstream scan still reports this HIGH finding. No exception was added.

The replacement uses Ubuntu 24.04's signed supported repositories:

- ClamAV/libclamav `1.5.4+dfsg-0ubuntu0.24.04.1`.
- libxml2 `2.9.14+dfsg-1.3ubuntu3.10` (vendor-backported fix; the smaller upstream
  version number does not imply the fix is missing). The Docker build asserts
  at least Ubuntu's fixed `2.9.14+dfsg-1.3ubuntu3.9` package.
- Pinned Ubuntu base; only the signed signature bundle is copied from upstream
  ClamAV, not its affected native libraries. No cross-distribution library mixing.

Evidence: [Ubuntu CVE status](https://ubuntu.com/security/CVE-2026-86140),
[Ubuntu security notice](https://ubuntu.com/security/notices/USN-8787-1),
[ClamAV supported releases](https://docs.clamav.net/faq/faq-eol.html).
The vulnerable function concerns XML validation; XML/document scanning was NOT
removed or declared unreachable to bypass the finding.

### Runtime and final release images

`deploy/scanner/Dockerfile`, `clamd.conf`, `freshclam.conf` and `entrypoint.sh`
build a dedicated scanner. Both clamd and FreshClam run as `clamav`; tini reaps
children. A native setpriv utility performs the privilege drop. An initial
Go-based helper introduced runtime-library findings and was replaced, not ignored.
FreshClam starts after the scanner socket is ready, validates downloaded databases
and notifies clamd to reload. Either child exiting terminates the container for
Compose's restart policy. PDF, OLE2, XML and archive scanning remain enabled;
size/time-limit overruns alert rather than being silently accepted as clean.

Persistent signatures stay in `/var/lib/clamav`; the ephemeral socket is in
`/run/clamav`. New volumes are seeded; existing downloaded databases are not
overwritten. The production scanner has no published port. Keep its existing
3-GiB limit under observation: concurrent signature reloads can roughly double
engine memory. Do not disable database testing to reduce memory.

Fresh Docker Scout high/critical scans, **linux/amd64**:

| Final local image | High | Critical | Image ID / index digest |
| --- | ---: | ---: | --- |
| enter-backend:scanner-review-20261014 | 0 | 0 | `33f8f511e53d98f4c9ccde07d23f9cf382237a6a1daff3dde6478de1c5343085` |
| enter-frontend:scanner-review-20261014 | 0 | 0 | `b8a8d65cdd2f37b825f322fc4d4b6c0ec9e5f2de6b54519ac5d1d7ad8f2e3728` |
| enter-scanner:scanner-review-20261014 | 0 | 0 | `b836e256ed1f8ed3d888baad9a9f53cb79cec00e6a7caf2e6289bf83f7995792` |

Prefix each digest with `sha256:`. Scans used `--only-severity critical,high
--exit-code`; these are not claims about every severity or future advisories.
No `--ignore-suppressed` flag or custom CVE suppression was used.
Compose resolves backend/worker, frontend and scanner to these tags when
ENTER_RELEASE=scanner-review-20261014. Scanner build context is deploy/scanner;
the backend remains Alpine. Local development configuration was not changed.
Retagging/rebuilding can change image contents: compare IDs or rescan the rebuilt
artifacts before staging; never assume the same tag guarantees the reviewed bytes.

### Additional production-stack findings — still blocked

The requested three images are clear, but **not all production containers are**.
An additional remote x86 scan found:

| Existing production image | Reported high/critical package findings |
| --- | --- |
| caddy:2-alpine, x86 manifest prefix `173b26306d71` | 12 high, 3 critical; Go stdlib 1.26.8 and other bundled Go dependencies |
| postgres:17-alpine | 31 high, 4 critical; Go helper runtime, zlib 1.3.2-r0 and libxml2 2.13.9-r2 |

These counts are package findings, not necessarily unique CVE IDs. Upstream
Scout exception metadata was visible but was not used to declare these images
safe. The proxy/database images were not replaced as part of the narrowly approved
scanner task. PostgreSQL still carries the same libxml2 CVE; the whole-stack
finding is therefore NOT fully eliminated. Their runtime reachability and supported
remediation need a separate review; do not expose them based on the scanner pass.

### Reproduction and validation

Build the three reviewed recipes locally (no AWS resources):

```sh
docker build --pull --platform linux/amd64 -f backend/Dockerfile.production -t enter-backend:scanner-review-20261014 .
docker build --pull --platform linux/amd64 -f frontend/Dockerfile -t enter-frontend:scanner-review-20261014 .
docker build --pull --platform linux/amd64 -t enter-scanner:scanner-review-20261014 deploy/scanner
docker scout cves --only-severity critical,high --exit-code enter-backend:scanner-review-20261014
docker scout cves --only-severity critical,high --exit-code enter-frontend:scanner-review-20261014
docker scout cves --only-severity critical,high --exit-code enter-scanner:scanner-review-20261014
```

Use `--no-cache` when deliberately refreshing package layers; then rescan and
record new IDs. Initial unsupported build-context and test-fixture attempts were
corrected, not counted as passing tests. Plain EICAR streams are detected, while
appending EICAR outside a PDF's semantic content did not trigger this engine.
The accepted upload-path fixture is a valid DOCX ZIP with an embedded EICAR file;
it exercises actual archive scanning. EICAR is a harmless antivirus test fixture,
not a guarantee that all malicious documents can be detected.

### Exact next steps toward restricted AWS staging

Latest local validation: 36 relevant backend regressions passed in a disposable
database; the real-service integration suite passed on the final scanner image
(clean PDF/DOCX, embedded EICAR rejection and denied preview/download, scanner
outage/retry, worker SIGKILL/restart, updater termination/restart, authentication,
private ownership, submission and deletion). The container-backed browser journey
also passed. FreshClam downloaded daily version 28153, validated it and notified
clamd, which logged a successful engine reload. Version 28153 survived a full
scanner-container replacement using the persistent signature volume. Ruff, Bash
syntax, Compose validation, whitespace checks and Django deployment checks passed.

The rehearsal used x86 containers under ARM-host emulation, real ClamAV and a
local S3/SQS emulator—not native EC2 or actual AWS IAM/SES. This task did not
rerun the entire frontend unit suite because no UI/application code changed.
One initial EICAR-in-PDF test failed as described above; a temporary test stack
missing the production restart policy was corrected; socket placement in a
host-mounted signature directory was corrected to `/run/clamav`. The final
versions passed. Existing development data was not migrated or modified here.
Only disposable rehearsal containers/database were removed after testing;
signature-test data and scan reports are temporary local artifacts.

1. Approve a focused Caddy/PostgreSQL image remediation and regression test. Keep
   the scanner changes; do not change the existing development database or reset
   its data to test new images. Re-scan all five final image artifacts.
2. Review/commit/push the verified files yourself. Confirm the feature branch,
   inspect staged diffs and exclude backups, credentials, test output and resumes.
3. Check AWS account plan, eligible credits/expiry and region. Set billing alerts;
   they are not a spending cap. Approve the 8-GiB x86 EC2 cost estimate before
   provisioning. Keep staging restricted to named testers with fictional data.
4. Configure root MFA, SSM/operator permissions and a least-privilege EC2 role.
   Create encrypted EBS and a restricted security group. Keep database, scanner
   and API ports private; restrict tester access to HTTPS. Plan certificate
   issuance without temporarily exposing the application unrestricted.
5. Create private ACL-disabled S3 with encryption/TLS-only access, a separate
   backup destination, and SQS plus DLQ using this runbook's timeout settings.
   Prove unsigned S3 reads fail; LocalStack could not establish that property.
6. Configure SES sender/domain/DKIM/SPF/DMARC and approved test recipients. Set
   staging DNS and protected .env.production values; retain disabled AI and blank
   provider keys. Never copy development data into production.
7. Build/transfer and verify the final reviewed x86 images. Run Compose validation,
   start a fresh PostgreSQL instance, run migrations and Django deployment checks.
   Start scanner/API/worker/frontend/Caddy using section 4 only after image gates pass.
8. Verify HTTPS renewal, private IAM/S3 access, real SQS/DLQ behavior, FreshClam
   update/reload, worker recovery, monitoring and off-host backup restoration.
   Run the complete fictional-candidate staging journey and native load test.
9. Obtain separate approval for public launch after legal/privacy, budget and
   staging evidence are reviewed. Keep previous release IDs and database backups
   for rollback; never use volume deletion as rollback.

No infrastructure provisioning, Git commits/pushes, deployments, external AI calls
or external emails were performed. Signature/package/advisory downloads were the
only required external security-update traffic. Local SMTP used Mailpit only.
