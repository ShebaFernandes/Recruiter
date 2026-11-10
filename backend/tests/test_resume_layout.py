"""Synthetic layouts; no candidate files or external providers are accessed."""

from copy import deepcopy
from io import BytesIO
from unittest.mock import patch

import pytest
from docx import Document
from talent.models import Resume
from talent.resume_layout import (
    DocumentBlock,
    DocumentPage,
    DocumentStructure,
    classify_layout,
    extract_document,
    parse_document,
)
from talent.services import _parse_resume_legacy, parse_resume

from .test_candidate_experience import upload
from .test_document_evidence import pdf_bytes
from .test_resume_promotions import promotion_lines, resume_file


def content(lines, *, table=False):
    document = Document()
    if table:
        document.add_paragraph('WORK EXPERIENCE')
        grid = document.add_table(rows=0, cols=3)
        for values in lines:
            row = grid.add_row()
            for cell, value in zip(row.cells, values, strict=True):
                cell.text = value
    else:
        for line in lines:
            document.add_paragraph(line)
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def test_disabled_is_exact_legacy_and_does_not_extract_structure(settings):
    settings.RESUME_LAYOUT_MODE = 'disabled'
    payload = content(['WORK EXPERIENCE', 'Engineer | Example Labs | Jan 2020 - Present'])
    expected = _parse_resume_legacy(BytesIO(payload), 'sample.docx')
    with patch('talent.resume_layout.extract_document', side_effect=AssertionError):
        assert parse_resume(BytesIO(payload), 'sample.docx') == expected


def test_shadow_changes_only_private_diagnostics(settings):
    settings.RESUME_LAYOUT_MODE = 'shadow'
    payload = content(['WORK EXPERIENCE', 'Engineer | Example Labs | Jan 2020 - Present'])
    expected = _parse_resume_legacy(BytesIO(payload), 'sample.docx')
    actual = parse_resume(BytesIO(payload), 'sample.docx')
    diagnostics = actual.pop('_layout_routing')
    assert actual == expected
    assert diagnostics['mode'] == 'shadow'
    assert diagnostics['family'] == 'single_column'
    assert 'Example Labs' not in str(diagnostics)
    assert diagnostics['strategies_compared'] <= 2


def test_table_cells_are_real_cells_not_pipe_characters():
    payload = content([('Example Labs', 'Engineer', 'Jan 2020 - Present')], table=True)
    document = extract_document(BytesIO(payload), 'sample.docx')
    assert classify_layout(document).family == 'table'
    row = next(block for block in document.pages[0].blocks if block.cells)
    assert row.cells == ['Example Labs', 'Engineer', 'Jan 2020 - Present']
    assert row.evidence_id == 'docx:t0:r0'
    plain = extract_document(BytesIO(content([
        'Engineer | Example Labs | Jan 2020 - Present'])), 'sample.docx')
    assert classify_layout(plain).family == 'single_column'


@pytest.mark.parametrize('family', ['single_column', 'columns', 'table', 'mixed', 'unknown'])
def test_layout_families_and_section_regions(family):
    blocks = [DocumentBlock('h', 1, 'WORK EXPERIENCE')]
    if family in {'columns', 'mixed'}:
        blocks += [DocumentBlock(f'{column}{index}', 1, f'Line {index}',
                                 [.1 if column == 'left' else .6, .2 + index * .1, .4, .3],
                                 column) for column in ('left', 'right') for index in range(2)]
    if family in {'table', 'mixed'}:
        blocks.append(DocumentBlock('row', 1, 'Company | Engineer', cells=['Company', 'Engineer']))
    if family == 'unknown':
        blocks = []
    document = DocumentStructure('test.pdf', [DocumentPage(1, blocks)], {'work_experiences': []})
    profile = classify_layout(document)
    assert profile.family == family
    assert all(0 <= page['score'] <= 1 for page in profile.pages)
    assert profile.section_structure == ('unknown' if family == 'unknown' else 'explicit')


