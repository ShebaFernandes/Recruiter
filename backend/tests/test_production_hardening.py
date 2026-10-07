import json
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from talent.models import RateLimitBucket, Resume, ResumeProcessingJob, WorkExperience
from talent.resume_processing import (
    ResumeInfectedError,
    dispatch_pending_jobs,
    enqueue_resume_job,
    process_resume_job,
)

from .test_candidate_flow import resume_docx


def _upload(client, name="async.docx"):
    return client.post(
        "/api/v1/candidate/resumes/",
        {
            "file": SimpleUploadedFile(
                name,
                resume_docx(),
                content_type=(
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
            )
        },
        format="multipart",
    )


@pytest.mark.django_db
def test_resume_job_retries_and_duplicate_delivery_is_idempotent(
    client, candidate_account, tmp_path, monkeypatch
):
    from talent import resume_processing

    with override_settings(MEDIA_ROOT=tmp_path, RESUME_RETRY_BASE_SECONDS=0):
        response = _upload(client)
        assert response.status_code == 202
        resume = Resume.objects.get(pk=response.data["latest_resume"]["id"])
        job = resume.processing_job
        assert resume.file.name.startswith("quarantine/")
        assert resume.processing_status == Resume.ProcessingStatus.UPLOADED
        assert resume.scan_status == Resume.ScanStatus.QUARANTINED

        real_parser = resume_processing.parse_resume
        calls = 0

        def flaky_parser(file_object, filename):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("transient parser outage")
            return real_parser(file_object, filename)

        monkeypatch.setattr(resume_processing, "parse_resume", flaky_parser)
        assert process_resume_job(job.pk, str(job.idempotency_key)) == "retry"
        resume.refresh_from_db()
        job.refresh_from_db()
        assert job.state == ResumeProcessingJob.State.QUEUED
        assert job.attempts == 1
        assert resume.scan_status == Resume.ScanStatus.CLEAN
        assert resume.processing_status == Resume.ProcessingStatus.QUEUED

        assert process_resume_job(job.pk, str(job.idempotency_key)) == "completed"
        resume.refresh_from_db()
        job.refresh_from_db()
        experience_ids = list(
            WorkExperience.objects.filter(candidate=resume.candidate).values_list("id", flat=True)
        )
        assert resume.processing_status == Resume.ProcessingStatus.COMPLETED
        assert resume.scan_status == Resume.ScanStatus.CLEAN
        assert resume.file.name.startswith("resumes/")
        assert job.state == ResumeProcessingJob.State.COMPLETED

        assert process_resume_job(job.pk, str(job.idempotency_key)) == "duplicate"
        assert list(
            WorkExperience.objects.filter(candidate=resume.candidate).values_list("id", flat=True)
        ) == experience_ids


@pytest.mark.django_db
def test_infected_resume_is_terminal_private_and_never_extracted(
    client, candidate_account, tmp_path, monkeypatch
):
    from talent import resume_processing

    class InfectedScanner:
        def scan(self, file_object):
            raise ResumeInfectedError("The uploaded file did not pass the security scan.")

    monkeypatch.setattr(resume_processing, "get_resume_scanner", lambda: InfectedScanner())
    with override_settings(MEDIA_ROOT=tmp_path):
        response = _upload(client, "infected.docx")
        resume = Resume.objects.get(pk=response.data["latest_resume"]["id"])
        job = resume.processing_job
        assert process_resume_job(job.pk, str(job.idempotency_key)) == "infected"
        resume.refresh_from_db()
        job.refresh_from_db()
        assert resume.scan_status == Resume.ScanStatus.INFECTED
        assert resume.processing_status == Resume.ProcessingStatus.FAILED
        assert not resume.extracted_data
        assert job.state == ResumeProcessingJob.State.FAILED
        assert client.get(f"/api/v1/resumes/{resume.pk}/download/").status_code == 404
        retry = client.post(f"/api/v1/candidate/resumes/{resume.pk}/retry/")
        assert retry.status_code == 409


@pytest.mark.django_db
def test_stale_processing_job_is_reclaimed_after_timeout(client, candidate_account, tmp_path):
    with override_settings(MEDIA_ROOT=tmp_path, RESUME_PROCESSING_TIMEOUT_SECONDS=30):
        response = _upload(client, "stale.docx")
        resume = Resume.objects.get(pk=response.data["latest_resume"]["id"])
        job = resume.processing_job
        job.state = ResumeProcessingJob.State.PROCESSING
        job.locked_at = timezone.now() - timedelta(seconds=31)
        job.save(update_fields=["state", "locked_at", "updated_at"])
        assert dispatch_pending_jobs() == 1
        job.refresh_from_db()
        assert job.state == ResumeProcessingJob.State.QUEUED
        assert job.locked_at is None
        assert process_resume_job(job.pk, str(job.idempotency_key)) == "completed"
        job.refresh_from_db()
        assert job.attempts == 1
        assert job.completed_at is not None


@pytest.mark.django_db
def test_deleted_job_message_is_acknowledgeable_without_worker_crash():
    assert process_resume_job(999_999_999, "stale-message") == "missing"


@pytest.mark.django_db
def test_sqs_message_contains_durable_job_identity(
    client, candidate_account, tmp_path, monkeypatch
):
    sent = {}

    class FakeSQS:
        def send_message(self, **kwargs):
            sent.update(kwargs)
            return {"MessageId": "sqs-message-1"}

    monkeypatch.setattr("talent.resume_processing._sqs_client", lambda: FakeSQS())
    with override_settings(MEDIA_ROOT=tmp_path, RESUME_QUEUE_BACKEND="database"):
        response = _upload(client, "queue.docx")
    job = ResumeProcessingJob.objects.get(resume_id=response.data["latest_resume"]["id"])
    with override_settings(
        RESUME_QUEUE_BACKEND="sqs",
        RESUME_SQS_QUEUE_URL="https://sqs.example.invalid/resumes",
    ):
        assert enqueue_resume_job(job.pk, delay_seconds=12) == "sqs-message-1"
    job.resume.refresh_from_db()
    assert job.resume.processing_status == Resume.ProcessingStatus.QUEUED
    body = json.loads(sent["MessageBody"])
    assert sent["QueueUrl"].endswith("/resumes")
    assert sent["DelaySeconds"] == 12
    assert body == {"job_id": job.pk, "idempotency_key": str(job.idempotency_key)}


@pytest.mark.django_db
def test_http_only_cookie_auth_requires_csrf_and_logout_clears_cookie():
    client = APIClient(enforce_csrf_checks=True)
    csrf = client.get("/api/v1/auth/csrf/")
    csrf_token = csrf.data["csrfToken"]
    headers = {"HTTP_X_CSRFTOKEN": csrf_token}
    with override_settings(TESTING=False, DEBUG=False, AUTH_COOKIE_SECURE=True):
        signup = client.post(
            "/api/v1/auth/signup/",
            {
                "email": "cookie-recruiter@example.com",
                "password": "strong-pass-123",
                "full_name": "Cookie Recruiter",
                "company": "Enter",
                "role": "recruiter",
            },
            format="json",
            **headers,
        )
        assert signup.status_code == 201
        assert "token" not in signup.data
        auth_cookie = signup.cookies["enter_session"]
        assert auth_cookie["httponly"] is True
        assert auth_cookie["secure"] is True
        assert auth_cookie["samesite"] == "Lax"
        assert client.get("/api/v1/auth/me/").status_code == 200
        assert client.post(
            "/api/v1/searches/", {"query": "Backend engineer"}, format="json"
        ).status_code == 403
        allowed = client.post(
            "/api/v1/searches/",
            {"query": "Backend engineer"},
            format="json",
            **headers,
        )
        assert allowed.status_code == 201
        logout = client.post("/api/v1/auth/logout/", format="json", **headers)
        assert logout.status_code == 204
        assert logout.cookies["enter_session"]["max-age"] == 0


@pytest.mark.django_db
def test_login_rate_limit_is_backend_enforced(monkeypatch):
    from talent.throttling import LoginRateThrottle

    monkeypatch.setattr(LoginRateThrottle, "THROTTLE_RATES", {"login": "2/min"})
    RateLimitBucket.objects.all().delete()
    client = APIClient()
    statuses = [
        client.post(
            "/api/v1/auth/login/",
            {"email": "limited@example.com", "password": "wrong-password"},
            format="json",
        ).status_code
        for _ in range(3)
    ]
    limited = client.post(
        "/api/v1/auth/login/",
        {"email": "limited@example.com", "password": "wrong-password"},
        format="json",
    )
    assert statuses == [400, 400, 429]
    assert limited.status_code == 429
    assert limited.data["code"] == "rate_limited"
    assert "try again" in limited.data["detail"].lower()
    assert int(limited["Retry-After"]) >= 1


@pytest.mark.django_db
def test_public_account_operation_rate_limits_are_backend_enforced(monkeypatch):
    from talent.throttling import (
        PasswordResetConfirmRateThrottle,
        PasswordResetRateThrottle,
        SignupRateThrottle,
        VerificationConsumeRateThrottle,
        VerificationRateThrottle,
    )

    client = APIClient()
    cases = [
        (
            SignupRateThrottle,
            "signup",
            "/api/v1/auth/signup/",
            {
                "email": "throttled-signup@example.com",
                "password": "strong-pass-123",
                "full_name": "Throttled Signup",
                "role": "candidate",
            },
        ),
        (
            VerificationRateThrottle,
            "verification",
            "/api/v1/auth/resend-verification/",
            {"email": "unknown-verification@example.com"},
        ),
        (
            PasswordResetRateThrottle,
            "password_reset",
            "/api/v1/auth/password-reset/request/",
            {"email": "unknown-reset@example.com"},
        ),
    ]
    for throttle_class, scope, path, payload in cases:
        monkeypatch.setattr(throttle_class, "THROTTLE_RATES", {scope: "1/min"})
        first = client.post(path, payload, format="json")
        assert first.status_code in {200, 201}
        limited = client.post(path, payload, format="json")
        assert limited.status_code == 429
        assert limited.data["code"] == "rate_limited"

    token_cases = [
        (
            VerificationConsumeRateThrottle,
            "verification_consume",
            "/api/v1/auth/verify-email/",
            {"token": "invalid-verification-token"},
        ),
        (
            PasswordResetConfirmRateThrottle,
            "password_reset_confirm",
            "/api/v1/auth/password-reset/confirm/",
            {"token": "invalid-reset-token", "password": "new-strong-pass-456"},
        ),
    ]
    for throttle_class, scope, path, payload in token_cases:
        monkeypatch.setattr(throttle_class, "THROTTLE_RATES", {scope: "1/min"})
        assert client.post(path, payload, format="json").status_code == 400
        limited = client.post(path, payload, format="json")
        assert limited.status_code == 429
        assert limited.data["code"] == "rate_limited"


@pytest.mark.django_db
def test_authenticated_upload_and_search_rate_limits_are_backend_enforced(
    client, candidate_account, monkeypatch
):
    from talent.throttling import RecruiterSearchRateThrottle, ResumeUploadRateThrottle

    monkeypatch.setattr(
        ResumeUploadRateThrottle, "THROTTLE_RATES", {"resume_upload": "1/min"}
    )
    assert client.post("/api/v1/candidate/resumes/", {}, format="multipart").status_code == 400
    limited_upload = client.post("/api/v1/candidate/resumes/", {}, format="multipart")
    assert limited_upload.status_code == 429

    client.post("/api/v1/auth/logout/")
    signup = client.post(
        "/api/v1/auth/signup/",
        {
            "email": "throttled-recruiter@example.com",
            "password": "strong-pass-123",
            "full_name": "Throttled Recruiter",
            "company": "Enter",
            "role": "recruiter",
        },
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Token {signup.data['token']}")
    monkeypatch.setattr(
        RecruiterSearchRateThrottle, "THROTTLE_RATES", {"recruiter_search": "1/min"}
    )
    assert client.post("/api/v1/searches/", {"query": ""}, format="json").status_code == 400
    limited_search = client.post(
        "/api/v1/searches/", {"query": "Backend engineer"}, format="json"
    )
    assert limited_search.status_code == 429
    assert limited_search.data["code"] == "rate_limited"
