"""Run the explicitly authorized 12-document fictional Gemini benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

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
from talent.services import _resume_date, parse_resume  # noqa: E402

AUTHORIZED_MANIFEST_SHA256 = (
    "c9d246e648f3ed58fcf20e35700f3b6b3f06d7dbc39a6c8a096b28a3a79c984c"
)
MODEL = "gemini-3.5-flash-lite"
MAX_OUTPUT_TOKENS = 3000
MAX_AGGREGATE_RESERVATION = Decimal("0.101")
INPUT_PRICE = Decimal("0.30")
OUTPUT_PRICE = Decimal("2.50")
BENCHMARK = ROOT / ".local-benchmark" / "gemini-varied"
MANIFEST = BENCHMARK / "manifest.json"
REPORT = BENCHMARK / "results.json"
RECALL_REPORT = BENCHMARK / "recall-retest-results.json"
RECALL_TARGETS = {
    "explicit-career-gap": (
        "0b5023e0ac428f4e4cf7378b3cc2df9c28a6dd3a88f18aa1c8dc3fbffcf108e3"
    ),
    "unknown-start-date": (
        "054aa69e9684109bd79c65eecded39c6cfce314ea7b9d7a83a06aa62799b8f96"
    ),
}
MAX_RECALL_RESERVATION = Decimal("0.016668")
PROMOTION_SLUGS = {
    "promotion-gap",
    "compact-year-promotions",
    "distant-employer-heading",
}
GAP_SLUGS = {
    "promotion-gap",
    "rehire-same-employer",
    "explicit-career-gap",
    "contract-and-permanent",
}
OVERLAP_SLUGS = {"overlapping-advisory", "contract-and-permanent"}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normal(value) -> str:
    return " ".join(str(value or "").casefold().split())


def _iso(value):
    return value.isoformat() if isinstance(value, date) else value


def _role(row) -> tuple:
    return (
        row["company"],
        row["role"],
        _iso(row.get("start_date")),
        _iso(row.get("end_date")),
        bool(row.get("is_current")),
        row.get("date_label", ""),
    )


def _date_endpoint(expected, actual_date, label: str, side: int) -> bool:
    if expected is None:
        return actual_date is None
    if re.fullmatch(r"\d{4}", expected):
        parts = re.split(r"\s+[\-–—]\s+", label, maxsplit=1)
        return actual_date is None and len(parts) == 2 and parts[side].strip() == expected
    return actual_date == _resume_date(expected)


def _validate_manifest(manifest: dict) -> tuple[list[dict], Decimal]:
    if _hash(MANIFEST) != AUTHORIZED_MANIFEST_SHA256:
        raise SystemExit("Authorized manifest hash does not match; no request made.")
    documents = manifest.get("documents", [])
    if manifest.get("model") != MODEL or len(documents) != 12:
        raise SystemExit("Manifest model or document count changed; no request made.")
    total = Decimal("0")
    for item in documents:
        path = Path(item["path"])
        if not path.is_relative_to(BENCHMARK) or _hash(path) != item["sha256"]:
            raise SystemExit(f"Fixture hash changed for {item['slug']}; no request made.")
        if item["max_output_tokens"] != MAX_OUTPUT_TOKENS:
            raise SystemExit("Manifest output limit changed; no request made.")
        with path.open("rb") as source:
            text = interpretation_text(parse_resume(source, path.name))
        reserved_input = request_input_token_reservation(text)
        reservation = (
            Decimal(reserved_input) * INPUT_PRICE
            + Decimal(MAX_OUTPUT_TOKENS) * OUTPUT_PRICE
        ) / Decimal("1000000")
        if reserved_input != item["reserved_input_tokens"]:
            raise SystemExit(f"Reservation input changed for {item['slug']}; no request made.")
        if reservation.quantize(Decimal("0.000001")) != Decimal(
            item["paid_equivalent_reservation_usd"]
        ):
            raise SystemExit(f"Reservation changed for {item['slug']}; no request made.")
        total += reservation
    if total > MAX_AGGREGATE_RESERVATION:
        raise SystemExit("Aggregate reservation exceeds authorization; no request made.")
    return documents, total


def _environment_checks(execute: bool) -> dict:
    host = settings.DATABASES["default"].get("HOST")
    required = {
        "local_database": host in {"127.0.0.1", "localhost"},
        "local_storage": settings.STORAGES["default"]["BACKEND"]
        == "django.core.files.storage.FileSystemStorage",
        "database_queue": settings.RESUME_QUEUE_BACKEND == "database",
        "endpoint": settings.GEMINI_API_BASE_URL.rstrip("/")
        == "https://generativelanguage.googleapis.com/v1beta",
        "provider": settings.RESUME_AI_PROVIDER == "gemini",
        "model": settings.RESUME_AI_MODEL == MODEL,
        "key_configured": bool(settings.GEMINI_API_KEY or settings.RESUME_AI_API_KEY),
        "one_attempt": settings.RESUME_AI_MAX_ATTEMPTS == 1,
        "no_paid_retry": settings.RESUME_AI_FALLBACK == "rules",
        "output_limit": settings.RESUME_AI_MAX_OUTPUT_TOKENS == MAX_OUTPUT_TOKENS,
        "prices": settings.RESUME_AI_INPUT_USD_PER_MILLION == INPUT_PRICE
        and settings.RESUME_AI_OUTPUT_USD_PER_MILLION == OUTPUT_PRICE,
    }
    if execute:
        required.update(
            {
                "enabled": settings.RESUME_AI_ENABLED,
                "external_approved": settings.RESUME_AI_EXTERNAL_PROCESSING_APPROVED,
                "paid_disabled": not settings.RESUME_AI_ALLOW_PAID,
                "free_tier_approved": settings.RESUME_AI_GEMINI_FREE_TIER_APPROVED,
                "canary_rollout": settings.RESUME_AI_ROLLOUT_MODE == "canary",
                "legal_evidence": settings.LEGAL_RESUME_AI_APPROVED
                and bool(settings.LEGAL_RESUME_AI_VERSION)
                and bool(settings.LEGAL_RESUME_AI_SHA256),
            }
        )
    elif settings.RESUME_AI_ENABLED:
        required["disabled_during_preflight"] = False
    if not all(required.values()):
        raise SystemExit(f"Benchmark safeguards are incomplete: {required}; no request made.")
    return required


def _compare(item: dict, profile, resume, usage, profile_data: dict) -> dict:
    expected = item["expected"]
    rows = list(
        WorkExperience.objects.filter(candidate=profile).values(
            "company",
            "role",
            "start_date",
            "end_date",
            "is_current",
            "date_label",
            "description",
            "confidence_status",
        )
    )
    actual = [_role(row) for row in rows]
    expected_roles = expected["work_experiences"]
    role_results = []
    used = set()
    for expected_role in expected_roles:
        match_index = next(
            (
                index
                for index, row in enumerate(rows)
                if index not in used
                and _normal(row["company"]) == _normal(expected_role["company"])
                and _normal(row["role"]) == _normal(expected_role["title"])
            ),
            None,
        )
        row = rows[match_index] if match_index is not None else None
        if match_index is not None:
            used.add(match_index)
        employer = bool(row) and _normal(row["company"]) == _normal(expected_role["company"])
        title = bool(row) and _normal(row["role"]) == _normal(expected_role["title"])
        start = bool(row) and _date_endpoint(
            expected_role["start"], _iso(row["start_date"]), row["date_label"], 0
        )
        end = bool(row) and _date_endpoint(
            expected_role["end"], _iso(row["end_date"]), row["date_label"], 1
        )
        current = bool(row) and bool(row["is_current"]) == bool(expected_role["current"])
        role_results.append(
            {
                "company": expected_role["company"],
                "title": expected_role["title"],
                "employer_correct": employer,
                "title_correct": title,
                "start_correct": start,
                "end_correct": end,
                "current_correct": current,
                "role_correct": employer and title and start and end and current,
            }
        )
    extras = [actual[index] for index in range(len(rows)) if index not in used]
    extracted = resume.extracted_data.get("work_experiences", [])
    actual_achievements = {
        achievement
        for row in extracted
        for achievement in row.get("achievements", [])
    }
    expected_achievements = {row["achievement"] for row in expected_roles}
    expected_skills = set(expected["skills"])
    actual_skills = set(profile_data.get("skills", []))
    profile_roles = [_role(row) for row in profile_data.get("work_experiences", [])]
    return {
        "role_results": role_results,
        "roles_correct": sum(row["role_correct"] for row in role_results),
        "roles_total": len(role_results),
        "employers_correct": sum(row["employer_correct"] for row in role_results),
        "titles_correct": sum(row["title_correct"] for row in role_results),
        "date_endpoints_correct": sum(
            row["start_correct"] + row["end_correct"] for row in role_results
        ),
        "date_endpoints_total": len(role_results) * 2,
        "current_roles_correct": sum(
            row["current_correct"]
            for row, expected_role in zip(role_results, expected_roles, strict=True)
            if expected_role["current"]
        ),
        "current_roles_total": sum(row["current"] for row in expected_roles),
        "unsupported_roles": extras,
        "missing_skills": sorted(expected_skills - actual_skills),
        "unsupported_skills": sorted(actual_skills - expected_skills),
        "skills_correct": len(expected_skills & actual_skills),
        "skills_total": len(expected_skills),
        "missing_achievements": sorted(expected_achievements - actual_achievements),
        "unsupported_achievements": sorted(actual_achievements - expected_achievements),
        "achievements_correct": len(expected_achievements & actual_achievements),
        "achievements_total": len(expected_achievements),
        "professional_title_correct": profile_data.get("headline")
        == expected["professional_title"],
        "summary_correct": profile_data.get("summary") == expected["summary"],
        "profile_roles_match_database": profile_roles == actual,
        "validation_rejections": usage.validation_rejections,
    }


def _totals(results: list[dict]) -> dict:
    comparisons = [item["comparison"] for item in results]
    usages = [item["usage"] for item in results]
    total = lambda key: sum(item[key] for item in comparisons)  # noqa: E731
    return {
        "documents_completed": len(results),
        "requests_made": sum(item["request_count"] for item in results),
        "roles_correct": total("roles_correct"),
        "roles_total": total("roles_total"),
        "employers_correct": total("employers_correct"),
        "titles_correct": total("titles_correct"),
        "date_endpoints_correct": total("date_endpoints_correct"),
        "date_endpoints_total": total("date_endpoints_total"),
        "current_roles_correct": total("current_roles_correct"),
        "current_roles_total": total("current_roles_total"),
        "skills_correct": total("skills_correct"),
        "skills_total": total("skills_total"),
        "achievements_correct": total("achievements_correct"),
        "achievements_total": total("achievements_total"),
        "input_tokens": sum(item["input_tokens"] for item in usages),
        "output_tokens": sum(item["output_tokens"] for item in usages),
        "provider_latency_ms": sum(item["latency_ms"] for item in usages),
        "actual_cost_usd": str(
            sum(Decimal(item["actual_cost_usd"] or "0") for item in usages)
        ),
        "paid_equivalent_cost_usd": str(
            (
                Decimal(sum(item["input_tokens"] for item in usages)) * INPUT_PRICE
                + Decimal(sum(item["output_tokens"] for item in usages)) * OUTPUT_PRICE
            )
            / Decimal("1000000")
        ),
        "promotion_cases_correct": sum(
            item["slug"] in PROMOTION_SLUGS
            and item["comparison"]["roles_correct"] == item["comparison"]["roles_total"]
            for item in results
        ),
        "promotion_cases_total": len(PROMOTION_SLUGS),
        "gap_cases_correct": sum(
            item["slug"] in GAP_SLUGS
            and item["comparison"]["date_endpoints_correct"]
            == item["comparison"]["date_endpoints_total"]
            for item in results
        ),
        "gap_cases_total": len(GAP_SLUGS),
        "overlap_cases_correct": sum(
            item["slug"] in OVERLAP_SLUGS
            and item["comparison"]["date_endpoints_correct"]
            == item["comparison"]["date_endpoints_total"]
            for item in results
        ),
        "overlap_cases_total": len(OVERLAP_SLUGS),
        "all_profile_roles_match_database": all(
            item["profile_roles_match_database"] for item in comparisons
        ),
    }


def _write_report(report: dict, path: Path = REPORT) -> None:
    path.write_text(json.dumps(report, indent=2, default=str) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    parser.add_argument(
        "--recall-retest",
        action="store_true",
        help="Restrict execution to the two separately authorized recall fixtures.",
    )
    parser.add_argument(
        "--recover-resume-id",
        type=int,
        help="Record an already-completed final result without making a request.",
    )
    args = parser.parse_args()
    if args.manifest_sha256 != AUTHORIZED_MANIFEST_SHA256:
        raise SystemExit("Authorization does not match the benchmark; no request made.")
    manifest = json.loads(MANIFEST.read_text())
    documents, reservation = _validate_manifest(manifest)
    report_path = REPORT
    if args.recall_retest:
        if args.recover_resume_id:
            raise SystemExit("Recall retest cannot be combined with result recovery.")
        documents = [item for item in documents if item["slug"] in RECALL_TARGETS]
        if (
            len(documents) != 2
            or any(item["sha256"] != RECALL_TARGETS[item["slug"]] for item in documents)
        ):
            raise SystemExit("Recall retest fixtures changed; no request made.")
        reservation = sum(
            (Decimal(item["paid_equivalent_reservation_usd"]) for item in documents),
            Decimal("0"),
        )
        if reservation > MAX_RECALL_RESERVATION:
            raise SystemExit("Recall retest reservation exceeds authorization; no request made.")
        report_path = RECALL_REPORT
    checks = _environment_checks(args.execute_authorized)
    preflight = {
        "manifest_sha256": AUTHORIZED_MANIFEST_SHA256,
        "model": MODEL,
        "documents": len(documents),
        "expected_roles": sum(
            len(item["expected"]["work_experiences"]) for item in documents
        ),
        "max_output_tokens_per_document": MAX_OUTPUT_TOKENS,
        "aggregate_reservation_usd": str(reservation.quantize(Decimal("0.000001"))),
        "checks": checks,
        "external_requests": 0,
    }
    if args.recover_resume_id:
        if not REPORT.exists():
            raise SystemExit("No partial report exists to recover.")
        report = json.loads(REPORT.read_text())
        if len(report.get("results", [])) != 11:
            raise SystemExit("Recovery requires exactly 11 previously recorded results.")
        item = documents[11]
        resume = Resume.objects.select_related("candidate", "candidate__user").get(
            pk=args.recover_resume_id
        )
        with resume.file.open("rb") as source:
            stored_digest = hashlib.sha256(source.read()).hexdigest()
        if stored_digest != item["sha256"] or resume.original_name != Path(item["path"]).name:
            raise SystemExit("Stored final resume does not match the authorized fixture.")
        usages = list(ResumeAIUsage.objects.filter(resume=resume).order_by("attempt"))
        if (
            len(usages) != 1
            or usages[0].outcome != ResumeAIUsage.Outcome.SUCCEEDED
            or usages[0].provider != "gemini"
            or usages[0].model != MODEL
            or resume.extracted_data.get("_interpretation", {}).get("source") != "ai"
        ):
            raise SystemExit("Stored final result is not one successful authorized Gemini call.")
        usage = usages[0]
        client = APIClient()
        client.force_authenticate(user=resume.candidate.user)
        response = client.get("/api/v1/candidate/profile/")
        profile_data = response.data if response.status_code == 200 else {}
        job = resume.processing_job
        result = {
            "sequence": 12,
            "slug": item["slug"],
            "sha256": item["sha256"],
            "resume_id": resume.pk,
            "job_id": job.pk,
            "worker_outcome": "completed",
            "job_state": job.state,
            "interpretation_source": "ai",
            "request_count": 1,
            "profile_api_status": response.status_code,
            "usage": {
                "outcome": usage.outcome,
                "http_status": usage.http_status,
                "provider_error_code": usage.provider_error_code,
                "provider_error_status": usage.provider_error_status,
                "failure_category": usage.failure_category,
                "failure_stage": usage.failure_stage,
                "stop_reason": usage.stop_reason,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "latency_ms": usage.latency_ms,
                "wall_latency_ms": usage.latency_ms,
                "actual_cost_usd": str(usage.actual_cost_usd),
                "reserved_cost_usd": str(usage.estimated_cost_usd),
            },
            "comparison": _compare(
                item, resume.candidate, resume, usage, profile_data
            ),
            "recovered_after_local_reporting_guard": True,
        }
        report["results"].append(result)
        report["totals"] = _totals(report["results"])
        report["completed_at"] = timezone.now().isoformat()
        report["reporting_note"] = (
            "Call 12 completed before a one-microdollar per-document rounding guard "
            "stopped the reporter; this result was recovered from the local database."
        )
        _write_report(report)
        print(json.dumps(result, indent=2, default=str))
        print(json.dumps(report["totals"], indent=2), flush=True)
        return
    if not args.execute_authorized:
        print(json.dumps(preflight, indent=2))
        return
    if report_path.exists():
        raise SystemExit("A benchmark result already exists; refusing to make duplicate calls.")

    report = {"preflight": preflight, "results": [], "stopped": False, "stop_reason": ""}
    for index, item in enumerate(documents, start=1):
        path = Path(item["path"])
        content = path.read_bytes()
        with path.open("rb") as source:
            parsed = parse_resume(source, path.name)
        email = f"gemini-varied-{index}-{timezone.now().strftime('%Y%m%d%H%M%S%f')}@example.test"
        user = User.objects.create_user(email, email=email)
        profile = CandidateProfile.objects.create(
            user=user,
            full_name=parsed.get("full_name") or f"Fictional Candidate {index:02d}",
            email_verified_at=timezone.now(),
        )
        resume = Resume(
            candidate=profile,
            original_name=path.name,
            version=1,
            processing_status=Resume.ProcessingStatus.QUEUED,
            scan_status=Resume.ScanStatus.CLEAN,
            ai_processing_consent_at=timezone.now(),
            ai_processing_consent_version=settings.LEGAL_RESUME_AI_VERSION,
            ai_processing_consent_sha256=settings.LEGAL_RESUME_AI_SHA256,
        )
        resume.file.save(path.name, ContentFile(content), save=False)
        resume.save()
        settings.RESUME_AI_CANARY_RESUME_IDS = {resume.pk}
        job = ResumeProcessingJob.objects.create(
            resume=resume, max_attempts=1, enqueued_at=timezone.now()
        )
        started = time.perf_counter()
        outcome = process_resume_job(job.pk, str(job.idempotency_key))
        wall_latency_ms = round((time.perf_counter() - started) * 1000)
        resume.refresh_from_db()
        job.refresh_from_db()
        usages = list(ResumeAIUsage.objects.filter(resume=resume).order_by("attempt"))
        usage = usages[0] if usages else None
        if usage and usage.estimated_cost_usd > Decimal(
            item["paid_equivalent_reservation_usd"]
        ) + Decimal("0.000001"):
            raise RuntimeError("Recorded reservation exceeded the authorized document limit.")
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/api/v1/candidate/profile/")
        profile_data = response.data if response.status_code == 200 else {}
        result = {
            "sequence": index,
            "slug": item["slug"],
            "sha256": item["sha256"],
            "resume_id": resume.pk,
            "job_id": job.pk,
            "worker_outcome": outcome,
            "job_state": job.state,
            "interpretation_source": resume.extracted_data.get("_interpretation", {}).get(
                "source", ""
            ),
            "request_count": len(usages),
            "profile_api_status": response.status_code,
            "usage": {
                "outcome": usage.outcome if usage else "missing",
                "http_status": usage.http_status if usage else None,
                "provider_error_code": usage.provider_error_code if usage else "",
                "provider_error_status": usage.provider_error_status if usage else "",
                "failure_category": usage.failure_category if usage else "no_usage_record",
                "failure_stage": usage.failure_stage if usage else "no_usage_record",
                "stop_reason": usage.stop_reason if usage else "",
                "input_tokens": usage.input_tokens if usage else 0,
                "output_tokens": usage.output_tokens if usage else 0,
                "latency_ms": usage.latency_ms if usage else 0,
                "wall_latency_ms": wall_latency_ms,
                "actual_cost_usd": (
                    str(usage.actual_cost_usd)
                    if usage and usage.actual_cost_usd is not None
                    else None
                ),
                "reserved_cost_usd": (
                    str(usage.estimated_cost_usd) if usage else None
                ),
            },
        }
        failed = (
            outcome != "completed"
            or usage is None
            or usage.outcome != ResumeAIUsage.Outcome.SUCCEEDED
            or result["interpretation_source"] != "ai"
        )
        if not failed:
            result["comparison"] = _compare(
                item, profile, resume, usage, profile_data
            )
        report["results"].append(result)
        report["totals"] = _totals(
            [row for row in report["results"] if "comparison" in row]
        )
        if failed:
            report["stopped"] = True
            report["stop_reason"] = (
                f"{item['slug']}: provider/schema/access or worker failure; no further calls"
            )
        _write_report(report, report_path)
        print(
            json.dumps(
                {
                    "sequence": index,
                    "slug": item["slug"],
                    "http_status": result["usage"]["http_status"],
                    "outcome": result["usage"]["outcome"],
                    "roles_correct": result.get("comparison", {}).get("roles_correct"),
                    "roles_total": result.get("comparison", {}).get("roles_total"),
                    "input_tokens": result["usage"]["input_tokens"],
                    "output_tokens": result["usage"]["output_tokens"],
                    "stopped": report["stopped"],
                }
            ),
            flush=True,
        )
        if failed:
            break
    report["completed_at"] = timezone.now().isoformat()
    _write_report(report, report_path)
    print(json.dumps(report["totals"], indent=2), flush=True)


if __name__ == "__main__":
    main()
