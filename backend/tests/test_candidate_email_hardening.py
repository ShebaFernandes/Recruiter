import io
import os
import smtplib
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from talent.account_security import (
    issue_account_token,
    send_password_reset_email,
    send_verification_email,
)
from talent.models import AccountActionToken, CandidateProfile, UserRole

PASSWORD = "Candidate-security-123!"


def candidate(*, active=True, verified=False):
    user = User.objects.create_user(
        username="security@example.com", email="security@example.com",
        password=PASSWORD, is_active=active,
    )
    UserRole.objects.create(user=user, role="candidate")
    CandidateProfile.objects.create(
        user=user, email_verified_at=timezone.now() if verified else None,
    )
    return user


@pytest.mark.django_db
@pytest.mark.parametrize("cookie", [False, True])
def test_active_unverified_candidate_cannot_login_or_use_existing_token(cookie):
    user = candidate()
    client = APIClient()
    response = client.post("/api/v1/auth/login/", {
        "email": user.email, "password": PASSWORD,
    }, format="json")
    assert response.status_code == 403
    assert response.data["code"] == "email_not_verified"
    token = Token.objects.create(user=user)
    if cookie:
        from django.conf import settings
        client.cookies[settings.AUTH_COOKIE_NAME] = token.key
    else:
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    for method, path in [
        ("get", "auth/me/"), ("get", "candidate/profile/"),
        ("patch", "candidate/profile/"), ("post", "candidate/resumes/"),
        ("post", "candidate/profile/submit/"), ("get", "resumes/1/download/"),
    ]:
        assert getattr(client, method)(f"/api/v1/{path}", {}, format="json").status_code == 401


@pytest.mark.django_db
def test_disabled_verified_candidate_cannot_reactivate_with_verification_or_reset():
    user = candidate(verified=True)
    verification = issue_account_token(user, AccountActionToken.Purpose.VERIFY_EMAIL)
    reset = issue_account_token(user, AccountActionToken.Purpose.RESET_PASSWORD)
    session = Token.objects.create(user=user)
    user.is_active = False
    user.save(update_fields=["is_active"])
    client = APIClient()
    mail.outbox.clear()
    response = client.post("/api/v1/auth/resend-verification/", {"email": user.email})
    unknown = client.post("/api/v1/auth/resend-verification/", {"email": "unknown@example.com"})
    assert response.status_code == unknown.status_code == 200
    assert response.data == unknown.data
    assert not mail.outbox
    assert client.post("/api/v1/auth/verify-email/", {"token": verification}).status_code == 400
    assert client.post("/api/v1/auth/password-reset/confirm/", {
        "token": reset, "password": "Changed-secure-password-456!",
    }).status_code == 200
    user.refresh_from_db()
    assert not user.is_active
    assert client.post("/api/v1/auth/login/", {
        "email": user.email, "password": "Changed-secure-password-456!",
    }).status_code == 400
    client.credentials(HTTP_AUTHORIZATION=f"Token {session.key}")
    assert client.get("/api/v1/candidate/profile/").status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize("password", ["12345678", "password", "security@example.com"])
def test_signup_applies_all_existing_password_validators(password):
    response = APIClient().post("/api/v1/auth/signup/", {
        "email": "security@example.com", "password": password,
        "full_name": "Fictional Candidate", "role": "candidate",
    })
    assert response.status_code == 400
    assert "password" in response.data
    assert not User.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("app_env,debug,enabled,allowed", [
    ("local", True, False, False), ("local", True, True, True),
    ("staging", True, True, False), ("production", True, True, False),
    ("local", False, True, False),
])
def test_local_shortcuts_are_guarded_at_runtime(settings, app_env, debug, enabled, allowed):
    settings.APP_ENV = app_env
    settings.DEBUG = debug
    settings.EXPOSE_LOCAL_EMAIL_LINKS = enabled
    response = APIClient().post("/api/v1/auth/signup/", {
        "email": "security@example.com", "password": PASSWORD,
        "full_name": "Fictional Candidate", "role": "candidate",
    })
    assert response.status_code == 201
    assert ("local_verification_url" in response.data) is allowed
    if allowed:
        output = io.StringIO()
        call_command("issue_local_account_token", "security@example.com", "verify_email",
                     stdout=output)
        assert output.getvalue().strip()
    else:
        with pytest.raises(CommandError, match="explicit local/test opt-in"):
            call_command("issue_local_account_token", "security@example.com", "verify_email")


@pytest.mark.django_db
@pytest.mark.parametrize("error,category", [
    (smtplib.SMTPAuthenticationError(535, b"private@example.com credential secret"),
     "smtp_authentication"),
    (TimeoutError("private@example.com secret token"), "timeout"),
    (smtplib.SMTPException("private@example.com secret token"), "smtp_failure"),
    (OSError("private@example.com secret token"), "connection_failure"),
])
def test_delivery_failures_are_sanitized_and_responses_non_enumerating(error, category, caplog):
    user = candidate(active=False)
    client = APIClient()
    with patch("talent.account_security.send_mail", side_effect=error):
        known = client.post("/api/v1/auth/resend-verification/", {"email": user.email})
        unknown = client.post("/api/v1/auth/resend-verification/", {
            "email": "unknown@example.com",
        })
        assert known.status_code == unknown.status_code == 200
        assert known.data == unknown.data
        user.is_active = True
        user.save(update_fields=["is_active"])
        known = client.post("/api/v1/auth/password-reset/request/", {"email": user.email})
        unknown = client.post("/api/v1/auth/password-reset/request/", {
            "email": "unknown@example.com",
        })
        assert known.status_code == unknown.status_code == 200
        assert known.data == unknown.data
    assert f"category={category}" in caplog.text
    for sensitive in ["private@example.com", user.email, "secret", "credential", "Traceback"]:
        assert sensitive not in caplog.text


