"""Synthetic approval fixtures only. No reviewer evidence or real users are invented."""

import hashlib
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from talent import google_oauth as google
from talent import google_signup as signup
from talent import legal
from talent.models import (
    ExternalIdentity,
    GoogleOAuthTransaction,
    GoogleSignupEvidence,
    LegalAcceptance,
)

from .test_google_oauth import BASE, IDENTITY, callback, candidate, start
from .test_legal_workflow import published_legal_settings

pytestmark = pytest.mark.django_db


@pytest.fixture
def approved(settings, tmp_path):
    for key, value in published_legal_settings(tmp_path).items():
        setattr(settings, key, value)
    settings.GOOGLE_OAUTH_ENABLED = True
    settings.GOOGLE_OAUTH_CLIENT_ID = "synthetic-client"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "synthetic-secret"
    settings.GOOGLE_OAUTH_REDIRECT_URI = "http://127.0.0.1:8010/api/v1/auth/google/callback/"
    settings.GOOGLE_SIGNUP_AUTOCREATE_ENABLED = True
    review = settings.BASE_DIR.parent / "review/google-single-button/review-manifest.json"
    approval = {
        "decision": "approved",
        "mechanism_id": signup.MECHANISM,
        "reviewer_name": "SYNTHETIC TEST ONLY",
        "reviewer_role": "TEST FIXTURE",
        "decision_reference": "NOT A REAL APPROVAL",
        "conditions": "none",
        "approved_at": (timezone.now() - timedelta(days=1)).isoformat(),
        "notice_sha256": signup.sha(signup.NOTICE),
        "review_package_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
        "documents": {
            p: {"version": d["version"], "sha256": d["sha256"]}
            for p, d in legal.documents().items()
        },
    }
    path = tmp_path / "synthetic-approval.json"
    path.write_text(json.dumps(approval))
    settings.GOOGLE_SIGNUP_APPROVAL_FILE = str(path)
    settings.GOOGLE_SIGNUP_APPROVAL_SHA256 = hashlib.sha256(path.read_bytes()).hexdigest()
    return approval


def offered(client):
    response = client.get(BASE + "config/")
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    return response.data["signup_notice"]


def begin_notice(client, **body):
    notice = offered(client)
    return start(
        client,
        body={"notice_challenge": notice["challenge"], "notice_version": notice["version"], **body},
    )[0]


def test_automatic_signup_records_actual_button_action_and_no_optional_consent(client, approved):
    before = timezone.now()
    state = begin_notice(client)
    after_button = timezone.now()
    assert User.objects.count() == 0
    response = callback(client, state)
    assert "result=success" in response.url
    user = User.objects.get(email=IDENTITY["email"])
    assert not user.has_usable_password()
    assert user.candidate_profile.email_verified_at
    assert user.candidate_profile.registration_country_code == "IN"
    evidence = GoogleSignupEvidence.objects.get()
    assert before <= evidence.received_at <= after_button < evidence.account_created_at
    assert evidence.notice_text == signup.NOTICE
    assert evidence.method == signup.METHOD
    assert evidence.age_self_declared and evidence.country_code == "IN"
    assert evidence.terms_acceptance.accepted_at == evidence.received_at
    assert evidence.age_acceptance.accepted_at == evidence.received_at
    assert evidence.privacy_sha256 == legal.documents()["privacy"]["sha256"]
    assert set(LegalAcceptance.objects.values_list("purpose", flat=True)) == {"age", "terms"}
    assert settings.AUTH_COOKIE_NAME in response.cookies
    # A subsequent login does not need a new signup declaration or change data.
    snapshot = {
        f.name: getattr(user.candidate_profile, f.name) for f in user.candidate_profile._meta.fields
    }
    state2, _ = start(client)
    assert "result=success" in callback(client, state2).url
    assert User.objects.count() == GoogleSignupEvidence.objects.count() == 1
    user.candidate_profile.refresh_from_db()
    assert {
        f.name: getattr(user.candidate_profile, f.name) for f in user.candidate_profile._meta.fields
    } == snapshot
    assert "result=failed" in callback(client, state).url


def test_existing_password_collision_never_accepts_or_changes_candidate(client, approved):
    user = candidate()
    original = user.password
    state = begin_notice(client)
    assert "result=link" in callback(client, state).url
    user.refresh_from_db()
    assert user.password == original
    assert User.objects.count() == 1
    assert not ExternalIdentity.objects.exists()
    assert not GoogleSignupEvidence.objects.exists()
    assert not LegalAcceptance.objects.exists()


@pytest.mark.parametrize(
    "change",
    [
        "missing_action",
        "missing_approval",
        "changed_approval",
        "changed_documents",
        "expired",
        "paused",
        "country",
    ],
)
def test_missing_or_changed_requirements_fail_closed(client, approved, settings, change):
    state = start(client)[0] if change == "missing_action" else begin_notice(client)
    if change == "missing_approval":
        settings.GOOGLE_SIGNUP_APPROVAL_FILE = "/nonexistent"
    elif change == "changed_approval":
        Path(settings.GOOGLE_SIGNUP_APPROVAL_FILE).write_text("{}")
    elif change == "changed_documents":
        settings.LEGAL_TERMS_SHA256 = "0" * 64
    elif change == "expired":
        obj = GoogleOAuthTransaction.objects.get(state_hash=google.digest(state))
        obj.payload["signup_action"]["received_at"] = (
            timezone.now() - timedelta(minutes=11)
        ).isoformat()
        obj.save()
    elif change == "paused":
        settings.CANDIDATE_REGISTRATION_PAUSED = True
    elif change == "country":
        settings.CANDIDATE_REGISTRATION_COUNTRIES = {"US"}
    assert "result=signup_unavailable" in callback(client, state).url
    assert not User.objects.exists()
    assert not GoogleSignupEvidence.objects.exists()


