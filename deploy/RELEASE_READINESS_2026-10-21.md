# ENTER release readiness — 21 October 2026

## Approval boundary

Local fixes and read-only staging checks; a local release commit was subsequently
approved for the reviewed files. No push, deployment, live
restart, migration, infrastructure change, or scheduled backup was performed.
The commands below are a proposed later procedure, NOT commands executed today.

Current staging: `https://staging.enter.careers`, account `431988153216`, Sydney,
instance `i-08f84202dbb6b4cce`, `/opt/enter/Recruiter`, Compose project `recruiter`.
Deployed commit: `9da648092a01bc932544302674df06b2838e9d5e`.
Candidate base: `81b912f328566835ef9b2d1dc02c534659b3bdbe` plus reviewed working-tree fixes.
The release commit containing this report is the candidate; its full SHA is recorded
in the final handoff and SHA-specific deployment instructions after committing.
Do not deploy the base SHA alone; it does not contain these fixes.

## Scope and compatibility

- CSP adds only `media-src 'self' https://d8j0ntlcm91z4.cloudfront.net`.
  The approved platform video remains unchanged. The public mountain landing page
  remains separate and unchanged. Reduced motion retains its neutral static fallback.
- Expanded resume preview uses a body portal to escape backdrop-filter containing
  blocks. Its existing controls, document requests, and permission checks remain.
  Focus returns to the inline maximize control after minimize/Escape.
- Mobile choice sizing now wins over the desktop selector (34px rather than 32px).
- Tests reflect approved 94% auth/96% dense ivory surfaces and 98% white fields,
  existing focus halo, and inline custom-choice entry. No transparency redesign.
- Since staging, backend runtime changes are limited to accepting and validating
  `portfolio_url` in existing career-preferences JSON. Backend tests cover it.
- No model, migration, dependency, Compose, queue contract, or worker-code change.
  API and worker share the backend image: replace BOTH together to keep versions
  aligned. Do not rebuild or recreate DB, scanner, or edge for this release.

## Backup and live state (read-only rechecked)

Verified backup:
`s3://enter-staging-backups-2021/postgres/2026/10/21/070059-1a48a7d3fe0445ddad0bd12f256498d1.dump`

101,744 bytes; last modified `2026-10-21T07:01:01Z`; AES256 server-side encryption.
SHA-256: `1ec0b5aae58265316590313c8f9d549c5bab7faced5d1ab9393b38629082444a`.
Prior isolated restore and S3 readback passed; current HEAD metadata matches.
All six live containers are running with unchanged start times. DB, API, worker,
and scanner report healthy; frontend/edge have no configured Docker healthcheck.

Aggregate checks found zero users joined/logged in and zero profiles
updated/submitted after the dump began. This is NOT proof that every table is
unchanged: queue, sessions and other state can change. Recheck immediately before
deployment and obtain a fresh verified backup if any new business data exists or
the deployment is delayed. Never restore this dump over later live data as a code rollback.

## Rollback image IDs (locally stored Docker content IDs, not registry digests)

| Service | Current immutable image ID |
| --- | --- |
| backend + worker | `sha256:f264e4a5249adca347de6c4cbed1bb99c7c2fadd1bdb15809664eb109191155a` |
| frontend | `sha256:498a0016562cb77a1d638ee2b6696e1e2d2278fd430ce953e19bb8d25b30ca82` |
| db | `sha256:b90e5d43d79cd7fe2dd182981d01e679512b17f39684f02c4fc2687e670dcbca` |
| edge | `sha256:8d252107800410fa523fcf6143e11d53c067384d76a907949a6523f127330624` |
| scanner | `sha256:79690dbbff25303e861c6b4a93f3dd6bd19a883896403e89c1aae01ceaabb19e` |

## Proposed minimal deployment — only after separate approval

1. Approve a commit for the reviewed changes. Record its full SHA as
   `RELEASE_SHA`; require a clean worktree and rerun final tests on that commit.
   Verify the server still runs the recorded images and Compose is unchanged.
