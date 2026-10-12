from types import SimpleNamespace

import pytest
from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.test import Client
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from talent.admin import RecruiterAdminForm
from talent.models import CandidateProfile, Project, RecruiterProfile, UserRole
from talent.views import _recruiter_can_access_candidate

from .recruiter_helpers import provision_recruiter

pytestmark = pytest.mark.django_db
PASSWORD = "Approval-test-password-123!"
ENDPOINTS = [
    ("get", "/searches/"),
    ("post", "/searches/"),
    ("post", "/searches/1/answer/"),
    ("get", "/searches/1/results/"),
    ("get", "/projects/"),
    ("post", "/projects/"),
    ("get", "/projects/1/"),
    ("patch", "/projects/1/"),
    ("delete", "/projects/1/"),
    ("post", "/projects/1/candidates/"),
    ("delete", "/projects/1/candidates/1/"),
    ("get", "/candidates/1/"),
    ("put", "/candidates/1/status/"),
    ("delete", "/candidates/1/status/"),
    ("post", "/candidates/compare/"),
    ("get", "/notifications/"),
    ("post", "/notifications/1/read/"),
    ("get", "/resumes/1/download/"),
]


@pytest.mark.parametrize("identity", ["anonymous", "candidate", "unapproved", "inactive"])
def test_all_recruiter_endpoints_reject_unauthorized_identity(identity):
    client = APIClient()
    if identity != "anonymous":
        user = User.objects.create_user("restricted@example.com", password=PASSWORD)
        if identity == "candidate":
            UserRole.objects.create(user=user, role="candidate")
            CandidateProfile.objects.create(
                user=user, full_name="Candidate", email_verified_at=timezone.now(),
            )
        else:
            UserRole.objects.create(user=user, role="recruiter")
            RecruiterProfile.objects.create(user=user, is_approved=identity == "inactive")
        if identity == "inactive":
            user.is_active = False
            user.save()
        client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}")
    for method, path in ENDPOINTS:
        response = getattr(client, method)("/api/v1" + path, {}, format="json")
        assert response.status_code in (401, 403, 404), (identity, path, response.status_code)
        # Candidate resume requests return 404 for another owner's document.
        if not (identity == "candidate" and path.startswith("/resumes/")):
            assert response.status_code in (401, 403), (identity, path)


def test_public_signup_cannot_create_recruiter_or_approve_candidate(client):
    payload = {
        "email": "employee@enterrecruitment.com",
        "password": PASSWORD,
        "full_name": "Employee",
        "role": "recruiter",
        "is_approved": True,
    }
    assert client.post("/api/v1/auth/signup/", payload, format="json").status_code == 403
    assert not User.objects.filter(username=payload["email"]).exists()
    payload["role"] = "candidate"
    assert client.post("/api/v1/auth/signup/", payload, format="json").status_code == 201
    assert not RecruiterProfile.objects.exists()
    assert CandidateProfile.objects.count() == 1


def test_approval_and_revocation_preserve_work_and_block_existing_cookie(client):
    response = provision_recruiter(
        client,
        {
            "email": "approved@example.com",
            "password": PASSWORD,
            "full_name": "Approved",
        },
    )
    assert response.status_code == 200
    recruiter = RecruiterProfile.objects.get(user__username="approved@example.com")
    assert recruiter.approved_by.is_superuser and recruiter.approved_at
    project = client.post("/api/v1/projects/", {"name": "Saved work"}, format="json")
    assert project.status_code == 201
    token_key = response.data["token"]
    assert client.get("/api/v1/searches/").status_code == 200
    # Direct revocation must block even without deleting the token.
    RecruiterProfile.objects.filter(pk=recruiter.pk).update(is_approved=False)
    assert Token.objects.filter(key=token_key).exists()
    assert client.get("/api/v1/auth/me/").status_code == 401
    assert client.get("/api/v1/projects/").status_code == 401
    assert Project.objects.filter(pk=project.data["id"], recruiter=recruiter).exists()
    client.cookies.clear()
    denied = client.post(
        "/api/v1/auth/login/",
        {
            "email": recruiter.user.email,
            "password": PASSWORD,
        },
        format="json",
    )
    assert denied.status_code == 403
    recruiter.refresh_from_db()
    form = RecruiterAdminForm(
        data={
            "user": recruiter.user_id,
            "full_name": "Approved",
            "company": "ENTER",
            "is_approved": False,
        },
        instance=recruiter,
    )
    assert form.is_valid(), form.errors
    admin.site._registry[RecruiterProfile].save_model(
        SimpleNamespace(user=User.objects.get(username="test-provisioning-admin")),
        form.save(commit=False),
        form,
        True,
    )
    assert not Token.objects.filter(key=token_key).exists()
    assert Project.objects.filter(pk=project.data["id"]).exists()


def test_resume_visibility_helper_requires_current_approval(client, candidate_account):
    candidate = CandidateProfile.objects.get(user_id=candidate_account["user"]["id"])
    from django.utils import timezone

    candidate.profile_status = "submitted"
    candidate.submission_consent_at = timezone.now()
    candidate.save()
    user = User.objects.create_user("unapproved@example.com", password=PASSWORD)
    UserRole.objects.create(user=user, role="recruiter")
    recruiter = RecruiterProfile.objects.create(user=user)
    assert not _recruiter_can_access_candidate(recruiter, candidate)