@pytest.mark.django_db
def test_signup_delivery_failure_and_configured_expiry_wording(settings, caplog):
    client = APIClient()
    with patch("talent.account_security.send_mail", return_value=0):
        response = client.post("/api/v1/auth/signup/", {
            "email": "security@example.com", "password": PASSWORD,
            "full_name": "Fictional Candidate", "role": "candidate",
        })
    assert response.status_code == 503
    assert "local_verification_url" not in response.data
    assert "account_email_delivery_failed" in caplog.text
    user = User.objects.get(username="security@example.com")
    assert not user.is_active
    settings.EMAIL_VERIFICATION_TOKEN_TTL_SECONDS = 900
    settings.PASSWORD_RESET_TOKEN_TTL_SECONDS = 61
    send_verification_email(user)
    send_password_reset_email(user)
    assert "expires in 15 minutes" in mail.outbox[-2].body
    assert "expires in 61 seconds" in mail.outbox[-1].body


def load_settings(overrides):
    # A fresh interpreter verifies startup guards without contacting any service.
    env = {"PATH": os.environ.get("PATH", ""), "DEBUG": "false", "APP_ENV": "production",
           "TESTING": "false", "DJANGO_SECRET_KEY": "test-only-not-a-secret-" * 4,
           "DATABASE_URL": "postgresql://test:test@127.0.0.1:1/not_used",
           "ALLOWED_HOSTS": "app.example.test", "CORS_ALLOWED_ORIGINS": "https://app.example.test",
           "CSRF_TRUSTED_ORIGINS": "https://app.example.test",
           "FRONTEND_URL": "https://app.example.test", "AWS_STORAGE_BUCKET_NAME": "test-only",
           "AWS_S3_REGION_NAME": "ap-south-1", "AWS_SQS_REGION_NAME": "ap-south-1",
           "RESUME_QUEUE_BACKEND": "sqs",
           "RESUME_SQS_QUEUE_URL": "https://sqs.ap-south-1.amazonaws.com/000/test",
           "RESUME_SCANNER_BACKEND": "clamav", "AUTH_COOKIE_SECURE": "true",
           "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
           "EMAIL_HOST": "smtp.example.test", "EMAIL_HOST_USER": "placeholder",
           "EMAIL_HOST_PASSWORD": "placeholder", "DEFAULT_FROM_EMAIL": "test@example.test",
           "EMAIL_USE_TLS": "true", "AI_PROVIDER": "disabled",
           "LEGAL_CONTENT_APPROVED": "true"}
    env.update(overrides)
    return subprocess.run(
        [sys.executable, "-c", "from config import settings; "
         "print(settings.EXPOSE_LOCAL_EMAIL_LINKS, settings.EMAIL_TIMEOUT)"],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
        check=False,
    )


@pytest.mark.parametrize("overrides,expected", [
    ({"LEGAL_CONTENT_APPROVED": "false"}, "Approve published privacy"),
    ({"ALLOWED_HOSTS": "*"}, "exact host names"),
    ({"CORS_ALLOWED_ORIGINS": "https://*.example.com"}, "exact HTTPS origins"),
    ({"SECURE_SSL_REDIRECT": "false"}, "must enforce HTTPS"),
    ({"AI_PROVIDER": "openai", "OPENAI_API_KEY": ""}, "server-side API key"),
    ({"AI_ALLOW_DETERMINISTIC_FALLBACK": "true"}, "silently using"),
    ({"RESUME_SCANNER_BACKEND": "development"}, "real malware scanner"),
    ({"RESUME_PROCESS_HARD_TIMEOUT_SECONDS": "400"}, "shorter than its lease"),
    ({"APP_ENV": "staging", "DEBUG": "true"}, "must disable DEBUG and TESTING"),
    ({"TESTING": "true"}, "must disable DEBUG and TESTING"),
    ({"EXPOSE_LOCAL_EMAIL_LINKS": "true"}, "shortcuts are forbidden"),
    ({"EMAIL_USE_TLS": "false"}, "requires STARTTLS or implicit SSL"),
    ({"EMAIL_USE_SSL": "true"}, "not both"),
    ({"EMAIL_TIMEOUT": "0"}, "between 1 and 60"),
    ({"EMAIL_TIMEOUT": "61"}, "between 1 and 60"),
    ({"EMAIL_HOST_PASSWORD": ""}, "SMTP configuration is missing"),
    ({"EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend"},
     "requires a transactional email backend"),
])
def test_unsafe_deployed_email_configuration_fails_startup(overrides, expected):
    result = load_settings(overrides)
    assert result.returncode != 0
    assert expected in result.stderr


@pytest.mark.parametrize("overrides", [
    {}, {"EMAIL_USE_TLS": "false", "EMAIL_USE_SSL": "true", "EMAIL_PORT": "465"},
    {"APP_ENV": "local", "DEBUG": "true"},
])
def test_safe_settings_load_and_shortcuts_default_off(overrides):
    result = load_settings(overrides)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False 10"
