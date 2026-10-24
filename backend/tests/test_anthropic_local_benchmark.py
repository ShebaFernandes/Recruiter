"""Two-document local benchmark; all candidates and provider responses are fictional."""

import sys
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.utils import timezone
from rest_framework.authtoken.models import Token
from talent.ai_providers import AIProviderResult
from talent.models import Resume, ResumeAIUsage, ResumeProcessingJob, WorkExperience
from talent.resume_processing import process_resume_job
from talent.services import _resume_date

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from anthropic_resume_local_benchmark import (  # noqa: E402
    CASES,
    build_document,
    mocked_claude_response,
)

pytestmark = pytest.mark.django_db


def test_september_date_normalization_preserves_full_month():
    assert _resume_date("September 2019") == "2019-09-01"
    assert _resume_date("Sept. 2019") == "2019-09-01"


def test_benchmark_runtime_is_local_and_isolated(settings):
    assert connection.settings_dict["HOST"] in {"127.0.0.1", "localhost"}
    assert connection.settings_dict["NAME"].startswith("test_")
    assert settings.STORAGES["default"]["BACKEND"] == (
        "django.core.files.storage.FileSystemStorage"
    )
    assert settings.RESUME_QUEUE_BACKEND == "database"
    assert settings.RESUME_SCANNER_BACKEND == "development"


@pytest.fixture(autouse=True)
def isolated_benchmark(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.RESUME_QUEUE_BACKEND = "database"
    settings.RESUME_SCANNER_BACKEND = "development"
    settings.RESUME_AI_ENABLED = True
    settings.RESUME_AI_EXTERNAL_PROCESSING_APPROVED = True
    settings.RESUME_AI_ALLOW_PAID = False
    settings.RESUME_AI_PROVIDER = "anthropic"
    settings.RESUME_AI_MODEL = "claude-sonnet-5-5"
    settings.RESUME_AI_MAX_ATTEMPTS = 1
    settings.RESUME_AI_INPUT_USD_PER_MILLION = Decimal("2")
    settings.RESUME_AI_OUTPUT_USD_PER_MILLION = Decimal("10")
    settings.RESUME_AI_ROLLOUT_MODE = "consenting"
    settings.LEGAL_RESUME_AI_VERSION = "enter-resume-ai-consent-test-v1"
    settings.LEGAL_RESUME_AI_SHA256 = "1" * 64


def authenticate_fictional_candidate(client, full_name, suffix):
    email = f"fictional-benchmark-{suffix}@example.test"
    response = client.post(
        "/api/v1/auth/signup/",
        {
            "email": email,
            "password": "fictional-test-pass-123",
            "full_name": full_name,
            "role": "candidate",
        },
        format="json",
    )
    assert response.status_code == 201
    user = User.objects.get(username=email)
    user.is_active = True
    user.save(update_fields=["is_active"])
    user.candidate_profile.email_verified_at = timezone.now()
    user.candidate_profile.save(update_fields=["email_verified_at", "profile_updated_at"])
    token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")


def upload_and_process(client, case, provider, content=None):
    provider.generate.side_effect = lambda _instructions, payload, _schema, _name: (
        AIProviderResult(
            mocked_claude_response(case, payload["document_text"]),
            "anthropic",
            "claude-sonnet-5-5",
            request_id="synthetic-request",
            input_tokens=700,
            output_tokens=500,
        )
    )
    response = client.post(
        "/api/v1/candidate/resumes/",
        {
            "file": SimpleUploadedFile(
                case.filename,
                content or build_document(case),
                content_type=(
                    "application/pdf"
                    if case.kind == "pdf"
                    else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
            )
        },
        format="multipart",
    )
    assert response.status_code == 202, response.data
    resume_id = response.data["latest_resume"]["id"]
    Resume.objects.filter(pk=resume_id).update(
        ai_processing_consent_at=timezone.now(),
        ai_processing_consent_version="enter-resume-ai-consent-test-v1",
        ai_processing_consent_sha256="1" * 64,
    )
    job = ResumeProcessingJob.objects.get(resume_id=resume_id)
    assert process_resume_job(job.pk, str(job.idempotency_key)) == "completed"
    return client.get("/api/v1/candidate/profile/").data


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.slug)
def test_mocked_claude_populates_profile_records_and_protects_manual_history(
    client, monkeypatch, case
):
    authenticate_fictional_candidate(client, case.lines[0], case.slug)
    provider = Mock()
    monkeypatch.setattr("talent.resume_understanding.resume_provider", lambda: provider)

    profile = upload_and_process(client, case, provider)
    assert profile["headline"] == case.professional_title
    assert profile["summary"] == case.summary
    assert set(case.skills).issubset(profile["skills"])
    assert [
        (row["company"], row["role"], row["start_date"], row["end_date"], row["is_current"])
        for row in profile["work_experiences"]
    ] == [
        (role.company, role.role, role.start_date, role.end_date, role.is_current)
        for role in case.roles
    ]
    stored = Resume.objects.get(pk=profile["latest_resume"]["id"])
    assert list(
        WorkExperience.objects.filter(candidate=stored.candidate)
        .order_by("start_date")
        .values_list("company", "role", "start_date", "end_date", "is_current")
    ) == [
        (
            role.company,
            role.role,
            date.fromisoformat(role.start_date)
            if role.start_date
            else None,
            date.fromisoformat(role.end_date)
            if role.end_date
            else None,
            role.is_current,
        )
        for role in case.roles
    ]
    usage = ResumeAIUsage.objects.get(resume=stored)
    assert usage.outcome == ResumeAIUsage.Outcome.SUCCEEDED
    assert usage.input_tokens == 700
    assert usage.output_tokens == 500
    assert usage.estimated_cost_usd == 0
    assert usage.actual_cost_usd == Decimal("0.006400")

    corrected = profile["work_experiences"]
    corrected[0]["role"] = "Candidate corrected role"
    edited = client.patch(
        "/api/v1/candidate/profile/",
        {"work_experiences": corrected},
        format="json",
    )
    assert edited.status_code == 200, edited.data

    changed_case = replace(
        case,
        lines=case.lines[:-2] + ("Benchmark version: 2",) + case.lines[-2:],
    )
    after_replacement = upload_and_process(
        client, case, provider, content=build_document(changed_case)
    )
    assert after_replacement["work_experiences"][0]["role"] == "Candidate corrected role"
    assert "work_experiences" in after_replacement["resume_review"]["fields"]
