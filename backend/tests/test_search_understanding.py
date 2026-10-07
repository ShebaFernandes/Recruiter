import json
import urllib.error

import pytest
from django.test import override_settings
from talent.search_understanding import understand_search


class FakeOpenAIResponse:
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


def test_openai_interpreter_uses_structured_output_and_dynamic_role(monkeypatch):
    captured = {}
    model_output = {
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

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return FakeOpenAIResponse(
            {
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": json.dumps(model_output)}
                        ]
                    }
                ]
            }
        )

    monkeypatch.setattr("talent.search_understanding.urllib.request.urlopen", fake_urlopen)
    with override_settings(
        SEARCH_UNDERSTANDING_BACKEND="openai",
        OPENAI_API_KEY="test-key",
        OPENAI_SEARCH_MODEL="gpt-4o-mini",
        SEARCH_AI_ALLOW_FALLBACK=False,
        SEARCH_AI_TIMEOUT_SECONDS=7,
    ):
        result = understand_search("AI Full-Stack Developer with 3 years of exp remote")

    assert result.source == "openai"
    assert result.model == "gpt-4o-mini"
    assert result.criteria["role"] == "AI Full-Stack Developer"
    assert result.follow_up_question == ""
    assert captured["body"]["text"]["format"]["type"] == "json_schema"
    assert captured["body"]["text"]["format"]["strict"] is True
    assert "AI Full-Stack Developer" in captured["body"]["input"]
    assert captured["timeout"] == 7


@pytest.mark.django_db
def test_ai_unavailable_returns_recoverable_service_error(
    client, recruiter_account, monkeypatch
):
    def unavailable(*args, **kwargs):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr("talent.search_understanding.urllib.request.urlopen", unavailable)
    with override_settings(
        SEARCH_UNDERSTANDING_BACKEND="openai",
        OPENAI_API_KEY="test-key",
        SEARCH_AI_ALLOW_FALLBACK=False,
    ):
        response = client.post(
            "/api/v1/searches/", {"query": "Founding engineer remote"}, format="json"
        )

    assert response.status_code == 503
    assert response.data["code"] == "search_understanding_unavailable"
    assert "try again" in response.data["detail"].lower()