def test_non_superuser_cannot_manage_approval_even_with_all_model_permissions():
    staff = User.objects.create_user("staff", password=PASSWORD, is_staff=True)
    staff.user_permissions.set(Permission.objects.all())
    client = Client()
    client.force_login(staff)
    for path in [
        "talent/recruiterprofile/",
        "talent/recruiterprofile/add/",
        "talent/userrole/",
        "auth/user/",
        "auth/group/",
    ]:
        assert client.get("/admin/" + path).status_code == 403
        assert client.post("/admin/" + path, {"is_approved": True}).status_code == 403


def test_admin_add_and_change_pages_render_and_record_approval(settings):
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    administrator = User.objects.create_superuser("approval-admin", password=PASSWORD)
    client = Client()
    client.force_login(administrator)
    assert client.get("/admin/talent/recruiterprofile/add/").status_code == 200
    response = client.post(
        "/admin/talent/recruiterprofile/add/",
        {
            "email": "admin-created@example.com",
            "password": PASSWORD,
            "full_name": "Admin Created",
            "company": "ENTER",
            "_continue": "Save",
        },
    )
    assert response.status_code == 302
    assert client.get(response.url).status_code == 200
    recruiter = RecruiterProfile.objects.get(user__username="admin-created@example.com")
    assert not recruiter.is_approved
    change_url = f"/admin/talent/recruiterprofile/{recruiter.pk}/change/"
    response = client.post(
        change_url,
        {
            "full_name": recruiter.full_name,
            "company": "ENTER",
            "is_approved": "on",
            "_continue": "Save",
        },
    )
    assert response.status_code == 302
    recruiter.refresh_from_db()
    assert recruiter.is_approved and recruiter.approved_by == administrator
    assert client.get(change_url).status_code == 200
    assert not recruiter.user.is_staff and not recruiter.user.is_superuser


def test_admin_login_keeps_csrf_and_uses_existing_login_quota(settings, monkeypatch):
    from talent.throttling import LoginRateThrottle

    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
    monkeypatch.setattr(LoginRateThrottle, "THROTTLE_RATES", {"login": "1/min"})
    client = Client(enforce_csrf_checks=True)
    assert client.post("/admin/login/", {}).status_code == 403
    assert client.get("/admin/login/").status_code == 200
    headers = {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}
    assert client.post("/admin/login/", {}, **headers).status_code == 200
    response = client.post("/admin/login/", {}, **headers)
    assert response.status_code == 429 and int(response["Retry-After"]) > 0


@pytest.mark.parametrize(
    "path",
    [
        "signup",
        "login",
        "verify-email",
        "resend-verification",
        "password-reset/request",
        "password-reset/confirm",
    ],
)
def test_anonymous_auth_post_requires_csrf_and_trusted_origin(path):
    client = APIClient(enforce_csrf_checks=True)
    url = f"/api/v1/auth/{path}/"
    assert client.post(url, {}, format="json").status_code == 403
    token = client.get("/api/v1/auth/csrf/").data["csrfToken"]
    assert (
        client.post(
            url, {}, format="json", HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://hostile.example"
        ).status_code
        == 403
    )
    response = client.post(
        url, {}, format="json", HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="http://localhost:5173"
    )
    assert response.status_code in (200, 400)


def test_admin_form_rejects_candidate_conversion_and_weak_password(client, candidate_account):
    form = RecruiterAdminForm(
        data={
            "user": candidate_account["user"]["id"],
            "full_name": "Candidate",
            "is_approved": True,
        }
    )
    assert not form.is_valid()
    form = RecruiterAdminForm(
        data={
            "email": "new@example.com",
            "password": "123",
            "full_name": "New",
            "is_approved": True,
        }
    )
    assert not form.is_valid()


def test_password_reset_cannot_approve_or_reactivate_recruiter(client):
    from talent.account_security import issue_account_token
    from talent.models import AccountActionToken

    user = User.objects.create_user("pending@example.com", password=PASSWORD)
    UserRole.objects.create(user=user, role="recruiter")
    recruiter = RecruiterProfile.objects.create(user=user)
    token = issue_account_token(user, AccountActionToken.Purpose.RESET_PASSWORD)
    response = client.post(
        "/api/v1/auth/password-reset/confirm/",
        {
            "token": token,
            "password": "Replacement-password-789!",
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.data["role"] == "recruiter"
    recruiter.refresh_from_db()
    assert not recruiter.is_approved
    assert (
        client.post(
            "/api/v1/auth/login/",
            {
                "email": user.username,
                "password": "Replacement-password-789!",
            },
            format="json",
        ).status_code
        == 403
    )
    user.is_active = False
    user.save()
    RecruiterProfile.objects.filter(pk=recruiter.pk).update(is_approved=True)
    response = client.post(
        "/api/v1/auth/login/",
        {
            "email": user.username,
            "password": "Replacement-password-789!",
        },
        format="json",
    )
    assert response.status_code == 400
    assert "email_not_verified" not in str(response.data)
