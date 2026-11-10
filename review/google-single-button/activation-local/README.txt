DRAFT 02 — LOCAL ACTIVATION INPUTS

Selected by Sheba: live-v1.0 plus the exact Draft 02 amendments.
Selected prepared bundle: live-v1.0/ (not root-v1.2/).
Proposed effective date: 2026-11-10, explicitly subject to policy approval.
No approved snapshot, runtime .env, production setting or candidate record changed.

PRESERVED DEVELOPER APPROVAL
  developer-approval-message.txt: user-supplied written decision, verbatim.
  developer-approval-record.json: reviewer, role, actual supplied timestamp,
  message reference/hash, local-only condition, selected baseline and scope.
  This establishes developer authorization. It does not establish policy approval.
  The original unsigned Draft 02 review files remain historical and unchanged.

PREPARED LEGAL BUNDLE
  live-v1.0/TERMS_PUBLICATION.txt and PRIVACY_POLICY_PUBLICATION.txt contain
  complete public text with ONLY Draft 02's T1/T2/T3 and P1/P2/P3/P4 changes.
  Publication status remains PENDING. The proposed new version IDs are distinct
  from historical versions. Unchanged sections and public-text hashes validate.
  terms.diff and privacy.diff show every replacement/insertion against live-v1.0.
  bundle-manifest.json contains exact Terms, Privacy, age and submission hashes,
  original baseline hashes, notice hash and preserved Draft 02 package hash.
  Age/submission text and original version IDs remain unchanged.
  root-v1.2/ is an unselected comparison alternative, not an activated release.

EXACT RECORD REQUIRED FOR ACTIVATION
  live-v1.0/approval-record.pending.json supplies the mechanism and document
  fingerprints. Missing decision fields are intentionally null, not fabricated.
  The authorized policy owner must confirm approval of the exact notice,
  amendments and button mechanism for actual candidate registration, including
  the selected legal baseline and effective date. Record their actual identity,
  policy authority/role, decision time with timezone, written reference and any
  conditions. Preserve the separate developer restriction: local testing only.
  Any approval conditions must be respected, not silently replaced with "none".

  Runtime fields validated by google_signup.release(): decision, mechanism_id,
  reviewer_name, reviewer_role, approved_at, decision_reference, conditions,
  notice_sha256, review_package_sha256, and documents.{terms,privacy,age,submission}
  .{version,sha256}. A real approval file is hash-pinned separately through
  GOOGLE_SIGNUP_APPROVAL_FILE and GOOGLE_SIGNUP_APPROVAL_SHA256.

LOCAL CONFIGURATION — NOT APPLIED
  live-v1.0/local-settings.pending.env enumerates exact document paths,
  version IDs and hashes. Approval and effective-date inputs remain incomplete;
  both legal publication and automatic signup stay disabled in this artifact.
  Do not load this preparation file as operational configuration.

  After actual policy authorization, finalize a separate immutable local release
  copy with the approved effective date/status; validate public-text hashes and
  the approval file. Configure only the isolated .env; enable the existing legal
  hash gate and GOOGLE_SIGNUP_AUTOCREATE_ENABLED only after validation. Preserve
  private env permissions, credential redaction and existing email/password gates.
  Do not overwrite a previously approved legal snapshot or historical decision.

VALIDATION
  TESTING=true PYTHONPATH=backend .venv/bin/python \
    review/google-single-button/activation-local/validate.py
  This validates prepared document hashes, unchanged sections, age/submission
  hashes and IDs, and the required rejection of unapproved publication status.
  It changes no runtime settings or candidate records.

REMAINING BLOCKER
  Authorized policy approval of the exact prepared live-v1.0 legal bundle and
  single-button acceptance/eligibility mechanism, with its effective date.
  The supplied developer approval deliberately leaves that authorization pending.
  Automatic registration and real-Google signup tests must wait for it. Once it
  exists, use an actual disposable Google account, not a synthetic approval or
  an existing candidate's account, for the complete local verification.
