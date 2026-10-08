from copy import deepcopy

import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.test import override_settings
from django.utils import timezone
from talent.ai_providers import AIProviderResult
from talent.models import CandidateProfile, RecruiterProfile, Search
from talent.search_grounding import CRITERIA_DEFAULTS, ground_criteria
from talent.search_understanding import (
    SearchUnderstandingUnavailable,
    continue_search,
    understand_search,
)


def proposed(**overrides):
    return {**deepcopy(CRITERIA_DEFAULTS), "role": "Backend Engineer", **overrides}


@pytest.fixture
def provider(monkeypatch):
    calls = []
    response = {
        "criteria": proposed(),
        "follow_up_question": "",
        "follow_up_options": [],
    }

    def generate(self, instructions, input_payload, schema, schema_name):
        calls.append(input_payload)
        return AIProviderResult(deepcopy(response), "openrouter", "test-free-model")

    monkeypatch.setattr("talent.ai_providers.OpenRouterChatProvider.generate", generate)
    with override_settings(
        AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY="test-key",
        AI_ALLOW_DETERMINISTIC_FALLBACK=False,
    ):
        yield response, calls


def test_exact_live_hallucination_is_neutralized(provider):
    response, _ = provider
    response["criteria"] = proposed(
        min_experience=3,
        max_experience=3,
        location="remote",
        remote_ok=True,
        max_salary_lpa=0,
        notice_period_days=0,
        employment_type="Full-time",
    )
    result = understand_search("Backend engineer with 3 years of experience, remote")
    assert result.source == "openrouter"
    assert result.follow_up_question == ""
    for key in ("max_experience", "max_salary_lpa", "notice_period_days"):
        assert result.criteria[key] is None
    assert result.criteria["min_experience"] == 3
    assert result.criteria["employment_type"] == ""
    assert result.criteria["location"] == ""


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "Backend engineer, remote only, immediate joiner, at least three years",
            {
                "notice_period_days": 0,
                "min_experience": 3,
                "max_experience": None,
                "work_preferences": ["Remote"],
            },
        ),
        (
            "Backend engineer remote, can start right away, up to five years",
            {"notice_period_days": 0, "min_experience": None, "max_experience": 5},
        ),
        (
            "Backend engineer remote with zero years, maximum salary zero LPA, 0 days notice",
            {"min_experience": 0, "max_salary_lpa": 0, "notice_period_days": 0},
        ),
        (
            "Backend engineer remote with 3–7 years, available within two weeks, "
            "budget twenty five LPA",
            {
                "min_experience": 3,
                "max_experience": 7,
                "notice_period_days": 14,
                "max_salary_lpa": 25,
            },
        ),
        (
            "Backend engineer remote, no salary cap, no notice restriction, any employment type",
            {"max_salary_lpa": None, "notice_period_days": None, "employment_type": ""},
        ),
        (
            "Backend engineer remote, not an immediate joiner, full-time is not required",
            {"notice_period_days": None, "employment_type": ""},
        ),
        ("Backend engineer, remote is also okay", {"remote_ok": True, "work_preferences": []}),
    ],
)
def test_explicit_natural_language_values_are_not_missing(query, expected):
    result, question = ground_criteria(proposed(work_preferences=["Remote"]), query)
    assert question == ""
    for field, value in expected.items():
        assert result[field] == value


def test_missing_location_cannot_be_filled_by_ai_guess(provider):
    response, _ = provider
    response["criteria"] = proposed(location="Mumbai", remote_ok=True)
    result = understand_search("Backend engineer with at least 3 years")
    assert result.criteria["location"] == ""
    assert result.criteria["remote_ok"] is False
    assert "location" in result.follow_up_question
    assert result.criteria["notice_period_days"] is None
    assert result.criteria["max_salary_lpa"] is None


def test_invented_skills_and_mislabelled_location_do_not_become_filters():
    result, question = ground_criteria(
        proposed(location="Backend", skills=["Java", "Python", "JavaScript"]),
        "Backend engineer with JavaScript; Python is not required",
    )
    assert result["skills"] == ["JavaScript"]
    assert result["location"] == ""
    assert "location" in question


def test_open_ended_titles_locations_and_aliases_are_supported():
    result, question = ground_criteria(
        proposed(role="AI Full-Stack Developer", location="Zurich", skills=["PostgreSQL"]),
        "AI full stack developer based in Zurich with Postgres",
    )
    assert result["location"] == "Zurich"
    assert result["skills"] == ["PostgreSQL"]
    assert result["role"]
    assert not question


