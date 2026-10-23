"""All provider responses and documents are synthetic; network calls are mocked."""

from copy import deepcopy
from decimal import Decimal
from unittest.mock import Mock

import pytest
from talent.ai_providers import (
    AIProviderMalformedResponse,
    AIProviderRateLimited,
    AIProviderResult,
    AIProviderTimeout,
    AIProviderUnavailable,
)
from talent.resume_understanding import (
    SCHEMA,
    interpretation_text,
    resume_provider,
    total_experience,
    understand_resume,
    validate_interpretation,
)
from talent.services import parse_resume

TEXT = """Name: Sample Person
Location: Pune
Engineer | Example Studio | Jan 2020 - Dec 2021
Built a Python service used by 12 teams.
Senior Engineer | Example Studio | Jan 2022 - Present
Shipped a Python and Kafka platform.
Skills: Python, Kafka, Java
Education: Example University
"""


def fact(value, evidence=None):
    return {"value": value, "evidence": evidence or value or ""}


def response():
    return {
        "full_name": fact("Sample Person", "Name: Sample Person"),
        "location": fact("Pune", "Location: Pune"),
        "work_experiences": [
            {"company": "Example Studio", "role": "Engineer", "start": "Jan 2020",
             "end": "Dec 2021", "employment_type": None, "location": None,
             "details": "Built a Python service used by 12 teams.",
             "evidence": "Engineer | Example Studio | Jan 2020 - Dec 2021\n"
                         "Built a Python service used by 12 teams."},
            {"company": "Example Studio", "role": "Senior Engineer", "start": "Jan 2022",
             "end": "Present", "employment_type": None, "location": None,
             "details": "Shipped a Python and Kafka platform.",
             "evidence": "Senior Engineer | Example Studio | Jan 2022 - Present\n"
                         "Shipped a Python and Kafka platform."},
        ],
        "skills": [fact("Java"), fact("Kafka"), fact("Python")],
        "standout_signal": fact("Built a Python service used by 12 teams."),
        "education": [fact("Example University")],
    }


def rules():
    return {"raw_text": TEXT, "skills": ["Java", "Python"], "work_experiences": [],
            "headline": "Engineer"}


@pytest.fixture
def enabled(settings):
    settings.RESUME_AI_ENABLED = True
    settings.RESUME_AI_EXTERNAL_PROCESSING_APPROVED = True
    settings.RESUME_AI_ALLOW_PAID = False
    settings.RESUME_AI_PROVIDER = "openrouter"
    settings.RESUME_AI_MODEL = "openrouter/free"


def test_valid_evidence_promotions_dedup_and_backend_computation():
    data = response()
    data["work_experiences"].append(deepcopy(data["work_experiences"][0]))
    parsed = validate_interpretation(data, TEXT)
    assert len(parsed["work_experiences"]) == 2
    assert parsed["headline"] == "Senior Engineer"
    assert parsed["current_company"] == "Example Studio"
    assert parsed["strongest_skills"] == ["Python", "Kafka", "Java"]
    assert parsed["likely_directions"] == ["Staff Engineering"]
    assert parsed["standout_signal"] in TEXT
    assert parsed["work_experiences"][0]["start_date"] == "2020-01-01"
    assert parsed["total_experience"] > 5


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(expected_salary_lpa=50),
    lambda d: d["work_experiences"][0].update(company="Invented Company"),
    lambda d: d["work_experiences"][0].update(start="2010-01-01"),
    lambda d: d["work_experiences"][0].update(details="Increased revenue 500%"),
    lambda d: d["skills"].append(fact("Kubernetes", "Skills: Python, Kafka, Java")),
    lambda d: d.update(standout_signal=fact("Built a service used by 99 teams.")),
    lambda d: d["work_experiences"][0].update(start="Dec 2021", end="Jan 2020"),
    lambda d: d["work_experiences"][0].update(role="Built a Python service used by 12 teams."),
])
def test_unsupported_or_invalid_output_is_rejected(mutation):
    data = response()
    mutation(data)
    with pytest.raises(AIProviderMalformedResponse):
        validate_interpretation(data, TEXT)


