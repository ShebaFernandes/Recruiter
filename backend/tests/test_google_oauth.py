"""Synthetic provider responses; never requires Google credentials or real accounts."""

import time
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.utils import timezone
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import RSAKey
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from talent import google_oauth as google
from talent.models import (
    CandidateProfile,
    ExternalIdentity,
    GoogleOAuthTransaction,
    LegalAcceptance,
    OpportunityApplication,
    Resume,
    UserRole,
    WorkExperience,
)
from talent.throttling import LoginRateThrottle

pytestmark = pytest.mark.django_db
BASE = "/api/v1/auth/google/"
IDENTITY = {
    "subject": "google-synthetic-1",
    "email": "fictional@gmail.com",
    "full_name": "Fictional Candidate",
    "authoritative": True,
}


@pytest.fixture(autouse=True)
def oauth_settings(settings):
    settings.GOOGLE_OAUTH_ENABLED = True
    settings.GOOGLE_OAUTH_CLIENT_ID = "synthetic-client"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "synthetic-secret"
    settings.GOOGLE_OAUTH_REDIRECT_URI = "http://127.0.0.1:8010/api/v1/auth/google/callback/"
    settings.CANDIDATE_REGISTRATION_COUNTRIES = {"IN"}


def start(client, path="start/", body=None):
    response = client.post(BASE + path, body or {}, format="json")
    assert response.status_code == 200, response.data
    query = parse_qs(urlsplit(response.data["url"]).query)
    return query["state"][0], query


def callback(client, state, identity=None):
    with patch("talent.google_oauth.exchange", return_value=identity or IDENTITY):
        return client.get(BASE + "callback/", {"state": state, "code": "synthetic-code"})


def pending_signup(client, identity=None):
    state, _ = start(client)
    response = callback(client, state, identity)
    assert "result=signup" in response.url
    return state


def complete(client, **body):
    # Synthetic fixtures explicitly exercise the existing reviewed-confirmation flow.
    # Never use disabled legal settings as permission to create a candidate.
    from talent import legal

    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        docs = legal.documents()
        data = {
            "country_code": "IN",
            "age_accepted": True,
            "terms_accepted": True,
            "age_version": docs["age"]["version"],
            "terms_version": docs["terms"]["version"],
            **body,
        }
        return client.post(BASE + "complete/", data, format="json")


def candidate(email="fictional@gmail.com", password="strong-pass-123"):
    user = User.objects.create_user(username=email, email=email, password=password)
    UserRole.objects.create(user=user, role="candidate")
    CandidateProfile.objects.create(
        user=user, email=email, full_name="Existing name", email_verified_at=timezone.now()
    )
    return user


def test_disabled_by_default_is_safe(client, settings):
    settings.GOOGLE_OAUTH_ENABLED = False
    assert client.get(BASE + "config/").data == {"enabled": False}
    assert client.post(BASE + "start/", {}, format="json").status_code == 400
    assert not GoogleOAuthTransaction.objects.exists()


def test_pkce_and_browser_bound_state(client):
    state, query = start(client, body={"next": "https://evil.example"})
    assert query["scope"] == ["openid email profile"]
    assert query["response_type"] == ["code"]
    assert query["code_challenge_method"] == ["S256"]
    assert "synthetic-secret" not in str(query)
    obj = GoogleOAuthTransaction.objects.get(state_hash=google.digest(state))
    assert obj.payload["next"] == "/"
    assert obj.payload["verifier"] not in query["code_challenge"]
    assert client.cookies[google.BROWSER_COOKIE]["httponly"]
    assert client.cookies[google.BROWSER_COOKIE]["samesite"] == "Lax"
    other = APIClient()
    assert "result=failed" in callback(other, state).url
    assert GoogleOAuthTransaction.objects.get(pk=obj.pk).stage == "authorize"


def test_new_google_candidate_and_repeat_login_logout(client):
    pending_signup(client)
    response = complete(client)
    assert response.status_code == 200, response.data
    user = User.objects.get()
    assert not user.has_usable_password()
    assert user.is_active and user.role_profile.role == "candidate"
    assert user.candidate_profile.visibility == ""
    assert not user.candidate_profile.submission_consent_at
    assert ExternalIdentity.objects.get().user_id == user.pk
    assert client.get("/api/v1/auth/me/").data["id"] == user.pk
    assert client.cookies[settings.AUTH_COOKIE_NAME]["httponly"]
    assert client.post("/api/v1/auth/logout/").status_code == 204
    state, _ = start(client)
    assert "result=success" in callback(client, state).url
    assert client.get("/api/v1/auth/me/").data["id"] == user.pk
    assert User.objects.count() == 1


