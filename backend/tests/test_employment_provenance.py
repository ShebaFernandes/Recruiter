"""Real offline worker -> saved rows -> owner/recruiter API provenance."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from talent.models import Resume, ResumeProcessingJob
from talent.serializers import CandidateProfileSerializer
from talent.worker_runtime import run_bounded_job

from .test_resume_reliability_matrix import _fixture_bytes

SCENARIOS = json.loads((Path(__file__).parent / 'fixtures/employment-scenarios.json').read_text())
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def private_storage(settings, tmp_path):
    # Reset test IDs must never reuse clean file paths from another test/run.
    settings.MEDIA_ROOT = tmp_path


def upload_job(client, scenario, extension='docx'):
    content = _fixture_bytes(extension, ['Name: Asha Rao', *scenario['lines']])
    response = client.post('/api/v1/candidate/resumes/', {
        'file': SimpleUploadedFile(f'fictional.{extension}', content),
    }, format='multipart')
    assert response.status_code == 202
    return ResumeProcessingJob.objects.get(resume_id=response.data['latest_resume']['id'])


@pytest.mark.parametrize('scenario', SCENARIOS, ids=lambda row: row['name'])
@pytest.mark.parametrize('extension', ['pdf', 'docx'])
def test_real_worker_saved_employment_matches_current_upload(
    client, candidate_account, scenario, extension,
):
    job = upload_job(client, scenario, extension)
    assert run_bounded_job(job.pk) == 'completed'
    data = client.get('/api/v1/candidate/profile/').data
    history = data['employment_extraction']
    assert data['latest_resume']['processing_status'] == 'completed'
    assert len(data['work_experiences']) == scenario['roles']
    assert history['resume_id'] == job.resume_id
    assert len(history['verified_role_ids']) == scenario['roles']
    assert history['unverified_role_ids'] == []
    assert history['source'] == 'rules'
    expected = ('verified_fallback' if scenario['roles'] else
                'confirmed_no_employment' if scenario['name'] == 'fresher' else 'review_required')
    assert history['status'] == expected
    assert not job.resume.ai_usage.exists()
    profile = User.objects.get(pk=candidate_account['user']['id']).candidate_profile
    # The recruiter receives the SAME safe classification, never raw evidence/consent.
    recruiter = CandidateProfileSerializer(profile, context={
        'request': SimpleNamespace(user=SimpleNamespace(id=-1), build_absolute_uri=lambda p: p),
    }).data
    assert recruiter['employment_extraction'] == history
    assert 'raw_text' not in str(recruiter) and 'source_evidence' not in str(recruiter)
    if scenario['name'] == 'partial':
        assert data['work_experiences'][0]['start_date'] is None
        assert data['work_experiences'][0]['end_date'] is None


def test_unresolved_replacement_preserves_manual_rows_but_cannot_verify_them(
    client, candidate_account,
):
    first = upload_job(client, SCENARIOS[0])
    assert run_bounded_job(first.pk) == 'completed'
    initial = client.get('/api/v1/candidate/profile/').data
    rows = initial['work_experiences']
    rows[0]['description'] = 'Candidate corrected this description.'
    edited = client.patch('/api/v1/candidate/profile/', {'work_experiences': rows}, format='json')
    assert edited.status_code == 200
    saved = edited.data['work_experiences']
    new = upload_job(client, SCENARIOS[-1])
    assert run_bounded_job(new.pk) == 'completed'
    data = client.get('/api/v1/candidate/profile/').data
    assert data['work_experiences'] == saved
    assert data['employment_extraction']['verified_role_ids'] == []
    assert len(data['employment_extraction']['candidate_confirmed_role_ids']) == 3
    assert len(data['employment_extraction']['unverified_role_ids']) == 3
    assert data['employment_extraction']['status'] == 'review_required'


def test_latest_failure_or_pending_upload_never_reuses_previous_verified_outcome(
    client, candidate_account,
):
    first = upload_job(client, SCENARIOS[3])
    assert run_bounded_job(first.pk) == 'completed'
    saved = client.get('/api/v1/candidate/profile/').data['work_experiences']
    job = upload_job(client, {'lines': [], 'roles': 0})
    pending = client.get('/api/v1/candidate/profile/').data['employment_extraction']
    assert pending['resume_id'] == job.resume_id
    assert pending['status'] == 'processing'
    assert pending['verified_role_ids'] == []
    # Valid document container with no readable text; parser fails, no fake success.
    job.resume.file.save('empty.docx', SimpleUploadedFile('empty.docx', _fixture_bytes('docx', [])))
    job.max_attempts = 1
    job.save(update_fields=['max_attempts'])
    assert run_bounded_job(job.pk) == 'failed'
    data = client.get('/api/v1/candidate/profile/').data
    assert data['work_experiences'] == saved
    assert data['employment_extraction']['status'] == 'review_required'
    assert data['employment_extraction']['reason_code'] == 'latest_resume_failed'
    assert data['employment_extraction']['verified_role_ids'] == []


def test_equal_counts_do_not_verify_different_roles_or_manual_changes(client, candidate_account):
    first = upload_job(client, SCENARIOS[3])
    assert run_bounded_job(first.pk) == 'completed'
    profile = first.resume.candidate
    row = profile.work_experiences.get()
    row.role = 'Candidate corrected role'
    row.confidence_status = 'candidate_confirmed'
    row.save()
    data = client.get('/api/v1/candidate/profile/').data
    assert data['employment_extraction']['accepted_role_count'] == 1
    assert data['employment_extraction']['verified_role_ids'] == []
    assert data['employment_extraction']['candidate_confirmed_role_ids'] == [row.pk]
    # Historical stored metadata is not rewritten by reading the profile.
    assert Resume.objects.get(pk=first.resume_id).extracted_data['_employment_outcome'][
        'profile_state'
    ] == 'applied'


def test_mocked_gemini_evidence_is_distinct_from_rules_and_requires_matching_saved_rows(
    client, candidate_account, settings, monkeypatch,
):
    from unittest.mock import Mock

    from talent.ai_providers import AIProviderResult

    from .test_candidate_experience import upload
    from .test_candidate_flow import resume_pdf
    from .test_resume_understanding import TEXT, response

    settings.RESUME_AI_ENABLED = True
    settings.RESUME_AI_EXTERNAL_PROCESSING_APPROVED = True
    settings.RESUME_AI_PROVIDER = 'gemini'
    settings.RESUME_AI_MODEL = 'synthetic-offline-model'
    settings.RESUME_AI_ALLOW_PAID = False
    settings.RESUME_AI_GEMINI_FREE_TIER_APPROVED = False
    settings.RESUME_AI_ROLLOUT_MODE = 'consenting'
    settings.LEGAL_RESUME_AI_VERSION = 'synthetic-test-consent'
    settings.LEGAL_RESUME_AI_SHA256 = '1' * 64
    provider = Mock()
    provider.generate.return_value = AIProviderResult(
        response(), 'gemini', 'synthetic-offline-model',
    )
    monkeypatch.setattr('talent.resume_understanding.resume_provider', lambda: provider)
    data = upload(client, resume_pdf(TEXT.splitlines()), 'fictional.pdf').data
    provider.generate.assert_called_once()
    assert data['employment_extraction']['status'] == 'verified_ai'
    assert data['employment_extraction']['source'] == 'ai'
    assert len(data['employment_extraction']['verified_role_ids']) == 2


@pytest.mark.parametrize('extension', ['pdf', 'docx'])
def test_internship_and_current_job_save_separate_evidence_bound_periods(
    client, candidate_account, extension,
):
    scenario = {'lines': [
        'EXPERIENCE',
        'Orchid Research and Technologies',
        'AI Intern / SDE Intern - AI',
        'Jan 2026 - Jul 2026',
        'Built reliable research tools.',
        'Cedar Recruitment',
        'AI Full-Stack Developer',
        'Sep 2026 - Present',
        'Built reliable recruiting tools.',
    ]}
    job = upload_job(client, scenario, extension)
    assert run_bounded_job(job.pk) == 'completed'
    data = client.get('/api/v1/candidate/profile/').data
    rows = sorted(data['work_experiences'], key=lambda row: row['start_date'])
    assert len(rows) == 2
    assert rows[0]['company'] == 'Orchid Research and Technologies'
    assert rows[0]['role'] == 'AI Intern / SDE Intern - AI'
    assert rows[0]['employment_type'] == 'Internship'
    assert rows[0]['end_date'] == '2026-07-01'
    assert rows[1]['company'] == 'Cedar Recruitment' and rows[1]['is_current']
    assert rows[1]['start_date'] == '2026-09-01'
    assert rows[0]['description'] == 'Built reliable research tools.'
    assert set(data['employment_extraction']['verified_role_ids']) == {row['id'] for row in rows}
    assert not job.resume.ai_usage.exists()
