import json
import socket
import urllib.error

import pytest
from django.test import override_settings
from talent.ai_providers import (
    AnthropicMessagesProvider,
    OpenAIResponsesProvider,
    get_ai_provider,
)
from talent.models import Search
from talent.search_understanding import (
    INTERPRETATION_SCHEMA,
    SearchUnderstandingUnavailable,
    understand_search,
)

VALID_INTERPRETATION = {
    "criteria": {
        "role": "AI Full-Stack Developer",
        "skills": [],
        "min_experience": 3,
        "max_experience": None,
        "location": "",
        "remote_ok": True,
        "notice_period_days": None,
        "max_salary_lpa": None,
        "employment_type": "",
        "work_preferences": ["Remote"],
    },
    "follow_up_question": "",
    "follow_up_options": [],
}


class FakeProviderResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


@pytest.mark.django_db
def test_open_ended_ai_full_stack_query_is_not_given_a_role_clarification(
    client, recruiter_account
):
    response = client.post(
        "/api/v1/searches/",
        {"query": "AI Full-Stack Developer with 3 years of exp remote"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["state"] == "complete"
    assert response.data["criteria"]["role"] == "AI Full-Stack Developer"
    assert response.data["criteria"]["min_experience"] == 3.0
    assert response.data["criteria"]["remote_ok"] is True
    assert response.data["follow_up_question"] == ""
    assert response.data["follow_up_options"] == []


@pytest.mark.django_db
def test_missing_role_does_not_offer_a_hardcoded_job_title_list(client, recruiter_account):
    response = client.post(
        "/api/v1/searches/", {"query": "5 years experience"}, format="json"
    )

    assert response.status_code == 201
    assert response.data["state"] == "needs_clarification"
    assert response.data["follow_up_options"] == ["Let me type it"]


def test_provider_selection_is_explicit():
    with override_settings(
        ANTHROPIC_API_KEY="test-anthropic-key",
        OPENAI_API_KEY="test-openai-key",
    ):
        assert isinstance(get_ai_provider("openai"), OpenAIResponsesProvider)
        assert isinstance(get_ai_provider("anthropic"), AnthropicMessagesProvider)


def test_openai_responses_adapter_uses_strict_structured_output(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return FakeProviderResponse(
            {
                "id": "resp_test_openai",
                "model": "gpt-4o-mini",
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(VALID_INTERPRETATION),
                            }
                        ]
                    }
                ],
            }
        )

    monkeypatch.setattr("talent.ai_providers.urllib.request.urlopen", fake_urlopen)
    with override_settings(
        AI_PROVIDER="openai",
        OPENAI_API_KEY="test-openai-key",
        OPENAI_SEARCH_MODEL="gpt-4o-mini",
        AI_ALLOW_DETERMINISTIC_FALLBACK=False,
        AI_REQUEST_TIMEOUT_SECONDS=7,
    ):
        result = understand_search("AI Full-Stack Developer with 3 years of exp remote")

    assert result.source == "openai"
    assert result.model == "gpt-4o-mini"
    assert result.request_id == "resp_test_openai"
    assert result.criteria["role"] == "AI Full-Stack Developer"
    assert captured["url"].endswith("/responses")
    assert captured["body"]["text"]["format"]["type"] == "json_schema"
    assert captured["body"]["text"]["format"]["strict"] is True
    assert captured["timeout"] == 7


def test_anthropic_adapter_uses_messages_structured_output_and_safe_headers(
    monkeypatch, caplog
):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return FakeProviderResponse(
            {
                "id": "msg_test_anthropic",
                "model": "claude-sonnet-5-5",
                "content": [
                    {"type": "text", "text": json.dumps(VALID_INTERPRETATION)}
                ],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 123, "output_tokens": 45},
            }
        )

    monkeypatch.setattr("talent.ai_providers.urllib.request.urlopen", fake_urlopen)
    with override_settings(
        AI_PROVIDER="anthropic",
        ANTHROPIC_API_KEY="test-anthropic-key",
        ANTHROPIC_SEARCH_MODEL="claude-sonnet-5-5",
        ANTHROPIC_API_VERSION="2023-06-01",
        ANTHROPIC_SEARCH_MAX_OUTPUT_TOKENS=2048,
        AI_ALLOW_DETERMINISTIC_FALLBACK=False,
        AI_REQUEST_TIMEOUT_SECONDS=9,
    ):
        result = understand_search("AI Full-Stack Developer with 3 years of exp remote")

    assert result.source == "anthropic"
    assert result.model == "claude-sonnet-5-5"
    assert result.request_id == "msg_test_anthropic"
    assert result.criteria["role"] == "AI Full-Stack Developer"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    output_format = captured["body"]["output_config"]["format"]
    assert output_format["type"] == "json_schema"
    assert output_format["schema"] == INTERPRETATION_SCHEMA
    assert captured["body"]["system"]
    assert captured["body"]["max_tokens"] == 2048
    assert captured["headers"]["Authorization"] == "Bearer test-anthropic-key"
    assert captured["headers"]["Anthropic-version"] == "2023-06-01"
    assert captured["timeout"] == 9
    assert "ai_search_provider_success provider=anthropic" in caplog.text
    assert "test-anthropic-key" not in caplog.text
    assert "AI Full-Stack Developer with 3 years of exp remote" not in caplog.text