2. Build only frontend and backend on the local Mac for linux/amd64, test the
   resulting images, and transfer image archives. This avoids build CPU/RAM load
   on staging. Check local/server disk capacity first. Never overwrite old tags.
   Example commands after the actual SHA has been assigned:

   ```sh
   RELEASE_SHA='<approved-full-commit-sha>'
   docker build --platform linux/amd64 -f backend/Dockerfile.production -t "enter-backend:$RELEASE_SHA" .
   docker build --platform linux/amd64 -f frontend/Dockerfile --build-arg VITE_API_URL=/api/v1 -t "enter-frontend:$RELEASE_SHA" .
   docker save -o "/private/tmp/enter-$RELEASE_SHA.images.tar" "enter-backend:$RELEASE_SHA" "enter-frontend:$RELEASE_SHA"
   shasum -a 256 "/private/tmp/enter-$RELEASE_SHA.images.tar"
   scp -i /Users/enter/.ssh/enter-staging-key.pem "/private/tmp/enter-$RELEASE_SHA.images.tar" ubuntu@3.26.28.4:/tmp/
   ```

   Independently compare the server archive SHA-256 before `docker load`.
   Pin/record the resulting built image IDs; base-image updates during build
   require renewed verification, not an assumption that source tests suffice.
   Preserve the current server checkout, `.env.production`, server-only files,
   Caddyfile, and all `/srv/enter-data` directories. Image-only deployment needs
   no `git pull`, checkout, or file sync into the existing deployment directory.
   The deployed release SHA is thereafter recorded by image tag (the preserved
   host source checkout will still show the older SHA; do not confuse these).
3. Verify backup freshness, migrations, API/worker readiness, and queue counts.
   Wait for in-flight resume jobs to finish; do not force interrupt them. Stop
   and reschedule if work cannot drain safely. Queue messages must not be purged.
4. On EC2, after all gates pass, use the EXISTING Compose/configuration:

   ```sh
   cd /opt/enter/Recruiter
   RELEASE_SHA='<approved-full-commit-sha>'
   sudo docker load -i "/tmp/enter-$RELEASE_SHA.images.tar"
   sudo docker image tag sha256:f264e4a5249adca347de6c4cbed1bb99c7c2fadd1bdb15809664eb109191155a enter-backend:rollback-20261021
   sudo docker image tag sha256:498a0016562cb77a1d638ee2b6696e1e2d2278fd430ce953e19bb8d25b30ca82 enter-frontend:rollback-20261021
   sudo env ENTER_RELEASE="$RELEASE_SHA" docker compose --project-name recruiter --env-file .env.production -f compose.production.yaml up -d --no-deps --no-build --pull never backend worker
   sudo docker compose --project-name recruiter --env-file .env.production -f compose.production.yaml exec -T backend python manage.py check_resume_operations
   # Proceed only after API/worker health and same-origin readiness pass.
   sudo env ENTER_RELEASE="$RELEASE_SHA" docker compose --project-name recruiter --env-file .env.production -f compose.production.yaml up -d --no-deps --no-build --pull never frontend
   ```

   No `migrate`, full-stack `up`, `down`, `prune`, or volume operations.
   Existing DB/scanner/edge image tags need not exist under the new SHA because
   `--no-deps` explicitly excludes their recreation. Verify that exclusion.
5. Verify HTTPS externally and through loopback; homepage, CSP/video, API readiness,
   auth, synthetic verification, upload/scan/process/preview, private access denial,
   profile submission, recruiter search/visibility, worker queue health. Real SES,
   SQS, ClamAV, and private S3 integration require approved staging smoke testing;
   local mocks/development scanner do not prove these provider paths.

Expect a short API interruption while the single backend container is recreated,
a worker processing pause, and a short frontend interruption during replacement.
This is not zero-downtime. Existing database, uploads and queue remain intact.
If a job is interrupted despite draining, durable queue visibility/retry handling
must be checked before declaring success; do not manually delete its message.

## Code-only rollback (after deployment approval, if necessary)