def test_existing_email_requires_explicit_link_and_preserves_data(client):
    user = candidate()
    profile = user.candidate_profile
    profile.career_preferences = {"meaning": "synthetic"}
    profile.save()
    experience = WorkExperience.objects.create(
        candidate=profile, company="Existing Co", role="Engineer"
    )
    resume = Resume.objects.create(
        candidate=profile, file="synthetic/resume.pdf", original_name="resume.pdf"
    )
    application = OpportunityApplication.objects.create(
        candidate=profile, opportunity_id="synthetic-role"
    )
    profile_before = CandidateProfile.objects.values().get(pk=profile.pk)
    state, _ = start(client)
    assert "result=link" in callback(client, state).url
    assert not ExternalIdentity.objects.exists()
    assert not Token.objects.exists()
    assert User.objects.count() == 1
    state, _ = start(client, "link/start/", {"email": user.email, "password": "strong-pass-123"})
    assert "result=confirm_link" in callback(client, state).url
    assert client.post(BASE + "link/confirm/", {}, format="json").status_code == 400
    result = client.post(BASE + "link/confirm/", {"confirm": True}, format="json")
    assert result.status_code == 200
    assert result.data["user"]["id"] == user.pk
    assert CandidateProfile.objects.values().get(pk=profile.pk) == profile_before
    assert WorkExperience.objects.get().pk == experience.pk
    assert Resume.objects.get().pk == resume.pk
    assert OpportunityApplication.objects.get().pk == application.pk
    user.refresh_from_db()
    assert user.check_password("strong-pass-123")
    assert client.post(BASE + "link/confirm/", {"confirm": True}, format="json").status_code == 400


@pytest.mark.parametrize(
    "variation", ["cancel", "expired", "replay", "exchange_error", "bad_state"]
)
def test_failed_responses_never_create_accounts(client, variation):
    state, _ = start(client)
    if variation == "cancel":
        response = client.get(BASE + "callback/", {"state": state, "error": "access_denied"})
        assert "result=cancelled" in response.url
    elif variation == "expired":
        GoogleOAuthTransaction.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        assert "result=failed" in callback(client, state).url
    elif variation == "replay":
        callback(client, state)
        assert "result=failed" in callback(client, state).url
    elif variation == "exchange_error":
        with patch("talent.google_oauth.exchange", side_effect=ValueError("bad token")):
            assert (
                "result=failed" in client.get(BASE + "callback/", {"state": state, "code": "x"}).url
            )
    else:
        assert "result=failed" in callback(client, "wrong-state").url
    assert not User.objects.exists()


def test_registration_controls_rechecked_after_google(client, settings):
    pending_signup(client)
    settings.CANDIDATE_REGISTRATION_PAUSED = True
    assert complete(client).status_code == 503
    assert not User.objects.exists()
    settings.CANDIDATE_REGISTRATION_PAUSED = False
    assert complete(client, country_code="US").status_code == 400
    assert complete(client).status_code == 200
    assert complete(client).status_code == 400


def test_signup_race_with_password_account_never_duplicates(client):
    pending_signup(client)
    candidate()
    assert complete(client).status_code == 400
    assert User.objects.count() == 1
    assert not ExternalIdentity.objects.exists()


def test_database_case_insensitive_email_and_username_constraints():
    candidate()
    for fields in [
        {"username": "another", "email": "FICTIONAL@gmail.com"},
        {"username": "FICTIONAL@gmail.com", "email": "different@example.test"},
    ]:
        with pytest.raises(IntegrityError), transaction.atomic():
            User.objects.create(**fields)


def test_non_authoritative_email_requires_enter_verification(client):
    pending_signup(client, {**IDENTITY, "email": "fictional@example.test", "authoritative": False})
    response = complete(client)
    assert response.status_code == 201
    assert response.data["requires_email_verification"]
    user = User.objects.get()
    assert not user.is_active
    assert user.candidate_profile.email_verified_at is None
    assert not Token.objects.exists()


