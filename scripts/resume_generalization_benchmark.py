"""Fixed-seed fictional PDF/DOCX benchmark; no provider or candidate storage access."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import resource
import subprocess
import sys
import time
import types
from collections import defaultdict
from dataclasses import replace
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["RESUME_AI_ENABLED"] = "false"
os.environ["RESUME_LOCAL_OCR_ENABLED"] = "false"

import django  # noqa: E402

django.setup()

from resume_accuracy_benchmark import Case, Role, cases, document  # noqa: E402
from talent.employment_reconciliation import trusted_rows  # noqa: E402
from talent.resume_understanding import validate_interpretation  # noqa: E402
from talent.services import parse_resume  # noqa: E402


def fixture_cases():
    """Twenty layouts, five independent employer sets, plus freshers and scans."""
    selected = [case for case in cases() if case.roles and not case.image_only][:20]
    for variant in range(5):
        for template in selected:
            substitutions = {role.company: f"{role.company} {chr(65 + variant)}"
                             for role in template.roles}
            lines = list(template.lines)
            for source, target in sorted(substitutions.items(), key=lambda pair: -len(pair[0])):
                lines = [line.replace(source, target) for line in lines]
            roles = [replace(role, company=substitutions[role.company])
                     for role in template.roles]
            yield replace(template, name=f"{template.name}_{variant}", lines=lines, roles=roles)
    for variant in range(10):
        yield Case(f"fresher_{variant}", ["PROJECTS", "Built a scheduling prototype",
                                        "EDUCATION", f"Example College {variant}"], [],
                   "docx" if variant % 2 else "pdf")
    for variant in range(10):
        yield Case(f"image_only_{variant}", [],
                   [Role(f"Fictional Scanner {variant}", "Engineer", "2020", "2022")],
                   "pdf", image_only=True)
    for variant in range(10):
        company = f"Fictional Layout Works {variant}"
        yield Case(f"quote_drift_{variant}", [
            "WORK EXPERIENCE", f"{company} | Jan 2020 - Dec 2022",
            "Platform Engineer | Bengaluru", "SKILLS", "Python",
        ], [Role(company, "Platform Engineer", "2020-01-01", "2022-12-01")],
            "pdf" if variant % 2 else "docx")


def category(case):
    if case.image_only:
        return "scanned_pdf_ocr_disabled"
    if case.name.startswith("quote_drift"):
        return "quote_layout_drift"
    if not case.roles:
        return "fresher"
    if case.table:
        return "docx_table"
    if case.columns:
        return "pdf_columns"
    if "promotion" in case.name:
        return "promotions"
    if "intern" in case.name:
        return "internships"
    if "unknown" in case.name or "undated" in case.name:
        return "undated"
    if "long" in case.name:
        return "long_history"
    return case.kind


def line_has_role(line, title):
    return bool(re.search(r"(?<![\w])" + re.escape(title) + r"(?![\w])", line))


def response(case, text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    proposals = []
    for role in case.roles:
        company_positions = [index for index, line in enumerate(lines)
                             if role.company in line]
        role_positions = [index for index, line in enumerate(lines)
                          if line_has_role(line, role.title)]
        preferred = [index for index in role_positions
                     if lines[index].startswith(role.title)
                     or f"| {role.title} |" in lines[index]]
        if preferred:
            role_positions = preferred
        if company_positions and role_positions:
            pairs = [(company_index, role_index)
                     for company_index in company_positions
                     for role_index in role_positions if company_index <= role_index]
            company_index, role_index = min(
                pairs, key=lambda pair: (pair[1] - pair[0], pair[1])) if pairs else (
                    company_positions[0], role_positions[0])
            company_line, role_line = lines[company_index], lines[role_index]
            if (role_index + 1 < len(lines)
                    and re.match(r"^(?:\d{4}|\d{1,2}/\d{4}|[A-Z][a-z]{2,8} \d{4})"
                                 r"\s*[-–—]", lines[role_index + 1])):
                role_line += "\n" + lines[role_index + 1]
        else:
            company_line, role_line = "", ""
        # Fictional provider quotes can normalize table separators and line breaks.
        # The fixed variant exposes quote drift without changing factual values.
        drift = case.name.startswith("quote_drift")
        if drift and company_line and role_line and company_line != role_line:
            company_line = company_line.replace(" | ", " ")
            role_line = role_line.replace(" | ", " ")
        def source_date(value, role_line=role_line, company_line=company_line):
            if not value:
                return None
            parsed = datetime.fromisoformat(value) if len(value) > 4 else None
            options = [value]
            if parsed:
                options = [parsed.strftime(pattern) for pattern in (
                    "%b %Y", "%B %Y", "%Y-%m", "%m/%Y", "%m-%Y", "%Y/%m",
                )] + [value[:4]]
            for option in options:
                if any(option in line for line in (role_line, company_line)):
                    return option
            return value[:4]
        start = source_date(role.start)
        end = next((label for label in ("Present", "Current", "Now")
                    if role.current and label in (role_line + company_line)), None)
        if not role.current:
            end = source_date(role.end)
        proposals.append({
            "company": role.company, "role": role.title,
            "start": start, "end": end, "employment_type": None,
            "location": None, "employer_evidence": company_line,
            "role_evidence": role_line, "details": "", "achievements": [],
        })
    empty = {"value": None, "evidence": ""}
    return {"full_name": empty, "location": empty,
            "professional_title": empty, "professional_summary": empty,
            "work_experiences": proposals, "skills": [],
            "standout_signal": empty, "education": []}


def key(row):
    return (" ".join(row["company"].casefold().split()),
            " ".join(row["role"].casefold().split()))


def score(case, rows):
    expected = {(role.company.casefold(), role.title.casefold()) for role in case.roles}
    actual = {key(row) for row in rows}
    expected_dates = sum(bool(role.start) + bool(role.end or role.current)
                         for role in case.roles)
    # Dates are covered when the validated role retains a non-Unknown endpoint.
    date_hits = 0
    for role in case.roles:
        row = next((item for item in rows if key(item) ==
                    (role.company.casefold(), role.title.casefold())), None)
        if row:
            labels = (row.get("date_label") or "").split(" — ")
            date_hits += bool(role.start and len(labels) == 2 and labels[0] != "Unknown")
            date_hits += bool((role.end or role.current) and len(labels) == 2
                              and labels[1] != "Unknown")
    return {"expected": len(expected), "accepted": len(actual),
            "matched": len(expected & actual), "false_positives": len(actual - expected),
            "dates": expected_dates, "date_hits": date_hits,
            "zero_role_failure": bool(expected and not actual)}


def baseline_validator():
    source = subprocess.run(
        ["git", "show", "HEAD:backend/talent/resume_understanding.py"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout
    module = types.ModuleType("talent._benchmark_baseline_validator")
    module.__package__ = "talent"
    exec(compile(source, "baseline_resume_understanding.py", "exec"), module.__dict__)
    return module.validate_interpretation


def source_document(case):
    if not case.image_only:
        return document(case)
    image = Image.new("RGB", (1000, 350), "white")
    ImageDraw.Draw(image).text(
        (30, 90), f"Engineer | {case.roles[0].company} | 2020 - 2022", fill="black")
    output = BytesIO()
    image.save(output, format="PDF")
    return output.getvalue(), f"{case.name}.pdf"


def summarize(items):
    totals = defaultdict(int)
    for item in items:
        for name, value in item.items():
            if isinstance(value, (int, bool)):
                totals[name] += value
    return {"fixtures": len(items), "expected_roles": totals["expected"],
            "accepted_roles": totals["accepted"],
            "precision": round(totals["matched"] / totals["accepted"], 4)
            if totals["accepted"] else 1.0,
            "recall": round(totals["matched"] / totals["expected"], 4)
            if totals["expected"] else 1.0,
            "date_coverage": round(totals["date_hits"] / totals["dates"], 4)
            if totals["dates"] else 1.0,
            "false_positive_roles": totals["false_positives"],
            "zero_role_failures": totals["zero_role_failure"],
            "schema_errors": totals["schema_errors"],
            "career_journey_successes": totals["career_journey_success"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--baseline-head", action="store_true")
    parser.add_argument("--postgres", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    validator = baseline_validator() if args.baseline_head else validate_interpretation
    if args.postgres:
        if not os.environ.get("DATABASE_URL", "").startswith(
                "postgresql://enter:enter@127.0.0.1:5433/enter"):
            raise SystemExit("Only the local PostgreSQL test server is permitted")
        from django.contrib.auth.models import User
        from django.test.utils import setup_databases, teardown_databases
        from talent.employment_reconciliation import reconcile_employment
        from talent.models import CandidateProfile
        from talent.serializers import CandidateProfileSerializer

        database_config = setup_databases(verbosity=0, interactive=False)
    groups = defaultdict(list)
    try:
        for index, case in enumerate(fixture_cases()):
            content, filename = source_document(case)
            parsed = parse_resume(BytesIO(content), filename)
            text = parsed["raw_text"]
            try:
                validated = validator(
                    response(case, text), text, parsed.get("_evidence_views"))
                accepted = trusted_rows(validated)
                schema_errors = 0
            except Exception:
                accepted = []
                schema_errors = 1
            result = score(case, accepted)
            result["schema_errors"] = schema_errors
            if args.postgres:
                user = User.objects.create_user(username=f"fictional-general-{index}")
                profile = CandidateProfile.objects.create(
                    user=user, full_name="Fictional Benchmark",
                    email=f"fictional-general-{index}@example.invalid",
                )
                reconcile_employment(profile, accepted)
                profile.refresh_from_db()
                visible = CandidateProfileSerializer(profile).data["work_experiences"]
                saved_result = score(case, visible)
                result["career_journey_success"] = int(
                    saved_result["matched"] == saved_result["expected"]
                    and not saved_result["false_positives"])
            else:
                result["career_journey_success"] = None
            groups[category(case)].append(result)
    finally:
        if args.postgres:
            teardown_databases(database_config, verbosity=0)
    report = {"mode": "fictional_offline_mocked_proposals", "paid_calls": 0,
              "postgres_profile_serialization": args.postgres,
              "runtime": {
                  "elapsed_seconds": round(time.perf_counter() - started, 3),
                  "peak_process_rss_mib": round(
                      resource.getrusage(resource.RUSAGE_SELF).ru_maxrss /
                      (1024 * 1024 if platform.system() == "Darwin" else 1024), 1),
              },
              "overall": summarize([item for rows in groups.values() for item in rows]),
              "categories": {name: summarize(rows) for name, rows in sorted(groups.items())}}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
