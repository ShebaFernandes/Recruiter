"""Prepare hash-pinned review artifacts without approval claims or runtime writes."""

import difflib
import hashlib
import json
import os
import re
from pathlib import Path

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from talent import google_signup as signup  # noqa: E402 - Django must be initialized first
from talent import legal  # noqa: E402 - Django must be initialized first

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
REVIEW = OUT.parent
amendments = (REVIEW / "policy-amendments.txt").read_text()


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def clause(start, end):
    return amendments.split(start, 1)[1].split(end, 1)[0].strip()


terms_clauses = [
    clause("T1. Section 1, eligibility paragraph — replace with:", "\nT2."),
    clause("T2. Section 2, first paragraph — replace with:", "\nT3."),
    clause("T3. Section 9, first paragraph — replace with:", "\nRetain the existing"),
]
privacy_clauses = [
    clause("P1. Section 2, first information-category bullet — replace with:", "\nP2."),
    clause("P2. Section 2, bullet about draft/paused/submitted state — replace with:", "\nP3."),
    clause("— add:", "\nP4."),
    clause(
        "P4. Section 7, paragraph beginning “You must separately confirm” — replace with:",
        "\nREVIEW DECISION",
    ),
]


def replace_paragraph(text, prefix, replacement):
    pattern = r"(?m)^" + re.escape(prefix) + r"[^\n]*(?:\n(?!\n|- )[^\n]+)*"
    result, count = re.subn(pattern, lambda _: replacement, text)
    if count != 1:
        raise ValueError(f"Expected one paragraph: {prefix}; found {count}")
    return result


notice_hash = digest(signup.NOTICE)
review_hash = hashlib.sha256((REVIEW / "review-manifest.json").read_bytes()).hexdigest()
manifest = json.loads((REVIEW / "review-manifest.json").read_text())
assert all(
    hashlib.sha256((REVIEW / f).read_bytes()).hexdigest() == h
    for f, h in manifest["draft_files"].items()
)
assert signup.NOTICE in (REVIEW / "signup-notice.txt").read_text()

for baseline, source in [
    ("live-v1.0", ROOT / "deploy/live-legal-v1.0"),
    ("root-v1.2", ROOT / "deploy"),
]:
    folder = OUT / baseline
    folder.mkdir(exist_ok=True)
    original = {
        p: legal._published_text(source / f)
        for p, f in [
            ("terms", "TERMS_PUBLICATION.txt"),
            ("privacy", "PRIVACY_POLICY_PUBLICATION.txt"),
        ]
    }
    terms = replace_paragraph(original["terms"], "New registration is limited", terms_clauses[0])
    terms = replace_paragraph(terms, "Provide accurate registration information", terms_clauses[1])
    terms = replace_paragraph(terms, "ENTER records the candidate identifier", terms_clauses[2])
    privacy = replace_paragraph(
        original["privacy"], "- your name, email address", privacy_clauses[0]
    )
    privacy = replace_paragraph(privacy, "- draft, paused, and submitted", privacy_clauses[1])
    # Preserve every other category bullet; paragraphs above must stop at the next bullet.
    if "- your PDF or DOCX resume" not in privacy or "- support, privacy" not in privacy:
        raise ValueError("A replacement removed an unrelated information-category bullet")
    cookie = re.search(r"(?m)^The platform uses a Secure[^\n]*(?:\n(?!\n)[^\n]+)*", privacy)
    if not cookie:
        raise ValueError("Cookie disclosure anchor absent")
    privacy = privacy[: cookie.end()] + "\n\n" + privacy_clauses[2] + privacy[cookie.end() :]
    privacy = replace_paragraph(privacy, "You must separately confirm", privacy_clauses[3])
    texts = {
        "terms": terms,
        "privacy": privacy,
        "age": "I confirm that I am at least 18 years old.",
        "submission": (
            "I confirm that I have reviewed my profile and ask ENTER to save it as submitted. "
            "Recruiter access is currently disabled. ENTER will ask for my separate, explicit "
            "permission before sharing my profile or resume with approved recruiters."
        ),
    }
    versions = {p: f"enter-candidate-{p}-{baseline}-google-draft02-local-review" for p in texts}
    # Existing declarations/confirmation texts have not changed: retain their original IDs.
    versions.update(age="enter-candidate-age-v1.0", submission="enter-candidate-submission-v1.0")
    docs = {p: {"version": versions[p], "sha256": digest(t)} for p, t in texts.items()}
    for purpose, filename in [
        ("terms", "TERMS_PUBLICATION.txt"),
        ("privacy", "PRIVACY_POLICY_PUBLICATION.txt"),
    ]:
        (folder / filename).write_text(
            f"Document identifier: {versions[purpose]}\nEffective date: PENDING ACTUAL APPROVAL\n"
            "PUBLICATION STATUS: PENDING\n\nPROPOSED PUBLIC COPY\n"
            + texts[purpose]
            + "END OF PROPOSED PUBLIC COPY\n"
        )
        (folder / f"{purpose}.diff").write_text(
            "".join(
                difflib.unified_diff(
                    original[purpose].splitlines(True),
                    texts[purpose].splitlines(True),
                    fromfile=str(source / filename),
                    tofile=f"prepared-{baseline}/{filename}",
                )
            )
        )
    (folder / "bundle-manifest.json").write_text(
        json.dumps(
            {
                "status": "PREPARED_NOT_APPROVED_NOT_ACTIVE",
                "baseline": baseline,
                "baseline_file_sha256": {
                    p: hashlib.sha256((source / f).read_bytes()).hexdigest()
                    for p, f in [
                        ("terms", "TERMS_PUBLICATION.txt"),
                        ("privacy", "PRIVACY_POLICY_PUBLICATION.txt"),
                    ]
                },
                "documents": docs,
                "notice_sha256": notice_hash,
                "review_package_sha256": review_hash,
                "effective_date": None,
            },
            indent=2,
        )
        + "\n"
    )
    (folder / "approval-record.pending.json").write_text(
        json.dumps(
            {
                "decision": None,
                "reviewer_name": None,
                "reviewer_role": None,
                "approved_at": None,
                "decision_reference": None,
                "conditions": None,
                "mechanism_id": signup.MECHANISM,
                "notice_sha256": notice_hash,
                "review_package_sha256": review_hash,
                "documents": docs,
                "legal_baseline": baseline,
                "effective_date": None,
            },
            indent=2,
        )
        + "\n"
    )
    config = {
        "GOOGLE_SIGNUP_AUTOCREATE_ENABLED": "false",
        "LEGAL_CONTENT_APPROVED": "false",
        "LEGAL_WORKFLOW_PREVIEW": "false",
        "LEGAL_DOCUMENT_ROOT": str(folder),
        "LEGAL_EFFECTIVE_DATE": "",
        "GOOGLE_SIGNUP_APPROVAL_FILE": "",
        "GOOGLE_SIGNUP_APPROVAL_SHA256": "",
    }
    for p in docs:
        config[f"LEGAL_{p.upper()}_VERSION"] = versions[p]
        config[f"LEGAL_{p.upper()}_SHA256"] = docs[p]["sha256"]
    (folder / "local-settings.pending.env").write_text(
        "# PREPARATION ONLY. Do not load as runtime configuration. Approval is pending.\n"
        + "\n".join(f"{k}={v}" for k, v in config.items())
        + "\n"
    )
    print(
        baseline
        + ": prepared document copies, exact diffs, hashes, incomplete audit template; NOT ACTIVE"
    )
