"""Configuration-only deployment checks. Fake endpoints; never connects to AWS/mail."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

environment = {
    "PATH": os.environ.get("PATH", ""),
    "DEBUG": "false",
    "APP_ENV": "production",
    "TESTING": "false",
    "LEGAL_CONTENT_APPROVED": "true",  # synthetic check, NOT real approval
    "LEGAL_DOCUMENT_ROOT": str(ROOT / "deploy" / "live-legal-v1.0"),
    "LEGAL_EFFECTIVE_DATE": "2026-10-22",
    "LEGAL_PRIVACY_VERSION": "enter-candidate-privacy-v1.0",
    "LEGAL_TERMS_VERSION": "enter-candidate-terms-v1.0",
    "LEGAL_AGE_VERSION": "enter-candidate-age-v1.0",
    "LEGAL_SUBMISSION_VERSION": "enter-candidate-submission-v1.0",
    "LEGAL_PRIVACY_SHA256": "ebbafdb80abbcaf856490d1385b74b2cf8e15ec8826e7297753c836c7f8db49e",
    "LEGAL_TERMS_SHA256": "55b5b1ebca80a523218760499bedd2c93650b9ff04350f4355c483d313e825ef",
    "LEGAL_AGE_SHA256": "66b79e5cc63ddd3760ed02abb947604bf28ca152fc991dd09e59e5711e960bdf",
    "LEGAL_SUBMISSION_SHA256": "d1beaf60fbea2b351f039dc64f37a54e76d8e42083fe216da199ece72b1b70ba",
    "CANDIDATE_REGISTRATION_COUNTRIES": "IN",
    "DJANGO_SECRET_KEY": "synthetic-deployment-check-not-for-use-" * 3,
    "DATABASE_URL": "postgresql://test:test@127.0.0.1:1/not_used",
    "ALLOWED_HOSTS": "app.example.test",
    "CORS_ALLOWED_ORIGINS": "https://app.example.test",
    "CSRF_TRUSTED_ORIGINS": "https://app.example.test",
    "FRONTEND_URL": "https://app.example.test",
    "AWS_STORAGE_BUCKET_NAME": "test-not-used",
    "AWS_S3_REGION_NAME": "ap-south-1",
    "AWS_SQS_REGION_NAME": "ap-south-1",
    "RESUME_QUEUE_BACKEND": "sqs",
    "RESUME_SQS_QUEUE_URL": "https://sqs.ap-south-1.amazonaws.com/000/not-used",
    "RESUME_SCANNER_BACKEND": "clamav",
    "AUTH_COOKIE_SECURE": "true",
    "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
    "EMAIL_HOST": "smtp.example.test",
    "EMAIL_HOST_USER": "not-used",
    "EMAIL_HOST_PASSWORD": "not-used",
    "DEFAULT_FROM_EMAIL": "test@example.test",
    "EMAIL_USE_TLS": "true",
    "AI_PROVIDER": "disabled",
    "AWS_EC2_METADATA_DISABLED": "true",
}
result = subprocess.run(
    [sys.executable, "manage.py", "check", "--deploy"],
    cwd=ROOT / "backend",
    env=environment,
    check=False,
)
raise SystemExit(result.returncode)