def test_unknown_end_not_current_and_zero_distinct_from_unknown():
    assert total_experience([]) is None
    assert total_experience([{"start_date": "2020-01-01", "end_date": None}]) is None
    assert total_experience([{"start_date": "2020-01-01", "end_date": "2020-01-01"}]) == 0
    rows = [{"start_date": "2020-01-01", "end_date": "2022-01-01"},
            {"start_date": "2021-01-01", "end_date": "2023-01-01"}]
    assert total_experience(rows) == 3
    data = response()
    data["work_experiences"][1]["end"] = None
    parsed = validate_interpretation(data, TEXT)
    assert not parsed["work_experiences"][1]["is_current"]
    assert "Unknown" in parsed["work_experiences"][1]["date_label"]
    assert parsed["total_experience"] is None


def test_employer_and_dates_cannot_be_borrowed_from_another_role():
    data = response()
    data["work_experiences"][0].update(
        company="Other Studio", start="Jan 2022", end="Present", details="",
        evidence="Engineer | Example Studio | Jan 2020 - Dec 2021\n"
                 "Manager | Other Studio | Jan 2022 - Present",
    )
    text = TEXT + "Manager | Other Studio | Jan 2022 - Present"
    with pytest.raises(AIProviderMalformedResponse):
        validate_interpretation(data, text)


def test_disabled_and_unapproved_never_call_provider(settings, monkeypatch):
    provider = Mock(side_effect=AssertionError("Network must not be used"))
    monkeypatch.setattr("talent.resume_understanding.resume_provider", provider)
    settings.RESUME_AI_ENABLED = False
    assert understand_resume(rules(), Mock())["_interpretation"]["reason"] == "disabled"
    settings.RESUME_AI_ENABLED = True
    settings.RESUME_AI_EXTERNAL_PROCESSING_APPROVED = False
    assert understand_resume(rules(), Mock())["_interpretation"]["source"] == "rules"
    provider.assert_not_called()


def test_mocked_success_and_timeout_fallback(enabled, monkeypatch):
    provider = Mock()
    provider.generate.return_value = AIProviderResult(response(), "openrouter", "fictional:free")
    monkeypatch.setattr("talent.resume_understanding.resume_provider", lambda: provider)
    result = understand_resume(rules(), lambda: True)
    assert result["_interpretation"]["source"] == "ai"
    assert result["headline"] == "Senior Engineer"
    assert "full_name" not in result  # Local identity is never overridden by AI.
    provider.generate.side_effect = AIProviderTimeout()
    provider.reset_mock()
    result = understand_resume(rules(), lambda: True)
    assert result["_interpretation"] == {"source": "rules", "reason": "timeout"}
    assert result["headline"] == "Engineer"
    assert provider.generate.call_count == 1


def test_malformed_response_budget_and_no_retry_after_exhaustion(enabled, monkeypatch):
    provider = Mock()
    provider.generate.return_value = AIProviderResult({}, "openrouter", "fictional:free")
    monkeypatch.setattr("talent.resume_understanding.resume_provider", lambda: provider)
    reserve = Mock(return_value=True)
    assert understand_resume(rules(), reserve)["_interpretation"]["source"] == "rules"
    assert provider.generate.call_count == reserve.call_count == 2
    provider.reset_mock()
    understand_resume(rules(), lambda: False)
    provider.generate.assert_not_called()


def test_reliable_deterministic_history_skips_ai_call(enabled, monkeypatch):
    provider = Mock()
    monkeypatch.setattr("talent.resume_understanding.resume_provider", lambda: provider)
    data = rules() | {
        "work_experiences": [
            {
                "company": "Example Studio",
                "role": "Engineer",
                "start_date": "2020-01-01",
                "end_date": "2021-01-01",
            }
        ],
        "_employment_parse": {"reliable": True},
    }
    result = understand_resume(data, lambda: True)
    assert result["_interpretation"] == {
        "source": "rules",
        "reason": "deterministic_reliable",
    }
    provider.generate.assert_not_called()


