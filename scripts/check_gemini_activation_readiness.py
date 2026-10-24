"""Offline, fail-closed checks for Gemini activation preparation.

Preparation mode confirms that the current production release remains AI-disabled
and that the future activation artifacts are internally consistent. Publication
and activation additionally require approved publication statuses and one completed
accountable release-approval record. The record may document genuine qualified
legal clearance or management privacy/legal risk acceptance, but must never confuse
the two. This script never reads a secret's contents and never makes a network call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"

DOCUMENTS = {
    "privacy": {
        "path": DEPLOY / "PRIVACY_POLICY_PUBLICATION.txt",
        "version": "enter-candidate-privacy-v1.2",
        "sha256": "6549ab6514b940459b8b853ee63643fc97c91f9dfc2d62aac511083c6b1bf574",
    },
    "terms": {
        "path": DEPLOY / "TERMS_PUBLICATION.txt",
        "version": "enter-candidate-terms-v1.2",
        "sha256": "c545340b49350c664d0073e081dd4314a6464238adc6a61f9fc8a87b5647dd53",
    },
    "resume_ai": {
        "path": DEPLOY / "RESUME_AI_CONSENT_PUBLICATION.txt",
        "version": "enter-resume-ai-consent-v1.1",
        "sha256": "e9ba89892b3b29aa738ef7dc7ff2913149be87c44080a058ddfa3cc677041040",
    },
}

LIVE_DOCUMENTS = {
    "PRIVACY_POLICY_PUBLICATION.txt": (
        "ebbafdb80abbcaf856490d1385b74b2cf8e15ec8826e7297753c836c7f8db49e"
    ),
    "TERMS_PUBLICATION.txt": (
        "55b5b1ebca80a523218760499bedd2c93650b9ff04350f4355c483d313e825ef"
    ),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def public_text(path: Path) -> tuple[str, str]:
    source = path.read_text()
    lines = source.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.strip() == "PROPOSED PUBLIC COPY"]
    ends = [
        index
        for index, line in enumerate(lines)
        if line.strip() == "END OF PROPOSED PUBLIC COPY"
    ]
    require(
        len(starts) == 1 and len(ends) == 1 and starts[0] < ends[0],
        f"Invalid public-copy boundary: {path}",
    )
    text = "".join(lines[starts[0] + 1 : ends[0]]).strip() + "\n"
    return source, text


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def verify_documents(phase: str) -> None:
    expected_status = (
        "PUBLICATION STATUS: PENDING REVIEW"
        if phase == "preparation"
        else "PUBLICATION STATUS: APPROVED"
    )
    for item in DOCUMENTS.values():
        source, text = public_text(item["path"])
        statuses = [
            line.strip()
            for line in source.splitlines()
            if line.startswith("PUBLICATION STATUS:")
        ]
        require(statuses == [expected_status], f"Unexpected status: {item['path'].name}")
        require(digest(text) == item["sha256"], f"Public text changed: {item['path'].name}")

    live_root = DEPLOY / "live-legal-v1.0"
    for name, expected_hash in LIVE_DOCUMENTS.items():
        source, text = public_text(live_root / name)
        require(
            "PUBLICATION STATUS: APPROVED" in source,
            f"Live v1.0 status changed: {name}",
        )
        require(digest(text) == expected_hash, f"Live v1.0 hash changed: {name}")


def verify_completed_ceo_approval() -> None:
    register = (DEPLOY / "CONSENT_AND_LEGAL_SIGNOFF_FINAL_REVIEW.txt").read_text()
    normalized = " ".join(register.split())
    required = (
        "Dikshita Verma, CEO, ENTER Recruitment Private Limited",
        "2026-10-24T20:00:00+05:30",
        "completed CEO approval",
        "do not establish a legal qualification",
        "contact address, not a legal-review",
    )
    for value in required:
        require(value in normalized, f"CEO approval record is incomplete: {value}")
    for item in DOCUMENTS.values():
        require(item["version"] in register, f"CEO record lacks {item['version']}")
        require(item["sha256"] in register, f"CEO record lacks {item['sha256']}")


def verify_current_release_is_disabled() -> None:
    production = (ROOT / "compose.production.yaml").read_text()
    disabled = (DEPLOY / "compose.ai-disabled-release.yaml").read_text()
    for source in (production, disabled):
        for line in (
            'GEMINI_API_KEY: ""',
            'RESUME_AI_API_KEY: ""',
            'RESUME_AI_ENABLED: "false"',
            'RESUME_AI_EXTERNAL_PROCESSING_APPROVED: "false"',
            'RESUME_AI_ALLOW_PAID: "false"',
        ):
            require(line in source, f"Current release lost fail-closed setting: {line}")
    dockerfile = (ROOT / "backend" / "Dockerfile.production").read_text()
    require(
        "deploy/live-legal-v1.0/PRIVACY_POLICY_PUBLICATION.txt" in dockerfile,
        "Current production image no longer packages live v1.0 privacy",
    )
    require(
        "deploy/RESUME_AI_CONSENT_PUBLICATION.txt" not in dockerfile,
        "Current production image unexpectedly packages pending Gemini consent",
    )


def verify_activation_artifacts() -> None:
    publication = (DEPLOY / "compose.gemini-publication.yaml").read_text()
    canary = (DEPLOY / "compose.gemini-canary.yaml").read_text()
    consenting = (DEPLOY / "compose.gemini-consenting.yaml").read_text()
    dockerfile = (ROOT / "backend" / "Dockerfile.gemini-canary").read_text()

    require("services:\n  backend:" in publication, "Publication overlay must target backend")
    require("\n  worker:" not in publication, "Publication overlay must not enable the worker")
    require('RESUME_AI_ENABLED: "false"' in publication, "Publication must keep AI disabled")
    require("services:\n  worker:" in canary, "Canary overlay must target worker")
    require("\n  backend:" not in canary, "Canary key overlay must not target backend")
    require("gemini_resume_api_key" in canary, "Canary worker secret is missing")
    require(
        "RESUME_AI_API_KEY_FILE: /run/secrets/gemini_resume_api_key" in canary,
        "Worker must read Gemini key from its secret file",
    )
    require('GEMINI_API_KEY: ""' in canary, "Gemini key must not be an environment value")
    require('RESUME_AI_ALLOW_PAID: "true"' in canary, "Canary must require paid service")
    require(
        'RESUME_AI_GEMINI_FREE_TIER_APPROVED: "false"' in canary,
        "Production canary must prohibit Gemini Free tier",
    )
    require("RESUME_AI_ROLLOUT_MODE: canary" in canary, "First rollout must be canary")
    require(
        "RESUME_AI_CANARY_RESUME_IDS: ${ENTER_GEMINI_CANARY_RESUME_ID:" in canary,
        "Canary must require one explicit resume ID",
    )
    require("RESUME_AI_ROLLOUT_MODE: consenting" in consenting, "Consenting overlay missing")
    require('RESUME_AI_CANARY_RESUME_IDS: ""' in consenting, "Consenting mode must clear IDs")
    require("RESUME_AI_CONSENT_PUBLICATION.txt" in dockerfile, "Gemini image lacks consent")
    require("ARG ENTER_BASE_BACKEND_IMAGE" in dockerfile, "Gemini image lacks exact base pin")


def completed_string(value: object, label: str) -> str:
    require(isinstance(value, str) and value.strip(), f"Evidence missing: {label}")
    return value.strip()


def positive_decimal(value: object, label: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except InvalidOperation as error:
        raise RuntimeError(f"Evidence is not numeric: {label}") from error
    require(number > 0, f"Evidence must be positive: {label}")
    return number


def verify_evidence(path: Path) -> dict:
    require(path.is_file(), "Completed activation evidence file is missing")
    require(
        path.name != "GEMINI_ACTIVATION_EVIDENCE.example.json",
        "Example evidence is not approval",
    )
    evidence = json.loads(path.read_text())
    require(evidence.get("status") == "APPROVED", "Release decision is not approved")
    date.fromisoformat(
        completed_string(evidence.get("publication_effective_date"), "effective date")
    )

    approval = evidence.get("release_approval", {})
    basis = completed_string(approval.get("basis"), "release approval basis")
    require(
        basis in {"qualified_legal_clearance", "management_risk_acceptance"},
        "Release approval basis must be qualified legal clearance or management risk acceptance",
    )
    for field in ("reviewer_name", "authority", "review_reference", "review_date"):
        completed_string(approval.get(field), f"release approval {field}")
    date.fromisoformat(approval["review_date"])
    if basis == "qualified_legal_clearance":
        require(
            approval.get("independent_qualified_legal_clearance") is True,
            "Qualified legal clearance must be expressly recorded",
        )
    else:
        require(
            approval.get("independent_qualified_legal_clearance") is False,
            "Management risk acceptance must not be labelled qualified legal clearance",
        )
        require(
            approval.get("management_risk_accepted") is True,
            "Management privacy/legal risk acceptance must be explicit",
        )
    scope = approval.get("scope_confirmed", {})
    require(scope and all(scope.values()), "Release-approval scope is incomplete")

    approved = evidence.get("approved_documents", {})
    for purpose, expected in DOCUMENTS.items():
        actual = approved.get(purpose, {})
        require(actual.get("version") == expected["version"], f"Wrong {purpose} version")
        require(actual.get("sha256") == expected["sha256"], f"Wrong {purpose} hash")

    controls = evidence.get("provider_controls", {})
    require(controls.get("google_project") == "enter", "Wrong Google project")
    require(controls.get("paid_tier") == "Paid Tier 1", "Paid Tier 1 is not recorded")
    require(controls.get("paid_service_verified") is True, "Paid service is not verified")
    require(controls.get("auto_reload_enabled") is False, "Google Auto-reload must remain off")
    require(
        Decimal(str(controls.get("google_monthly_cap_inr"))) == Decimal("100"),
        "Google monthly project cap must remain INR 100",
    )
    for field in (
        "dpa_reference",
        "logging_and_retention_review_reference",
        "api_key_owner_authorization_reference",
    ):
        completed_string(controls.get(field), f"provider control {field}")
    for field in (
        "daily_budget_usd",
        "monthly_budget_usd",
        "input_usd_per_million",
        "output_usd_per_million",
    ):
        positive_decimal(controls.get(field), f"provider control {field}")
    require(
        Decimal(str(controls.get("input_usd_per_million"))) == Decimal("0.30"),
        "Gemini input price does not match the reviewed price",
    )
    require(
        Decimal(str(controls.get("output_usd_per_million"))) == Decimal("2.50"),
        "Gemini output price does not match the reviewed price",
    )

    limits = evidence.get("activation_limits", {})
    require(limits.get("model") == "gemini-3.5-flash-lite", "Wrong Gemini model")
    require(limits.get("paid_attempts") == 1, "Canary must allow one paid attempt")
    require(limits.get("paid_retries") == 0, "Paid retries must remain disabled")
    require(limits.get("historical_reprocessing") is False, "Historical processing is forbidden")
    for field in ("rule_fallback", "manual_edit_protection", "worker_only_secret"):
        require(limits.get(field) is True, f"Activation control missing: {field}")
    return evidence


def verify_secret(path: Path) -> None:
    require(path.is_file(), "Worker-only Gemini secret file is missing")
    mode = stat.S_IMODE(path.stat().st_mode)
    require(mode & 0o007 == 0, "Gemini secret must not be accessible to other users")
    require(path.stat().st_uid == 0, "Gemini secret must be root-owned")
    require(path.stat().st_size > 0, "Gemini secret file is empty")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=("preparation", "publication", "activation"),
        default="preparation",
    )
    parser.add_argument("--evidence-file", type=Path)
    parser.add_argument("--secret-file", type=Path)
    parser.add_argument("--canary-resume-id", type=int)
    args = parser.parse_args()

    verify_documents(args.phase)
    verify_completed_ceo_approval()
    verify_current_release_is_disabled()
    verify_activation_artifacts()

    result = {
        "gemini_technical_preparation": "PASS",
        "current_production": "AI-disabled and live-v1.0 legal preserved",
        "ceo_approval": "recorded and complete",
        "release_approval_evidence": "pending one attributable release decision",
        "external_requests": 0,
    }
    if args.phase in {"publication", "activation"}:
        require(args.evidence_file is not None, "Activation evidence file is required")
        verify_evidence(args.evidence_file)
        result.update(
            {
                "release_approval_evidence": "verified structurally",
                "publication_gate": "PASS",
            }
        )
    if args.phase == "activation":
        require(args.secret_file is not None, "Worker-only secret file is required")
        require(
            args.canary_resume_id is not None and args.canary_resume_id > 0,
            "One fictional canary resume ID is required",
        )
        verify_secret(args.secret_file)
        result.update(
            {
                "activation_gate": "PASS",
                "canary_resume_id": args.canary_resume_id,
            }
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