def test_pdf_coordinates_and_ids_are_stable():
    payload = pdf_bytes(['WORK EXPERIENCE', 'Engineer | Example Labs | Jan 2020 - Present'])
    first = extract_document(BytesIO(payload), 'test.pdf')
    second = extract_document(BytesIO(payload), 'test.pdf')
    assert first.pages == second.pages
    assert first.pages[0].blocks
    assert all(0 <= coordinate <= 1 for block in first.pages[0].blocks for coordinate in block.bbox)


@pytest.mark.parametrize('extension', ['pdf', 'docx'])
def test_enabled_career_journey_preserves_companies_and_promotions(settings, extension):
    settings.RESUME_LAYOUT_MODE = 'enabled'
    parsed = parse_resume(resume_file(promotion_lines(), extension), f'resume.{extension}')
    rows = parsed['work_experiences']
    assert len(rows) == 7
    assert [row['company'] for row in rows[:3]] == ['Northstar (Example Group)'] * 3
    assert {row['role'] for row in rows[:3]} == {
        'Head of AI Engineering', 'Engineering Manager', 'Senior Engineer'}
    assert rows[0]['start_date'] == '2023-04-01'
    assert parsed['_layout_routing']['employment_structure'] == 'grouped_promotions'
    assert parsed['_employment_parse']['complete_for_archival'] is False
    assert parsed['_employment_parse']['rule_role_keys'] == []


def test_year_only_dates_remain_literal_instead_of_inventing_months(settings):
    settings.RESUME_LAYOUT_MODE = 'enabled'
    parsed = parse_resume(BytesIO(content([
        'WORK EXPERIENCE', 'Engineer | Example Labs | 2019 - 2021'])), 'test.docx')
    row = parsed['work_experiences'][0]
    assert row['start_date'] is None and row['end_date'] is None
    assert row['date_label'] == '2019 - 2021'


def test_table_row_cannot_borrow_another_rows_employer(settings):
    settings.RESUME_LAYOUT_MODE = 'enabled'
    parsed = parse_resume(BytesIO(content([
        ('Example Labs', '', 'Jan 2020 - Dec 2021'),
        ('', 'Engineer', 'Jan 2022 - Present'),
    ], table=True)), 'test.docx')
    assert parsed['work_experiences'] == []


def test_unknown_and_ocr_required_preserve_status(settings):
    settings.RESUME_LAYOUT_MODE = 'enabled'
    from pypdf import PdfWriter

    stream = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(stream)
    result = parse_resume(stream, 'scan.pdf')
    assert result['_layout_routing']['source'] == 'scanned'
    assert result['_layout_routing']['family'] == 'unknown'
    assert result['_employment_parse']['ocr_required'] is True
    assert result['work_experiences'] == []


def test_ambiguous_associations_are_removed_and_flagged(settings, monkeypatch):
    settings.RESUME_LAYOUT_MODE = 'enabled'
    import talent.resume_layout as module

    payload = content(['WORK EXPERIENCE', 'Engineer | Example Labs | Jan 2020 - Present'])
    document = extract_document(BytesIO(payload), 'test.docx')
    profile = classify_layout(document)
    monkeypatch.setattr(module, '_reading_text', lambda *_: document.baseline['raw_text'] + '\n')
    row = document.baseline['work_experiences'][0]
    different = {**row, 'company': 'Other Labs'}
    with patch.object(module, '_validated_rows', side_effect=[[deepcopy(row)], [different]]):
        result = parse_document(document, profile)
    assert result['work_experiences'] == []
    assert result['_layout_review_required'] is True
    from talent.resume_processing import _employment_outcome

    assert _employment_outcome(result)['status'] == 'review_required'


