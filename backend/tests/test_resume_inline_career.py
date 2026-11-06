from io import BytesIO

from talent.services import parse_resume


def test_inline_career_preserves_promotions_and_sentence_boundaries():
    text = '''Example Candidate
WORK EXPERIENCE 6+ years in product management
SENIOR PRODUCT MANAGER – R&D – Example.ai (Canada) – June 2025 – Present
Own product strategy.
PRODUCT MANAGER – R&D – Example.ai (Canada) – Aug 2023 – May 2025
Delivered research
projects.
SENIOR PATENT RESEARCH ANALYST – Example Pvt. Ltd. (India) – May 2022 – Jul 2023
Supported clients.
PATENT RESEARCH ANALYST – Example Pvt. Ltd. (India) – Oct 2020 – Apr 2022
Conducted analysis.
JUNIOR PATENT RESEARCH ANALYST – Example Pvt. Ltd. (India) – Aug 2019 – Sep 2020
EDUCATION
Bachelor of Technology
'''
    result = parse_resume(BytesIO(text.encode()), 'resume.txt')
    rows = result['work_experiences']
    assert len(rows) == 5
    assert [(r['start_date'], r['end_date']) for r in rows] == [
        ('2025-06-01', None), ('2023-08-01', '2025-05-01'),
        ('2022-05-01', '2023-07-01'), ('2020-10-01', '2022-04-01'),
        ('2019-08-01', '2020-09-01'),
    ]
    assert rows[0]['role'] == 'SENIOR PRODUCT MANAGER – R&D'
    assert rows[0]['company'] == 'Example.ai (Canada)'
    assert rows[-1]['company'] == 'Example Pvt. Ltd. (India)'
    assert rows[0]['is_current']
    assert result['total_experience'] == 6


def test_pdf_split_dates_and_embedded_profile_link():
    from unittest.mock import patch

    from pypdf import PdfReader, PdfWriter
    from pypdf.annotations import Link

    from .test_document_evidence import pdf_bytes

    text = """Example Candidate
PROFESSIONAL EXPERIENCE
02/2026 EngineeringManager,EXAMPLE SYSTEMS,Delhi
01/2025 Managed engineering delivery.
04/2024 TechLead,EXAMPLE LABS,Gurgaon
03/2022 Delivered products.
EDUCATION
2015 Bachelor of Technology
"""
    writer = PdfWriter()
    writer.append(PdfReader(BytesIO(pdf_bytes(text.splitlines()))))
    writer.add_annotation(0, Link(rect=(50, 750, 150, 765),
                                 url='https://www.linkedin.com/in/example-candidate/'))
    output = BytesIO()
    writer.write(output)
    with patch('talent.document_evidence.pdf_views', return_value=([], {})):
        result = parse_resume(output, 'resume.pdf')
    assert result['linkedin_url'] == 'https://www.linkedin.com/in/example-candidate/'
    assert [(r['company'], r['start_date'], r['end_date'])
            for r in result['work_experiences']] == [
        ('EXAMPLE SYSTEMS', '2025-01-01', '2026-02-01'),
        ('EXAMPLE LABS', '2022-03-01', '2024-04-01'),
    ]
