"""Fictional documents only; never access candidate resume storage."""

from io import BytesIO

from django.test import override_settings
from PIL import Image, ImageDraw
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from talent import services
from talent.document_evidence import pdf_views
from talent.resume_understanding import (
    revalidate_cached_interpretation,
    validate_interpretation,
)


def pdf_bytes(lines, *, columns=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({
        NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica'),
    })
    page[NameObject('/Resources')] = DictionaryObject({
        NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})
    })
    commands = ['BT', '/F1 10 Tf']
    for index, line in enumerate(lines):
        x = 50 if not columns or index < 2 else 310
        row = index if not columns or index < 2 else index - 2
        escaped = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        commands.extend([f'1 0 0 1 {x} {740 - row * 24} Tm', f'({escaped}) Tj'])
    commands.append('ET')
    stream = DecodedStreamObject()
    stream.set_data('\n'.join(commands).encode('latin-1'))
    page[NameObject('/Contents')] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _response(lines):
    facts = []
    for company, role, start, end in lines:
        quote = f'{role} | {company} | {start} - {end}'
        facts.append({
            'company': company, 'role': role, 'start': start, 'end': end,
            'employment_type': None, 'location': None,
            'employer_evidence': quote, 'role_evidence': quote,
            'details': '', 'achievements': [],
        })
    empty = {'value': None, 'evidence': ''}
    return {
        'full_name': empty, 'location': empty, 'professional_title': empty,
        'professional_summary': empty, 'work_experiences': facts,
        'skills': [], 'standout_signal': empty, 'education': [],
    }


def test_five_role_pdf_recovers_evidence_when_primary_text_loses_words(monkeypatch):
    jobs = [
        ('Fictional Studio', 'Software Intern', 'Jan 2020', 'Jun 2020'),
        ('Imaginary Labs', 'Backend Engineer', 'Jul 2020', 'Dec 2021'),
        ('Sample Systems', 'Senior Engineer', 'Jan 2022', 'Dec 2022'),
        ('Invented Works', 'Engineering Lead', 'Jan 2023', 'Dec 2023'),
        ('Example Cloud', 'Platform Manager', 'Jan 2024', 'Dec 2024'),
    ]
    content = pdf_bytes(['WORK EXPERIENCE', *(
        f'{role} | {company} | {start} - {end}'
        for company, role, start, end in jobs)])
    broken = 'WORK EXPERIENCE\n' + '\n'.join(
        f'{role[:2]} ... {company[:2]} ... {start} - {end}'
        for company, role, start, end in jobs)
    monkeypatch.setattr(services, 'extract_text', lambda *_args: broken)
    monkeypatch.setattr(services, '_poppler_pdf_text', lambda *_args: '')
    parsed = services.parse_resume(BytesIO(content), 'fictional.pdf')
    payload = _response(jobs)
    before = validate_interpretation(payload, broken)
    after = validate_interpretation(payload, parsed['raw_text'], parsed['_evidence_views'])
    assert len(before['work_experiences']) == 0
    assert len(after['work_experiences']) == 5
    assert [row['date_label'] for row in after['work_experiences']] == [
        f'{start} — {end}' for _, _, start, end in jobs]
    assert parsed['_document_layout']['selected_method'] == 'pdfplumber'
    assert parsed['_employment_parse']['complete_for_archival'] is False
    assert all(row['_evidence_location']['page'] == 1
               for row in after['work_experiences'])
    offline = revalidate_cached_interpretation(
        parsed, {'_interpretation': {'source': 'ai'}, '_evidence': payload})
    assert offline['_interpretation']['source'] == 'ai_cached'
    assert len(offline['work_experiences']) == 5


def test_separate_views_cannot_manufacture_role_association():
    payload = _response([('Example Studio', 'Backend Engineer', 'Jan 2020', 'Dec 2021')])
    views = [
        {'method': 'primary', 'text': 'Example Studio\nJan 2020 - Dec 2021', 'blocks': []},
        {'method': 'pdfplumber', 'text': 'Backend Engineer\nJan 2020 - Dec 2021',
         'blocks': []},
    ]
    result = validate_interpretation(payload, views[0]['text'], views)
    assert result['work_experiences'] == []