Keep the previous images. Drain active worker work before switching back where
possible. In the existing deployment directory:

```sh
sudo env ENTER_RELEASE=rollback-20261021 docker compose --project-name recruiter --env-file .env.production -f compose.production.yaml up -d --no-deps --no-build --pull never backend worker frontend
```

Recheck image IDs, health, HTTPS and queued jobs. No schema rollback or database
restore is needed for this release. Preserve all data written after deployment.
The old API may not accept new portfolio edits; restoring the matching old frontend
avoids version skew. Do not delete the saved portfolio data.

## Cost

No new AWS infrastructure or plan upgrade. Local tests/builds do not add AWS
compute resources. Read-only metadata requests and image-transfer overhead are
small; storage capacity must be checked before loading images. Existing EC2/EBS/
IPv4 spending continues. A fresh small backup adds negligible S3 storage/request
cost, not a new compute service. Exact incremental billed cost is not yet available.

## Verification

TypeScript/build, ESLint, 98 frontend unit tests, 206 PostgreSQL backend tests,
Ruff, Django system checks and migration-drift checks passed. Production nginx
CSP playback and reduced-motion tests passed (2). Auth tests passed at
390/768/1024/1440; recruiter search/filters/compare/project flow passed. Surface
review passed at all four widths across video frames. All six candidate browser
flows passed on PostgreSQL, including the full PDF/DOCX lifecycle and real retry
backoffs. Across final runs/reruns: 18 core browser tests passed, one optional
original-HTML reference comparison was skipped, two production CSP tests passed,
and one four-width video/surface review passed (21 distinct passing checks).

The combined run had 16 passes, two auth timing failures, and one skip under the
old 30-second budget; the complete auth file then passed all seven tests with a
60-second multi-screen budget. Production CSP playback passed separately after
the build stopped changing and concurrent browser runs ended. Earlier SQLite
locking and test-server origin errors were test-harness issues; final candidate
flows used isolated local PostgreSQL. No assertions were removed to hide a real
UI defect: obsolete glow/Add-option/work-setup expectations were replaced with
the current approved UI behavior.

Evidence directories (local, synthetic data only):
- `/private/tmp/enter-release-final-suite` (all six candidate flows and recruiter flows)
- `/private/tmp/enter-release-auth-final` (7/7 auth)
- `/private/tmp/enter-release-csp-final-alone` (2/2 production CSP)
- `/private/tmp/enter-release-surfaces` (four-width surface/video review)
- `/private/tmp/enter-release-lifecycle-final` (PDF/DOCX viewport screenshots)

Outstanding gates: exact-commit image build/scan verification, fresh
backup decision, and explicit deployment approval. SMTP delivery and real AWS
queue/storage/scanner paths are reserved for approved staging smoke tests.

### Files changed in this task

- `frontend/nginx.conf`: narrowly scoped media CSP.
- `frontend/src/components/CandidateResumePreview.tsx`: viewport portal and focus restoration.
- `frontend/src/components/candidate-experience.css`: restore intended mobile chip target sizing.
- `frontend/src/components/CandidateExperience.test.tsx`: portal/focus regression assertions.
- `frontend/tests/production-csp.spec.ts`: real production-header playback/fallback checks.
- `frontend/tests/design-contract.ts`: explicit approved surface and focus contracts.
- `frontend/tests/auth-ui.spec.ts`: tablet coverage, surface contract, multi-screen timeout budget.
- `frontend/tests/recruiter-search-ui.spec.ts`: approved dense surface opacity.
- `frontend/tests/candidate-flow.spec.ts`: approved inline choice behavior and work-mode wording.
- This report and `deploy/release-changed-files-2026-10-21.txt`.

The manifest lists all 654 tracked paths changed since staging (including earlier
approved UI/assets and tracked review artifacts), plus these new release files.
No existing review artifacts or server-only files were deleted.

PDF checks verify authenticated PDF bytes, blob iframe source, fallback download
link, and viewport controls. Headless screenshots do not establish native PDF
viewer paint behavior on every browser; include a real-browser check in staging smoke tests.
