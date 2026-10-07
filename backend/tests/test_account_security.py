import re
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from talent.models import (
    AccountActionToken,
    CandidateProfile,
    CandidateStatus,
    CandidateUpdateNotification,
    ProfileView,
    Resume,
    WorkExperience,
)

from .test_candidate_flow import resume_docx

PASSWORD = "strong-pass-123"


def _email_token(message, parameter):
    match = re.search(rf"[?&]{parameter}=([^\s]+)", message.body)
    assert match
    return match.group(1)


def _signup_and_verify(client, email="verified@example.com"):
    mail.outbox.clear()
    signup = client.post(
        "/api/v1/auth/signup/",
        {
            "email": email,
            "password": PASSWORD,
            "full_name": "Verified Candidate",
            "role": "candidate",
        },
        format="json",
    )
    assert signup.status_code == 201
    assert signup.data["requires_email_verification"] is True
    assert "token" not in signup.data
    assert len(mail.outbox) == 1
    token = _email_token(mail.outbox[0], "verify-email")
    verified = client.post("/api/v1/auth/verify-email/", {"token": token}, format="json")
    assert verified.status_code == 200, verified.data
    client.credentials(HTTP_AUTHORIZATION=f"Token {verified.data['token']}")
    return verified.data, token


@pytest.mark.django_db
def test_candidate_email_verification_resend_expiry_and_one_time_use(settings):
    client = APIClient()
    mail.outbox.clear()
    signup = client.post(
        "/api/v1/auth/signup/",
        {
            "email": "pending@example.com",
            "password": PASSWORD,
            "full_name": "Pending Candidate",
            "role": "candidate",
        },
        format="json",
    )
    assert signup.status_code == 201
    assert signup.data["detail"] == "Check your email to verify your candidate account."
    assert signup.data["requires_email_verification"] is True
    assert signup.data["local_verification_url"].startswith(
        "http://127.0.0.1:5173/?verify-email="
    )
    user = User.objects.get(username="pending@example.com")
    assert user.is_active is False
    assert user.candidate_profile.email_verified_at is None
    assert not Token.objects.filter(user=user).exists()

    blocked = client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    assert blocked.status_code == 403
    assert blocked.data["code"] == "email_not_verified"

    first_token = _email_token(mail.outbox[0], "verify-email")
    generic = client.post(
        "/api/v1/auth/resend-verification/", {"email": user.email}, format="json"
    )
    unknown = client.post(
        "/api/v1/auth/resend-verification/",
        {"email": "unknown@example.com"},
        format="json",
    )
    assert generic.data == unknown.data
    assert len(mail.outbox) == 1

    with override_settings(EXPOSE_LOCAL_EMAIL_LINKS=False):
        production_style_signup = client.post(
            "/api/v1/auth/signup/",
            {
                "email": "no-local-link@example.com",
                "password": PASSWORD,
                "full_name": "No Local Link",
                "role": "candidate",
            },
            format="json",
        )
    assert production_style_signup.status_code == 201
    assert "local_verification_url" not in production_style_signup.data
    mail.outbox.pop()

    AccountActionToken.objects.filter(user=user).update(
        created_at=timezone.now()
        - timedelta(seconds=settings.ACCOUNT_EMAIL_RESEND_COOLDOWN_SECONDS + 1)
    )
    client.post("/api/v1/auth/resend-verification/", {"email": user.email}, format="json")
    assert len(mail.outbox) == 2
    second_token = _email_token(mail.outbox[1], "verify-email")
    assert client.post(
        "/api/v1/auth/verify-email/", {"token": first_token}, format="json"
    ).status_code == 400

    verified = client.post(
        "/api/v1/auth/verify-email/", {"token": second_token}, format="json"
    )
    assert verified.status_code == 200
    user.refresh_from_db()
    user.candidate_profile.refresh_from_db()
    assert user.is_active is True
    assert user.candidate_profile.email_verified_at is not None
    assert client.post(
        "/api/v1/auth/verify-email/", {"token": second_token}, format="json"
    ).status_code == 400

    mail.outbox.clear()
    expired_signup = client.post(
        "/api/v1/auth/signup/",
        {
            "email": "expired@example.com",
            "password": PASSWORD,
            "full_name": "Expired Candidate",
            "role": "candidate",
        },
        format="json",
    )
    assert expired_signup.status_code == 201
    expired_token = _email_token(mail.outbox[0], "verify-email")
    AccountActionToken.objects.filter(user__username="expired@example.com").update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert client.post(
        "/api/v1/auth/verify-email/", {"token": expired_token}, format="json"
    ).status_code == 400


