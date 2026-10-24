"""Run one explicitly authorized paid-Gemini schema smoke on fictional text."""

import argparse
import hashlib
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FIXTURE = ROOT / ".local-benchmark/gemini-resume/minimal-schema-smoke.txt"
RESULT = ROOT / (
    ".local-benchmark/gemini-resume/"
    "minimal-schema-smoke-gemini-3.5-flash-lite-result.json"
)
EXPECTED_SHA256 = "19b95335e7f3fd9b6ead5039449d64adfb990fdcd9f3f93217e14ce8f65c087d"
EXPECTED_MODEL = "gemini-3.5-flash-lite"
EXPECTED_MAX_OUTPUT_TOKENS = 850
MAX_RESERVATION = Decimal("0.003")

sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings  # noqa: E402
from talent.ai_providers import AIProviderError  # noqa: E402
from talent.resume_understanding import (  # noqa: E402
    INSTRUCTIONS,
    SCHEMA,
    request_input_token_reservation,
    resume_provider,
    validate_interpretation,
)


def stop(message):
    raise SystemExit(message)


document = FIXTURE.read_text(encoding="utf-8")
fixture_sha256 = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
if fixture_sha256 != EXPECTED_SHA256:
    stop("Synthetic fixture hash does not match the authorized document.")
parser = argparse.ArgumentParser()
parser.add_argument("--authorized-sha256", required=True)
parser.add_argument("--execute-authorized", action="store_true")
args = parser.parse_args()
if args.authorized_sha256 != EXPECTED_SHA256:
    stop("Authorization does not match the fictional fixture; no request made.")
if not args.execute_authorized:
    print(
        json.dumps(
            {
                "mode": "preflight-only",
                "external_requests": 0,
                "fixture_sha256": fixture_sha256,
                "model": EXPECTED_MODEL,
                "max_output_tokens": EXPECTED_MAX_OUTPUT_TOKENS,
            },
            indent=2,
        )
    )
    raise SystemExit(0)
if settings.RESUME_AI_PROVIDER != "gemini":
    stop("Gemini is not the configured provider.")
if settings.RESUME_AI_MODEL != EXPECTED_MODEL:
    stop("The authorized Gemini model is not configured.")
if settings.GEMINI_API_BASE_URL.rstrip("/") != "https://generativelanguage.googleapis.com/v1beta":
    stop("The Gemini endpoint is not the reviewed endpoint.")
if not (settings.RESUME_AI_API_KEY or settings.GEMINI_API_KEY):
    stop("The Gemini API key is not configured.")
if not settings.RESUME_AI_ALLOW_PAID:
    stop("Paid Gemini use is not approved for this process.")
if settings.RESUME_AI_GEMINI_FREE_TIER_APPROVED:
    stop("The Gemini Free-tier gate must remain disabled.")
if not settings.RESUME_AI_EXTERNAL_PROCESSING_APPROVED:
    stop("External processing is not approved for this process.")
if not (
    settings.LEGAL_RESUME_AI_APPROVED
    and settings.LEGAL_RESUME_AI_VERSION
    and settings.LEGAL_RESUME_AI_SHA256
):
    stop("Approved, hash-pinned Gemini consent evidence is missing.")
if settings.RESUME_AI_MAX_ATTEMPTS != 1:
    stop("The smoke test must have exactly one attempt.")
if settings.RESUME_AI_MAX_OUTPUT_TOKENS != EXPECTED_MAX_OUTPUT_TOKENS:
    stop("The smoke test output cap must be 850 tokens.")
if settings.DATABASES["default"]["HOST"] not in {"127.0.0.1", "localhost"}:
    stop("The database is not local.")
if settings.RESUME_QUEUE_BACKEND != "database":
    stop("The queue is not the isolated local database queue.")
if settings.STORAGES["default"]["BACKEND"] != "django.core.files.storage.FileSystemStorage":
    stop("Resume storage is not local filesystem storage.")

