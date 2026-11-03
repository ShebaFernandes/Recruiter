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


@pytest.mark.parametrize("columns", [1, 2])
def test_layout_table_preserves_employment_paragraphs(columns):
    document = Document()
    document.add_paragraph("Name: Fictional Candidate")
    table = document.add_table(rows=1, cols=columns)
    if columns == 2:
        table.cell(0, 0).text = "CONTACT\nfictional@example.com"
    cell = table.cell(0, columns - 1)
    for line in [
        "PROFESSIONAL EXPERIENCE",
        "Senior Software Engineer at Cedar Software",
        "Jan 2021 - Present",
        "Built payment systems that reduced processing time by 30%.",
    ]:
        cell.add_paragraph(line)
    output = BytesIO()
    document.save(output)
    parsed = parse_resume(BytesIO(output.getvalue()), "layout.docx")
    assert parsed["headline"] == "Senior Software Engineer"
    assert len(parsed["work_experiences"]) == 1
    role = parsed["work_experiences"][0]
    assert role["role"] == "Senior Software Engineer"
    assert role["company"] == "Cedar Software"
    assert role["start_date"] == "2021-01-01"
    assert role["end_date"] is None
    assert parsed["standout_signal"] == (
        "Built payment systems that reduced processing time by 30%."
    )


@pytest.mark.parametrize("extension", ["pdf", "docx"])
def test_summary_heading_and_bullet_achievement_keep_source_facts(extension):
    summary = "Senior engineer with experience building reliable payment platforms."
    achievement = "Reduced payment processing time by 30% through queue optimisation."
    lines = [
        "Name: Fictional Candidate", "PROFESSIONAL SUMMARY", summary,
        "PROFESSIONAL EXPERIENCE", "Senior Software Engineer at Cedar Software",
        "Jan 2021 - Present", "- " + achievement,
        "EDUCATION", "Example University",
    ]
    parsed = parse_resume(BytesIO(_fixture_bytes(extension, lines)), f"sample.{extension}")
    assert parsed["summary"] == summary
    assert parsed["standout_signal"] == achievement
    assert parsed["headline"] == "Senior Software Engineer"
    assert len(parsed["work_experiences"]) == 1


@pytest.mark.parametrize("extension", ["pdf", "docx"])
def test_letter_spaced_sections_and_title_date_before_employer(extension):
    lines = [
        "Name: Fictional Candidate", "S U M M A R Y S T A T E M E N T",
        "Operations leader with experience improving service delivery.",
        "PROFILE HIGHLIGHTS", "- Developed a training platform that reduced",
        "onboarding time by 40% across service teams.", "E X P E R I E N C E",
        "Senior Operations Manager          January 2025- Present", "Cedar Services",
        "Managed service operations.",
        "Assistant Manager          April 2020- January 2025", "Maple Systems",
        "Team Lead          December 2016- April 2020", "Orchid Software",
        "Mentor          March 2009- December 2016", "Pine Technologies",
        "E D U C A T I O N", "Example University",
    ]
    parsed = parse_resume(BytesIO(_fixture_bytes(extension, lines)), f"sample.{extension}")
    assert parsed["headline"] == "Senior Operations Manager"
    assert [row["company"] for row in parsed["work_experiences"]] == [
        "Cedar Services", "Maple Systems", "Orchid Software", "Pine Technologies",
    ]
    assert parsed["summary"].startswith("Operations leader")
    assert parsed["standout_signal"] == (
        "Developed a training platform that reduced onboarding time by 40% across service teams."
    )


@pytest.mark.parametrize("heading", [
    "EXPERIENCE", "PROFESSIONAL EXPERIENCE", "CAREER HISTORY",
    "SELECTED EXPERIENCE", "E X P E R I E N C E",
])
@pytest.mark.parametrize("dates", [
    "Jan 2021 - Present", "January 2021 - Current", "2021-01 - Present", "01/2021 - Present",
])
@pytest.mark.parametrize("layout", ["pipe", "at", "separate", "title_first", "employer_first"])
def test_hundred_pdf_structure_combinations(heading, dates, layout):
    role, company = "Senior Software Engineer", "Fictional Cedar Systems"
    layouts = {
        "pipe": [f"{role} | {company} | {dates}"],
        "at": [f"{role} at {company}", dates],
        "separate": [company, role, dates],
        "title_first": [f"{role}          {dates}", company],
        "employer_first": [f"{company}          {dates}", role],
    }
    achievement = "Reduced payment processing time by 30% through queue optimisation."
    lines = [
        "Name: Fictional Candidate", "PROFESSIONAL SUMMARY",
        "Senior engineer building reliable payment platforms.", heading,
        *layouts[layout], "- " + achievement, "EDUCATION", "Example University",
    ]
    parsed = parse_resume(BytesIO(_fixture_bytes("pdf", lines)), "fictional.pdf")
    assert parsed["headline"] == role
    assert parsed["summary"] == "Senior engineer building reliable payment platforms."
    assert parsed["standout_signal"] == achievement
    assert len(parsed["work_experiences"]) == 1
    job = parsed["work_experiences"][0]
    assert (job["company"], job["role"]) == (company, role)
    assert job["start_date"] == "2021-01-01"
    assert job["end_date"] is None
    assert job["is_current"]
