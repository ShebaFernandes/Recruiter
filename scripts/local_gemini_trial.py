"""Explicitly authorized, isolated fictional Gemini trial; default is offline preflight."""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / '.local-benchmark' / 'gemini-trial'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--continue-after-connectivity-repair', action='store_true')
    args = parser.parse_args()
    # This file contains only local settings and a path to the worker credential.
    for line in (FOLDER / 'local.env').read_text().splitlines():
        key, value = line.split('=', 1)
        os.environ[key] = value
    sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'scripts')]
    import django
    django.setup()
    from io import BytesIO

    from django.conf import settings
    from django.contrib.auth.models import User
    from django.core.files.base import ContentFile
    from django.core.management import call_command
    from django.db import connection
    from django.utils import timezone
    from resume_accuracy_benchmark import cases, document
    from talent.models import CandidateProfile, Resume, ResumeAIUsage, ResumeProcessingJob
    from talent.resume_processing import process_resume_job
    from talent.resume_understanding import interpretation_text, request_input_token_reservation
    from talent.services import parse_resume

    assert settings.APP_ENV == 'local'
    assert connection.settings_dict['HOST'] == '127.0.0.1'
    assert connection.settings_dict['NAME'] == 'enter_resume_ai_trial'
    assert settings.STORAGES['default']['BACKEND'] == 'django.core.files.storage.FileSystemStorage'
    assert settings.RESUME_QUEUE_BACKEND == 'database'
    assert settings.RESUME_AI_PROVIDER == 'gemini'
    assert settings.RESUME_AI_MODEL == 'gemini-3.5-flash-lite'
    assert settings.GEMINI_API_BASE_URL == 'https://generativelanguage.googleapis.com/v1beta'
    assert settings.RESUME_AI_DAILY_BUDGET_USD == Decimal('0.10')
    assert settings.RESUME_AI_MONTHLY_BUDGET_USD == Decimal('1')
    assert settings.RESUME_AI_MAX_ATTEMPTS == 1
    assert settings.RESUME_AI_MAX_OUTPUT_TOKENS == 3000
    assert settings.RESUME_AI_INPUT_USD_PER_MILLION == Decimal('0.30')
    assert settings.RESUME_AI_OUTPUT_USD_PER_MILLION == Decimal('2.50')
    assert settings.RESUME_AI_ROLLOUT_MODE == 'canary'
    assert settings.RESUME_AI_FALLBACK == 'rules'
    assert settings.RESUME_AI_ALLOW_PAID and not settings.RESUME_AI_GEMINI_FREE_TIER_APPROVED
    call_command('migrate', verbosity=0, interactive=False)
    chosen = [case for case in cases() if not case.table and not case.image_only][:10]
    prepared = []
    for case in chosen:
        fictional = replace(case, lines=['Name: Fictional Candidate', *case.lines])
        content, filename = document(fictional)
        parsed = parse_resume(BytesIO(content), filename)
        tokens = request_input_token_reservation(interpretation_text(parsed),
                                                 parsed.get('_layout_regions') or [])
        reservation = (Decimal(tokens) * Decimal('0.30') + Decimal(3000) * Decimal('2.50'))
        reservation /= Decimal('1000000')
        prepared.append((case, content, filename, reservation))
    batch_ceiling = sum(x[3].quantize(Decimal('0.000001'), rounding=ROUND_CEILING)
                        for x in prepared)
    assert batch_ceiling <= settings.RESUME_AI_DAILY_BUDGET_USD
    print(json.dumps({'mode': 'execute' if args.execute else 'offline-preflight',
                      'fictional_resumes': len(prepared), 'daily_cap_usd': '0.10',
                      'monthly_cap_usd': '1.00', 'max_calls_per_resume': 1,
                      'maximum_single_reservation_usd': str(max(x[3] for x in prepared))}),
          flush=True)
    if not args.execute:
        return
    # Keep this authorization bounded across reruns, including failures/timeouts.
    report_path = FOLDER / 'results.json'
    results = json.loads(report_path.read_text()) if report_path.exists() else []
    if ResumeAIUsage.objects.count():
        if not args.continue_after_connectivity_repair:
            raise SystemExit('Trial already has usage. Review its report before another run.')
        assert len(results) == ResumeAIUsage.objects.count()
        assert len(results) < 10
    done = {result['fixture'] for result in results}
    for number, (case, content, filename, _) in enumerate(prepared):
        if case.name in done:
            continue
        user = User.objects.create_user(f'fictional-trial-{number}@example.test')
        profile = CandidateProfile.objects.create(user=user, full_name='Fictional Candidate',
                                                 email_verified_at=timezone.now())
        resume = Resume(candidate=profile, original_name=filename, version=1,
                        processing_status='queued', scan_status='clean',
                        ai_processing_consent_at=timezone.now(),
                        ai_processing_consent_version=settings.LEGAL_RESUME_AI_VERSION,
                        ai_processing_consent_sha256=settings.LEGAL_RESUME_AI_SHA256)
        resume.file.save(filename, ContentFile(content), save=False)
        resume.save()
        settings.RESUME_AI_CANARY_RESUME_IDS = {resume.pk}
        job = ResumeProcessingJob.objects.create(resume=resume, max_attempts=1,
                                                enqueued_at=timezone.now())
        outcome = process_resume_job(job.pk, str(job.idempotency_key))
        resume.refresh_from_db()
        profile.refresh_from_db()
        usage = resume.ai_usage.first()
        expected = {(r.company.casefold(), r.title.casefold(), r.start, r.end)
                    for r in case.roles}
        actual = {(r.company.casefold(), r.role.casefold(),
                   r.start_date.isoformat() if r.start_date else None,
                   r.end_date.isoformat() if r.end_date else None)
                  for r in profile.work_experiences.all()}
        result = {'fixture': case.name, 'job_outcome': outcome,
                  'source': resume.extracted_data.get('_interpretation', {}),
                  'expected_roles': len(expected), 'saved_roles': len(actual),
                  'career_records_exact': actual == expected,
                  'missing_roles': len(expected - actual), 'extra_roles': len(actual - expected),
                  'api_calls': resume.ai_usage.count(),
                  'cost_from_reported_tokens_usd': str(
                      (Decimal(usage.input_tokens) * settings.RESUME_AI_INPUT_USD_PER_MILLION
                       + Decimal(usage.output_tokens) * settings.RESUME_AI_OUTPUT_USD_PER_MILLION)
                      / Decimal('1000000'))
                  if usage and usage.actual_cost_usd is not None else None,
                  'held_reservation_usd': str(usage.estimated_cost_usd)
                  if usage and usage.actual_cost_usd is None else '0',
                  'input_tokens': usage.input_tokens if usage else 0,
                  'output_tokens': usage.output_tokens if usage else 0,
                  'failure': usage.failure_category if usage else '',
                  'http_status': usage.http_status if usage else None,
                  'validation_rejections': usage.validation_rejections if usage else []}
        results.append(result)
        (FOLDER / 'results.json').write_text(json.dumps(results, indent=2))
        print(json.dumps(result), flush=True)
        # Stop on unconfirmed billing or provider failures; never keep paying blindly.
        if usage and (usage.failure_category or usage.actual_cost_usd is None):
            break
    print('Report: ' + str(FOLDER / 'results.json'), flush=True)


if __name__ == '__main__':
    main()