def test_notice_is_browser_bound_single_use_and_versioned(client, approved):
    notice = offered(client)
    data = {"notice_challenge": notice["challenge"], "notice_version": notice["version"]}
    assert APIClient().post(BASE + "start/", data, format="json").status_code == 400
    assert client.post(BASE + "start/", data, format="json").status_code == 200
    # A different browser cannot consume the legitimate browser's challenge.
    notice = offered(client)
    data = {"notice_challenge": notice["challenge"], "notice_version": notice["version"]}
    assert client.post(BASE + "start/", data, format="json").status_code == 200
    assert client.post(BASE + "start/", data, format="json").status_code == 400
    notice = offered(client)
    assert (
        client.post(
            BASE + "start/",
            {**data, "notice_challenge": notice["challenge"], "notice_version": "stale"},
            format="json",
        ).status_code
        == 400
    )
    assert not User.objects.exists()


def test_cancelled_authentication_never_records_signup(client, approved):
    state = begin_notice(client)
    response = client.get(BASE + "callback/", {"state": state, "error": "access_denied"})
    assert "result=cancelled" in response.url
    assert not User.objects.exists()
    assert not LegalAcceptance.objects.exists()


def test_public_documents_are_exact_versioned_approved_text_only(client, approved):
    notice = offered(client)
    for purpose in ["terms", "privacy"]:
        response = client.get(notice[purpose + "_url"])
        assert response.status_code == 200
        assert response.content.decode() == legal.documents()[purpose]["text"]
        assert response["X-Content-Type-Options"] == "nosniff"
    assert client.get(BASE + "documents/terms/?version=wrong").status_code == 404
    assert client.get(BASE + "documents/age/").status_code == 404
    assert client.post(BASE + "complete/", {}, format="json").status_code == 410


def test_non_authoritative_google_email_still_requires_enter_verification(client, approved):
    state = begin_notice(client)
    with patch("talent.google_views.send_verification_email") as send:
        response = callback(client, state, {**IDENTITY, "authoritative": False})
    assert "result=verification_required" in response.url
    assert not User.objects.get().is_active
    assert User.objects.get().candidate_profile.email_verified_at is None
    assert settings.AUTH_COOKIE_NAME not in response.cookies
    send.assert_called_once()


def test_invalid_audit_gate_does_not_advertise_draft_or_block_linked_login(
    client, approved, settings
):
    settings.GOOGLE_SIGNUP_APPROVAL_SHA256 = ""
    assert "signup_notice" not in client.get(BASE + "config/").data
    user = candidate(password=None)
    ExternalIdentity.objects.create(user=user, subject=IDENTITY["subject"])
    assert "result=success" in callback(client, start(client)[0]).url


@pytest.mark.django_db(transaction=True)
def test_concurrent_automatic_signups_keep_one_candidate_and_one_evidence(approved):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import close_old_connections, connection

    if connection.vendor != "postgresql":
        pytest.skip("Concurrent uniqueness requires disposable PostgreSQL")
    clients = [APIClient(), APIClient()]
    states = [begin_notice(c) for c in clients]
    barrier = Barrier(2)

    def exchange(*args, **kwargs):
        barrier.wait(timeout=10)
        return IDENTITY

    def finish(item):
        client, state = item
        close_old_connections()
        try:
            return client.get(BASE + "callback/", {"state": state, "code": "synthetic-code"}).url
        finally:
            close_old_connections()

    with patch("talent.google_oauth.exchange", side_effect=exchange):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(finish, zip(clients, states, strict=True)))
    assert any("result=success" in r for r in results)
    assert (
        User.objects.count()
        == ExternalIdentity.objects.count()
        == GoogleSignupEvidence.objects.count()
        == 1
    )
    assert LegalAcceptance.objects.count() == 2


@pytest.mark.parametrize(
    "environment,allowed",
    [("local", True), ("test", True), ("staging", True), ("production", False)],
)
def test_policy_approval_scope_cannot_enable_production(approved, settings, environment, allowed):
    path = Path(settings.GOOGLE_SIGNUP_APPROVAL_FILE)
    approved["release_scope"] = "local_testing_and_staging_validation"
    path.write_text(json.dumps(approved))
    settings.GOOGLE_SIGNUP_APPROVAL_SHA256 = hashlib.sha256(path.read_bytes()).hexdigest()
    settings.APP_ENV = environment
    if allowed:
        assert signup.release()
    else:
        with pytest.raises(signup.SignupUnavailable):
            signup.release()


def test_policy_effective_date_must_match_configured_release(approved, settings):
    path = Path(settings.GOOGLE_SIGNUP_APPROVAL_FILE)
    approved["effective_date"] = "2026-11-10"
    path.write_text(json.dumps(approved))
    settings.GOOGLE_SIGNUP_APPROVAL_SHA256 = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(signup.SignupUnavailable):
        signup.release()
