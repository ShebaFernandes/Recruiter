import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.conf import settings

from .services import apply_search_answer, next_search_question, parse_search_query


class SearchUnderstandingUnavailable(Exception):
    """Raised when the configured semantic search interpreter cannot respond safely."""


@dataclass(frozen=True)
class SearchInterpretation:
    criteria: dict
    follow_up_question: str
    follow_up_options: list[str]
    source: str
    model: str = ""


CRITERIA_DEFAULTS = {
    "role": "",
    "skills": [],
    "min_experience": None,
    "max_experience": None,
    "location": "",
    "remote_ok": False,
    "notice_period_days": None,
    "max_salary_lpa": None,
    "employment_type": "",
    "work_preferences": [],
}

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


def _response_text(payload):
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return content["text"]
    raise SearchUnderstandingUnavailable("The AI search response did not contain output text.")


def _normalize_interpretation(payload, model):
    criteria_payload = payload.get("criteria")
    if not isinstance(criteria_payload, dict):
        raise SearchUnderstandingUnavailable("The AI search response was invalid.")
    criteria = {
        key: criteria_payload.get(key, default.copy() if isinstance(default, list) else default)
        for key, default in CRITERIA_DEFAULTS.items()
    }
    question = str(payload.get("follow_up_question") or "").strip()
    raw_options = payload.get("follow_up_options") or []
    options = []
    for option in raw_options:
        value = str(option).strip()
        if value and value not in options:
            options.append(value)
    if question and "Let me type it" not in options:
        options.append("Let me type it")
    if not question:
        options = []
    return SearchInterpretation(criteria, question, options[:5], "openai", model)


def _openai_interpret(query, criteria=None, question="", answer=""):
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise SearchUnderstandingUnavailable("AI search is not configured.")
    model = settings.OPENAI_SEARCH_MODEL
    user_payload = {"search_query": query}
    if criteria is not None:
        user_payload.update(
            {
                "existing_criteria": criteria,
                "pending_question": question,
                "recruiter_answer": answer,
            }
        )
    request_body = {
        "model": model,
        "instructions": SYSTEM_INSTRUCTIONS,
        "input": json.dumps(user_payload, ensure_ascii=False),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "candidate_search_interpretation",
                "strict": True,
                "schema": INTERPRETATION_SCHEMA,
            }
        },
    }
    request = urllib.request.Request(
        f"{settings.OPENAI_API_BASE_URL.rstrip('/')}/responses",
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=settings.SEARCH_AI_TIMEOUT_SECONDS
        ) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        return _normalize_interpretation(json.loads(_response_text(response_payload)), model)
    except (urllib.error.URLError, TimeoutError, socket.timeout, json.JSONDecodeError) as exc:
        raise SearchUnderstandingUnavailable(
            "AI search understanding is temporarily unavailable."
        ) from exc


def _interpret(query, criteria=None, question="", answer=""):
    backend = settings.SEARCH_UNDERSTANDING_BACKEND
    if backend == "deterministic":
        return _deterministic_interpretation(query, criteria, question, answer)
    if backend != "openai":
        raise SearchUnderstandingUnavailable("The configured search interpreter is invalid.")
    try:
        return _openai_interpret(query, criteria, question, answer)
    except SearchUnderstandingUnavailable:
        if not settings.SEARCH_AI_ALLOW_FALLBACK:
            raise
        fallback = _deterministic_interpretation(query, criteria, question, answer)
        return SearchInterpretation(
            fallback.criteria,
            fallback.follow_up_question,
            fallback.follow_up_options,
            "deterministic_fallback",
        )


def understand_search(query):
    return _interpret(query)


def continue_search(query, criteria, question, answer):
    return _interpret(query, criteria, question, answer)