def test_google_only_account_cannot_gain_password_via_reset(client):
    user = candidate(password=None)
    client.post("/api/v1/auth/password-reset/request/", {"email": user.email}, format="json")
    assert not mail.outbox


def test_disabled_candidate_not_reactivated(client):
    user = candidate()
    ExternalIdentity.objects.create(user=user, subject=IDENTITY["subject"])
    user.is_active = False
    user.save()
    state, _ = start(client)
    assert "result=failed" in callback(client, state).url
    user.refresh_from_db()
    assert not user.is_active
    assert not Token.objects.exists()


def test_recruiter_google_is_not_enabled(client, recruiter_account):
    client.credentials()
    user = User.objects.get(pk=recruiter_account["user"]["id"])
    state, _ = start(client)
    assert "result=link" in callback(client, state, {**IDENTITY, "email": user.email}).url
    response = client.post(
        BASE + "link/start/", {"email": user.email, "password": "strong-pass-123"}, format="json"
    )
    assert response.status_code == 400
    assert not ExternalIdentity.objects.exists()
    client.credentials(HTTP_AUTHORIZATION=f"Token {recruiter_account['token']}")
    assert client.get("/api/v1/candidate/profile/").status_code == 403
    assert (
        client.post(BASE + "reauth/", {"action": "delete_account"}, format="json").status_code
        == 403
    )


def test_link_rejects_password_reset_and_wrong_google_account(client):
    user = candidate()
    state, _ = start(client, "link/start/", {"email": user.email, "password": "strong-pass-123"})
    assert "result=failed" in callback(client, state, {**IDENTITY, "email": "other@gmail.com"}).url
    state, _ = start(client, "link/start/", {"email": user.email, "password": "strong-pass-123"})
    user.set_password("changed-password-123")
    user.save()
    assert "result=failed" in callback(client, state).url
    assert not ExternalIdentity.objects.exists()


def test_csrf_required_on_anonymous_google_mutations():
    client = APIClient(enforce_csrf_checks=True)
    for path in ["start/", "link/start/", "complete/", "link/confirm/"]:
        assert client.post(BASE + path, {}, format="json").status_code == 403
    csrf = client.get("/api/v1/auth/csrf/").data["csrfToken"]
    assert client.post(BASE + "start/", {}, format="json", HTTP_X_CSRFTOKEN=csrf).status_code == 200


def test_google_uses_existing_login_rate_quota(client):
    with patch.dict(LoginRateThrottle.THROTTLE_RATES, {"login": "1/min"}):
        start(client)
        response = client.post("/api/v1/auth/login/", {"email": "x", "password": "x"})
        assert response.status_code == 429


def test_session_bound_google_reauthentication_for_deletion(client):
    user = candidate(password=None)
    ExternalIdentity.objects.create(user=user, subject=IDENTITY["subject"])
    token = Token.objects.create(user=user)
    client.cookies[settings.AUTH_COOKIE_NAME] = token.key
    assert (
        client.delete(
            "/api/v1/candidate/account/", {"confirmation": "DELETE"}, format="json"
        ).status_code
        == 400
    )
    state, _ = start(client, "reauth/", {"action": "delete_account"})
    assert "result=reauthenticated" in callback(client, state).url
    assert (
        client.delete(
            "/api/v1/candidate/account/", {"confirmation": "DELETE"}, format="json"
        ).status_code
        == 204
    )
    assert not User.objects.exists()


def test_reauthentication_proof_rejected_after_logout(client):
    user = candidate(password=None)
    ExternalIdentity.objects.create(user=user, subject=IDENTITY["subject"])
    token = Token.objects.create(user=user)
    client.cookies[settings.AUTH_COOKIE_NAME] = token.key
    state, _ = start(client, "reauth/", {"action": "delete_account"})
    client.post("/api/v1/auth/logout/")
    assert "result=failed" in callback(client, state).url


def test_new_google_signup_requires_current_legal_acceptance(client):
    from .test_legal_workflow import acceptance

    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        pending_signup(client)
        assert (
            client.post(BASE + "complete/", {"country_code": "IN"}, format="json").status_code
            == 400
        )
        assert not User.objects.exists()
        assert complete(client, **acceptance("age", "terms")).status_code == 200
        assert set(LegalAcceptance.objects.values_list("purpose", flat=True)) == {"age", "terms"}
        assert not User.objects.get().candidate_profile.submission_consent_at