def test_column_scopes_do_not_join_employer_and_role():
    content = pdf_bytes([
        'Example Studio', 'Other content',
        'Backend Engineer | Jan 2020 - Dec 2021', 'Other content',
    ], columns=True)
    views, layout = pdf_views(BytesIO(content), 'Example Studio\nBackend Engineer')
    assert layout['columns'] == 1
    payload = _response([('Example Studio', 'Backend Engineer', 'Jan 2020', 'Dec 2021')])
    result = validate_interpretation(payload, views[0]['text'], views)
    assert result['work_experiences'] == []


def test_adjacent_layout_blocks_recover_quote_formatting_without_inventing_values():
    content = pdf_bytes([
        'WORK EXPERIENCE', 'Fictional Layout Works | Jan 2020 - Dec 2022',
        'Platform Engineer | Bengaluru', 'SKILLS', 'Python',
    ])
    parsed = services.parse_resume(BytesIO(content), 'fictional-layout.pdf')
    proposal = _response([(
        'Fictional Layout Works', 'Platform Engineer', 'Jan 2020', 'Dec 2022')])
    proposal['work_experiences'][0]['employer_evidence'] = (
        'Fictional Layout Works Jan 2020 - Dec 2022')
    proposal['work_experiences'][0]['role_evidence'] = 'Platform Engineer Bengaluru'
    result = validate_interpretation(proposal, parsed['raw_text'], parsed['_evidence_views'])
    assert len(result['work_experiences']) == 1
    assert result['work_experiences'][0]['date_label'] == 'Jan 2020 — Dec 2022'


def test_layout_recovery_cannot_borrow_from_projects_or_across_sections():
    content = pdf_bytes([
        'PROJECTS', 'Fictional Layout Works | Jan 2020 - Dec 2022',
        'Platform Engineer | Bengaluru', 'WORK EXPERIENCE',
        'Other Studio | Jan 2021 - Dec 2023', 'Analyst | Remote',
    ])
    parsed = services.parse_resume(BytesIO(content), 'fictional-project.pdf')
    proposal = _response([(
        'Fictional Layout Works', 'Platform Engineer', 'Jan 2020', 'Dec 2022')])
    proposal['work_experiences'][0]['employer_evidence'] = 'Fictional Layout Works Jan 2020'
    proposal['work_experiences'][0]['role_evidence'] = 'Platform Engineer Bengaluru'
    result = validate_interpretation(proposal, parsed['raw_text'], parsed['_evidence_views'])
    assert result['work_experiences'] == []


def test_layout_recovery_does_not_turn_employer_name_into_a_role():
    content = pdf_bytes(['WORK EXPERIENCE', 'Engineer Labs | Jan 2020 - Dec 2022'])
    parsed = services.parse_resume(BytesIO(content), 'fictional-employer-only.pdf')
    proposal = _response([('Engineer Labs', 'Engineer', 'Jan 2020', 'Dec 2022')])
    proposal['work_experiences'][0]['employer_evidence'] = 'Engineer Labs Jan 2020'
    proposal['work_experiences'][0]['role_evidence'] = 'Engineer Jan 2020'
    result = validate_interpretation(proposal, parsed['raw_text'], parsed['_evidence_views'])
    assert result['work_experiences'] == []


def test_image_only_resume_is_not_classified_as_a_fresher():
    image = Image.new('RGB', (900, 220), 'white')
    ImageDraw.Draw(image).text(
        (20, 60), 'Engineer | Fictional Co | Jan 2020 - Dec 2021', fill='black')
    content = BytesIO()
    image.save(content, format='PDF')
    with override_settings(RESUME_LOCAL_OCR_ENABLED=False):
        parsed = services.parse_resume(BytesIO(content.getvalue()), 'fictional-scan.pdf')
    assert parsed['work_experiences'] == []
    assert parsed['_employment_parse']['ocr_required'] is True
    assert parsed['_employment_parse']['explicit_no_employment'] is False
    assert parsed['_employment_parse']['complete_for_archival'] is False