def test_confirmed_requirements_survive_multiple_turns_and_ai_omissions(provider):
    response, calls = provider
    query = "At least 3 years, maximum salary 30 LPA, immediate joiner"
    history = [
        {
            "question": "Which role or job title should candidates match?",
            "answer": "Backend Engineer",
        }
    ]
    response["criteria"] = proposed(role="", location="Bengaluru", max_salary_lpa=0)
    result = continue_search(
        query,
        proposed(max_salary_lpa=30, notice_period_days=0, min_experience=3),
        "Do you have a preferred location?",
        "Bengaluru",
        history=history,
    )
    assert calls[0]["search_query"] == query
    assert calls[0]["clarification_history"] == history
    assert result.criteria["role"] == "Backend Engineer"
    assert result.criteria["location"] == "Bengaluru"
    assert result.criteria["min_experience"] == 3
    assert result.criteria["max_salary_lpa"] == 30
    assert result.criteria["notice_period_days"] == 0
    assert not result.follow_up_question


def test_latest_explicit_removal_and_zero_confirmation():
    history = [
        {"question": "Maximum compensation in LPA?", "answer": "0"},
        {"question": "Anything else?", "answer": "No salary cap, Python is not required"},
        {"question": "Maximum notice period in days?", "answer": "0"},
    ]
    result, question = ground_criteria(
        proposed(skills=["Python"], max_salary_lpa=100),
        "Backend engineer remote with Python, budget 30 LPA",
        history,
    )
    assert result["max_salary_lpa"] is None
    assert result["notice_period_days"] == 0
    assert result["skills"] == []
    assert question == ""


def test_clarification_resolves_ambiguity_without_reasking():
    result, question = ground_criteria(
        proposed(),
        "Backend engineer remote, salary 30 LPA",
        [{"question": "What is your maximum compensation budget in LPA?", "answer": "25"}],
    )
    assert result["max_salary_lpa"] == 25
    assert question == ""
    result, question = ground_criteria(
        proposed(),
        "Backend engineer remote, full-time or contract",
        [{"question": "Which employment type should I use?", "answer": "Any"}],
    )
    assert result["employment_type"] == ""
    assert question == ""


def test_ambiguous_role_requires_confirmation_then_accepts_answer():
    query = "Backend or Frontend Engineer, remote"
    _, question = ground_criteria(proposed(), query)
    assert "role" in question
    result, question = ground_criteria(
        proposed(),
        query,
        [
            {"question": "Which role should I prioritize?", "answer": "Backend Engineer"},
        ],
    )
    assert result["role"] == "Backend Engineer"
    assert not question


def test_any_location_and_notice_without_restrictions_are_unconstrained():
    result, question = ground_criteria(
        proposed(location="Any"),
        "Backend engineer, no notice period restriction",
        [
            {"question": "What location do you prefer?", "answer": "Any"},
        ],
    )
    assert result["location"] == ""
    assert result["notice_period_days"] is None
    assert not question


@pytest.mark.parametrize(
    "query", ["Backend engineer remote 7–3 years", "Backend engineer remote 3 or 5 years"]
)
def test_ambiguous_ranges_require_clarification(query):
    result, question = ground_criteria(proposed(), query)
    assert result["min_experience"] is None
    assert result["max_experience"] is None
    assert "experience range" in question


@pytest.mark.parametrize(
    ("phrase", "field"),
    [
        ("-3 years experience", "min_experience"),
        ("maximum salary -10 LPA", "max_salary_lpa"),
        ("-30 days notice", "notice_period_days"),
    ],
)
def test_negative_source_values_are_not_reinterpreted_as_positive(phrase, field):
    result, question = ground_criteria(proposed(), f"Backend engineer remote, {phrase}")
    assert result[field] is None
    assert "non-negative" in question


@pytest.mark.parametrize("number", [float("nan"), float("inf"), -1, True])
def test_invalid_provider_numbers_fail_before_filters(provider, number):
    provider[0]["criteria"]["max_salary_lpa"] = number
    with pytest.raises(SearchUnderstandingUnavailable):
        understand_search("Backend engineer remote")


def make_candidate(name, **overrides):
    user = User.objects.create_user(username=name, email=f"{name}@example.com")
    return CandidateProfile.objects.create(
        user=user,
        full_name=name,
        headline="Backend Engineer",
        location="Bengaluru",
        total_experience=5,
        profile_status="submitted",
        visibility="approved_recruiters",
        submission_consent_at=timezone.now(),
        submitted_at=timezone.now(),
        **overrides,
    )


