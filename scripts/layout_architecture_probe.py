"""Offline fictional PDF layout experiment; no candidate files or provider requests."""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import statistics
import sys
import time
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["RESUME_AI_ENABLED"] = "false"
os.environ["RESUME_LOCAL_OCR_ENABLED"] = "false"

import django  # noqa: E402

django.setup()

from talent.candidate_experience import resume_identity_issue  # noqa: E402
from talent.resume_understanding import validate_interpretation  # noqa: E402
from talent.services import parse_resume  # noqa: E402


def pdf_bytes(items, grid=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})
    })
    commands = ["BT", "/F1 10 Tf"]
    for x, y, value in items:
        escaped = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.extend((f"1 0 0 1 {x} {y} Tm", f"({escaped}) Tj"))
    commands.append("ET")
    if grid:
        commands.extend(("0.5 w", *(f"{x} 610 m {x} 700 l S" for x in (50, 240, 420, 570)),
                         *(f"50 {y} m 570 {y} l S" for y in (610, 640, 670, 700))))
    stream = DecodedStreamObject()
    stream.set_data("\n".join(commands).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def cases():
    for number in range(10):
        company_a, company_b = f"Fictional Atlas {number}", f"Example Cedar {number}"
        role_a = ("Platform Engineer", "Software Developer", "Data Analyst",
                  "Product Designer", "Research Engineer")[number % 5]
        role_b = ("Engineering Manager", "Lead Developer", "Senior Analyst",
                  "Design Manager", "Research Lead")[number % 5]
        roles = [(company_a, role_a, "Jan 2020", "Dec 2021"),
                 (company_b, role_b, "Jan 2022", "Dec 2024")]
        x_shift, y_shift = (number % 3) * 3, (number % 3) * 2
        heading = ("WORK EXPERIENCE", "EMPLOYMENT HISTORY",
                   "PROFESSIONAL EXPERIENCE")[number % 3]
        stacked = [(55 + x_shift, 740, heading)]
        for index, (company, role, start, end) in enumerate(roles):
            stacked.append((55 + x_shift, 705 - index * 35 + y_shift,
                            f"{role} | {company} | {start} - {end}"))
        yield f"stacked-{number}", "stacked", pdf_bytes(stacked), roles, []

        column = [(50, 740, "SKILLS"), (50, 710, "Python and PostgreSQL"),
                  (320 + x_shift, 740, heading)]
        for index, (company, role, start, end) in enumerate(roles):
            column.append((320 + x_shift, 705 - index * 35 + y_shift,
                           f"{role} | {company} | {start} - {end}"))
        yield f"columns-{number}", "columns", pdf_bytes(column), roles, []

        table = [(58 + x_shift, 680 + y_shift, company_a),
                 (248 + x_shift, 680 + y_shift, role_a),
                 (428 + x_shift, 680 + y_shift, "Jan 2020 - Dec 2021"),
                 (58 + x_shift, 650 + y_shift, company_b),
                 (248 + x_shift, 650 + y_shift, role_b),
                 (428 + x_shift, 650 + y_shift, "Jan 2022 - Dec 2024")]
        false_role = (company_a, role_b, "Jan 2022", "Dec 2024")
        yield f"ruled-{number}", "ruled_table", pdf_bytes(table, grid=True), roles, [false_role]
        yield f"unruled-{number}", "unruled_table", pdf_bytes(table), roles, [false_role]

        unrelated = [(50, 740, "PROJECTS"), (50, 705, company_a),
                     (320 + x_shift, 740, heading),
                     (320 + x_shift, 705, f"{role_a} | Jan 2020 - Dec 2021")]
        fake = (company_a, role_a, "Jan 2020", "Dec 2021")
        yield f"cross-{number}", "cross_column_negative", pdf_bytes(unrelated), [], [fake]

        promotion = [(55, 740, "WORK EXPERIENCE"),
                     (55, 705, company_a),
                     (55, 680, "Junior Engineer | Jan 2020 - Dec 2021"),
                     (55, 650, "Senior Engineer | Jan 2022 - Dec 2024")]
        yield f"promotion-{number}", "promotions", pdf_bytes(promotion), [
            (company_a, "Junior Engineer", "Jan 2020", "Dec 2021"),
            (company_a, "Senior Engineer", "Jan 2022", "Dec 2024"),
        ], []

        overlaps = [(55, 740, "EMPLOYMENT HISTORY"),
                    (55, 705, f"Platform Engineer | {company_a} | Jan 2020 - Dec 2022"),
                    (55, 675, f"Consultant | {company_b} | Jun 2021 - Dec 2023")]
        yield f"overlap-{number}", "overlaps", pdf_bytes(overlaps), [
            (company_a, "Platform Engineer", "Jan 2020", "Dec 2022"),
            (company_b, "Consultant", "Jun 2021", "Dec 2023"),
        ], []

        undated = [(55, 740, "WORK EXPERIENCE"),
                   (58 + x_shift, 680, company_a), (248 + x_shift, 680, role_a),
                   (58 + x_shift, 650, company_b), (248 + x_shift, 650, role_b)]
        yield f"undated-{number}", "undated_table", pdf_bytes(undated), [
            (company_a, role_a, None, None),
            (company_b, role_b, None, None),
        ], [(company_a, role_b, None, None)]

        partial = [(55, 740, "WORK EXPERIENCE"),
                   (58 + x_shift, 680, company_a), (248 + x_shift, 680, role_a),
                   (428 + x_shift, 680, "2020 - 2021"),
                   (58 + x_shift, 650, company_b), (248 + x_shift, 650, role_b),
                   (428 + x_shift, 650, "2022 - Present")]
        yield f"partial-{number}", "partial_dates_table", pdf_bytes(partial), [
            (company_a, role_a, "2020", "2021"),
            (company_b, role_b, "2022", "Present"),
        ], [(company_a, role_b, "2022", "Present")]

        bleed = [(50, 740, "PROJECTS"), (320, 740, "WORK EXPERIENCE"),
                 (50, 705, company_a),
                 (320 + x_shift, 705, f"{role_a} | Jan 2020 - Dec 2021"),
                 (50, 675, company_b),
                 (320 + x_shift, 675, f"{role_b} | Jan 2022 - Dec 2024")]
        yield f"bleed-{number}", "section_bleed_negative", pdf_bytes(bleed), [], roles

        mixed = table + [(55, 570, "WORK EXPERIENCE"),
                         (55, 545, "Analyst | Fictional Harbor | Jan 2018 - Dec 2019")]
        yield f"mixed-{number}", "mixed_table_and_flow", pdf_bytes(mixed, grid=True), [
            *roles, ("Fictional Harbor", "Analyst", "Jan 2018", "Dec 2019"),
        ], [false_role]

        long = [(55, 760, "EMPLOYMENT HISTORY")]
        long_roles = []
        for index in range(4):
            employer = f"Sample Studio {number} {index}"
            title = f"Engineer Level {index + 1}"
            start, end = f"Jan {2016 + index * 2}", f"Dec {2017 + index * 2}"
            long.append((55, 725 - index * 30,
                         f"{title} | {employer} | {start} - {end}"))
            long_roles.append((employer, title, start, end))
        yield f"long-{number}", "long_history", pdf_bytes(long), long_roles, []


def proposal(roles):
    empty = {"value": None, "evidence": ""}
    return {
        "full_name": empty, "location": empty, "professional_title": empty,
        "professional_summary": empty, "standout_signal": empty,
        "education": [], "skills": [],
        "work_experiences": [{
            "company": company, "role": role, "start": start, "end": end,
            "employment_type": None, "location": None,
            "employer_evidence": company,
            "role_evidence": " | ".join(part for part in
                                        (role, company,
                                         f"{start} - {end}" if start and end else "")
                                        if part),
            "details": "", "achievements": [],
        } for company, role, start, end in roles],
    }


def identity_cases():
    """Fictional identity layouts; document contact and account contact can differ."""
    profile = SimpleNamespace(
        full_name="Asha Rao", email_verified_at=True,
        user=SimpleNamespace(email="verified@example.test"),
    )
    samples = (
        ("name-header", ["Asha Rao", "different@example.test"], None),
        ("title-header", ["Platform Engineer", "different@example.test"], "identity_unverified"),
        ("verified-email", ["Platform Engineer", "verified@example.test"], None),
        ("ambiguous-other-name", ["Other Person", "verified@example.test"],
         "identity_unverified"),
        ("explicit-other-name", ["Name: Other Person", "verified@example.test"],
         "identity_mismatch"),
        ("unrelated-reference", ["Asha Rao", "REFERENCES", "Other Person"], None),
    )
    results = []
    for label, lines, expected in samples:
        payload = pdf_bytes([(55, 740 - index * 25, line)
                             for index, line in enumerate(lines)])
        began = time.perf_counter()
        parsed = parse_resume(BytesIO(payload), label + ".pdf")
        actual = resume_identity_issue(SimpleNamespace(version=2, extracted_data=parsed), profile)
        results.append({"case": label, "passed": actual == expected,
                        "result": actual or "verified",
                        "elapsed_ms": round((time.perf_counter() - began) * 1000, 2)})
    return results


def run(mode):
    category = {}
    timings = []
    for name, kind, payload, expected, traps in cases():
        began = time.perf_counter()
        parsed = parse_resume(BytesIO(payload), name + ".pdf")
        views = parsed.get("_evidence_views") or []
        if mode == "baseline":
            # Reconstruct the previous validation authority on the same source
            # views. The full-page views were safe only on single-column pages.
            columns = bool(parsed['_document_layout'].get('columns'))
            views = [{**view, 'validation_safe': (
                view['method'] not in {'primary', 'pdfplumber', 'poppler'} or not columns
            )} for view in views if view['method'] in {
                'primary', 'pdfplumber', 'poppler',
                'pdfplumber_left', 'pdfplumber_right',
            }]
        result = validate_interpretation(
            proposal(expected + traps), parsed["raw_text"], views,
        )
        elapsed = (time.perf_counter() - began) * 1000
        timings.append(elapsed)
        actual = {(row["company"], row["role"]) for row in result["work_experiences"]}
        truth = {(company, role) for company, role, _, _ in expected}
        expected_dates = {(company, role): tuple(value for value in (start, end) if value)
                          for company, role, start, end in expected}
        supported_dates = sum(
            sum(label in row["date_label"] for label in expected_dates[key])
            for row in result["work_experiences"]
            if (key := (row["company"], row["role"])) in expected_dates
        )
        bucket = category.setdefault(kind, {"documents": 0, "expected_roles": 0,
                                            "true_roles": 0, "false_associations": 0,
                                            "expected_date_endpoints": 0,
                                            "supported_date_endpoints": 0,
                                            "latencies_ms": []})
        bucket["documents"] += 1
        bucket["expected_roles"] += len(truth)
        bucket["true_roles"] += len(actual & truth)
        bucket["false_associations"] += len(actual - truth)
        bucket["expected_date_endpoints"] += sum(len(dates) for dates in expected_dates.values())
        bucket["supported_date_endpoints"] += supported_dates
        bucket["latencies_ms"].append(elapsed)
    for bucket in category.values():
        bucket["median_ms"] = round(statistics.median(bucket.pop("latencies_ms")), 2)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "mode": mode, "fictional_documents": sum(row["documents"] for row in category.values()),
        "paid_calls": 0, "categories": category,
        "median_document_ms": round(statistics.median(timings), 2),
        "p95_document_ms": round(sorted(timings)[int(len(timings) * .95) - 1], 2),
        "peak_process_rss_mib": round(rss / (1024 * 1024 if platform.system() == "Darwin"
                                              else 1024), 1),
        "identity_cases": identity_cases(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("baseline", "integrated"), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = run(args.mode)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