@pytest.mark.django_db
def test_anthropic_result_flows_through_api_and_is_persisted(
    client, recruiter_account, monkeypatch
):
    def fake_urlopen(request, timeout):
        return FakeProviderResponse(
            {
                "id": "msg_persisted",
                "model": "claude-sonnet-5-5",
                "content": [
                    {"type": "text", "text": json.dumps(VALID_INTERPRETATION)}
                ],
                "stop_reason": "end_turn",
            }
        )

    monkeypatch.setattr("talent.ai_providers.urllib.request.urlopen", fake_urlopen)
    with override_settings(
        AI_PROVIDER="anthropic",
        ANTHROPIC_API_KEY="test-key",
        AI_ALLOW_DETERMINISTIC_FALLBACK=False,
    ):
        response = client.post(
            "/api/v1/searches/",
            {"query": "AI Full-Stack Developer with 3 years of exp remote"},
            format="json",
        )

    assert response.status_code == 201
    assert response.data["understanding_source"] == "anthropic"
    assert response.data["understanding_model"] == "claude-sonnet-5-5"
    search = Search.objects.get(pk=response.data["id"])
    assert search.understanding_source == "anthropic"
    assert search.criteria["role"] == "AI Full-Stack Developer"


def test_malformed_provider_response_is_rejected_before_search(monkeypatch):
    malformed = {**VALID_INTERPRETATION, "criteria": {"role": "Backend Engineer"}}

    def fake_urlopen(request, timeout):
        return FakeProviderResponse(
            {
                "id": "msg_malformed",
                "content": [{"type": "text", "text": json.dumps(malformed)}],
                "stop_reason": "end_turn",
            }
        )

    monkeypatch.setattr("talent.ai_providers.urllib.request.urlopen", fake_urlopen)
    with override_settings(
        AI_PROVIDER="anthropic",
        ANTHROPIC_API_KEY="test-key",
        AI_ALLOW_DETERMINISTIC_FALLBACK=False,
    ):
        with pytest.raises(SearchUnderstandingUnavailable) as exc_info:
            understand_search("Backend engineer remote")

    assert exc_info.value.code == "ai_provider_malformed_response"
    assert exc_info.value.status_code == 502


@pytest.mark.django_db
def test_anthropic_rate_limit_returns_429_and_retry_after(
    client, recruiter_account, monkeypatch
):
    def rate_limited(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://api.anthropic.com/v1/messages",
            429,
            "Too Many Requests",
            {"Retry-After": "17"},
            None,
        )

    monkeypatch.setattr("talent.ai_providers.urllib.request.urlopen", rate_limited)
    with override_settings(
        AI_PROVIDER="anthropic",
        ANTHROPIC_API_KEY="test-key",
        AI_ALLOW_DETERMINISTIC_FALLBACK=False,
    ):
        response = client.post(
            "/api/v1/searches/", {"query": "Founding engineer remote"}, format="json"
        )

    assert response.status_code == 429
    assert response.data["code"] == "ai_provider_rate_limited"
    assert response.headers["Retry-After"] == "17"


@pytest.mark.parametrize(
    ("raised", "expected_code"),
    [
        (socket.timeout("slow"), "ai_provider_timeout"),
        (urllib.error.URLError("offline"), "ai_provider_unavailable"),
    ],
)
def test_provider_timeout_and_unavailable_are_distinguished(
    monkeypatch, raised, expected_code
):
    def unavailable(*args, **kwargs):
        raise raised

    monkeypatch.setattr("talent.ai_providers.urllib.request.urlopen", unavailable)
    with override_settings(
        AI_PROVIDER="anthropic",
        ANTHROPIC_API_KEY="test-key",
        AI_ALLOW_DETERMINISTIC_FALLBACK=False,
    ):
        with pytest.raises(SearchUnderstandingUnavailable) as exc_info:
            understand_search("Founding engineer remote")

    assert exc_info.value.code == expected_code
    assert exc_info.value.status_code == 503


def test_development_fallback_is_explicitly_identified(caplog):
    with override_settings(
        AI_PROVIDER="anthropic",
        ANTHROPIC_API_KEY="",
        AI_ALLOW_DETERMINISTIC_FALLBACK=True,
    ):
        result = understand_search("Backend engineer remote")

    assert result.source == "deterministic_fallback"
    assert result.model == ""
    assert "ai_search_provider_fallback provider=anthropic error=unavailable" in caplog.text
