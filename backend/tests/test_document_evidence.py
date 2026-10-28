"""Fictional documents only; never access candidate resume storage."""

from io import BytesIO

import pytest
from django.test import override_settings
from docx import Document
from PIL import Image, ImageDraw
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from talent import services
from talent.document_evidence import pdf_views
from talent.models import CandidateProfile, WorkExperience
from talent.resume_processing import _employment_outcome
from talent.resume_understanding import (
    revalidate_cached_interpretation,
    understand_resume,
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


def positioned_pdf_bytes(items, *, ruled=False):
    """Fictional aligned cells, optionally enclosed by visible table lines."""
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
    for x, y, value in items:
        escaped = value.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        commands.extend((f'1 0 0 1 {x} {y} Tm', f'({escaped}) Tj'))
    commands.append('ET')
    if ruled:
        commands.extend(('0.5 w',
                         *(f'{x} 610 m {x} 700 l S' for x in (50, 240, 420, 570)),
                         *(f'50 {y} m 570 {y} l S' for y in (610, 640, 670, 700))))
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


def test_qualified_employment_heading_and_split_docx_blocks_recover_source_evidence():
    document = Document()
    for line in (
        'EXPERIENCE & LEADERSHIP', 'Fictional', 'Cedar Systems',
        'Platform', 'Engineer', 'Jan 2020 - Dec 2022',
        'PROJECTS', 'Unrelated Name built a prototype',
    ):
        document.add_paragraph(line)
    output = BytesIO()
    document.save(output)
    parsed = services.parse_resume(BytesIO(output.getvalue()), 'fictional-split.docx')
    proposal = _response([('Fictional Cedar Systems', 'Platform Engineer',
                           'Jan 2020', 'Dec 2022')])
    proposal['work_experiences'][0]['employer_evidence'] = 'Fictional Cedar Systems'
    proposal['work_experiences'][0]['role_evidence'] = (
        'Platform Engineer Jan 2020 - Dec 2022')
    result = validate_interpretation(proposal, parsed['raw_text'], parsed['_evidence_views'])
    assert len(result['work_experiences']) == 1
    assert result['work_experiences'][0]['date_label'] == 'Jan 2020 — Dec 2022'


def test_missing_heading_allows_only_nearby_same_entry_blocks():
    document = Document()
    for line in (
        'Fictional Cedar Systems | Jan 2020 - Dec 2022',
        'Platform Engineer',
        'Other Labs | Jan 2023 - Dec 2024',
        'Data Analyst',
    ):
        document.add_paragraph(line)
    output = BytesIO()
    document.save(output)
    parsed = services.parse_resume(BytesIO(output.getvalue()), 'fictional-unheaded.docx')
    proposal = _response([
        ('Fictional Cedar Systems', 'Platform Engineer', 'Jan 2020', 'Dec 2022'),
        ('Other Labs', 'Data Analyst', 'Jan 2023', 'Dec 2024'),
    ])
    for row in proposal['work_experiences']:
        row['employer_evidence'] = row['company']
        row['role_evidence'] = row['role']
    result = validate_interpretation(proposal, parsed['raw_text'], parsed['_evidence_views'])
    assert {(row['company'], row['role']) for row in result['work_experiences']} == {
        ('Fictional Cedar Systems', 'Platform Engineer'),
        ('Other Labs', 'Data Analyst'),
    }


def test_unrelated_employer_between_blocks_is_not_borrowed():
    document = Document()
    for line in (
        'EMPLOYMENT HISTORY', 'Fictional Cedar Systems',
        'Other Labs', 'Platform Engineer | Jan 2020 - Dec 2022',
    ):
        document.add_paragraph(line)
    output = BytesIO()
    document.save(output)
    parsed = services.parse_resume(BytesIO(output.getvalue()), 'fictional-adversarial.docx')
    proposal = _response([
        ('Fictional Cedar Systems', 'Platform Engineer', 'Jan 2020', 'Dec 2022'),
        ('Other Labs', 'Data Analyst', 'Jan 2020', 'Dec 2022'),
    ])
    for row in proposal['work_experiences']:
        row['employer_evidence'] = row['company'] + ' Jan 2020'
        row['role_evidence'] = row['role'] + ' Dec 2022'
    result = validate_interpretation(proposal, parsed['raw_text'], parsed['_evidence_views'])
    assert result['work_experiences'] == []


def test_distant_pdf_fragments_do_not_form_an_employment_entry():
    content = pdf_bytes([
        'Platform Engineer', 'Profile summary', 'Projects',
        'Built a fictional prototype', 'Education', 'Example University',
        'Fictional Cedar Systems | Jan 2020 - Dec 2022',
    ])
    parsed = services.parse_resume(BytesIO(content), 'fictional-distant.pdf')
    proposal = _response([(
        'Fictional Cedar Systems', 'Platform Engineer', 'Jan 2020', 'Dec 2022')])
    proposal['work_experiences'][0]['employer_evidence'] = 'Fictional Cedar Systems Jan 2020'
    proposal['work_experiences'][0]['role_evidence'] = 'Platform Engineer Jan 2020'
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
    assert _employment_outcome(parsed)['reason_code'] == 'unsupported_scan_ocr_disabled'


def test_nonaligned_borderless_rows_preserve_uncertainty_instead_of_joining_cells():
    cells = [(55, 740, 'WORK EXPERIENCE'),
             (58, 680, 'Fictional Atlas'), (248, 680, 'Platform Engineer'),
             (428, 680, 'Jan 2020 - Dec 2021'),
             (88, 650, 'Example Cedar'), (278, 650, 'Engineering Manager'),
             (458, 650, 'Jan 2022 - Dec 2024')]
    parsed = services.parse_resume(BytesIO(positioned_pdf_bytes(cells)), 'nonaligned.pdf')
    proposal = _response([
        ('Fictional Atlas', 'Platform Engineer', 'Jan 2020', 'Dec 2021'),
        ('Example Cedar', 'Engineering Manager', 'Jan 2022', 'Dec 2024'),
        ('Fictional Atlas', 'Engineering Manager', 'Jan 2022', 'Dec 2024'),
    ])
    result = validate_interpretation(proposal, parsed['raw_text'], parsed['_evidence_views'])
    assert {(row['company'], row['role']) for row in result['work_experiences']} == {
        ('Fictional Atlas', 'Platform Engineer'),
        ('Example Cedar', 'Engineering Manager'),
    }
    assert parsed['_document_layout']['layout_uncertain'] is True
    assert parsed['_employment_parse']['complete_for_archival'] is False


def test_scrambled_primary_order_uses_positioned_view_without_false_association(monkeypatch):
    lines = ['WORK EXPERIENCE',
             'Platform Engineer | Fictional Atlas | Jan 2020 - Dec 2021',
             'Engineering Manager | Example Cedar | Jan 2022 - Dec 2024',
             'Consultant | Fictional Harbor | Jan 2018 - Dec 2019']
    monkeypatch.setattr(services, 'extract_text', lambda *_args: '\n'.join(reversed(lines)))
    parsed = services.parse_resume(BytesIO(pdf_bytes(lines)), 'scrambled.pdf')
    proposal = _response([
        ('Fictional Atlas', 'Platform Engineer', 'Jan 2020', 'Dec 2021'),
        ('Example Cedar', 'Engineering Manager', 'Jan 2022', 'Dec 2024'),
        ('Fictional Harbor', 'Consultant', 'Jan 2018', 'Dec 2019'),
        ('Fictional Atlas', 'Engineering Manager', 'Jan 2022', 'Dec 2024'),
    ])
    result = validate_interpretation(proposal, parsed['raw_text'], parsed['_evidence_views'])
    assert parsed['_document_layout']['text_layer_disordered'] is True
    assert parsed['_employment_parse']['complete_for_archival'] is False
    assert {(row['company'], row['role']) for row in result['work_experiences']} == {
        ('Fictional Atlas', 'Platform Engineer'),
        ('Example Cedar', 'Engineering Manager'),
        ('Fictional Harbor', 'Consultant'),
    }


@override_settings(RESUME_AI_ENABLED=False)
def test_uncertain_layout_rule_fallback_cannot_bypass_spatial_evidence():
    content = positioned_pdf_bytes([
        (55, 740, 'WORK EXPERIENCE'),
        (58, 680, 'Fictional Atlas'), (248, 680, 'Platform Engineer'),
        (428, 680, 'Jan 2020 - Dec 2021'),
        (88, 650, 'Example Cedar'), (278, 650, 'Engineering Manager'),
        (458, 650, 'Jan 2022 - Dec 2024'),
    ])
    parsed = services.parse_resume(BytesIO(content), 'uncertain-rules.pdf')
    parsed['work_experiences'] = [{
        'company': 'Fictional Atlas', 'role': 'Engineering Manager',
        'date_label': 'Jan 2022 — Dec 2024',
        'source_evidence': 'Fictional Atlas Engineering Manager Jan 2022 Dec 2024',
    }]
    result = understand_resume(parsed, lambda *_args: None, ai_allowed=False)
    assert result['work_experiences'] == []
    assert result['_employment_parse']['complete_for_archival'] is False


def test_ruled_and_borderless_rows_keep_employer_title_dates_together():
    jobs = [
        ('Fictional Atlas', 'Platform Engineer', 'Jan 2020', 'Dec 2021'),
        ('Example Cedar', 'Engineering Manager', 'Jan 2022', 'Dec 2024'),
    ]
    cells = [(58, 680, jobs[0][0]), (248, 680, jobs[0][1]),
             (428, 680, 'Jan 2020 - Dec 2021'),
             (58, 650, jobs[1][0]), (248, 650, jobs[1][1]),
             (428, 650, 'Jan 2022 - Dec 2024')]
    false_pair = ('Fictional Atlas', 'Engineering Manager', 'Jan 2022', 'Dec 2024')
    for ruled in (False, True):
        parsed = services.parse_resume(
            BytesIO(positioned_pdf_bytes(cells, ruled=ruled)), 'fictional-table.pdf')
        result = validate_interpretation(
            _response([*jobs, false_pair]), parsed['raw_text'], parsed['_evidence_views'])
        assert {(row['company'], row['role']) for row in result['work_experiences']} == {
            (company, role) for company, role, _, _ in jobs}
        assert {row['date_label'] for row in result['work_experiences']} == {
            f'{start} — {end}' for _, _, start, end in jobs}
        assert parsed['_document_layout']['table_rows'] >= 2
        assert all(row['_evidence_location']['page'] == 1
                   for row in result['work_experiences'])
        assert all(row['_evidence_location']['column'].startswith('p1:t')
                   for row in result['work_experiences'])
        assert len({row['_evidence_location']['entry_id']
                    for row in result['work_experiences']}) == 2


def test_table_scopes_preserve_non_table_role_and_reject_cross_row_pair():
    cells = [(58, 680, 'Fictional Atlas'), (248, 680, 'Platform Engineer'),
             (428, 680, 'Jan 2020 - Dec 2021'),
             (58, 650, 'Example Cedar'), (248, 650, 'Engineering Manager'),
             (428, 650, 'Jan 2022 - Dec 2024'),
             (55, 570, 'WORK EXPERIENCE'),
             (55, 545, 'Analyst | Fictional Harbor | Jan 2018 - Dec 2019')]
    expected = [
        ('Fictional Atlas', 'Platform Engineer', 'Jan 2020', 'Dec 2021'),
        ('Example Cedar', 'Engineering Manager', 'Jan 2022', 'Dec 2024'),
        ('Fictional Harbor', 'Analyst', 'Jan 2018', 'Dec 2019'),
    ]
    parsed = services.parse_resume(
        BytesIO(positioned_pdf_bytes(cells, ruled=True)), 'fictional-mixed.pdf')
    result = validate_interpretation(_response([
        *expected,
        ('Fictional Atlas', 'Engineering Manager', 'Jan 2022', 'Dec 2024'),
    ]), parsed['raw_text'], parsed['_evidence_views'])
    assert {(row['company'], row['role']) for row in result['work_experiences']} == {
        (company, role) for company, role, _, _ in expected}


def test_table_role_and_header_identity_remain_separate_supported_facts():
    cells = [(55, 760, 'Name: Asha Rao'), (55, 735, 'WORK EXPERIENCE'),
             (58, 680, 'Fictional Atlas'), (248, 680, 'Platform Engineer'),
             (428, 680, 'Jan 2020 - Dec 2021'),
             (58, 650, 'Example Cedar'), (248, 650, 'Engineering Manager'),
             (428, 650, 'Jan 2022 - Dec 2024')]
    jobs = [
        ('Fictional Atlas', 'Platform Engineer', 'Jan 2020', 'Dec 2021'),
        ('Example Cedar', 'Engineering Manager', 'Jan 2022', 'Dec 2024'),
    ]
    parsed = services.parse_resume(BytesIO(positioned_pdf_bytes(cells)), 'fictional-header.pdf')
    proposal = _response(jobs)
    proposal['full_name'] = {'value': 'Asha Rao', 'evidence': 'Name: Asha Rao'}
    result = validate_interpretation(proposal, parsed['raw_text'], parsed['_evidence_views'])
    assert result['full_name'] == 'Asha Rao'
    assert len(result['work_experiences']) == 2
    assert not any(item['category'] == 'profile.full_name_evidence'
                   for item in result['_validation_rejections'])


def test_undated_borderless_employment_is_partial_not_complete():
    cells = [(55, 740, 'WORK EXPERIENCE'),
             (58, 680, 'Fictional Atlas'), (248, 680, 'Platform Engineer'),
             (58, 650, 'Example Cedar'), (248, 650, 'Engineering Manager')]
    parsed = services.parse_resume(
        BytesIO(positioned_pdf_bytes(cells)), 'fictional-undated.pdf')
    proposal = _response([
        ('Fictional Atlas', 'Platform Engineer', None, None),
        ('Example Cedar', 'Engineering Manager', None, None),
    ])
    for fact in proposal['work_experiences']:
        fact['role_evidence'] = fact['role']
        fact['employer_evidence'] = fact['company']
    result = validate_interpretation(proposal, parsed['raw_text'], parsed['_evidence_views'])
    assert len(result['work_experiences']) == 2
    assert all(row['confidence_status'] == 'partial' for row in result['work_experiences'])
    assert parsed['_employment_parse']['complete_for_archival'] is False


def test_explicitly_unsafe_views_cannot_regain_authority_through_fallback():
    quote = 'Platform Engineer | Fictional Atlas | Jan 2020 - Dec 2021'
    result = validate_interpretation(
        _response([('Fictional Atlas', 'Platform Engineer', 'Jan 2020', 'Dec 2021')]),
        quote, [{'method': 'unsafe_flattened', 'text': quote, 'blocks': [],
                 'validation_safe': False}])
    assert result['work_experiences'] == []


def test_project_table_cannot_validate_invented_employment():
    cells = [(55, 740, 'PROJECTS'),
             (58, 680, 'Fictional Atlas'), (248, 680, 'Platform Engineer'),
             (428, 680, 'Jan 2020 - Dec 2021'),
             (58, 650, 'Example Cedar'), (248, 650, 'Engineering Manager'),
             (428, 650, 'Jan 2022 - Dec 2024')]
    fake_jobs = [
        ('Fictional Atlas', 'Platform Engineer', 'Jan 2020', 'Dec 2021'),
        ('Example Cedar', 'Engineering Manager', 'Jan 2022', 'Dec 2024'),
    ]
    for ruled in (False, True):
        parsed = services.parse_resume(
            BytesIO(positioned_pdf_bytes(cells, ruled=ruled)), 'fictional-projects.pdf')
        result = validate_interpretation(
            _response(fake_jobs), parsed['raw_text'], parsed['_evidence_views'])
        assert result['work_experiences'] == []


@pytest.mark.django_db
def test_worker_saves_validated_borderless_roles_without_duplicate_or_archive(
    client, candidate_account, monkeypatch, settings, tmp_path,
):
    from .test_candidate_experience import upload

    settings.MEDIA_ROOT = tmp_path
    jobs = [
        ('Fictional Atlas', 'Platform Engineer', 'Jan 2020', 'Dec 2021'),
        ('Example Cedar', 'Engineering Manager', 'Jan 2022', 'Dec 2024'),
    ]
    document = positioned_pdf_bytes([
        (55, 760, 'Name: Asha Rao'), (55, 735, 'WORK EXPERIENCE'),
        (58, 680, jobs[0][0]), (248, 680, jobs[0][1]),
        (428, 680, 'Jan 2020 - Dec 2021'),
        (58, 650, jobs[1][0]), (248, 650, jobs[1][1]),
        (428, 650, 'Jan 2022 - Dec 2024'),
    ])

    def fictional_proposals(rules, *_args, **_kwargs):
        accepted = validate_interpretation(
            _response(jobs), rules['raw_text'], rules['_evidence_views'])
        merged = {**rules, **accepted}
        merged['_interpretation'] = {'source': 'rules', 'reason': 'fictional_mock'}
        return merged

    monkeypatch.setattr('talent.resume_processing.understand_resume', fictional_proposals)
    first = upload(client, document, 'fictional-borderless.pdf').data
    original_ids = {row['id'] for row in first['work_experiences']}
    assert len(original_ids) == 2
    assert first['resume_review'] is None
    assert not CandidateProfile.objects.get().resumes.first().extracted_data[
        '_employment_parse']['complete_for_archival']

    repeated = upload(client, document, 'fictional-borderless-repeat.pdf').data
    assert {row['id'] for row in repeated['work_experiences']} == original_ids
    assert repeated['archived_work_experiences'] == []
    assert WorkExperience.all_objects.count() == 2
