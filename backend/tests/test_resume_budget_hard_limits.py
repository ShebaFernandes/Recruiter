"""Budget gates use synthetic records only; no provider requests are made."""
from decimal import Decimal

import pytest
from django.utils import timezone
from talent.models import CandidateProfile, Resume, ResumeAIUsage, ResumeProcessingJob
from talent.resume_processing import _record_ai_attempt, _reserve_ai_attempt


@pytest.fixture
def caps(settings):
    settings.RESUME_AI_ALLOW_PAID = True
    settings.RESUME_AI_MAX_ATTEMPTS = 1
    settings.RESUME_AI_DAILY_BUDGET_USD = Decimal('0.10')
    settings.RESUME_AI_MONTHLY_BUDGET_USD = Decimal('1')
    settings.RESUME_AI_INPUT_USD_PER_MILLION = Decimal('10')
    settings.RESUME_AI_OUTPUT_USD_PER_MILLION = Decimal('0')


def job_for(profile):
    resume = Resume.objects.create(candidate=profile, file='fictional.pdf',
                                   original_name='fictional.pdf')
    return ResumeProcessingJob.objects.create(resume=resume, state='processing', attempts=1,
                                             locked_at=timezone.now())


@pytest.mark.django_db
@pytest.mark.parametrize(('daily', 'monthly', 'held'), [
    ('0.10', '1', '0.095'), ('1', '0.10', '0.095'),
])
def test_uncertain_failure_keeps_budget_reserved(caps, settings, candidate_account,
                                               daily, monthly, held):
    profile = CandidateProfile.objects.get()
    settings.RESUME_AI_DAILY_BUDGET_USD = Decimal(daily)
    settings.RESUME_AI_MONTHLY_BUDGET_USD = Decimal(monthly)
    old = job_for(profile)
    usage = ResumeAIUsage.objects.create(resume=old.resume, attempt=1, provider='gemini',
                                        model='synthetic', outcome='reserved',
                                        estimated_cost_usd=Decimal(held))
    _record_ai_attempt(usage.pk, None, 'timeout', 100)
    usage.refresh_from_db()
    assert usage.actual_cost_usd is None
    assert usage.outcome == 'failed'
    assert _reserve_ai_attempt(job_for(profile), 1000) is False


@pytest.mark.django_db
def test_resume_cannot_purchase_a_second_attempt(caps, candidate_account):
    job = job_for(CandidateProfile.objects.get())
    assert _reserve_ai_attempt(job, 1000)
    assert _reserve_ai_attempt(job, 1000) is False
    assert job.resume.ai_usage.count() == 1


@pytest.mark.django_db
def test_reservation_rounds_up_not_down(caps, settings, candidate_account):
    settings.RESUME_AI_INPUT_USD_PER_MILLION = Decimal('0.30')
    usage_id = _reserve_ai_attempt(job_for(CandidateProfile.objects.get()), 1)
    assert ResumeAIUsage.objects.get(pk=usage_id).estimated_cost_usd == Decimal('0.000001')


@pytest.mark.django_db(transaction=True)
def test_concurrent_workers_cannot_exceed_daily_cap(caps, candidate_account):
    from concurrent.futures import ThreadPoolExecutor

    from django.db import close_old_connections
    from talent.models import RateLimitBucket

    profile = CandidateProfile.objects.get()
    jobs = [job_for(profile), job_for(profile)]
    RateLimitBucket.objects.create(key='resume-ai-budget', window_started_at=timezone.now())

    def reserve(job):
        close_old_connections()
        try:
            return bool(_reserve_ai_attempt(job, 6000))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve, jobs)) == [False, True]
    total = sum(ResumeAIUsage.objects.values_list('estimated_cost_usd', flat=True))
    assert total <= Decimal('0.10')


@pytest.mark.django_db
def test_confirmed_cost_rounds_up_for_budget_accounting(caps, settings, candidate_account):
    from talent.ai_providers import AIProviderResult

    settings.RESUME_AI_INPUT_USD_PER_MILLION = Decimal('0.30')
    usage_id = _reserve_ai_attempt(job_for(CandidateProfile.objects.get()), 1)
    response = AIProviderResult(data={}, provider='gemini', model='synthetic', input_tokens=1)
    _record_ai_attempt(usage_id, response, None, 1)
    assert ResumeAIUsage.objects.get(pk=usage_id).actual_cost_usd == Decimal('0.000001')
