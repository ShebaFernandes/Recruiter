import logging
import math
from dataclasses import dataclass

from django.conf import settings

from .ai_providers import AIProviderError, AIProviderMalformedResponse, get_ai_provider
from .search_grounding import CRITERIA_DEFAULTS, ground_criteria
from .services import apply_search_answer, next_search_question, parse_search_query

logger = logging.getLogger(__name__)


class SearchUnderstandingUnavailable(Exception):
    """A safe, user-facing failure from the search-understanding boundary."""

    def __init__(
        self,
        message,
        code="search_understanding_unavailable",
        status_code=503,
        retry_after=None,
    ):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retry_after = retry_after


@dataclass(frozen=True)
class SearchInterpretation:
    criteria: dict
    follow_up_question: str
    follow_up_options: list[str]
    source: str
    model: str = ""
    request_id: str = ""


INTERPRETATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "criteria": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "role": {"type": "string"},
                "skills": {"type": "array", "items": {"type": "string"}},
                "min_experience": {"type": ["number", "null"]},
                "max_experience": {"type": ["number", "null"]},
                "location": {"type": "string"},
                "remote_ok": {"type": "boolean"},
                "notice_period_days": {"type": ["integer", "null"]},
                "max_salary_lpa": {"type": ["number", "null"]},
                "employment_type": {
                    "type": "string",
                    "enum": ["", "Full-time", "Part-time", "Contract"],
                },
                "work_preferences": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["Remote", "Hybrid", "On-site", "Flexible"],
                    },
                },
            },
            "required": list(CRITERIA_DEFAULTS),
        },
        "follow_up_question": {"type": "string"},
        "follow_up_options": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["criteria", "follow_up_question", "follow_up_options"],
}

SYSTEM_INSTRUCTIONS = """You interpret a recruiter's natural-language candidate search.
Return only the structured response required by the supplied JSON schema.

Rules:
- Extract only requirements that the recruiter stated or confirmed. Never invent a requirement.
- Unspecified numeric fields MUST be null, unspecified strings MUST be "", and unspecified
  lists MUST be []. Zero is an explicit requirement, NEVER a placeholder for missing data.
- Do not assume full-time employment, immediate availability, a salary cap, or an experience
  upper bound. "At least 3 years" has no upper bound. "Immediate joiner" has notice period 0.
- "Remote only" requires remote work; "remote is also okay" must not exclude other setups.
- Respect negations and explicit removals, such as "no salary cap" or "Python is not required".
- Use the original query and confirmed clarification history as evidence. Existing criteria
  are suggestions, not evidence. Later recruiter corrections supersede earlier requirements.
- Preserve the complete intended job title, including qualifiers such as AI, ML, GenAI,
  Full-Stack, Staff, or Founding. Job titles are open-ended, not selected from a fixed list.
- Treat 'remote', 'work from home', or 'anywhere' as a complete location/work-setup answer.
- A number followed by years/yrs/experience is experience, not part of a job title.
- Ask at most one short follow-up question, and only when a role is genuinely absent or
  ambiguous, or when neither a location nor remote acceptance has been supplied.
- If the role and location/remote preference are already clear, return an empty question.
- Follow-up options must be short, relevant to the actual question, and derived from the
  recruiter's request. Do not return a generic fixed list of job titles. Include
  'Let me type it' when a question is present.
- For a clarification answer, merge it with the existing criteria and preserve earlier
  criteria unless the recruiter explicitly changes them.
"""


def _fallback_options(question):
    lower = question.lower()
    if not question:
        return []
    if "location" in lower or "remote" in lower:
        return ["Bengaluru", "Remote", "Anywhere", "Let me type it"]
    return ["Let me type it"]


def _deterministic_interpretation(query, criteria=None, question="", answer=""):
    if criteria is None:
        parsed, follow_up = parse_search_query(query)
    else:
        parsed = apply_search_answer(dict(criteria), answer)
        follow_up = next_search_question(parsed)
    return SearchInterpretation(
        criteria=parsed,
        follow_up_question=follow_up,
        follow_up_options=_fallback_options(follow_up),
        source="deterministic",
    )


def _schema_error():
    raise AIProviderMalformedResponse("The AI search response did not match the schema.")


