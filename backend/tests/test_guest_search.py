import time
import uuid
from unittest.mock import Mock, patch

import pytest
from django.core import signing
from rest_framework.test import APIClient
from talent.ai_providers import AIProviderResult, AIProviderTimeout
from talent.guest_search import COOKIE, SALT, TTL
from talent.models import Search
from talent.search_grounding import CRITERIA_DEFAULTS

pytestmark = pytest.mark.django_db
URL = "/api/v1/guest/searches/"


@pytest.fixture(autouse=True)
def guest_settings(settings):
    settings.GUEST_SEARCH_ENABLED = True
    settings.GUEST_SEARCH_RATES = {
        key: "1000/day" for key in settings.GUEST_SEARCH_RATES
    }
    settings.AI_PROVIDER = "openrouter"
    settings.AI_ALLOW_DETERMINISTIC_FALLBACK = False


def provider_response(**criteria):
    return AIProviderResult({
        "criteria": {**CRITERIA_DEFAULTS, "role": "Backend Engineer", "min_experience": 4,
                     **criteria},
        "follow_up_question": "", "follow_up_options": [],
    }, "openrouter", "test-model")


@pytest.fixture
def provider(monkeypatch):
    mock = Mock()
    mock.generate.return_value = provider_response()
    monkeypatch.setattr("talent.search_understanding.get_ai_provider", lambda _: mock)
    return mock


def start(client, query="Backend engineer with 4 years experience", **extra):
    return client.post(URL, {"query": query, "request_id": str(uuid.uuid4()), **extra},
                       format="json")


def answer(client, token, text="Remote only"):
    return client.post(f"{URL}answer/", {"token": token, "answer": text}, format="json")


def test_guest_uses_validated_grounded_ai_without_creating_recruiter_records(client, provider):
    provider.generate.return_value = provider_response(
        max_salary_lpa=0, notice_period_days=0, employment_type="Full-time",
    )
    response = start(client)
    assert response.status_code == 200
    assert response.data["understanding_source"] == "openrouter"
    assert response.data["state"] == "needs_clarification"
    assert response.data["query"] == "Backend engineer with 4 years experience"
    assert response.data["criteria"]["max_salary_lpa"] is None
    assert response.data["criteria"]["notice_period_days"] is None
    assert response.data["criteria"]["employment_type"] == ""
    assert response["Cache-Control"] == "private, no-store"
    assert response.cookies[COOKIE]["httponly"]
    assert response.cookies[COOKIE]["samesite"] == "Lax"
    assert not Search.objects.exists()
    assert not {"candidates", "results", "count", "email", "resume"} & response.data.keys()

    provider.generate.return_value = provider_response(remote_ok=True, work_preferences=["Remote"])
    completed = answer(client, response.data["token"])
    assert completed.status_code == 200
    assert completed.data["state"] == "complete"
    assert completed.data["criteria"]["min_experience"] == 4
    assert completed.data["criteria"]["work_preferences"] == ["Remote"]
    assert provider.generate.call_count == 2
    assert not Search.objects.exists()
    assert answer(client, completed.data["token"]).status_code == 409


def test_token_is_browser_bound_and_tamper_proof(client, provider):
    token = start(client).data["token"]
    assert answer(APIClient(), token).status_code == 410
    assert answer(client, token + "tampered").status_code == 410
    assert provider.generate.call_count == 1
    with patch("django.core.signing.time.time", return_value=time.time() + TTL + 1):
        assert answer(client, token).status_code == 410
    assert provider.generate.call_count == 1


def test_replayed_requests_and_excess_turns_do_not_call_ai(client, provider):
    request_id = str(uuid.uuid4())
    token = start(client, request_id=request_id).data["token"]
    assert start(client, request_id=request_id).status_code == 409
    assert answer(client, token).status_code == 200
    assert answer(client, token).status_code == 409
    assert provider.generate.call_count == 2
    state = signing.loads(token, salt=SALT)
    state["history"] = [{"question": "Location?", "answer": "Anywhere"}] * 5
    exhausted = signing.dumps(state, salt=SALT)
    assert answer(client, exhausted).status_code == 409
    assert provider.generate.call_count == 2


