import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from django.test import override_settings
from django.utils import timezone
from talent.management.commands.candidate_launch_runtime_check import runtime_errors

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "candidate_launch_check.py"
SPEC = importlib.util.spec_from_file_location("candidate_launch_check", SCRIPT_PATH)
assert SPEC and SPEC.loader
candidate_launch_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate_launch_check)
backup_marker_path = candidate_launch_check.backup_marker_path
verify_backup_marker = candidate_launch_check.verify_backup_marker

pytestmark = pytest.mark.django_db


def test_verified_backup_and_recovery_markers_are_required(tmp_path):
    base = tmp_path / "backup-verified.json"
    now = timezone.now().timestamp()
    for kind in ("hourly", "daily", "recovery"):
        path = backup_marker_path(base, kind)
        path.write_text(
            json.dumps(
                {
                    "verified_at": now,
                    "key": f"private/{kind}.dump",
                    "sha256": hashlib.sha256(kind.encode()).hexdigest(),
                    "bytes": 100,
                    "class": kind,
                }
            )
        )
        path.chmod(0o600)
        verify_backup_marker(path, kind, now)

    stale = backup_marker_path(base, "hourly")
    payload = json.loads(stale.read_text())
    payload["verified_at"] = now - 7201
    stale.write_text(json.dumps(payload))
    with pytest.raises(RuntimeError, match="stale"):
        verify_backup_marker(stale, "hourly", now)


def test_runtime_check_covers_single_candidate_launch_gate(monkeypatch):
    documents = {
        purpose: {"unpublished": False}
        for purpose in ("age", "terms", "privacy", "submission")
    }
    monkeypatch.setattr(
        "talent.management.commands.candidate_launch_runtime_check.legal.documents",
        lambda: documents,
    )
    storage = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "default_acl": None,
                "querystring_auth": True,
                "object_parameters": {"ServerSideEncryption": "AES256"},
            },
        }
    }
    with override_settings(
        APP_ENV="production",
        CANDIDATE_ONLY=True,
        CANDIDATE_REGISTRATION_PAUSED=True,
        RESUME_UPLOADS_PAUSED=True,
        CANDIDATE_REGISTRATION_COUNTRIES={"IN"},
        LEGAL_CONTENT_APPROVED=True,
        LEGAL_WORKFLOW_PREVIEW=False,
        AI_PROVIDER="disabled",
        RESUME_AI_ENABLED=False,
        STORAGES=storage,
        AWS_S3_REGION_NAME="ap-southeast-2",
        AWS_SQS_REGION_NAME="ap-southeast-2",
        SECURE_SSL_REDIRECT=True,
        AUTH_COOKIE_SECURE=True,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
        FRONTEND_URL="https://enter.careers",
        ALLOWED_HOSTS=["enter.careers"],
        CORS_ALLOWED_ORIGINS=["https://enter.careers"],
        CSRF_TRUSTED_ORIGINS=["https://enter.careers"],
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="email-smtp.ap-southeast-2.amazonaws.com",
        EMAIL_USE_TLS=True,
        EMAIL_USE_SSL=False,
        EXPOSE_LOCAL_EMAIL_LINKS=False,
        EMAIL_VERIFICATION_TOKEN_TTL_SECONDS=86400,
        SUBMISSION_CONSENT_VERSION="enter-candidate-submission-v1.0",
        LEGAL_SUBMISSION_VERSION="enter-candidate-submission-v1.0",
    ):
        assert runtime_errors() == []

    with override_settings(CANDIDATE_ONLY=False):
        assert "candidate-only mode must be enabled" in runtime_errors()