def _is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _normalize_interpretation(payload, provider, model, request_id=""):
    if not isinstance(payload, dict) or set(payload) != {
        "criteria",
        "follow_up_question",
        "follow_up_options",
    }:
        _schema_error()
    criteria_payload = payload.get("criteria")
    if not isinstance(criteria_payload, dict) or set(criteria_payload) != set(CRITERIA_DEFAULTS):
        _schema_error()
    for field in ("role", "location", "employment_type"):
        if not isinstance(criteria_payload[field], str):
            _schema_error()
    for field in ("skills", "work_preferences"):
        if not isinstance(criteria_payload[field], list) or not all(
            isinstance(value, str) for value in criteria_payload[field]
        ):
            _schema_error()
    for field in ("min_experience", "max_experience", "max_salary_lpa"):
        value = criteria_payload[field]
        if value is not None and not _is_number(value):
            _schema_error()
    notice = criteria_payload["notice_period_days"]
    if notice is not None and (not isinstance(notice, int) or not _is_number(notice)):
        _schema_error()
    if not isinstance(criteria_payload["remote_ok"], bool):
        _schema_error()
    if criteria_payload["employment_type"] not in {"", "Full-time", "Part-time", "Contract"}:
        _schema_error()
    if not set(criteria_payload["work_preferences"]).issubset(
        {"Remote", "Hybrid", "On-site", "Flexible"}
    ):
        _schema_error()
    if not isinstance(payload["follow_up_question"], str) or not isinstance(
        payload["follow_up_options"], list
    ):
        _schema_error()
    if not all(isinstance(value, str) for value in payload["follow_up_options"]):
        _schema_error()
    criteria = dict(criteria_payload)
    question = payload["follow_up_question"].strip()
    raw_options = payload["follow_up_options"]
    options = []
    for option in raw_options:
        value = str(option).strip()
        if value and value not in options:
            options.append(value)
    if question and "Let me type it" not in options:
        options.append("Let me type it")
    if not question:
        options = []
    return SearchInterpretation(criteria, question, options[:5], provider, model, request_id)


def _provider_interpret(query, criteria=None, question="", answer="", history=None):
    user_payload = {"search_query": query}
    if criteria is not None:
        safe_previous, _ = ground_criteria(criteria, query, history)
        user_payload.update(
            {
                "existing_criteria": safe_previous,
                "clarification_history": history or [],
                "pending_question": question,
                "recruiter_answer": answer,
            }
        )
    provider = get_ai_provider(settings.AI_PROVIDER)
    result = provider.generate(
        SYSTEM_INSTRUCTIONS,
        user_payload,
        INTERPRETATION_SCHEMA,
        "candidate_search_interpretation",
    )
    interpretation = _normalize_interpretation(
        result.data, result.provider, result.model, result.request_id
    )
    logger.info(
        "ai_search_provider_success provider=%s model=%s request_id=%s",
        result.provider,
        result.model,
        result.request_id or "not-returned",
    )
    return interpretation


def _public_provider_error(error):
    if error.kind == "rate_limited":
        return SearchUnderstandingUnavailable(
            "Enter's search assistant is busy. Please wait a moment and try again.",
            code="ai_provider_rate_limited",
            status_code=429,
            retry_after=error.retry_after or 30,
        )
    if error.kind == "timeout":
        return SearchUnderstandingUnavailable(
            "Enter's search assistant took too long to respond. Please try again.",
            code="ai_provider_timeout",
            status_code=503,
        )
    if error.kind == "malformed_response":
        return SearchUnderstandingUnavailable(
            "Enter could not safely understand that search. Please try rephrasing it.",
            code="ai_provider_malformed_response",
            status_code=502,
        )
    return SearchUnderstandingUnavailable(
        "Enter's search assistant is temporarily unavailable. Please try again shortly.",
        code="ai_provider_unavailable",
        status_code=503,
    )


def _ground_interpretation(result, query, criteria, question, answer, history):
    turns = [*(history or [])]
    if answer:
        turns.append({"question": question, "answer": answer})
    safe, clarification = ground_criteria(result.criteria, query, turns, previous=criteria)
    changed = sorted(field for field in safe if safe[field] != result.criteria.get(field))
    if changed:
        # Field names only: never log source text or candidate/recruiter information.
        logger.info("search_criteria_grounded fields=%s", ",".join(changed))
    return SearchInterpretation(
        safe,
        clarification,
        _fallback_options(clarification),
        result.source,
        result.model,
        result.request_id,
    )


def _interpret(query, criteria=None, question="", answer="", history=None):
    if settings.AI_PROVIDER == "deterministic":
        result = _deterministic_interpretation(query, criteria, question, answer)
        return _ground_interpretation(result, query, criteria, question, answer, history)
    try:
        result = _provider_interpret(query, criteria, question, answer, history)
        return _ground_interpretation(result, query, criteria, question, answer, history)
    except AIProviderError as error:
        if not settings.AI_ALLOW_DETERMINISTIC_FALLBACK:
            raise _public_provider_error(error) from error
        logger.warning(
            "ai_search_provider_fallback provider=%s error=%s",
            settings.AI_PROVIDER,
            error.kind,
        )
        fallback = _deterministic_interpretation(query, criteria, question, answer)
        result = SearchInterpretation(
            fallback.criteria,
            fallback.follow_up_question,
            fallback.follow_up_options,
            "deterministic_fallback",
        )
        return _ground_interpretation(result, query, criteria, question, answer, history)


def understand_search(query):
    return _interpret(query)


def continue_search(query, criteria, question, answer, history=None):
    return _interpret(query, criteria, question, answer, history)