@pytest.mark.django_db
def test_upload_persists_validated_journey_and_strips_worker_geometry(
    settings, tmp_path, client, candidate_account,
):
    settings.RESUME_LAYOUT_MODE = 'enabled'
    settings.RESUME_AI_ENABLED = False
    settings.MEDIA_ROOT = tmp_path
    payload = content([
        'Name: Asha Rao', 'WORK EXPERIENCE',
        'Engineer | Example Labs | Jan 2020 - Dec 2021',
        'Senior Engineer | Later Labs | Jan 2022 - Present',
    ])
    response = upload(client, payload)
    assert response.status_code == 200
    assert {(row['company'], row['role']) for row in response.data['work_experiences']} == {
        ('Example Labs', 'Engineer'), ('Later Labs', 'Senior Engineer')}
    resume = Resume.objects.get(pk=response.data['latest_resume']['id'])
    assert resume.extracted_data['_layout_routing']['mode'] == 'enabled'
    assert '_layout_regions' not in resume.extracted_data
    assert '_evidence_views' not in resume.extracted_data
    assert resume.extracted_data['_employment_outcome']['profile_state'] == 'applied'
    assert client.get('/api/v1/candidate/profile/').status_code == 200


@pytest.mark.django_db
def test_conflicting_routing_result_surfaces_review_without_overwriting_saved_roles(
    settings, tmp_path, client, candidate_account,
):
    settings.MEDIA_ROOT = tmp_path
    settings.RESUME_AI_ENABLED = False
    upload(client)
    profile_before = client.get('/api/v1/candidate/profile/').data
    payload = content(['Name: Asha Rao', 'WORK EXPERIENCE'])
    parsed = _parse_resume_legacy(BytesIO(payload), 'test.docx')
    parsed['_layout_review_required'] = True
    with patch('talent.resume_processing.parse_resume', return_value=parsed):
        response = upload(client, payload)
    assert response.status_code == 200
    assert response.data['work_experiences'] == profile_before['work_experiences']
    resume = Resume.objects.get(pk=response.data['latest_resume']['id'])
    assert resume.extracted_data['_employment_outcome']['reason_code'] == (
        'conflicting_layout_associations')


def test_document_budget_falls_back_without_authorizing_archival(settings):
    settings.RESUME_LAYOUT_MODE = 'enabled'
    payload = content(['WORK EXPERIENCE'] + ['Example line'] * 601)
    document = extract_document(BytesIO(payload), 'large.docx')
    assert document.incomplete
    assert sum(len(page.blocks) for page in document.pages) <= 600
    result = parse_document(document, classify_layout(document))
    assert result['raw_text'] == document.baseline['raw_text']
    assert not result['_employment_parse']['complete_for_archival']


def test_page_classification_can_mix_native_and_scanned_pages(settings):
    settings.RESUME_LAYOUT_MODE = 'enabled'
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    writer.append(PdfReader(BytesIO(pdf_bytes([
        'WORK EXPERIENCE', 'Engineer | Example Labs | Jan 2020 - Present']))))
    writer.add_blank_page(width=612, height=792)
    stream = BytesIO()
    writer.write(stream)
    document = extract_document(stream, 'mixed.pdf')
    profile = classify_layout(document)
    assert profile.source == 'mixed'
    assert profile.family == 'mixed'
    assert [page['family'] for page in profile.pages] == ['single_column', 'unknown']
    result = parse_document(document, profile)
    assert result['_employment_parse']['ocr_required']
    assert not result['_employment_parse']['complete_for_archival']
    assert result['_layout_routing']['review_required']


def test_layout_benchmark_improves_unseen_sidebar_and_table_templates():
    import json
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / 'scripts' / 'resume_layout_benchmark.py'
    result = subprocess.run([sys.executable, str(script)], check=True, capture_output=True,
                            text=True, timeout=30)
    report = json.loads(result.stdout)
    assert report['external_calls'] == report['paid_calls'] == 0
    assert report['classification_accuracy'] >= .9
    assert all(case['strategies']['automatic']['unsupported'] == 0 for case in report['cases'])
    assert all(case['strategies']['automatic']['matched'] >= case['strategies']['legacy']['matched']
               for case in report['cases'])
    held_out = {case['name']: case for case in report['cases'] if case['split'] == 'held_out'}
    assert {case['expected_family'] for case in held_out.values()} == {
        'single_column', 'columns', 'table', 'mixed', 'unknown'}
    for name in ('narrow_sidebar', 'ruled_pdf'):
        assert held_out[name]['strategies']['automatic']['complete_journey']
        assert not held_out[name]['strategies']['legacy']['complete_journey']


