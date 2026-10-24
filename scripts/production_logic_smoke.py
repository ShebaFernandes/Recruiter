"""DEBUG=false application smoke; external boundaries are mocked, NOT a stack rehearsal.

Uses a disposable PostgreSQL database and temporary private files. No SMTP, S3,
SQS or AI traffic. Real service integration remains a separate staging gate.
"""
import os
import re
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
if not os.environ.get("DATABASE_URL", "").startswith("postgresql://"):
    raise SystemExit("Set DATABASE_URL to the local PostgreSQL server.")
os.environ.update({
    "DJANGO_SETTINGS_MODULE": "config.settings", "APP_ENV": "staging",
    "DEBUG": "false", "TESTING": "false", "AI_PROVIDER": "disabled",
    "ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": "", "RESUME_AI_ENABLED": "false",
    "RESUME_AI_EXTERNAL_PROCESSING_APPROVED": "false",
    "DJANGO_SECRET_KEY": "fictional-local-smoke-never-use-in-production-" * 2,
    "ALLOWED_HOSTS": "app.example.test", "FRONTEND_URL": "https://app.example.test",
    "CORS_ALLOWED_ORIGINS": "https://app.example.test",
    "CSRF_TRUSTED_ORIGINS": "https://app.example.test",
    "AUTH_COOKIE_SECURE": "true", "SECURE_SSL_REDIRECT": "true",
    "AWS_STORAGE_BUCKET_NAME": "never-contact-this-bucket",
    "AWS_S3_REGION_NAME": "ap-south-1", "AWS_SQS_REGION_NAME": "ap-south-1",
    "AWS_EC2_METADATA_DISABLED": "true", "RESUME_QUEUE_BACKEND": "sqs",
    "RESUME_SQS_QUEUE_URL": "https://sqs.example.test/fictional",
    "RESUME_SCANNER_BACKEND": "clamav", "EXPOSE_LOCAL_EMAIL_LINKS": "false",
    "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
    "EMAIL_HOST": "smtp.example.test", "EMAIL_HOST_USER": "fictional",
    "EMAIL_HOST_PASSWORD": "fictional", "EMAIL_USE_TLS": "true",
    "DEFAULT_FROM_EMAIL": "noreply@example.test",
})


def main():
    import django

    django.setup()
    from django.conf import settings
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.test import override_settings
    from django.test.utils import setup_databases, teardown_databases
    from rest_framework.test import APIClient
    from talent.models import ResumeProcessingJob
    from talent.resume_processing import process_resume_job
    from talent.storage_cleanup import drain_cleanup

    assert not settings.DEBUG and not settings.TESTING
    settings.DATABASES["default"]["TEST"]["NAME"] = "test_enter_smoke_" + uuid.uuid4().hex[:12]
    old = setup_databases(verbosity=0, interactive=False)
    messages = []

    def capture_email(batch):
        messages.extend(batch)
        return len(batch)

    try:
        with tempfile.TemporaryDirectory(prefix="enter-production-smoke-") as media, (
            override_settings(MEDIA_ROOT=media, STORAGES={
                "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            })
        ), patch("django.core.mail.backends.smtp.EmailBackend.send_messages",
                 side_effect=capture_email), (
            patch("talent.resume_processing._sqs_client", return_value=Mock(
                send_message=Mock(return_value={"MessageId": "fictional"})))
        ), patch("talent.resume_processing.ClamAVResumeScanner.scan", return_value="clean"), (
            patch("boto3.client", side_effect=AssertionError("External AWS forbidden"))
        ), patch("talent.search_understanding.get_ai_provider",
                 side_effect=AssertionError("External AI forbidden")):
            # Import fixtures only AFTER strict production settings have loaded.
            from tests.test_candidate_flow import resume_docx

            client = APIClient(HTTP_HOST="app.example.test", HTTP_X_FORWARDED_PROTO="https")
            password = "fictional-smoke-password-123"
            signup = client.post("/api/v1/auth/signup/", {
                "email": "asha@example.com", "password": password,
                "full_name": "Asha Rao", "role": "candidate",
            }, format="json")
            assert signup.status_code == 201
            assert "local_verification_url" not in signup.data
            token = re.search(r"[?&]verify-email=([^\s]+)", messages[0].body).group(1)
            assert client.post("/api/v1/auth/verify-email/", {"token": token}).status_code == 200
            login = client.post("/api/v1/auth/login/", {
                "email": "asha@example.com", "password": password,
            }, format="json")
            assert login.status_code == 200
            assert "token" not in login.data  # Production uses the private auth cookie.
            upload = client.post("/api/v1/candidate/resumes/", {
                "file": SimpleUploadedFile("fictional.docx", resume_docx()),
            }, format="multipart")
            assert upload.status_code == 202
            resume_id = upload.data["latest_resume"]["id"]
            job = ResumeProcessingJob.objects.get(resume_id=resume_id)
            assert process_resume_job(job.pk, str(job.idempotency_key)) == "completed"
            profile = client.get("/api/v1/candidate/profile/")
            assert len(profile.data["work_experiences"]) == 2
            assert client.get(f"/api/v1/candidate/resumes/{resume_id}/preview/").status_code == 200
            updated = client.patch("/api/v1/candidate/profile/", {
                "meaningful_work": "Built a fictional event processing service.",
                "visibility": "matching_roles", "work_preferences": ["Remote"],
                "build_lead_preference": 50, "notice_period_days": 30,
            }, format="json")
            assert updated.status_code == 200 and updated.data["can_submit"]
            assert client.post("/api/v1/candidate/profile/submit/", {
                "consent": True,
            }, format="json").status_code == 200
            assert client.get("/api/v1/projects/").status_code == 403
            assert client.get("/api/v1/candidate/profile/").data["build_lead_preference"] == 50
            assert client.delete("/api/v1/candidate/account/", {
                "confirmation": "DELETE", "password": password,
            }, format="json").status_code == 204
            drain_cleanup()
            assert not any(path.is_file() for path in Path(media).rglob("*"))
            assert client.get("/api/v1/candidate/profile/").status_code == 401
            print("PASS: strict settings; signup/verify/login; DOCX extraction/history/preview; "
                  "preferences; consent/submission; role denial; deletion/cleanup.")
            print("MOCKED: SMTP, SQS, ClamAV. LOCAL SUBSTITUTE: private file storage. "
                  "NOT a full container/production-service simulation.")
    finally:
        teardown_databases(old, verbosity=0)


if __name__ == "__main__":
    main()
