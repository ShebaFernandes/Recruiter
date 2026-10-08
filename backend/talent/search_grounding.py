"""Ground proposed constraints in recruiter text, never in provider assertions.

This is a validation boundary, not an alternate AI provider. Open-ended roles,
locations and skills still come from the interpreter; bounded values are checked
against units and operators in the source. Saved searches use the same boundary.
"""

import math
import re
from copy import deepcopy

from .services import LOCATIONS, _search_role, next_search_question

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
NUMBER = r"-?\d+(?:\.\d+)?"
WORDS = dict(
    zip(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
        "fifteen sixteen seventeen eighteen nineteen twenty".split(),
        range(21),
        strict=True,
    )
)
WORDS.update(
    dict(
        zip(
            "thirty forty fifty sixty seventy eighty ninety".split(),
            range(30, 100, 10),
            strict=True,
        )
    )
)
ALIASES = {
    "back end": "backend",
    "front end": "frontend",
    "full stack": "fullstack",
    "developers": "developer",
    "engineers": "engineer",
    "engineering": "engineer",
    "programmer": "developer",
    "programmers": "developer",
    "dev": "developer",
    "swe": "software engineer",
    "artificial intelligence": "ai",
    "machine learning": "ml",
    "bangalore": "bengaluru",
    "nyc": "new york",
    "postgresql": "postgres",
    "javascript": "js",
    "amazon web services": "aws",
}


def _text(value):
    value = re.sub(r"[-–—]", " ", str(value).casefold())
    for source, target in ALIASES.items():
        value = re.sub(r"\b" + re.escape(source) + r"\b", target, value)
    return " ".join(value.split())


def _numbers(value):
    value = re.sub(
        r"\b(" + "|".join(WORDS) + r")\b", lambda match: str(WORDS[match[0]]), value.casefold()
    )
    return re.sub(r"\b([2-9]0)[ -]([1-9])\b", lambda m: str(int(m[1]) + int(m[2])), value)


def _negated(text, start, end):
    before = text[max(0, start - 55) : start]
    after = text[end : end + 30]
    return bool(
        re.search(
            r"\b(?:not|no|without|exclude|excluding|don't need|do not need)\s+"
            r"(?:(?:require|requiring|need|any|a|an|experience|with|in)\s+)*$",
            before,
        )
        or re.match(
            r"\s+(?:is |are )?(?:not required|not necessary|optional|doesn't matter)", after
        )
    )


def _supported(value, turns):
    """Latest mention wins; use word boundaries, not substring matches (e.g. Java/JS)."""
    value = _text(value)
    if not value:
        return False
    pattern = r"(?<!\w)" + re.escape(value) + r"(?!\w)"
    for turn in reversed(turns):
        normalized = _text(turn)
        matches = list(re.finditer(pattern, normalized))
        if matches:
            match = matches[-1]
            return not _negated(normalized, match.start(), match.end())
    return False


def _location_supported(value, query, history):
    if not isinstance(value, str) or not value.strip():
        return False
    turns = _turns(query, history)
    if not _supported(value, turns):
        return False
    normalized = _text(value)
    if normalized in {_text(city) for city in LOCATIONS}:
        return True
    pattern = re.escape(normalized)
    if any(
        re.search(
            rf"\b(?:in|from|near|around|location|based|within)\s+{pattern}\b|"
            rf"\b{pattern}\s+based\b",
            _text(turn),
        )
        for turn in turns
    ):
        return True
    return any(
        re.search(r"location|where|city|based", str(item.get("question", "")), re.I)
        and _supported(value, [str(item.get("answer", ""))])
        for item in history or []
    )


def _turns(query, history):
    turns = [query]
    for item in history or []:
        answer = str(item.get("answer", "")).strip()
        question = str(item.get("question", "")).casefold()
        if not answer:
            turns.append("")
            continue
        if re.search(r"location|where|city|based", question) and re.fullmatch(
            r"any|anywhere|no preference|any location|all locations", answer, flags=re.I
        ):
            answer = "anywhere"
        # A bare number is meaningful only in an explicitly unit-labelled question.
        if re.fullmatch(NUMBER, _numbers(answer)):
            if "notice" in question and "day" in question:
                answer = f"notice period up to {answer} days"
            elif ("salary" in question or "compensation" in question) and "lpa" in question:
                answer = f"maximum salary {answer} LPA"
            elif "experience" in question and "year" in question:
                answer = f"at least {answer} years experience"
        # Never treat AI question text as evidence unless the recruiter confirms it.
        if answer.casefold() in {"yes", "yes please", "correct", "that's right"}:
            answer = item.get("question", "")
        elif ("acceptable" in question or "remote candidates" in question) and re.fullmatch(
            r"remote(?: is fine| is okay)?", answer, flags=re.I
        ):
            answer += " is acceptable"
        if "employment type" in question and re.fullmatch(
            r"(?:any|all)(?: types)?(?: are)?(?: acceptable| okay)?", answer, flags=re.I
        ):
            answer = "any employment type"
        turns.append(answer)
    return turns