@pytest.mark.django_db
def test_password_reset_is_non_enumerating_one_time_and_revokes_sessions():
    client = APIClient()
    verified, _ = _signup_and_verify(client, "reset@example.com")
    original_api_token = verified["token"]
    mail.outbox.clear()

    known = client.post(
        "/api/v1/auth/password-reset/request/",
        {"email": "reset@example.com"},
        format="json",
    )
    unknown = client.post(
        "/api/v1/auth/password-reset/request/",
        {"email": "does-not-exist@example.com"},
        format="json",
    )
    assert known.status_code == unknown.status_code == 200
    assert known.data == unknown.data
    assert len(mail.outbox) == 1
    reset_token = _email_token(mail.outbox[0], "reset-password")

    weak = client.post(
        "/api/v1/auth/password-reset/confirm/",
        {"token": reset_token, "password": "short"},
        format="json",
    )
    assert weak.status_code == 400
    changed = client.post(
        "/api/v1/auth/password-reset/confirm/",
        {"token": reset_token, "password": "new-strong-pass-456"},
        format="json",
    )
    assert changed.status_code == 200
    assert client.post(
        "/api/v1/auth/password-reset/confirm/",
        {"token": reset_token, "password": "another-strong-pass-789"},
        format="json",
    ).status_code == 400

    stale_session = APIClient()
    stale_session.credentials(HTTP_AUTHORIZATION=f"Token {original_api_token}")
    assert stale_session.get("/api/v1/candidate/profile/").status_code == 401
    assert client.post(
        "/api/v1/auth/login/",
        {"email": "reset@example.com", "password": PASSWORD},
        format="json",
    ).status_code == 400
    assert client.post(
        "/api/v1/auth/login/",
        {"email": "reset@example.com", "password": "new-strong-pass-456"},
        format="json",
    ).status_code == 200


@pytest.mark.django_db
def test_api_token_expiry_and_logout_revoke_candidate_access(settings):
    client = APIClient()
    verified, _ = _signup_and_verify(client, "session@example.com")
    Token.objects.filter(key=verified["token"]).update(
        created=timezone.now() - timedelta(seconds=settings.AUTH_TOKEN_TTL_SECONDS + 1)
    )
    assert client.get("/api/v1/candidate/profile/").status_code == 401
    assert not Token.objects.filter(key=verified["token"]).exists()

    login = client.post(
        "/api/v1/auth/login/",
        {"email": "session@example.com", "password": PASSWORD},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Token {login.data['token']}")
    assert client.post("/api/v1/auth/logout/").status_code == 204
    assert client.get("/api/v1/candidate/profile/").status_code == 401


@pytest.mark.django_db
def test_candidate_account_deletion_removes_profile_relations_and_resume_files(tmp_path):
    with override_settings(MEDIA_ROOT=tmp_path):
        client = APIClient()
        verified, _ = _signup_and_verify(client, "delete-me@example.com")
        upload = SimpleUploadedFile(
            "delete-me.docx",
            resume_docx(name="Delete Me"),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        created = client.post(
            "/api/v1/candidate/resumes/", {"file": upload}, format="multipart"
        )
        assert created.status_code == 201
        profile_id = created.data["id"]
        client.patch(
            "/api/v1/candidate/profile/",
            {"visibility": "approved_recruiters", "work_preferences": ["Remote"]},
            format="json",
        )
        submitted = client.post(
            "/api/v1/candidate/profile/submit/", {"consent": True}, format="json"
        )
        assert submitted.status_code == 200
        assert submitted.data["submission_consent_at"]

        recruiter = APIClient()
        recruiter_signup = recruiter.post(
            "/api/v1/auth/signup/",
            {
                "email": "deletion-recruiter@example.com",
                "password": PASSWORD,
                "full_name": "Deletion Recruiter",
                "company": "Enter",
                "role": "recruiter",
            },
            format="json",
        )
        recruiter.credentials(
            HTTP_AUTHORIZATION=f"Token {recruiter_signup.data['token']}"
        )
        assert recruiter.get(f"/api/v1/candidates/{profile_id}/").status_code == 200
        assert recruiter.put(
            f"/api/v1/candidates/{profile_id}/status/",
            {"status": "sourced"},
            format="json",
        ).status_code == 200

        replacement = SimpleUploadedFile(
            "delete-me-v2.docx",
            resume_docx(name="Delete Me", role="Staff Backend Engineer"),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert client.post(
            "/api/v1/candidate/resumes/", {"file": replacement}, format="multipart"
        ).status_code == 201
        assert CandidateUpdateNotification.objects.filter(candidate_id=profile_id).exists()
        paused = client.patch(
            "/api/v1/candidate/profile/", {"visibility": "not_looking"}, format="json"
        )
        assert paused.data["discovery_status"] == "not_looking"
        resumes = list(Resume.objects.filter(candidate_id=profile_id))
        stored_files = [(resume.file.storage, resume.file.name) for resume in resumes]
        assert all(storage.exists(name) for storage, name in stored_files)

        assert client.delete(
            "/api/v1/candidate/account/",
            {"confirmation": "DELETE", "password": "wrong-password"},
            format="json",
        ).status_code == 400
        deleted = client.delete(
            "/api/v1/candidate/account/",
            {"confirmation": "DELETE", "password": PASSWORD},
            format="json",
        )
        assert deleted.status_code == 204
        assert not User.objects.filter(username="delete-me@example.com").exists()
        assert not CandidateProfile.objects.filter(pk=profile_id).exists()
        assert not Resume.objects.filter(candidate_id=profile_id).exists()
        assert not WorkExperience.objects.filter(candidate_id=profile_id).exists()
        assert not ProfileView.objects.filter(candidate_id=profile_id).exists()
        assert not CandidateStatus.objects.filter(candidate_id=profile_id).exists()
        assert not CandidateUpdateNotification.objects.filter(candidate_id=profile_id).exists()
        assert not Token.objects.filter(key=verified["token"]).exists()
        assert all(not storage.exists(name) for storage, name in stored_files)
        assert client.get("/api/v1/candidate/profile/").status_code == 401