@pytest.fixture
def signing_key():
    key = RSAKey.generate_key(2048)
    key.ensure_kid()
    return key


def signed_token(key, **overrides):
    claims = {
        "iss": google.ISSUER,
        "sub": "subject",
        "aud": settings.GOOGLE_OAUTH_CLIENT_ID,
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
        "nonce": "expected-nonce",
        "email": "fictional@gmail.com",
        "email_verified": True,
        **overrides,
    }
    return {"id_token": jwt.encode({"alg": "RS256", "kid": key.kid}, claims, key)}


def test_real_signature_and_claim_validation(signing_key):
    with patch("talent.google_oauth.jwks", return_value={"keys": [signing_key.as_dict()]}):
        identity = google.verify_token(signed_token(signing_key), "expected-nonce")
        assert identity["subject"] == "subject"


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://evil.example"},
        {"aud": "wrong-client"},
        {"exp": 1},
        {"nonce": "wrong"},
        {"nonce": None},
        {"email_verified": False},
        {"email_verified": "true"},
        {"azp": "wrong-client"},
        {"iat": 99999999999},
    ],
)
def test_invalid_signed_claims_rejected(signing_key, overrides):
    with patch("talent.google_oauth.jwks", return_value={"keys": [signing_key.as_dict()]}):
        with pytest.raises((JoseError, ValueError)):
            google.verify_token(signed_token(signing_key, **overrides), "expected-nonce")


def test_bad_signature_rejected(signing_key):
    other = RSAKey.generate_key(2048)
    other.ensure_kid()
    with patch("talent.google_oauth.jwks", return_value={"keys": [other.as_dict()]}):
        with pytest.raises((JoseError, ValueError)):
            google.verify_token(signed_token(signing_key), "expected-nonce")


def test_secure_cookie_configuration_and_no_token_in_callback_url(client, settings):
    settings.AUTH_COOKIE_SECURE = True
    state, _ = start(client)
    browser = client.cookies[google.cookie_name(google.BROWSER_COOKIE)]
    assert browser["secure"] and browser["httponly"] and browser["path"] == "/"
    assert browser["domain"] == ""
    response = callback(client, state)
    assert response["Cache-Control"] == "no-store"
    assert response["Referrer-Policy"] == "no-referrer"
    assert "synthetic-code" not in response.url
    assert "id_token" not in response.url
    assert complete(client).status_code == 200
    auth_cookie = client.cookies[settings.AUTH_COOKIE_NAME]
    assert auth_cookie["secure"] and auth_cookie["httponly"]


def test_reauth_proof_cannot_confirm_a_different_action(client):

    user = candidate(password=None)
    ExternalIdentity.objects.create(user=user, subject=IDENTITY["subject"])
    token = Token.objects.create(user=user)
    client.cookies[settings.AUTH_COOKIE_NAME] = token.key
    state, _ = start(client, "reauth/", {"action": "confirm_resume"})
    assert "result=reauthenticated" in callback(client, state).url
    assert (
        client.delete(
            "/api/v1/candidate/account/", {"confirmation": "DELETE"}, format="json"
        ).status_code
        == 400
    )
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.parametrize("auth_time", [None, 1, 99999999999])
def test_sensitive_reauthentication_requires_fresh_google_auth(signing_key, auth_time):
    with patch("talent.google_oauth.jwks", return_value={"keys": [signing_key.as_dict()]}):
        with pytest.raises(ValueError, match="Fresh Google"):
            google.verify_token(
                signed_token(signing_key, auth_time=auth_time),
                "expected-nonce",
                require_fresh_auth=True,
            )


@pytest.mark.parametrize(
    "next_path",
    [
        "/opportunities?role=backend-engineer",
        "/opportunities?role=backend-engineer&apply=1",
    ],
)
def test_google_transaction_preserves_only_valid_opportunity_intent(client, next_path):
    state, _ = start(client, body={"next": next_path})
    obj = GoogleOAuthTransaction.objects.get(state_hash=google.digest(state))
    assert obj.payload["next"] == next_path
    response = callback(client, state)
    query = parse_qs(urlsplit(response.url).query)
    assert query["next"] == [next_path]
    assert not User.objects.exists()
    assert not OpportunityApplication.objects.exists()


