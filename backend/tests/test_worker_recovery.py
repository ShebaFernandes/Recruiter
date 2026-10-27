import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import OperationalError, close_old_connections, connections
from django.utils import timezone
from rest_framework.test import APIClient
from talent import resume_processing as processing
from talent.models import Resume, ResumeProcessingJob, WorkerHeartbeat
from talent.worker_runtime import run_bounded_job, worker_available

from .test_candidate_flow import resume_pdf


def uploaded_job(client, content=None):
    response = client.post('/api/v1/candidate/resumes/', {
        'file': SimpleUploadedFile('fictional.pdf', content or resume_pdf()),
    }, format='multipart')
    assert response.status_code == 202
    return ResumeProcessingJob.objects.get(resume_id=response.data['latest_resume']['id'])


@pytest.mark.django_db
def test_last_live_attempt_is_not_failed_by_duplicate_delivery(client, candidate_account):
    job = uploaded_job(client)
    job.max_attempts = 1
    job.save()
    claimed, _ = processing._claim_job(job.pk)
    assert processing._claim_job(job.pk) == (None, 'busy')
    job.refresh_from_db()
    assert job.state == 'processing' and job.attempts == 1
    assert processing.process_resume_job(job.pk, claimed=claimed) == 'completed'
    assert processing.process_resume_job(job.pk) == 'duplicate'


@pytest.mark.django_db
def test_child_launch_failure_retries_without_losing_upload(client, candidate_account, monkeypatch):
    job = uploaded_job(client)
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with patch('talent.worker_runtime.subprocess.run', side_effect=OSError) as child:
        assert run_bounded_job(job.pk) == 'retry'
        assert urlsplit(child.call_args.kwargs['env']['DATABASE_URL']).hostname == '127.0.0.1'
    job.refresh_from_db()
    assert job.state == 'queued' and job.attempts == 1
    assert 'worker could not start' in job.last_error
    assert job.resume.file.storage.exists(job.resume.file.name)


@pytest.mark.django_db(transaction=True)
def test_worker_recovers_database_outage_and_keeps_other_workers_healthy(settings):
    settings.RESUME_QUEUE_BACKEND = 'database'
    WorkerHeartbeat.objects.create(worker_id='other-worker', state='idle')
    with patch('talent.management.commands.run_resume_worker.next_database_job_id',
               side_effect=[OperationalError('private connection detail'), 123]), \
         patch('talent.management.commands.run_resume_worker.run_bounded_job',
               return_value='missing') as run, \
         patch('talent.management.commands.run_resume_worker.time.sleep') as sleep:
        call_command('run_resume_worker', max_jobs=1)
    sleep.assert_called_once_with(2)
    run.assert_called_once_with(123)
    assert worker_available()
    assert WorkerHeartbeat.objects.get(worker_id='other-worker').state == 'idle'
    assert WorkerHeartbeat.objects.exclude(worker_id='other-worker').get().state == 'stopped'


@pytest.mark.django_db
def test_worker_phases_follow_actual_work_and_terminal_commit(client, candidate_account):
    job = uploaded_job(client)
    phases = []
    original_parse = processing.parse_resume
    original_apply = processing._apply_extracted_resume

    def observe():
        response = client.get('/api/v1/candidate/resume-status/')
        phases.append(response.data['resume']['processing_stage'])
        assert response.data['resume']['processing_status'] == 'processing'
        assert 'raw_text' not in json.dumps(response.data)

    class Scanner(processing.DevelopmentResumeScanner):
        def scan(self, file):
            observe()
            return super().scan(file)

    def parse(*args):
        observe()
        return original_parse(*args)

    def apply(*args):
        observe()
        return original_apply(*args)

    with patch.object(processing, 'get_resume_scanner', return_value=Scanner()), \
         patch.object(processing, 'parse_resume', side_effect=parse), \
         patch.object(processing, '_apply_extracted_resume', side_effect=apply):
        assert processing.process_resume_job(job.pk) == 'completed'
    assert phases == ['scanning', 'extracting', 'validating']
    response = client.get('/api/v1/candidate/resume-status/')
    assert response.data['resume']['processing_stage'] == 'completed'


