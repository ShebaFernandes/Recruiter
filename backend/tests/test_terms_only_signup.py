"""User-directed local revision: no fabricated age, country or privacy consent."""

import hashlib
import json
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from talent import google_signup as signup
from talent import legal
from talent.models import ExternalIdentity, GoogleSignupEvidence, LegalAcceptance

from .test_google_oauth import BASE, callback, start
from .test_legal_workflow import published_legal_settings

pytestmark = pytest.mark.django_db


@pytest.fixture
def terms_only(settings, tmp_path):
    for key, value in published_legal_settings(tmp_path).items():
        setattr(settings, key, value)
    settings.APP_ENV = "test"
    settings.DEBUG = True
    settings.CANDIDATE_SIMPLE_SIGNUP_ENABLED = True
    settings.CANDIDATE_REGISTRATION_COUNTRIES = set()
    settings.GOOGLE_SIGNUP_AUTOCREATE_ENABLED = True
    settings.GOOGLE_OAUTH_ENABLED = True
    settings.GOOGLE_OAUTH_CLIENT_ID = "synthetic-client"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "synthetic-secret"
    settings.GOOGLE_OAUTH_REDIRECT_URI = "http://127.0.0.1:8010/api/v1/auth/google/callback/"
    record = {
        "record_type": "direct_user_local_terms_only_authorization",
        "decision": "approved",
        "release_scope": "isolated_local_testing_only",
        "mechanism_id": signup.SHORT_MECHANISM,
        "notice_sha256": signup.sha(signup.SHORT_NOTICE),
        "authorization_recorded_at": (timezone.now() - timedelta(seconds=1)).isoformat(),
        "written_authorization": "SYNTHETIC TEST ONLY; NOT REAL POLICY APPROVAL",
        "documents": {
            p: {"version": d["version"], "sha256": d["sha256"]}
            for p, d in legal.documents().items()
            if p != "age"
        },
    }
    path = tmp_path / "synthetic-local-authorization.json"
    path.write_text(json.dumps(record))
    settings.GOOGLE_SIGNUP_APPROVAL_FILE = str(path)
    settings.GOOGLE_SIGNUP_APPROVAL_SHA256 = hashlib.sha256(path.read_bytes()).hexdigest()


def notice(client):
    result = client.get(BASE + "config/").data
    assert result["simple_signup"]
    assert result["signup_notice"]["text"] == signup.SHORT_NOTICE
    return result["signup_notice"]


def assert_truthful(user):
    evidence = GoogleSignupEvidence.objects.get(subject_user=user)
    assert evidence.age_acceptance is None
    assert evidence.age_self_declared is False
    assert evidence.country_code == user.candidate_profile.registration_country_code == ""
    assert set(LegalAcceptance.objects.filter(user=user).values_list("purpose", flat=True)) == set()
    assert evidence.notice_text == ""
    assert evidence.notice_sha256 == ""
    assert evidence.terms_acceptance is None
    assert user.candidate_profile.visibility == ""
    assert user.candidate_profile.submission_consent_at is None
    legal.require_terms(user)  # No later upload/submission request invents an age confirmation.
    return evidence


def test_google_signup_and_repeat_login_do_not_record_age_or_country(client, terms_only):
    n = notice(client)
    state = start(
        client,
        body={
            "notice_challenge": n["challenge"],
            "notice_version": n["version"],
            "age_accepted": True,
            "country_code": "IN",
        },
    )[0]
    assert "result=success" in callback(client, state).url
    user = User.objects.get()
    evidence = assert_truthful(user)
    assert not user.has_usable_password()
    assert evidence.method == "signup_button_google_no_notice_v2"
    assert "result=success" in callback(client, start(client)[0]).url
    assert (
        User.objects.count()
        == ExternalIdentity.objects.count()
        == GoogleSignupEvidence.objects.count()
        == 1
    )


def test_email_signup_records_the_actual_create_account_action_without_checkboxes(
    client, terms_only
):
    n = notice(client)
    response = client.post(
        "/api/v1/auth/signup/",
        {
            "email": "terms-only-synthetic@example.test",
            "full_name": "Synthetic Candidate",
            "role": "candidate",
            "password": "Synthetic-terms-only-123!",
            "notice_challenge": n["challenge"],
            "notice_version": n["version"],
            "age_accepted": True,
            "country_code": "IN",
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    user = User.objects.get()
    evidence = assert_truthful(user)
    assert evidence.method == "signup_button_email_no_notice_v2"
    assert not user.is_active  # Existing ENTER email-verification policy remains enforced.
    assert user.check_password("Synthetic-terms-only-123!")
    assert not ExternalIdentity.objects.exists()


def test_missing_or_stale_signup_challenge_cannot_create_account(client, terms_only):
    data = {
        "email": "missing@example.test",
        "full_name": "Synthetic",
        "role": "candidate",
        "password": "Synthetic-terms-only-123!",
    }
    assert client.post("/api/v1/auth/signup/", data, format="json").status_code == 503
    n = notice(client)
    data.update(notice_challenge=n["challenge"], notice_version="old-age-country-version")
    assert client.post("/api/v1/auth/signup/", data, format="json").status_code == 400
    assert not User.objects.exists()


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_local_user_instruction_cannot_authorize_a_public_release(
    terms_only, settings, environment
):
    settings.APP_ENV = environment
    with pytest.raises(signup.SignupUnavailable):
        signup.release()


def test_country_restriction_cannot_be_silently_bypassed(terms_only, settings):
    settings.CANDIDATE_REGISTRATION_COUNTRIES = {"IN"}
    with pytest.raises(signup.SignupUnavailable):
        signup.release()


@pytest.mark.django_db(transaction=True)
def test_concurrent_terms_only_signup_keeps_one_account_and_truthful_evidence(terms_only):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from unittest.mock import patch

    from django.db import close_old_connections, connection
    from rest_framework.test import APIClient

    from .test_google_oauth import IDENTITY

    if connection.vendor != "postgresql":
        pytest.skip("Concurrent uniqueness requires PostgreSQL")
    clients = [APIClient(), APIClient()]
    states = []
    for client in clients:
        n = notice(client)
        states.append(
            start(
                client, body={"notice_challenge": n["challenge"], "notice_version": n["version"]}
            )[0]
        )
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
    assert LegalAcceptance.objects.count() == 0
    assert_truthful(User.objects.get())
