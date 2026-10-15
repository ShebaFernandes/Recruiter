"""Configuration-only deployment checks. Fake endpoints; never connects to AWS/mail."""
import os
import subprocess
import sys
from pathlib import Path

environment = {
    "PATH": os.environ.get("PATH", ""), "DEBUG": "false", "APP_ENV": "production",
    "TESTING": "false", "LEGAL_CONTENT_APPROVED": "true",  # synthetic check, NOT real approval
    "DJANGO_SECRET_KEY": "synthetic-deployment-check-not-for-use-" * 3,
    "DATABASE_URL": "postgresql://test:test@127.0.0.1:1/not_used",
    "ALLOWED_HOSTS": "app.example.test", "CORS_ALLOWED_ORIGINS": "https://app.example.test",
    "CSRF_TRUSTED_ORIGINS": "https://app.example.test",
    "FRONTEND_URL": "https://app.example.test", "AWS_STORAGE_BUCKET_NAME": "test-not-used",
    "AWS_S3_REGION_NAME": "ap-south-1", "AWS_SQS_REGION_NAME": "ap-south-1",
    "RESUME_QUEUE_BACKEND": "sqs",
    "RESUME_SQS_QUEUE_URL": "https://sqs.ap-south-1.amazonaws.com/000/not-used",
    "RESUME_SCANNER_BACKEND": "clamav", "AUTH_COOKIE_SECURE": "true",
    "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
    "EMAIL_HOST": "smtp.example.test", "EMAIL_HOST_USER": "not-used",
    "EMAIL_HOST_PASSWORD": "not-used", "DEFAULT_FROM_EMAIL": "test@example.test",
    "EMAIL_USE_TLS": "true", "AI_PROVIDER": "disabled", "AWS_EC2_METADATA_DISABLED": "true",
}
result = subprocess.run(
    [sys.executable, "manage.py", "check", "--deploy"],
    cwd=Path(__file__).resolve().parents[1] / "backend", env=environment, check=False,
)
raise SystemExit(result.returncode)
