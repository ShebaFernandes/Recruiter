"""Privacy-safe fictional PDF/DOCX fixtures for resume reliability regression."""

from io import BytesIO

import pytest
from docx import Document
from talent.services import parse_resume

from .test_candidate_flow import resume_pdf


def _document_bytes(lines):
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def _fixture_bytes(extension, lines):
    return resume_pdf(lines) if extension == "pdf" else _document_bytes(lines)


@pytest.mark.parametrize(
    (
        "fixture_name",
        "extension",
        "lines",
        "expected_dates",
        "expected_current",
    ),
    [
        (
            "multi_employer_promotions",
            "docx",
            [
                "Name: Fictional Candidate",
                "PROFESSIONAL BACKGROUND",
                "Northstar Labs | Software Engineering Intern | Jun 2021 - Aug 2021",
                "Northstar Labs | Software Engineer | Sep 2021 - Dec 2023",
                "Maple Systems | Senior Software Engineer | Jan 2024 - Present",
                "EDUCATION",
                "Example University",
            ],
            [
                ("2021-06-01", "2021-08-01"),
                ("2021-09-01", "2023-12-01"),
                ("2024-01-01", None),
            ],
            1,
        ),
        (
            "table_based_internship",
            "pdf",
            [
                "Name: Fictional Candidate",
                "INTERNSHIP EXPERIENCE",
                "Orchid Analytics | Data Analyst Intern | May 2022 - Jul 2022",
                "EDUCATION",
                "Example University",
            ],
            [("2022-05-01", "2022-07-01")],
            0,
        ),
        (
            "undated_supported_role",
            "docx",
            [
                "Name: Fictional Candidate",
                "RELEVANT EXPERIENCE",
                "Junior Developer at Cedar Software",
                "PROJECTS",
                "Personal Project | Search prototype | 2025",
            ],
            [(None, None)],
            0,
        ),
        (
            "explicit_fresher_projects_only",
            "pdf",
            [
                "Name: Fictional Student",
                "Fresher seeking first role",
                "PROJECTS",
                "Personal Project | Recommendation Engine | 2025",
                "EDUCATION",
                "Example University",
            ],
            [],
            0,
        ),
    ],
)
def test_fictional_resume_fixture_matrix(
    fixture_name, extension, lines, expected_dates, expected_current
):
    del fixture_name
    parsed = parse_resume(
        BytesIO(_fixture_bytes(extension, lines)),
        f"fictional.{extension}",
    )

    assert [
        (row["start_date"], row["end_date"])
        for row in parsed["work_experiences"]
    ] == expected_dates
    assert sum(bool(row["is_current"]) for row in parsed["work_experiences"]) == expected_current
    assert all(row["company"] and row["role"] for row in parsed["work_experiences"])
    assert not any(
        row["role"].casefold() == "personal project"
        for row in parsed["work_experiences"]
    )