@pytest.mark.parametrize("scope", [
    "guest_ip_burst", "guest_ip_daily", "guest_browser_daily",
    "guest_global_burst", "guest_global_daily",
])
def test_every_quota_is_backend_enforced(client, provider, settings, scope):
    settings.GUEST_SEARCH_RATES = {**settings.GUEST_SEARCH_RATES, scope: "1/day"}
    assert start(client).status_code == 200
    response = start(client, query="Backend engineer remote")
    assert response.status_code == 429
    assert int(response["Retry-After"]) > 0
    assert provider.generate.call_count == 1


def test_global_limit_survives_different_browser_and_ip(client, provider, settings):
    settings.GUEST_SEARCH_RATES["guest_global_daily"] = "1/day"
    assert start(client).status_code == 200
    other = APIClient(REMOTE_ADDR="198.51.100.23")
    assert start(other).status_code == 429
    assert provider.generate.call_count == 1


def test_cookie_rotation_and_spoofed_forwarded_headers_do_not_bypass_ip_limit(
    client, provider, settings,
):
    settings.RATE_LIMIT_TRUST_X_FORWARDED_FOR = False
    settings.GUEST_SEARCH_RATES["guest_ip_daily"] = "1/day"
    assert start(client).status_code == 200
    other = APIClient(HTTP_X_FORWARDED_FOR="198.51.100.24")
    assert start(other).status_code == 429
    assert provider.generate.call_count == 1


def test_failure_is_not_retried_and_consumes_budget(client, provider, settings):
    settings.GUEST_SEARCH_RATES["guest_global_daily"] = "1/day"
    provider.generate.side_effect = AIProviderTimeout()
    response = start(client)
    assert response.status_code == 503
    assert "timeout" in response.data["code"]
    assert provider.generate.call_count == 1
    assert start(client).status_code == 429
    assert provider.generate.call_count == 1


def test_manual_retry_after_provider_failure_is_allowed(client, provider):
    request_id = str(uuid.uuid4())
    provider.generate.side_effect = AIProviderTimeout()
    assert start(client, request_id=request_id).status_code == 503
    provider.generate.side_effect = None
    assert start(client, request_id=request_id).status_code == 200
    assert provider.generate.call_count == 2


def test_malformed_provider_output_rejected(client, provider):
    provider.generate.return_value = AIProviderResult({"criteria": {}}, "openrouter", "test")
    assert start(client).status_code == 502
    assert not Search.objects.exists()


def test_disabled_endpoint_and_invalid_input_never_call_ai(client, provider, settings):
    settings.GUEST_SEARCH_ENABLED = False
    assert start(client).status_code == 503
    settings.GUEST_SEARCH_ENABLED = True
    for query in ["", "   ", "x" * 2001]:
        assert start(client, query=query).status_code == 400
    assert provider.generate.call_count == 0


def test_csrf_required_even_without_login(provider):
    browser = APIClient(enforce_csrf_checks=True)
    assert start(browser).status_code == 403
    csrf = browser.get("/api/v1/auth/csrf/").data["csrfToken"]
    browser.credentials(HTTP_X_CSRFTOKEN=csrf, HTTP_ORIGIN="https://untrusted.example")
    assert start(browser).status_code == 403
    browser.credentials(HTTP_X_CSRFTOKEN=csrf, HTTP_ORIGIN="http://127.0.0.1:5173")
    assert start(browser).status_code == 200
    assert provider.generate.call_count == 1


def test_guest_token_never_grants_candidate_or_workspace_access(client, provider):
    token = start(client).data["token"]
    client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
    for path in [
        "searches/", "searches/1/results/", "candidates/1/", "resumes/1/download/",
        "projects/", "projects/1/", "notifications/", "candidate/profile/",
    ]:
        assert client.get(f"/api/v1/{path}").status_code == 401, path
    for method, path, body in [
        ("post", "searches/", {"query": "Backend engineer"}),
        ("post", "projects/", {"name": "Unowned"}),
        ("put", "candidates/1/status/", {"status": "shortlisted"}),
        ("post", "candidates/compare/", {"candidate_ids": [1]}),
    ]:
        assert getattr(client, method)(f"/api/v1/{path}", body, format="json").status_code == 401
    assert provider.generate.call_count == 1


def test_guest_does_not_present_deterministic_output_as_ai(client, settings):
    settings.AI_PROVIDER = "deterministic"
    response = start(client)
    assert response.status_code == 503
    assert response.data["code"] == "guest_ai_unavailable"