@pytest.mark.parametrize(
    "next_path",
    [
        "//evil.example/opportunities",
        "/opportunities?role=unknown",
        "/opportunities?candidate_id=7",
        "/opportunities?apply=1",
        "/opportunities?role=backend-engineer&role=ai-ml-engineer",
    ],
)
def test_oauth_return_rejects_external_private_or_invalid_targets(next_path):
    assert google.destination(next_path) == "/"


def test_missing_legal_configuration_cannot_create_or_record_candidate(client, settings):
    settings.LEGAL_CONTENT_APPROVED = False
    settings.LEGAL_WORKFLOW_PREVIEW = False
    pending_signup(client)
    pending = client.get(BASE + "pending/")
    assert pending.status_code == 200
    assert pending.data["signup_available"] is False
    response = client.post(
        BASE + "complete/",
        {
            "country_code": "IN",
            "age_accepted": True,
            "terms_accepted": True,
            "terms_version": "unapproved-draft",
            "age_version": "unapproved-draft",
        },
        format="json",
    )
    assert response.status_code == 503
    assert response.data["code"] == "signup_requirements_unavailable"
    assert not User.objects.exists()
    assert not ExternalIdentity.objects.exists()
    assert not LegalAcceptance.objects.exists()


def test_existing_google_candidate_can_login_when_new_signup_is_blocked(client, settings):
    settings.LEGAL_CONTENT_APPROVED = False
    settings.LEGAL_WORKFLOW_PREVIEW = False
    user = candidate()
    ExternalIdentity.objects.create(user=user, subject=IDENTITY["subject"])
    state, _ = start(client)
    assert "result=success" in callback(client, state).url
    assert User.objects.count() == 1
    assert not LegalAcceptance.objects.exists()


@pytest.mark.parametrize("failure", ["token_timeout", "token_denied", "missing_id_token"])
def test_provider_failures_are_consumed_without_accounts_or_secret_logging(client, caplog, failure):
    import httpx

    state, _ = start(client)
    failure_error = (
        httpx.ReadTimeout("synthetic provider response must not be logged")
        if failure == "token_timeout"
        else ValueError("synthetic rejected response")
    )
    if failure == "missing_id_token":
        with patch("talent.google_oauth.client") as oauth:
            oauth.return_value.__enter__.return_value.fetch_token.return_value = {}
            response = client.get(BASE + "callback/", {"state": state, "code": "synthetic-code"})
    else:
        with patch("talent.google_oauth.exchange", side_effect=failure_error):
            response = client.get(BASE + "callback/", {"state": state, "code": "synthetic-code"})
    assert "result=failed" in response.url
    assert "result=failed" in callback(client, state).url
    assert not User.objects.exists()
    assert "synthetic provider response" not in caplog.text
    assert "synthetic rejected response" not in caplog.text
    assert "synthetic-code" not in response.url


def test_rotated_google_key_is_refreshed_and_validated(signing_key):
    old_key = RSAKey.generate_key(2048)
    old_key.ensure_kid()
    with patch(
        "talent.google_oauth.jwks",
        side_effect=[
            {"keys": [old_key.as_dict()]},
            {"keys": [signing_key.as_dict()]},
        ],
    ) as keys:
        assert (
            google.verify_token(signed_token(signing_key), "expected-nonce")["subject"] == "subject"
        )
    assert keys.call_count == 2
    assert keys.call_args.args == (True,)


def test_google_key_endpoint_timeout_does_not_authenticate(client):
    import httpx

    state, _ = start(client)
    with (
        patch("talent.google_oauth.client") as oauth,
        patch("talent.google_oauth.jwks", side_effect=httpx.ReadTimeout("Synthetic key timeout")),
    ):
        oauth.return_value.__enter__.return_value.fetch_token.return_value = {"id_token": "invalid"}
        assert (
            "result=failed"
            in client.get(BASE + "callback/", {"state": state, "code": "synthetic-code"}).url
        )
    assert not User.objects.exists()


@pytest.mark.parametrize("change", ["password", "disabled"])
def test_link_confirmation_rechecks_account_after_google_callback(client, change):
    user = candidate()
    state, _ = start(client, "link/start/", {"email": user.email, "password": "strong-pass-123"})
    assert "result=confirm_link" in callback(client, state).url
    if change == "password":
        user.set_password("Changed-synthetic-password-123!")
    else:
        user.is_active = False
    user.save()
    response = client.post(BASE + "link/confirm/", {"confirm": True}, format="json")
    assert response.status_code == 400
    assert not ExternalIdentity.objects.exists()
    assert not Token.objects.exists()


