"""Run one explicitly authorized paid-Gemini canary against synthetic local data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from anthropic_resume_local_benchmark import CASES  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.core.files.base import ContentFile  # noqa: E402
from django.utils import timezone  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402
from talent.models import (  # noqa: E402
    CandidateProfile,
    Resume,
    ResumeAIUsage,
    ResumeProcessingJob,
    WorkExperience,
)
from talent.resume_processing import process_resume_job  # noqa: E402
from talent.resume_understanding import (  # noqa: E402
    interpretation_text,
    request_input_token_reservation,
)
from talent.services import parse_resume  # noqa: E402

AUTHORIZED_SHA256 = "dcf9d6f1e5ce37e48418a50c28ec8c529374380305cdb08ba12a75f1fff6fd6b"
MODEL = "gemini-3.5-flash-lite"
MAX_OUTPUT_TOKENS = 3000
MAX_RESERVATION = Decimal("0.009")
INPUT_USD_PER_MILLION = Decimal("0.30")
OUTPUT_USD_PER_MILLION = Decimal("2.50")
FIXTURE = ROOT / ".local-benchmark" / "gemini-resume" / "fictional-promotion-gap.pdf"
REPORT = (
    ROOT
    / ".local-benchmark"
    / "gemini-resume"
    / "gemini-3.5-flash-lite-complex-result.json"
)


def _iso(value):
    return value.isoformat() if isinstance(value, date) else value


def _role_tuple(row):
    return (
        row["company"],
        row["role"],
        _iso(row.get("start_date")),
        _iso(row.get("end_date")),
        bool(row.get("is_current")),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorized-sha256", required=True)
    parser.add_argument(
        "--execute-authorized",
        action="store_true",
        help="Make the single external request after explicit authorization.",
    )
    args = parser.parse_args()
    content = FIXTURE.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if args.authorized_sha256 != AUTHORIZED_SHA256 or digest != AUTHORIZED_SHA256:
        raise SystemExit("Authorized fixture hash does not match; no request made.")
    if settings.DATABASES["default"].get("HOST") not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Database is not local; no request made.")
    if settings.STORAGES["default"]["BACKEND"] != (
        "django.core.files.storage.FileSystemStorage"
    ):
        raise SystemExit("Storage is not local; no request made.")
    if settings.RESUME_QUEUE_BACKEND != "database":
        raise SystemExit("Queue is not the local database queue; no request made.")
    if settings.GEMINI_API_BASE_URL.rstrip("/") != (
        "https://generativelanguage.googleapis.com/v1beta"
    ):
        raise SystemExit("Gemini endpoint is not the reviewed endpoint; no request made.")
    if settings.RESUME_AI_PROVIDER != "gemini" or settings.RESUME_AI_MODEL != MODEL:
        raise SystemExit("Gemini provider/model does not match the test; no request made.")
    if settings.RESUME_AI_MAX_OUTPUT_TOKENS != MAX_OUTPUT_TOKENS:
        raise SystemExit("Output limit does not match the test; no request made.")
    if (
        settings.RESUME_AI_INPUT_USD_PER_MILLION != INPUT_USD_PER_MILLION
        or settings.RESUME_AI_OUTPUT_USD_PER_MILLION != OUTPUT_USD_PER_MILLION
    ):
        raise SystemExit("Gemini accounting prices do not match the reviewed rates.")
    if args.execute_authorized and not (settings.GEMINI_API_KEY or settings.RESUME_AI_API_KEY):
        raise SystemExit("Gemini API key is not configured; no request made.")
    if not args.execute_authorized and settings.RESUME_AI_ENABLED:
        raise SystemExit("AI must remain disabled during preflight; no request made.")
    with FIXTURE.open("rb") as fixture_file:
        document_text = interpretation_text(parse_resume(fixture_file, FIXTURE.name))
    reserved_input_tokens = request_input_token_reservation(document_text)
    reservation = (
        Decimal(reserved_input_tokens) * settings.RESUME_AI_INPUT_USD_PER_MILLION
        + Decimal(MAX_OUTPUT_TOKENS) * settings.RESUME_AI_OUTPUT_USD_PER_MILLION
    ) / Decimal("1000000")
    if reservation > MAX_RESERVATION:
        raise SystemExit("Conservative reservation exceeds the test limit; no request made.")
    preflight = {
        "mode": "execute" if args.execute_authorized else "preflight-only",
        "external_requests": 0,
        "fixture": str(FIXTURE),
        "sha256": digest,
        "model": MODEL,
        "document_characters": len(document_text),
        "reserved_input_tokens": reserved_input_tokens,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "reserved_cost_usd": str(reservation.quantize(Decimal("0.000001"))),
        "database": (
            f"{settings.DATABASES['default']['HOST']}:"
            f"{settings.DATABASES['default']['PORT']}"
        ),
        "storage": settings.STORAGES["default"]["BACKEND"],
        "queue": settings.RESUME_QUEUE_BACKEND,
        "api_key_configured": bool(settings.GEMINI_API_KEY or settings.RESUME_AI_API_KEY),
    }
    if not args.execute_authorized:
        print(json.dumps(preflight, indent=2))
        return
    required = {
        "enabled": settings.RESUME_AI_ENABLED,
        "external_processing": settings.RESUME_AI_EXTERNAL_PROCESSING_APPROVED,
        "paid_service": settings.RESUME_AI_ALLOW_PAID,
        "free_tier_disabled": not settings.RESUME_AI_GEMINI_FREE_TIER_APPROVED,
        "provider": settings.RESUME_AI_PROVIDER == "gemini",
        "model": settings.RESUME_AI_MODEL == MODEL,
        "one_attempt": settings.RESUME_AI_MAX_ATTEMPTS == 1,
        "output_limit": settings.RESUME_AI_MAX_OUTPUT_TOKENS == MAX_OUTPUT_TOKENS,
        "daily_budget": settings.RESUME_AI_DAILY_BUDGET_USD >= MAX_RESERVATION,
        "monthly_budget": settings.RESUME_AI_MONTHLY_BUDGET_USD >= MAX_RESERVATION,
        "fallback": settings.RESUME_AI_FALLBACK == "rules",
        "rollout": settings.RESUME_AI_ROLLOUT_MODE == "canary",
        "key": bool(settings.GEMINI_API_KEY or settings.RESUME_AI_API_KEY),
        "legal_evidence": settings.LEGAL_RESUME_AI_APPROVED
        and bool(settings.LEGAL_RESUME_AI_VERSION)
        and bool(settings.LEGAL_RESUME_AI_SHA256),
    }
    if not all(required.values()):
        raise SystemExit(f"Canary safeguards are incomplete: {required}; no request made.")

    case = CASES[0]
    email = f"gemini-canary-{timezone.now().strftime('%Y%m%d%H%M%S%f')}@example.test"
    user = User.objects.create_user(email, email=email)
    profile = CandidateProfile.objects.create(
        user=user,
        full_name=case.lines[0],
        email_verified_at=timezone.now(),
    )
    resume = Resume(
        candidate=profile,
        original_name=case.filename,
        version=1,
        processing_status=Resume.ProcessingStatus.QUEUED,
        scan_status=Resume.ScanStatus.CLEAN,
        ai_processing_consent_at=timezone.now(),
        ai_processing_consent_version=settings.LEGAL_RESUME_AI_VERSION,
        ai_processing_consent_sha256=settings.LEGAL_RESUME_AI_SHA256,
    )
    resume.file.save(case.filename, ContentFile(content), save=False)
    resume.save()
    settings.RESUME_AI_CANARY_RESUME_IDS = {resume.pk}
    job = ResumeProcessingJob.objects.create(
        resume=resume,
        max_attempts=1,
        enqueued_at=timezone.now(),
    )

    started = time.perf_counter()
    outcome = process_resume_job(job.pk, str(job.idempotency_key))
    wall_latency_ms = round((time.perf_counter() - started) * 1000)
    resume.refresh_from_db()
    job.refresh_from_db()
    usage = ResumeAIUsage.objects.filter(resume=resume).order_by("attempt").first()

    client = APIClient()
    client.force_authenticate(user=user)
    profile_response = client.get("/api/v1/candidate/profile/")
    profile_data = profile_response.data if profile_response.status_code == 200 else {}
    stored_rows = list(
        WorkExperience.objects.filter(candidate=profile)
        .order_by("start_date", "pk")
        .values(
            "company",
            "role",
            "start_date",
            "end_date",
            "is_current",
            "description",
            "date_label",
            "confidence_status",
        )
    )
    expected_roles = [
        (role.company, role.role, role.start_date, role.end_date, role.is_current)
        for role in case.roles
    ]
    actual_roles = [_role_tuple(row) for row in stored_rows]
    extracted_rows = resume.extracted_data.get("work_experiences", [])
    extracted_achievements = {
        achievement
        for row in extracted_rows
        for achievement in row.get("achievements", [])
    }
    expected_achievements = {role.achievement for role in case.roles}
    actual_skills = set(profile_data.get("skills", []))
    expected_skills = set(case.skills)
    unsupported_roles = [row for row in actual_roles if row not in expected_roles]
    missing_roles = [row for row in expected_roles if row not in actual_roles]
    unsupported_skills = sorted(actual_skills - expected_skills)
    unsupported_achievements = sorted(extracted_achievements - expected_achievements)
    profile_roles = [_role_tuple(row) for row in profile_data.get("work_experiences", [])]
    recorded_reservation = usage.estimated_cost_usd if usage else None
    if recorded_reservation is not None and recorded_reservation > MAX_RESERVATION:
        raise RuntimeError("Recorded reservation exceeded the authorized maximum.")

    result = {
        "fixture": str(FIXTURE),
        "sha256": digest,
        "resume_id": resume.pk,
        "job_id": job.pk,
        "worker_outcome": outcome,
        "job_state": job.state,
        "interpretation": resume.extracted_data.get("_interpretation", {}),
        "expected_roles": expected_roles,
        "stored_roles": actual_roles,
        "roles_correct": sum(row in actual_roles for row in expected_roles),
        "roles_total": len(expected_roles),
        "missing_roles": missing_roles,
        "unsupported_roles": unsupported_roles,
        "promotion_roles_correct": sum(
            row in actual_roles for row in expected_roles if row[0] == "Blue Acorn Robotics"
        ),
        "promotion_roles_total": 2,
        "current_role_correct": expected_roles[-1] in actual_roles,
        "career_gap_preserved": (
            len(actual_roles) == 3
            and actual_roles[1][3] == "2021-01-01"
            and actual_roles[2][2] == "2021-04-01"
        ),
        "expected_skills": sorted(expected_skills),
        "profile_skills": sorted(actual_skills),
        "missing_skills": sorted(expected_skills - actual_skills),
        "unsupported_skills": unsupported_skills,
        "expected_achievements": sorted(expected_achievements),
        "extracted_achievements": sorted(extracted_achievements),
        "missing_achievements": sorted(expected_achievements - extracted_achievements),
        "unsupported_achievements": unsupported_achievements,
        "profile_api_status": profile_response.status_code,
        "profile_roles_match_database": profile_roles == actual_roles,
        "resume_review_pending": bool(profile_data.get("resume_review")),
        "request_count": ResumeAIUsage.objects.filter(resume=resume).count(),
        "request_id": usage.request_id if usage else "",
        "stop_reason": usage.stop_reason if usage else "",
        "input_tokens": usage.input_tokens if usage else 0,
        "output_tokens": usage.output_tokens if usage else 0,
        "reserved_input_tokens": usage.reserved_input_tokens if usage else 0,
        "reserved_cost_usd": (
            str(recorded_reservation) if recorded_reservation is not None else None
        ),
        "actual_cost_usd": (
            str(usage.actual_cost_usd) if usage and usage.actual_cost_usd is not None else None
        ),
        "provider_latency_ms": usage.latency_ms if usage else 0,
        "wall_latency_ms": wall_latency_ms,
        "failure_category": usage.failure_category if usage else "no_usage_record",
        "failure_stage": usage.failure_stage if usage else "no_usage_record",
        "validation_rejections": usage.validation_rejections if usage else [],
    }
    REPORT.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