def test_free_provider_routing_enforces_privacy_and_zero_cost(enabled, settings, monkeypatch):
    settings.OPENROUTER_API_KEY = "synthetic-secret"
    post = Mock(return_value={"choices": [{"finish_reason": "stop", "message": {"content": {}}}]})
    monkeypatch.setattr("talent.ai_providers._post_json", post)
    resume_provider().generate("instruction", {"document_text": "synthetic"}, SCHEMA, "resume")
    url, body, headers, timeout = post.call_args.args
    assert url == "https://openrouter.ai/api/v1/chat/completions"
    assert body["model"] == "openrouter/free"
    assert body["provider"] == {"require_parameters": True, "data_collection": "deny",
                                "zdr": True, "allow_fallbacks": False,
                                "max_price": {"prompt": 0, "completion": 0, "request": 0}}
    assert timeout <= 60
    assert body["max_tokens"] == 4000
    settings.RESUME_AI_MODEL = "paid-model"
    post.reset_mock()
    assert understand_resume(rules(), lambda: True)["_interpretation"]["source"] == "rules"
    post.assert_not_called()


def test_direct_identifiers_redacted_without_claiming_anonymity():
    data = {"full_name": "Sample Person", "email": "sample@example.test",
            "phone": "9999999999", "raw_text": "Sample Person sample@example.test 9999999999"}
    text = interpretation_text(data)
    assert "Sample" not in text and "@" not in text and "9999" not in text


def test_historical_remote_work_never_becomes_future_preference():
    from io import BytesIO

    from .test_candidate_flow import resume_pdf

    result = parse_resume(BytesIO(resume_pdf([
        "Name: Example Person", "Experience: Engineer|Example Studio|2020-01-01|Present|",
        "Worked remotely for a hybrid team with flexible deployment schedules.",
    ])), "example.pdf")
    assert result["work_preferences"] == []
    assert result["notice_period_days"] is None
    assert result["expected_salary_lpa"] is None


@pytest.mark.parametrize("error", [AIProviderRateLimited(), AIProviderUnavailable()])
def test_outage_and_rate_limit_fall_back_without_request_storm(enabled, monkeypatch, error):
    provider = Mock()
    provider.generate.side_effect = error
    monkeypatch.setattr("talent.resume_understanding.resume_provider", lambda: provider)
    assert understand_resume(rules(), lambda: True)["_interpretation"]["reason"] == error.kind
    assert provider.generate.call_count == 1


def test_openai_requires_explicit_cost_and_zdr_approval(enabled, settings, monkeypatch):
    settings.RESUME_AI_PROVIDER = "openai"
    settings.RESUME_AI_MODEL = "configured-paid-model"
    settings.OPENAI_API_KEY = "synthetic-secret"
    settings.RESUME_AI_OPENAI_ZDR_APPROVED = False
    with pytest.raises(AIProviderUnavailable):
        resume_provider()
    settings.RESUME_AI_ALLOW_PAID = True
    with pytest.raises(AIProviderUnavailable):
        resume_provider()
    settings.RESUME_AI_OPENAI_ZDR_APPROVED = True
    post = Mock(return_value={"output_text": "{}"})
    monkeypatch.setattr("talent.ai_providers._post_json", post)
    resume_provider().generate("instruction", {}, SCHEMA, "resume")
    assert post.call_args.args[1]["store"] is False
    assert post.call_args.args[1]["max_output_tokens"] == 4000


def test_gemini_uses_exact_model_structured_output_and_usage(enabled, settings, monkeypatch):
    settings.RESUME_AI_PROVIDER = "gemini"
    settings.RESUME_AI_MODEL = "gemini-3.5-flash-lite"
    settings.RESUME_AI_API_KEY = "synthetic-generic-key"
    settings.RESUME_AI_GEMINI_FREE_TIER_APPROVED = True
    post = Mock(return_value={
        "responseId": "synthetic-response",
        "candidates": [{
            "finishReason": "STOP",
            "content": {"parts": [{"text": "{}"}]},
        }],
        "usageMetadata": {
            "promptTokenCount": 321,
            "candidatesTokenCount": 45,
            "thoughtsTokenCount": 6,
        },
    })
    monkeypatch.setattr("talent.ai_providers._post_json", post)
    result = resume_provider().generate("instruction", {}, SCHEMA, "resume")
    url, body, headers, timeout = post.call_args.args
    assert url.endswith("/models/gemini-3.5-flash-lite:generateContent")
    assert headers["x-goog-api-key"] == "synthetic-generic-key"
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["responseJsonSchema"] == SCHEMA
    assert body["generationConfig"]["maxOutputTokens"] == 4000
    assert timeout <= 60
    assert result.input_tokens == 321
    assert result.output_tokens == 51


