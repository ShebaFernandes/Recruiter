"""Fictional zero-role recovery never turns a candidate retry into paid AI spend."""
from io import BytesIO
from unittest.mock import Mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from docx import Document
from talent.ai_providers import AIProviderResult
from talent.models import Resume, ResumeAIUsage, ResumeProcessingJob
from talent.resume_processing import _employment_outcome, process_resume_job
from talent.services import parse_resume

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(('reason', 'expected'), [
    ('candidate_permission_or_rollout_gate', 'ai_unavailable_or_not_consented'),
    ('unavailable', 'ai_unavailable_and_fallback_empty'),
    ('malformed_response', 'provider_response_failed_and_fallback_empty'),
])
def test_empty_fallback_records_why_no_employment_was_verified(reason, expected):
    result = _employment_outcome({
        'work_experiences': [], '_interpretation': {'source': 'rules', 'reason': reason},
    })
    assert result['status'] == 'review_required'
    assert result['reason_code'] == expected


def test_explicit_no_employment_is_distinct_from_failed_extraction():
    result = _employment_outcome({
        'work_experiences': [], '_employment_parse': {'explicit_no_employment': True},
        '_interpretation': {'source': 'rules', 'reason': 'disabled'},
    })
    assert result['status'] == 'confirmed_no_employment'


def document(*lines):
    result = Document()
    for line in lines:
        result.add_paragraph(line)
    stream = BytesIO()
    result.save(stream)
    return stream.getvalue()


def upload(client, *lines):
    response = client.post('/api/v1/candidate/resumes/', {
        'file': SimpleUploadedFile('fictional.docx', document(*lines)),
    }, format='multipart')
    assert response.status_code == 202
    return ResumeProcessingJob.objects.get(resume_id=response.data['latest_resume']['id'])


def test_completed_zero_role_can_retry_once_with_rules_only(
    client, candidate_account, settings, monkeypatch,
):
    settings.RESUME_AI_ENABLED = True
    settings.RESUME_AI_ROLLOUT_MODE = 'consenting'
    job = upload(client, 'Name: Asha Rao', 'Professional background',
                 'Worked on a fictional team, but the document has no employer or title.')
    assert process_resume_job(job.pk) == 'completed'
    first = client.get('/api/v1/candidate/profile/').data
    assert first['employment_extraction']['status'] == 'review_required'
    assert first['latest_resume']['can_retry']
    provider = Mock(side_effect=AssertionError('A retry must never call Gemini'))
    monkeypatch.setattr('talent.resume_understanding.resume_provider', provider)
    retried = client.post(f'/api/v1/candidate/resumes/{job.resume_id}/retry/')
    assert retried.status_code == 202
    assert process_resume_job(job.pk) == 'completed'
    final = client.get('/api/v1/candidate/profile/').data
    assert final['work_experiences'] == []
    assert not final['latest_resume']['can_retry']
    assert final['employment_extraction']['status'] == 'review_required'
    assert Resume.objects.get(pk=job.resume_id).extracted_data[
        '_interpretation']['reason'] == 'candidate_requested_rule_retry'
    assert not ResumeAIUsage.objects.filter(resume_id=job.resume_id).exists()
    provider.assert_not_called()
    assert client.post(f'/api/v1/candidate/resumes/{job.resume_id}/retry/').status_code == 409


def test_rule_retry_reconciles_newly_readable_history_without_new_upload_or_ai(
    client, candidate_account, settings, monkeypatch,
):
    settings.RESUME_AI_ENABLED = True
    job = upload(client, 'Name: Asha Rao', 'Old export with unreadable job layout.')
    assert process_resume_job(job.pk) == 'completed'
    original_resume_id = job.resume_id
    recovered = parse_resume(BytesIO(document(
        'Name: Asha Rao', 'WORK EXPERIENCE',
        'Engineer | Fictional Studio | Jan 2020 - Dec 2022',
    )), 'fictional.docx')
    assert len(recovered['work_experiences']) == 1
    assert client.post(f'/api/v1/candidate/resumes/{job.resume_id}/retry/').status_code == 202
    monkeypatch.setattr('talent.resume_processing.parse_resume', lambda *_args: recovered.copy())
    monkeypatch.setattr('talent.resume_understanding.resume_provider',
                        lambda: (_ for _ in ()).throw(AssertionError('Paid AI called')))
    assert process_resume_job(job.pk) == 'completed'
    data = client.get('/api/v1/candidate/profile/').data
    assert data['latest_resume']['id'] == original_resume_id
    assert [(row['company'], row['role']) for row in data['work_experiences']] == [
        ('Fictional Studio', 'Engineer')]
    assert data['employment_extraction']['status'] == 'verified_fallback'
    assert data['resume_review'] is None
    assert not ResumeAIUsage.objects.filter(resume_id=original_resume_id).exists()


def test_evidence_validated_ai_role_saves_without_deterministic_role(
    client, candidate_account, settings, monkeypatch,
):
    settings.RESUME_AI_ENABLED = True
    settings.RESUME_AI_EXTERNAL_PROCESSING_APPROVED = True
    settings.RESUME_AI_PROVIDER = 'gemini'
    settings.RESUME_AI_MODEL = 'fictional-model'
    settings.RESUME_AI_ROLLOUT_MODE = 'consenting'
    settings.RESUME_AI_MAX_ATTEMPTS = 1
    settings.LEGAL_RESUME_AI_VERSION = 'fictional-consent'
    settings.LEGAL_RESUME_AI_SHA256 = 'a' * 64
    monkeypatch.setattr('talent.legal.documents', lambda: {'resume_ai': {
        'version': settings.LEGAL_RESUME_AI_VERSION,
        'sha256': settings.LEGAL_RESUME_AI_SHA256,
    }})
    provider = Mock()
    provider.generate.return_value = AIProviderResult({
        'full_name': {'value': None, 'evidence': ''},
        'location': {'value': None, 'evidence': ''},
        'professional_title': {'value': None, 'evidence': ''},
        'professional_summary': {'value': None, 'evidence': ''},
        'standout_signal': {'value': None, 'evidence': ''},
        'skills': [], 'education': [],
        'work_experiences': [{
            'company': 'Cedar Labs', 'role': 'Engineering Advisor',
            'employer_evidence': 'Cedar Labs',
            'role_evidence': 'Engineering Advisor',
        }],
    }, 'gemini', 'fictional-model')
    monkeypatch.setattr('talent.resume_understanding.resume_provider', lambda: provider)
    response = client.post('/api/v1/candidate/resumes/', {
        'file': SimpleUploadedFile('fictional.docx', document(
            'Name: Asha Rao', 'Professional background', 'Cedar Labs',
            'Engineering Advisor', 'Designed fictional systems.',
        )),
        'resume_ai_accepted': 'true',
        'resume_ai_version': settings.LEGAL_RESUME_AI_VERSION,
    }, format='multipart')
    assert response.status_code == 202
    job = ResumeProcessingJob.objects.get(resume_id=response.data['latest_resume']['id'])
    assert process_resume_job(job.pk) == 'completed'
    parsed = Resume.objects.get(pk=job.resume_id).extracted_data
    assert parsed['_employment_parse']['recognized_roles'] == 0
    data = client.get('/api/v1/candidate/profile/').data
    assert [(item['company'], item['role']) for item in data['work_experiences']] == [
        ('Cedar Labs', 'Engineering Advisor')]
    assert data['employment_extraction']['status'] == 'verified_ai'
    assert data['resume_review'] is None
    provider.generate.assert_called_once()
