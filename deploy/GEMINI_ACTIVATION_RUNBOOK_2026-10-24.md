# ENTER paid-Gemini activation runbook

Status: **TECHNICALLY PREPARED — NOT AUTHORIZED FOR PUBLICATION OR ACTIVATION**

The current production release stays operational with live v1.0 Privacy and
Terms, rule-based resume extraction, and every Gemini/external-AI switch off.
Dikshita Verma's approval of the exact v1.2 Privacy, v1.2 Terms, and v1.1
resume-AI consent copies is complete in her role as CEO. It is not qualified
legal evidence. `sheba@enterrecruitment.com` is a contact address, not a legal
review reference.

This runbook does not authorize a provider call. It separates future legal
publication, one fictional paid-Gemini canary, and any later consenting rollout.

## Prepared artifacts

- `scripts/check_gemini_activation_readiness.py` performs offline preparation,
  publication, and activation checks without reading secret contents or making
  a network request.
- `backend/Dockerfile.gemini-canary` layers only the three reviewed legal files
  over an exact reviewed AI-disabled backend image.
- `deploy/compose.gemini-publication.yaml` publishes the approved legal package
  through the backend while keeping resume AI disabled and loading no key.
- `deploy/compose.gemini-canary.yaml` enables paid Gemini only in the worker, for
  one explicit fictional resume ID, with one attempt and rule fallback.
- `deploy/compose.gemini-consenting.yaml` is a separate post-canary step. It must
  never be combined during the first canary.
- `deploy/GEMINI_ACTIVATION_EVIDENCE.example.json` defines the existing evidence
  fields without inventing reviewer details or provider references.

## Phase 0 — keep the current release locked

Run:

```text
uv run python scripts/check_ai_disabled_release.py
uv run python scripts/check_gemini_activation_readiness.py
```

Both checks must pass. The second must report zero external requests, completed
CEO approval, and separately pending qualified legal evidence. Do not install a
Gemini key, change publication statuses, or restart production for this phase.

## Phase 1 — evidence and legal publication

Proceed only after the actual reviewer evidence is available. Create a completed
evidence JSON from the example and record the reviewer's name, legal
qualification or authority, review reference, actual review date, full scope,
the three exact versions and hashes, paid-project/DPA verification, logging and
retention review, key-owner authorization reference, verified token prices, and
approved daily/monthly budgets. Do not put an API key in that file.

Then:

1. Change only the three `PUBLICATION STATUS` lines from `PENDING REVIEW` to
   `APPROVED`. Do not alter the bounded public copy.
2. Record the real publication effective date; do not backdate it to the CEO
   approval timestamp.
3. Run the publication gate:

```text
uv run python scripts/check_gemini_activation_readiness.py \
  --phase publication \
  --evidence-file /absolute/path/to/completed-evidence.json
```

4. Build the legal-package backend from the exact deployed AI-disabled image:

```text
docker build --platform linux/amd64 \
  --build-arg ENTER_BASE_BACKEND_IMAGE=enter-backend:<ai-disabled-commit> \
  -f backend/Dockerfile.gemini-canary \
  -t enter-backend:<gemini-release> .
```

5. Verify the image's legal manifest, run deployment checks, verify a fresh
   recoverable backup, and register the rollback image IDs.
6. Apply only `deploy/compose.gemini-publication.yaml` to `backend`. Do not touch
   the worker yet. Confirm Privacy, Terms, and the optional AI consent return the
   approved versions/hashes over HTTPS while ordinary uploads still use rules.

If backend health or legal hash checks fail, restore the preceding backend image.
Do not roll back the database.

## Phase 2 — one fictional production canary

Use a newly generated fictional resume containing no real name, email, phone,
employer, client, or other candidate data.

1. Confirm the worker queue has no overdue or failed jobs, then stop only the
   worker briefly. Uploads remain durable while it is stopped.
2. Create a short-lived fictional candidate through the normal public flow and
   upload the fictional resume with the optional Gemini checkbox selected.
3. Record that single new resume ID. No historical or real resume ID may be used.
4. Store the production key outside Git and `.env.production`, owned by root and
   inaccessible to other host users. Mount it only through the worker secret in
   `deploy/compose.gemini-canary.yaml`.
5. Run the activation gate on the production host:

```text
uv run python scripts/check_gemini_activation_readiness.py \
  --phase activation \
  --evidence-file /absolute/path/to/completed-evidence.json \
  --secret-file /absolute/path/to/root-owned-gemini-key \
  --canary-resume-id <fictional-resume-id>
```

6. Set the approved effective date, budgets, current token prices, release tag,
   and the single fictional resume ID. Start only the worker with
   `compose.production.yaml` plus `compose.gemini-canary.yaml`.
7. Verify exactly one Gemini usage record for the fictional resume, one provider
   request, paid-service accounting, clean scan, evidence validation, profile
   review output, and no AI usage for any other resume.
8. Delete the fictional account through the normal candidate deletion flow and
   verify private-file cleanup. Retained closure evidence is expected.

If the provider, schema, validation, budget, worker, or profile check fails,
immediately recreate the worker with `deploy/compose.ai-disabled-release.yaml`.
Leave additive migrations and published legal records intact; do not perform a
destructive database rollback.

## Phase 3 — consenting rollout

Do not promote automatically after the canary. A separate explicit activation
decision is required. Recheck backup, worker health, budget values, key mount,
legal hashes, and canary evidence. Only then combine
`deploy/compose.gemini-consenting.yaml` after the canary overlay and recreate the
worker. The candidate checkbox remains optional and unchecked, rules remain the
fallback, non-consenting and historical resumes remain ineligible, and recruiter
access remains disabled.

Monitor provider failures, validation rejections, costs, queue age, processing
latency, and fallback rate. Any unexplained external request or budget anomaly
requires returning the worker to the AI-disabled overlay.