reserved_input_tokens = request_input_token_reservation(document)
reservation = (
    Decimal(reserved_input_tokens) * settings.RESUME_AI_INPUT_USD_PER_MILLION
    + Decimal(settings.RESUME_AI_MAX_OUTPUT_TOKENS)
    * settings.RESUME_AI_OUTPUT_USD_PER_MILLION
) / Decimal("1000000")
if reservation > MAX_RESERVATION:
    stop("The conservative application reservation exceeds the authorized maximum.")

report = {
    "fixture_sha256": fixture_sha256,
    "model": settings.RESUME_AI_MODEL,
    "request_count": 1,
    "reserved_input_tokens": reserved_input_tokens,
    "max_output_tokens": settings.RESUME_AI_MAX_OUTPUT_TOKENS,
    "reserved_cost_usd": str(reservation.quantize(Decimal("0.000001"))),
}

response = None
try:
    # Deliberately the only external provider invocation in this script.
    response = resume_provider().generate(
        INSTRUCTIONS,
        {"document_text": document},
        SCHEMA,
        "resume_understanding",
    )
    try:
        interpreted = validate_interpretation(response.data, document)
    except AIProviderError as error:
        paid_equivalent = (
            Decimal(response.input_tokens) * settings.RESUME_AI_INPUT_USD_PER_MILLION
            + Decimal(response.output_tokens) * settings.RESUME_AI_OUTPUT_USD_PER_MILLION
        ) / Decimal("1000000")
        report.update(
            {
                "outcome": "application_validation_failed",
                "http_status": response.http_status,
                "google_error_code": "",
                "google_error_status": "",
                "failure_category": error.kind,
                "failure_stage": error.stage,
                "request_id_present": bool(response.request_id),
                "stop_reason": response.stop_reason,
                "latency_ms": response.latency_ms,
                "valid_structured_json": True,
                "application_schema_valid": False,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "paid_equivalent_cost_usd": str(
                    paid_equivalent.quantize(Decimal("0.000001"))
                ),
                "fictional_role_extracted": False,
            }
        )
        interpreted = None
    if interpreted is None:
        raise SystemExit
    roles = interpreted.get("work_experiences", [])
    expected_role = next(
        (
            role
            for role in roles
            if role.get("company") == "Northstar Widgets"
            and role.get("role") == "Platform Engineer"
            and role.get("start_date") == "2021-03-01"
            and role.get("end_date") is None
            and role.get("is_current") is True
        ),
        None,
    )
    paid_equivalent = (
        Decimal(response.input_tokens) * settings.RESUME_AI_INPUT_USD_PER_MILLION
        + Decimal(response.output_tokens) * settings.RESUME_AI_OUTPUT_USD_PER_MILLION
    ) / Decimal("1000000")
    report.update(
        {
            "outcome": "succeeded",
            "http_status": response.http_status,
            "google_error_code": "",
            "google_error_status": "",
            "failure_stage": "",
            "request_id_present": bool(response.request_id),
            "stop_reason": response.stop_reason,
            "latency_ms": response.latency_ms,
            "valid_structured_json": True,
            "application_schema_valid": True,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "paid_equivalent_cost_usd": str(
                paid_equivalent.quantize(Decimal("0.000001"))
            ),
            "fictional_role_extracted": expected_role is not None,
            "work_experience_count": len(roles),
            "skills": interpreted.get("skills", []),
            "achievement_count": sum(
                len(role.get("achievements", [])) for role in roles
            ),
            "validation_rejections": interpreted.get("_validation_rejections", []),
        }
    )
except AIProviderError as error:
    report.update(
        {
            "outcome": "failed",
            "http_status": error.http_status,
            "google_error_code": error.provider_error_code,
            "google_error_status": error.provider_error_status,
            "failure_category": error.kind,
            "failure_stage": error.stage,
            "request_id_present": bool(error.request_id),
            "stop_reason": error.stop_reason,
            "latency_ms": error.latency_ms,
            "valid_structured_json": False,
            "application_schema_valid": False,
            "input_tokens": error.input_tokens,
            "output_tokens": error.output_tokens,
            "fictional_role_extracted": False,
        }
    )
except SystemExit:
    pass

RESULT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