@pytest.mark.django_db(transaction=True)
def test_concurrent_retries_enqueue_same_failed_job_only_once(client, candidate_account):
    job = uploaded_job(client)
    ResumeProcessingJob.objects.filter(pk=job.pk).update(state='failed', attempts=3)
    Resume.objects.filter(pk=job.resume_id).update(processing_status='failed')
    user_id = candidate_account['user']['id']
    barrier = Barrier(2)
    select = ResumeProcessingJob.objects.select_for_update

    def synchronized_select(*args, **kwargs):
        barrier.wait(timeout=10)
        return select(*args, **kwargs)

    def retry():
        close_old_connections()
        try:
            api = APIClient()
            api.force_authenticate(User.objects.get(pk=user_id))
            return api.post(f'/api/v1/candidate/resumes/{job.resume_id}/retry/').status_code
        finally:
            connections.close_all()

    with patch('talent.views.ResumeProcessingJob.objects.select_for_update',
               side_effect=synchronized_select), \
         patch('talent.views._enqueue_resume_safely') as enqueue, \
         ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: retry(), range(2)))
    assert sorted(results) == [202, 409]
    enqueue.assert_called_once_with(job.pk)
    job.refresh_from_db()
    assert job.state == 'queued' and job.attempts == 0
    assert ResumeProcessingJob.objects.filter(resume_id=job.resume_id).count() == 1


@pytest.mark.django_db
def test_phase_updates_are_fenced_and_failed_jobs_require_explicit_retry(client, candidate_account):
    job = uploaded_job(client)
    claimed, _ = processing._claim_job(job.pk)
    ResumeProcessingJob.objects.filter(pk=job.pk).update(locked_at=timezone.now())
    assert processing._set_job_phase(claimed, 'validating') == 0
    ResumeProcessingJob.objects.filter(pk=job.pk).update(state='failed', attempts=1)
    assert processing._claim_job(job.pk) == (None, 'failed')


@pytest.mark.django_db
def test_child_uses_resolved_db_host_and_name(client, candidate_account, settings, monkeypatch):
    job = uploaded_job(client)
    monkeypatch.setenv('DATABASE_URL', 'postgresql://wrong:wrong@other-host:9999/wrong')
    with patch('talent.worker_runtime.subprocess.run',
               side_effect=subprocess.TimeoutExpired('child', 240)) as child:
        assert run_bounded_job(job.pk) == 'retry'
    parsed = urlsplit(child.call_args.kwargs['env']['DATABASE_URL'])
    assert parsed.hostname == settings.DATABASES['default']['HOST']
    assert parsed.path == '/' + settings.DATABASES['default']['NAME']


@pytest.mark.django_db
def test_gemini_unavailable_falls_back_and_worker_retry_cannot_repeat_paid_call(
    client, candidate_account, settings,
):
    from unittest.mock import Mock

    from talent.ai_providers import AIProviderUnavailable
    from talent.models import ResumeAIUsage

    settings.RESUME_AI_ENABLED = True
    settings.RESUME_AI_EXTERNAL_PROCESSING_APPROVED = True
    settings.RESUME_AI_PROVIDER = 'gemini'
    settings.RESUME_AI_MODEL = 'synthetic-gemini-model'
    settings.RESUME_AI_ALLOW_PAID = False
    settings.RESUME_AI_GEMINI_FREE_TIER_APPROVED = False
    settings.RESUME_AI_MAX_ATTEMPTS = 1
    settings.RESUME_AI_ROLLOUT_MODE = 'consenting'
    settings.RESUME_AI_FALLBACK = 'rules'
    settings.LEGAL_RESUME_AI_VERSION = 'test-consent'
    settings.LEGAL_RESUME_AI_SHA256 = '1' * 64
    job = uploaded_job(client, resume_pdf([
        'Name: Asha Rao', 'EXPERIENCE',
        'Example Studio | Software Engineer | Jan 2020 - Dec 2021',
        'Built Python services.', 'Skills: Python',
    ]))
    Resume.objects.filter(pk=job.resume_id).update(
        ai_processing_consent_at=timezone.now(),
        ai_processing_consent_version=settings.LEGAL_RESUME_AI_VERSION,
        ai_processing_consent_sha256=settings.LEGAL_RESUME_AI_SHA256,
    )
    provider = Mock()
    provider.generate.side_effect = AIProviderUnavailable()
    with patch('talent.resume_understanding.resume_provider', return_value=provider):
        # A failed save after provider fallback must not buy another attempt on retry.
        with patch.object(processing, '_apply_extracted_resume', side_effect=RuntimeError):
            assert processing.process_resume_job(job.pk) == 'retry'
        ResumeProcessingJob.objects.filter(pk=job.pk).update(available_at=timezone.now())
        assert processing.process_resume_job(job.pk) == 'completed'
        assert processing.process_resume_job(job.pk) == 'duplicate'
    provider.generate.assert_called_once()
    job.resume.refresh_from_db()
    assert job.resume.processing_status == 'completed'
    assert job.resume.extracted_data['_interpretation']['source'] == 'rules'
    assert job.resume.candidate.work_experiences.exists()
    assert ResumeAIUsage.objects.filter(resume_id=job.resume_id).count() == 1
    assert client.get('/api/v1/candidate/resume-status/').data['resume'][
        'processing_status'
    ] == 'completed'
