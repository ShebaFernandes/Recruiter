# ENTER AI-disabled release candidate — local preparation

Status: locally prepared; not deployed.

This release preserves the currently published candidate legal copy and keeps
registration, resume uploads, saved profiles, queued work, and candidate access
available. It does not publish the pending Gemini-aware documents, enable Gemini,
load a Gemini consent hash, or permit external resume processing.

## Release invariants

- The backend image packages the approved live Privacy and Terms v1.0 snapshot
  from `deploy/live-legal-v1.0/`, with the existing immutable hashes.
- The three CEO-approved Gemini-aware files remain at `PUBLICATION STATUS: PENDING
  REVIEW`, with their recorded versions and public-text hashes unchanged.
- `compose.production.yaml` overrides recruiter AI and resume AI to disabled,
  clears provider keys from application containers, and does not add an AI secret.
- `deploy/compose.ai-disabled-release.yaml` repeats those fail-closed controls for
  the migration, backend, and worker containers without targeting the database,
  scanner, or edge services. Use it for the image-only production rollout.
- The production environment must retain
  `CANDIDATE_REGISTRATION_PAUSED=false` and `RESUME_UPLOADS_PAUSED=false`.
- `LEGAL_RESUME_AI_APPROVED=false`, `LEGAL_RESUME_AI_SHA256=` and all resume-AI
  enablement/paid/external-processing flags remain false.

Run the offline invariant check before building:

```sh
uv run python scripts/check_ai_disabled_release.py
uv run python scripts/check_ai_disabled_release.py --env-file /absolute/path/to/.env.production
uv run python scripts/check_deploy.py
```

The second command reads the production environment locally, reports only the
name of a failing invariant, and never prints secret values. Do not copy a
production environment into the repository.

Build and scan immutable images locally, record their digests, and keep the live
stack unchanged. This repository's current single-backend Compose topology cannot
prove a zero-connection-drop backend replacement. Do not recreate the live
backend merely to claim a non-interrupting release; use an authorized maintenance
window or a separately verified blue/green switch. No deployment is part of this
preparation.

For deployment, always combine the production Compose file with the application-
only release overlay and set the exact reviewed release tag. Run the one-off
migration with both files, then recreate only `backend worker frontend` with
`--no-deps --no-build --pull never`. Never run a full-stack `up` or `down` for
this release.

## Single remaining release-decision evidence requirement

Record one attributable decision containing the reviewer's name, actual authority,
review reference, and actual review date. It may be genuine qualified legal
clearance or explicit management privacy/legal risk acceptance, but must not
confuse the two. The decision must expressly cover the exact three recorded
versions and hashes and the Gemini processing/overseas transfer/DPA and Terms
liability/jurisdiction issues. This is ENTER's publication control for the pending
documents, not an identified statutory lawyer-signature requirement and not a
blocker to local AI-disabled build and release preparation.