@pytest.mark.django_db
def test_paid_budget_exhaustion_falls_back_without_call_or_usage(
    enabled, settings, tmp_path, client, candidate_account, monkeypatch,
):
    from .test_candidate_experience import upload
    from .test_candidate_flow import resume_pdf

    settings.MEDIA_ROOT = tmp_path
    settings.RESUME_AI_ALLOW_PAID = True
    settings.RESUME_AI_MODEL = "synthetic-paid-model"
    settings.RESUME_AI_DAILY_BUDGET_USD = Decimal("0.001")
    settings.RESUME_AI_MONTHLY_BUDGET_USD = Decimal("0.001")
    settings.RESUME_AI_INPUT_USD_PER_MILLION = Decimal("100")
    settings.RESUME_AI_OUTPUT_USD_PER_MILLION = Decimal("100")
    provider = Mock()
    monkeypatch.setattr("talent.resume_understanding.resume_provider", lambda: provider)
    result = upload(
        client,
        resume_pdf(["Name: Asha Rao", "Career details available on request."]),
        "synthetic.pdf",
    ).data
    provider.generate.assert_not_called()
    assert result["work_experiences"] == []
    stored = result["latest_resume"]["id"]
    from talent.models import Resume, ResumeAIUsage

    resume = Resume.objects.get(pk=stored)
    assert resume.extracted_data["_interpretation"]["reason"] == "budget_exhausted"
    assert not ResumeAIUsage.objects.filter(resume=resume).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("extension", ["pdf", "docx"])
def test_worker_persists_mocked_ai_interpretation_and_private_evidence(
    enabled, settings, tmp_path, client, candidate_account, monkeypatch, extension,
):
    from io import BytesIO

    from docx import Document
    from talent.models import Resume, ResumeAIUsage

    from .test_candidate_experience import upload
    from .test_candidate_flow import resume_pdf

    settings.MEDIA_ROOT = tmp_path
    lines = TEXT.replace("Sample Person", "Asha Rao").splitlines()
    if extension == "pdf":
        content = resume_pdf(lines)
    else:
        doc = Document()
        for line in lines:
            doc.add_paragraph(line)
        output = BytesIO()
        doc.save(output)
        content = output.getvalue()
    data = response()
    data["full_name"] = fact(None)
    provider = Mock()
    provider.generate.return_value = AIProviderResult(data, "openrouter", "fictional:free")
    monkeypatch.setattr("talent.resume_understanding.resume_provider", lambda: provider)
    result = upload(client, content, f"fictional.{extension}").data
    assert result["full_name"] == "Asha Rao"
    assert result["headline"] == "Senior Engineer"
    assert len(result["work_experiences"]) == 2
    assert result["career_preferences"]["strongest_skills"][0] == "Python"
    assert result["career_preferences"]["standout_signal"] in TEXT
    assert result["career_preferences"]["likely_directions"] == ["Staff Engineering"]
    stored = Resume.objects.get(pk=result["latest_resume"]["id"])
    assert stored.extracted_data["_ai_requests"] == 1
    assert stored.extracted_data["_interpretation"]["source"] == "ai"
    usage = ResumeAIUsage.objects.get(resume=stored)
    assert usage.outcome == ResumeAIUsage.Outcome.SUCCEEDED
    assert usage.provider == "openrouter"
    assert usage.estimated_cost_usd == 0
    assert "_evidence" in stored.extracted_data
    assert "_evidence" not in str(result) and "raw_text" not in str(result)
    assert "Asha Rao" not in provider.generate.call_args.args[1]["document_text"]
    from talent.resume_processing import process_resume_job

    assert process_resume_job(stored.processing_job.pk) == "duplicate"
    assert ResumeAIUsage.objects.filter(resume=stored).count() == 1