@pytest.mark.django_db
def test_postgres_missing_optional_fields_do_not_exclude_candidates(
    client,
    recruiter_account,
    provider,
):
    assert connection.vendor == "postgresql"
    first = make_candidate(
        "with-values", expected_salary_lpa=25, notice_period_days=30, employment_type="Contract"
    )
    unknown = make_candidate("unknown-values", expected_salary_lpa=None, notice_period_days=None)
    provider[0]["criteria"] = proposed(
        location="remote",
        remote_ok=True,
        max_salary_lpa=0,
        notice_period_days=0,
        employment_type="Full-time",
        min_experience=3,
        max_experience=3,
    )
    query = "  Backend engineer with 3 years of experience, remote  "
    response = client.post("/api/v1/searches/", {"query": query}, format="json")
    assert response.status_code == 201
    record = Search.objects.get(pk=response.data["id"])
    assert record.query == query
    result = client.get(f"/api/v1/searches/{record.pk}/results/")
    assert result.status_code == 200
    assert {row["candidate"]["id"] for row in result.data["results"]} == {first.pk, unknown.pk}
    assert record.criteria["max_salary_lpa"] is None


@pytest.mark.django_db
def test_postgres_explicit_zero_restricts_but_missing_does_not(client, recruiter_account, provider):
    zero = make_candidate("zero", expected_salary_lpa=0, notice_period_days=0)
    make_candidate("positive", expected_salary_lpa=25, notice_period_days=30)
    response = client.post(
        "/api/v1/searches/",
        {
            "query": "Backend engineer remote, maximum salary 0 LPA, immediate joiner",
        },
        format="json",
    )
    assert response.status_code == 201
    results = client.get(f"/api/v1/searches/{response.data['id']}/results/")
    assert [row["candidate"]["id"] for row in results.data["results"]] == [zero.pk]
    assert response.data["criteria"]["max_salary_lpa"] == 0
    assert response.data["criteria"]["notice_period_days"] == 0


@pytest.mark.django_db
def test_saved_search_is_grounded_before_results_ranking_and_serialization(
    client,
    recruiter_account,
):
    candidate = make_candidate("saved", expected_salary_lpa=20, notice_period_days=30)
    recruiter = RecruiterProfile.objects.get(user_id=recruiter_account["user"]["id"])
    record = Search.objects.create(
        recruiter=recruiter,
        query="Backend engineer remote",
        state="complete",
        criteria=proposed(
            max_salary_lpa=0,
            notice_period_days=0,
            max_experience=0,
            employment_type="Full-time",
            remote_ok=True,
        ),
    )
    response = client.get(f"/api/v1/searches/{record.pk}/results/")
    assert response.status_code == 200
    assert response.data["results"][0]["candidate"]["id"] == candidate.pk
    assert response.data["results"][0]["match_score"] >= 55
    assert response.data["search"]["criteria"]["max_salary_lpa"] is None
    recent = client.get("/api/v1/searches/")
    assert recent.data[0]["criteria"]["max_salary_lpa"] is None
    record.refresh_from_db()
    assert record.criteria["max_salary_lpa"] == 0  # Read-time defense, not a data migration.


@pytest.mark.django_db
def test_ungrounded_saved_role_cannot_grant_matching_only_access(client, recruiter_account):
    candidate = make_candidate("protected")
    candidate.visibility = "matching_roles"
    candidate.save(update_fields=["visibility"])
    recruiter = RecruiterProfile.objects.get(user_id=recruiter_account["user"]["id"])
    record = Search.objects.create(
        recruiter=recruiter,
        query="5 years experience",
        state="complete",
        criteria=proposed(remote_ok=True),
    )
    assert client.get(f"/api/v1/searches/{record.pk}/results/").status_code == 409
    assert client.get(f"/api/v1/candidates/{candidate.pk}/").status_code == 404
    assert client.get("/api/v1/searches/").data[0]["state"] == "needs_clarification"


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1"])
def test_invalid_manual_filters_are_rejected(client, recruiter_account, value):
    recruiter = RecruiterProfile.objects.get(user_id=recruiter_account["user"]["id"])
    record = Search.objects.create(
        recruiter=recruiter,
        query="Backend engineer remote",
        state="complete",
        criteria=proposed(remote_ok=True),
    )
    result = client.get(f"/api/v1/searches/{record.pk}/results/", {"max_salary_lpa": value})
    assert result.status_code == 400