def _unrestricted(text, topic):
    return bool(
        re.search(
            rf"\b(?:no|any|without)\s+(?:minimum |maximum )?{topic}"
            rf"(?:\s+(?:limit|cap|restriction|requirement))?\b|"
            rf"\b{topic}\s+(?:is |are )?"
            r"(?:flexible|negotiable|unrestricted|not important|doesn't matter)",
            text,
        )
    )


def ground_criteria(proposed, query, history=None, previous=None):
    """Return safe criteria and an optional clarification; never mutate stored inputs."""
    proposed = proposed if isinstance(proposed, dict) else {}
    previous = previous if isinstance(previous, dict) else {}
    result = deepcopy(CRITERIA_DEFAULTS)
    turns = _turns(query, history)
    questions = {}

    for field in ("role", "location"):
        for value in (proposed.get(field), previous.get(field)):
            supported = (
                isinstance(value, str) and _supported(value, turns)
                if field == "role"
                else _location_supported(value, query, history)
            )
            if field == "role" and _text(value) in {
                "any",
                "whatever",
                "not sure",
                "unsure",
                "someone",
                "anyone",
                "yes",
                "no",
            }:
                supported = False
            if supported:
                result[field] = value.strip()
                break
    if _text(result["location"]) in {"remote", "anywhere", "work from home"}:
        result["location"] = ""
    for value in [*(previous.get("skills") or []), *(proposed.get("skills") or [])]:
        if isinstance(value, str) and _supported(value, turns) and value not in result["skills"]:
            result["skills"].append(value)

    for index, turn in enumerate(turns):
        text = _numbers(turn)
        # Recover explicit job titles/answers if the provider omits a confirmed role.
        role = _search_role(turn)
        if role and _supported(role, [turn]):
            result["role"] = role
            questions.pop("role", None)
        alternatives = re.split(r"\bor\b", turn, maxsplit=1, flags=re.I)
        if len(alternatives) == 2:
            left, right = alternatives
            right_role = _search_role(right.strip())
            left_role = _search_role(left.strip())
            if right_role and not left_role:
                left_role = _search_role(f"{left.strip()} {right_role.split()[-1]}")
                if len(left_role.split()) < 2:
                    left_role = ""
            if left_role and right_role and _text(left_role) != _text(right_role):
                result["role"] = ""
                questions["role"] = "Which role should I prioritize for this search?"
        if index and history:
            question = str(history[index - 1].get("question", "")).casefold()
            if re.search(r"role|job title", question) and not role:
                # An open-ended, directly supplied job title need not be in a catalogue.
                if not re.search(r"\d|\b(?:any|whatever|yes|no|not sure)\b", turn, re.I):
                    result["role"] = turn.strip()
                    questions.pop("role", None)
            if re.search(r"location|where|city|based", question):
                if not re.search(
                    r"\b(?:remote|anywhere|hybrid|yes|no|not sure)\b", turn, re.I
                ) and re.fullmatch(r"[\w .'-]{2,70}", turn):
                    result["location"] = turn.strip()

        years = re.search(rf"({NUMBER})\s*(?:to|[-–])\s*({NUMBER})\s*(?:years?|yrs?)", text)
        single = re.search(rf"({NUMBER})\s*(\+)?\s*(?:years?|yrs?)\b", text)
        if _unrestricted(text, "experience"):
            result.update(min_experience=None, max_experience=None)
            questions.pop("experience", None)
        elif years and not _negated(text, years.start(), years.end()):
            result.update(min_experience=float(years[1]), max_experience=float(years[2]))
            questions.pop("experience", None)
        elif single and not _negated(text, single.start(), single.end()):
            prefix = text[max(0, single.start() - 35) : single.start()]
            upper = re.search(
                r"(?:up to|at most|maximum|max|no more than|not more than|under)\s*$", prefix
            )
            exact = re.search(r"\bexactly\s*$", prefix)
            value = float(single[1])
            result.update(
                min_experience=None if upper else value,
                max_experience=value if upper or exact else None,
            )
            questions.pop("experience", None)
        if re.search(rf"{NUMBER}\s+or\s+{NUMBER}\s*(?:years?|yrs?)", text):
            result.update(min_experience=None, max_experience=None)
            questions["experience"] = (
                "What experience range should I use, from minimum to maximum years?"
            )

        notice = re.search(rf"({NUMBER})\s*(days?|weeks?)\b", text)
        immediate = re.search(
            r"\b(?:immediate(?:ly)? (?:joiner|joining|available|availability)|"
            r"(?:join|start|available) (?:immediately|right away|asap)|"
            r"no notice(?!\s+(?:period\s+)?(?:limit|restriction|requirement))(?: period)?)\b",
            text,
        )
        if immediate and not _negated(text, immediate.start(), immediate.end()):
            result["notice_period_days"] = 0
        elif _unrestricted(text, r"(?:notice(?: period)?|availability)"):
            result["notice_period_days"] = None
        elif notice and re.search(
            r"\b(?:notice|join|joining|start|available|availability)\b", text
        ):
            if not _negated(text, notice.start(), notice.end()):
                days = float(notice[1]) * (7 if notice[2].startswith("week") else 1)
                if days.is_integer():
                    result["notice_period_days"] = int(days)

        salary = re.search(rf"({NUMBER})\s*(?:lpa|lakhs?(?: per annum)?)\b", text)
        if _unrestricted(text, r"(?:salary|compensation|budget)"):
            result["max_salary_lpa"] = None
            questions.pop("salary", None)
        elif salary and not _negated(text, salary.start(), salary.end()):
            prefix = text[max(0, salary.start() - 55) : salary.start()]
            if re.search(
                r"\b(?:up to|at most|under|maximum|max|cap|budget|no more than)\b", prefix
            ):
                result["max_salary_lpa"] = float(salary[1])
                questions.pop("salary", None)
            else:
                result["max_salary_lpa"] = None
                questions["salary"] = (
                    "What is your maximum compensation budget in LPA, or is it flexible?"
                )

        employment_matches = []
        for label, pattern in (
            ("Full-time", r"full[ -]?time"),
            ("Part-time", r"part[ -]?time"),
            ("Contract", r"contract(?:or|ual)?|freelanc(?:e|er|ing)"),
        ):
            match = re.search(rf"\b(?:{pattern})\b", text)
            if match:
                result["employment_type"] = (
                    "" if _negated(text, match.start(), match.end()) else label
                )
                if result["employment_type"]:
                    employment_matches.append(label)
        if len(employment_matches) > 1:
            result["employment_type"] = ""
            questions["employment"] = (
                "Which employment type should I use, or are all types acceptable?"
            )
        elif employment_matches:
            questions.pop("employment", None)
        if _unrestricted(text, "employment type"):
            result["employment_type"] = ""
            questions.pop("employment", None)

        remote = re.search(r"\b(?:remote|work from home|work remotely|wfh|anywhere)\b", text)
        if remote:
            positive = not _negated(text, remote.start(), remote.end())
            result["remote_ok"] = positive
            if not positive:
                result["work_preferences"] = []
            else:
                result["location"] = "" if "anywhere" in text else result["location"]
                strict = bool(re.search(r"remote only|only remote|fully remote|100% remote", text))
                permissive = bool(
                    re.search(r"fine|okay|\bok\b|acceptable|anywhere|also|open to", text)
                )
                if strict or (
                    not permissive and "Remote" in (proposed.get("work_preferences") or [])
                ):
                    result["work_preferences"] = ["Remote"]
                elif permissive:
                    result["work_preferences"] = []
        modes = ["Remote"] if remote and "Remote" in result["work_preferences"] else []
        for label, pattern in (
            ("Hybrid", r"hybrid"),
            ("On-site", r"on[ -]?site|in[ -]office|office based"),
            ("Flexible", r"flexible work|any work setup"),
        ):
            match = re.search(rf"\b(?:{pattern})\b", text)
            if match and not _negated(text, match.start(), match.end()):
                modes.append(label)
            elif match and label in result["work_preferences"]:
                result["work_preferences"].remove(label)
        if modes:
            result["work_preferences"] = modes

    if _text(result["location"]) in {"remote", "anywhere", "work from home"}:
        result["location"] = ""

    for field in ("min_experience", "max_experience", "max_salary_lpa", "notice_period_days"):
        value = result[field]
        if value is not None and (not math.isfinite(value) or value < 0):
            result[field] = None
            questions[field] = "Please confirm a non-negative value for your search requirement."
    low, high = result["min_experience"], result["max_experience"]
    if low is not None and high is not None and low > high:
        result.update(min_experience=None, max_experience=None)
        questions["experience"] = (
            "What experience range should I use, from minimum to maximum years?"
        )
    essential = next_search_question(result)
    return result, essential or next(iter(questions.values()), "")


def ground_saved_search(search):
    """Sanitize legacy criteria on read; do not rewrite records or make AI requests."""
    return ground_criteria(search.criteria, search.query, search.clarification_history)
