"""Fictional upload -> queued worker -> Gemini HTTP adapter -> saved profile, offline."""
import json
from decimal import Decimal
from unittest.mock import Mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from talent.models import ResumeProcessingJob
from talent.resume_processing import process_resume_job

from .test_candidate_flow import resume_pdf
from .test_resume_understanding import TEXT, response

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('gate', ['ready', 'no_consent', 'not_allowlisted', 'budget', 'external'])
def test_paid_canary_fictional_upload_safeguards(
    client, candidate_account, settings, monkeypatch, tmp_path, gate,
):
    settings.MEDIA_ROOT = tmp_path
    settings.AI_PROVIDER = 'deterministic'
    settings.RESUME_AI_ENABLED = True
    settings.RESUME_AI_EXTERNAL_PROCESSING_APPROVED = gate != 'external'
    settings.RESUME_AI_PROVIDER = 'gemini'
    settings.RESUME_AI_MODEL = 'gemini-3.5-flash-lite'
    settings.RESUME_AI_API_KEY = 'fictional-worker-key'
    settings.RESUME_AI_ALLOW_PAID = True
    settings.RESUME_AI_GEMINI_FREE_TIER_APPROVED = False
    settings.RESUME_AI_ROLLOUT_MODE = 'canary'
    settings.RESUME_AI_MAX_ATTEMPTS = 1
    settings.RESUME_AI_MAX_OUTPUT_TOKENS = 3000
    settings.RESUME_AI_DAILY_BUDGET_USD = Decimal('0.01')
    settings.RESUME_AI_MONTHLY_BUDGET_USD = Decimal('0' if gate == 'budget' else '0.01')
    settings.RESUME_AI_INPUT_USD_PER_MILLION = Decimal('0.30')
    settings.RESUME_AI_OUTPUT_USD_PER_MILLION = Decimal('2.50')
    settings.LEGAL_RESUME_AI_VERSION = 'fictional-local-consent-v1'
    settings.LEGAL_RESUME_AI_SHA256 = 'a' * 64
    monkeypatch.setattr('talent.legal.documents', lambda: {'resume_ai': {
        'version': settings.LEGAL_RESUME_AI_VERSION,
        'sha256': settings.LEGAL_RESUME_AI_SHA256,
    }})
    post = Mock(return_value={
        'responseId': 'fictional-offline-result',
        'candidates': [{'finishReason': 'STOP', 'content': {
            'parts': [{'text': json.dumps(response())}],
        }}],
        'usageMetadata': {'promptTokenCount': 500, 'candidatesTokenCount': 600},
    })
    monkeypatch.setattr('talent.ai_providers._post_json', post)
    # Fail any accidental network access, including alternative provider paths.
    monkeypatch.setattr('urllib.request.urlopen', Mock(side_effect=AssertionError('No network')))
    payload = {'file': SimpleUploadedFile('fictional.pdf', resume_pdf(TEXT.splitlines()))}
    if gate != 'no_consent':
        payload.update(resume_ai_accepted='true',
                       resume_ai_version=settings.LEGAL_RESUME_AI_VERSION)
    uploaded = client.post('/api/v1/candidate/resumes/', payload, format='multipart')
    assert uploaded.status_code == 202
    job = ResumeProcessingJob.objects.get(resume_id=uploaded.data['latest_resume']['id'])
    settings.RESUME_AI_CANARY_RESUME_IDS = set() if gate == 'not_allowlisted' else {job.resume_id}
    assert bool(job.resume.ai_processing_consent_at) == (gate != 'no_consent')
    assert process_resume_job(job.pk, str(job.idempotency_key)) == 'completed'
    data = client.get('/api/v1/candidate/profile/').data
    assert data['employment_extraction']['resume_id'] == job.resume_id
    if gate == 'ready':
        post.assert_called_once()
        assert post.call_args.args[0].endswith('/models/gemini-3.5-flash-lite:generateContent')
        assert data['employment_extraction']['status'] == 'verified_ai'
        ids = {row['id'] for row in data['work_experiences']}
        assert set(data['employment_extraction']['verified_role_ids']) == ids
        assert len(ids) == 2
        assert data['resume_review'] is None
        reviewed = client.patch('/api/v1/candidate/profile/', {
            'visibility': 'approved_recruiters',
            'work_preferences': ['Remote'],
            'notice_period_days': 30,
            'meaningful_work': 'Built a fictional service used by 12 teams.',
        }, format='json')
        assert reviewed.status_code == 200, reviewed.data
        assert reviewed.data['can_submit'] is True, reviewed.data['missing_fields']
        submitted = client.post('/api/v1/candidate/profile/submit/',
                                {'consent': True}, format='json')
        assert submitted.status_code == 200, submitted.data
        assert submitted.data['profile_status'] == 'submitted'
        assert {row['id'] for row in submitted.data['work_experiences']} == ids
        usage = job.resume.ai_usage.get()
        assert usage.attempt == 1
        assert usage.estimated_cost_usd <= Decimal('0.009')
    else:
        post.assert_not_called()
        assert not job.resume.ai_usage.exists()
    # Redelivery cannot spend another attempt or change saved history.
    assert process_resume_job(job.pk, str(job.idempotency_key)) == 'duplicate'
    assert post.call_count == (1 if gate == 'ready' else 0)
