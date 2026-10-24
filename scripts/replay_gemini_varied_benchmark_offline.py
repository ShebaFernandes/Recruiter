"""Replay the fictional Gemini benchmark through validation without provider calls."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from talent.resume_understanding import interpretation_text, validate_interpretation  # noqa: E402
from talent.services import _resume_date, parse_resume  # noqa: E402

BENCHMARK = ROOT / ".local-benchmark" / "gemini-varied"
MANIFEST = BENCHMARK / "manifest.json"
REPORT = BENCHMARK / "offline-replay-after-recall-fix.json"
MANIFEST_SHA256 = "c9d246e648f3ed58fcf20e35700f3b6b3f06d7dbc39a6c8a096b28a3a79c984c"


def normal(value: str) -> str:
    return " ".join(value.casefold().split())


def contains(line: str, value: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(normal(value)) + r"(?!\w)", normal(line)))


def role_line_index(lines: list[str], role: dict) -> int:
    candidates = [index for index, line in enumerate(lines) if contains(line, role["title"])]
    if role["start"]:
        dated = [index for index in candidates if contains(lines[index], role["start"])]
        if dated:
            candidates = dated
    if role["end"]:
        dated = [index for index in candidates if contains(lines[index], role["end"])]
        if dated:
            candidates = dated
    prefixed = [
        index
        for index in candidates
        if normal(lines[index]).startswith(normal(role["title"]))
        or f"| {normal(role['title'])} |" in normal(lines[index])
    ]
    if prefixed:
        candidates = prefixed
    if len(candidates) != 1:
        raise RuntimeError(f"Could not uniquely locate role evidence: {role['title']}")
    return candidates[0]


def employer_line(lines: list[str], company: str, role_index: int) -> str:
    prior = [line for line in lines[: role_index + 1] if contains(line, company)]
    if not prior:
        raise RuntimeError(f"Could not locate employer evidence: {company}")
    return prior[-1]


def fact(value, evidence=""):
    return {"value": value, "evidence": evidence or value or ""}


def provider_fixture(item: dict, text: str) -> dict:
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    experiences = []
    for role in item["expected"]["work_experiences"]:
        index = role_line_index(lines, role)
        achievement = role["achievement"]
        achievement_indexes = [
            candidate
            for candidate in range(index, len(lines))
            if contains(lines[candidate], achievement)
        ]
        if not achievement_indexes:
            raise RuntimeError(f"Could not locate achievement evidence: {achievement}")
        role_evidence = "\n".join(lines[index : achievement_indexes[0] + 1])
        experiences.append(
            {
                "company": role["company"],
                "role": role["title"],
                "start": role["start"],
                "end": "Present" if role["current"] else role["end"],
                "employment_type": None,
                "location": None,
                "employer_evidence": employer_line(lines, role["company"], index),
                "role_evidence": role_evidence,
                "details": achievement,
                "achievements": [fact(achievement)],
            }
        )
    if item["slug"] == "explicit-career-gap":
        gap_index = next(
            index for index, line in enumerate(lines) if "career break" in normal(line)
        )
        experiences.insert(
            1,
            {
                "company": "Quartz Product Studio",
                "role": "Career break",
                "start": "December 2020",
                "end": "August 2021",
                "employment_type": None,
                "location": None,
                "employer_evidence": employer_line(
                    lines, "Quartz Product Studio", gap_index
                ),
                "role_evidence": lines[gap_index],
                "details": "",
                "achievements": [],
            },
        )
    title = item["expected"]["professional_title"]
    summary = item["expected"]["summary"]
    title_line = next(line for line in lines if contains(line, title))
    summary_line = next(line for line in lines if contains(line, summary))
    skill_line = next(line for line in lines if normal(line).startswith("skills:"))
    return {
        "full_name": fact(None),
        "location": fact(None),
        "professional_title": fact(title, title_line),
        "professional_summary": fact(summary, summary_line),
        "work_experiences": experiences,
        "skills": [fact(skill, skill_line) for skill in item["expected"]["skills"]],
        "standout_signal": fact(None),
        "education": [],
    }


def endpoint_correct(expected, actual, label: str, side: int) -> bool:
    if expected is None:
        return actual is None
    if re.fullmatch(r"\d{4}", expected):
        parts = re.split(r"\s+[–—-]\s+", label, maxsplit=1)
        return actual is None and len(parts) == 2 and parts[side] == expected
    return actual == _resume_date(expected)


def main() -> None:
    if hashlib.sha256(MANIFEST.read_bytes()).hexdigest() != MANIFEST_SHA256:
        raise SystemExit("Benchmark manifest changed; offline replay refused.")
    manifest = json.loads(MANIFEST.read_text())
    results = []
    for item in manifest["documents"]:
        path = Path(item["path"])
        with path.open("rb") as source:
            text = interpretation_text(parse_resume(source, path.name))
        validated = validate_interpretation(provider_fixture(item, text), text)
        actual = {
            (normal(row["company"]), normal(row["role"])): row
            for row in validated["work_experiences"]
        }
        role_results = []
        for expected in item["expected"]["work_experiences"]:
            row = actual.get((normal(expected["company"]), normal(expected["title"])))
            start = bool(row) and endpoint_correct(
                expected["start"], row["start_date"], row["date_label"], 0
            )
            end = bool(row) and endpoint_correct(
                expected["end"], row["end_date"], row["date_label"], 1
            )
            current = bool(row) and row["is_current"] == expected["current"]
            role_results.append(
                {
                    "company": expected["company"],
                    "title": expected["title"],
                    "accepted": bool(row),
                    "start_correct": start,
                    "end_correct": end,
                    "current_correct": current,
                    "correct": bool(row) and start and end and current,
                }
            )
        expected_keys = {
            (normal(row["company"]), normal(row["title"]))
            for row in item["expected"]["work_experiences"]
        }
        results.append(
            {
                "slug": item["slug"],
                "roles": role_results,
                "unsupported_roles": [
                    {"company": row["company"], "role": row["role"]}
                    for key, row in actual.items()
                    if key not in expected_keys
                ],
                "validation_rejections": validated["_validation_rejections"],
            }
        )
    roles = [role for result in results for role in result["roles"]]
    report = {
        "mode": "offline-mocked-schema-replay",
        "external_requests": 0,
        "manifest_sha256": MANIFEST_SHA256,
        "roles_correct": sum(role["correct"] for role in roles),
        "roles_total": len(roles),
        "date_endpoints_correct": sum(
            role["start_correct"] + role["end_correct"] for role in roles
        ),
        "date_endpoints_total": len(roles) * 2,
        "unsupported_roles_accepted": sum(
            len(result["unsupported_roles"]) for result in results
        ),
        "results": results,
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    main()