@pytest.mark.django_db
def test_enabled_replacement_never_archives_omitted_history(
    settings, tmp_path, client, candidate_account,
):
    settings.MEDIA_ROOT = tmp_path
    settings.RESUME_LAYOUT_MODE = 'enabled'
    settings.RESUME_AI_ENABLED = False
    full = ['Name: Asha Rao', 'WORK EXPERIENCE',
            'Engineer | Example Labs | Jan 2020 - Dec 2021',
            'Senior Engineer | Later Labs | Jan 2022 - Present']
    initial = upload(client, content(full)).data
    replacement = upload(client, content(full[:2] + full[3:])).data
    assert len(initial['work_experiences']) == len(replacement['work_experiences']) == 2
    resume = Resume.objects.get(pk=replacement['latest_resume']['id'])
    assert resume.extracted_data['_employment_outcome']['archived_role_count'] == 0
    assert not resume.extracted_data['_employment_parse']['complete_for_archival']


def test_downstream_rules_keep_already_scoped_roles_on_uncertain_layout(settings):
    settings.RESUME_LAYOUT_MODE = 'enabled'
    settings.RESUME_AI_ENABLED = False
    from talent.resume_understanding import understand_resume

    parsed = parse_resume(resume_file(promotion_lines(), 'docx'), 'resume.docx')
    parsed['_document_layout']['layout_uncertain'] = True
    expected = deepcopy(parsed['work_experiences'])
    with patch('talent.resume_understanding._spatially_validated_rule_rows',
               side_effect=AssertionError('Already scoped by local routing')):
        result = understand_resume(parsed, lambda *_: None, ai_allowed=False)
    assert result['work_experiences'] == expected
    assert not result['_employment_parse']['complete_for_archival']


def test_shadow_pdf_extraction_facts_match_disabled_mode(settings):
    payload = pdf_bytes(['SKILLS', 'Python', 'WORK EXPERIENCE',
                         'Engineer | Example Labs | Jan 2020 - Present'], columns=True)
    settings.RESUME_LAYOUT_MODE = 'disabled'
    original = parse_resume(BytesIO(payload), 'test.pdf')
    settings.RESUME_LAYOUT_MODE = 'shadow'
    shadow = parse_resume(BytesIO(payload), 'test.pdf')
    shadow.pop('_layout_routing')
    shadow['_evidence_views'] = [view for view in shadow['_evidence_views']
                                 if view['method'] != 'layout_geometry']
    assert shadow == original


@pytest.mark.django_db
def test_ai_fallback_cannot_reintroduce_a_disputed_association_into_saved_history(
    settings, tmp_path, client, candidate_account,
):
    settings.MEDIA_ROOT = tmp_path
    settings.RESUME_AI_ENABLED = False
    settings.RESUME_LAYOUT_MODE = 'enabled'
    from talent.resume_layout import association_fingerprint

    payload = content(['Name: Asha Rao', 'WORK EXPERIENCE',
                       'Engineer | Example Labs | Jan 2020 - Present'])
    parsed = parse_resume(BytesIO(payload), 'test.docx')
    parsed['_layout_conflict_ids'] = [association_fingerprint(parsed['work_experiences'][0])]
    parsed['_layout_review_required'] = True
    parsed['_layout_review_reason'] = 'conflicting_layout_associations'
    # Model the downstream result after AI/cache recovery: the contested role is
    # present again, but its local association dispute has not been resolved.
    with patch('talent.resume_processing.parse_resume', return_value=parsed), patch(
        'talent.resume_processing.understand_resume', side_effect=lambda rules, *_a, **_k: rules
    ):
        response = upload(client, payload)
    assert response.status_code == 200
    assert response.data['work_experiences'] == []
    resume = Resume.objects.get(pk=response.data['latest_resume']['id'])
    assert resume.extracted_data['_employment_outcome']['status'] == 'review_required'
    assert '_layout_conflict_ids' not in resume.extracted_data