def test_production_auth_response_does_not_expose_token_in_json(client):
    user = candidate()
    with override_settings(DEBUG=False, TESTING=False, AUTH_COOKIE_SECURE=True):
        response = google.authenticated(user)
        assert "token" not in response.data
        assert response.cookies[settings.AUTH_COOKIE_NAME]["httponly"]
        assert response.cookies[settings.AUTH_COOKIE_NAME]["secure"]
        assert response["Cache-Control"] == "no-store"


@pytest.mark.django_db(transaction=True)
def test_concurrent_link_attempts_keep_one_identity_and_existing_candidate():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import close_old_connections, connection

    if connection.vendor != "postgresql":
        pytest.skip("Concurrent row locking is verified on disposable PostgreSQL")
    user = candidate()
    before = CandidateProfile.objects.values().get(user=user)
    clients = [APIClient(), APIClient()]
    for index, client in enumerate(clients):
        state, _ = start(
            client, "link/start/", {"email": user.email, "password": "strong-pass-123"}
        )
        assert (
            "result=confirm_link"
            in callback(client, state, {**IDENTITY, "subject": f"synthetic-subject-{index}"}).url
        )
    barrier = Barrier(2)

    def confirm(client):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return client.post(BASE + "link/confirm/", {"confirm": True}, format="json").status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(confirm, clients))
    assert sorted(results) == [200, 400]
    assert User.objects.count() == ExternalIdentity.objects.count() == 1
    assert CandidateProfile.objects.values().get(user=user) == before
    assert not LegalAcceptance.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_confirmed_signups_never_duplicate_candidates():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import close_old_connections, connection
    from talent import legal

    if connection.vendor != "postgresql":
        pytest.skip("Concurrent uniqueness is verified on disposable PostgreSQL")
    clients = [APIClient(), APIClient()]
    for client in clients:
        pending_signup(client)
    barrier = Barrier(2)
    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        docs = legal.documents()
        body = {
            "country_code": "IN",
            "age_accepted": True,
            "terms_accepted": True,
            "age_version": docs["age"]["version"],
            "terms_version": docs["terms"]["version"],
        }

        def submit(client):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return client.post(BASE + "complete/", body, format="json").status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(submit, clients))
    assert sorted(results) == [200, 400]
    assert (
        User.objects.count()
        == CandidateProfile.objects.count()
        == ExternalIdentity.objects.count()
        == 1
    )
    assert LegalAcceptance.objects.count() == 2


def test_local_callback_diagnostics_never_log_provider_details(client, settings, caplog):
    settings.DEBUG = True
    settings.APP_ENV = "local"
    state, _ = start(client)
    with patch("talent.google_oauth.exchange", side_effect=ValueError("sensitive-provider-body")):
        response = client.get(
            BASE + "callback/", {"state": state, "code": "sensitive-provider-code"}
        )
    assert "result=failed" in response.url
    assert "phase=identity_verification exception_type=ValueError" in caplog.text
    assert "sensitive-provider-body" not in caplog.text
    assert "sensitive-provider-code" not in caplog.text
    assert state not in caplog.text


def test_local_browser_binding_diagnostic_keeps_state_and_cookie_private(client, settings, caplog):
    settings.DEBUG = True
    settings.APP_ENV = "local"
    state, _ = start(client)
    client.cookies[google.BROWSER_COOKIE] = "synthetic-different-browser-cookie-not-for-logs"
    response = client.get(BASE + "callback/", {"state": state, "code": "sensitive-provider-code"})
    assert "result=failed" in response.url
    assert "reason=browser_binding_mismatch" in caplog.text
    assert "synthetic-different-browser-cookie-not-for-logs" not in caplog.text
    assert state not in caplog.text


def test_callback_debug_diagnostics_are_disabled_outside_local(client, settings, caplog):
    settings.DEBUG = False
    settings.APP_ENV = "production"
    response = client.get(
        BASE + "callback/", {"state": "sensitive-state", "code": "sensitive-code"}
    )
    assert "result=failed" in response.url
    assert "Google transaction validation rejected" not in caplog.text
    assert "Google Login failed" not in caplog.text
