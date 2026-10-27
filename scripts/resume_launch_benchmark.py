"""Offline fictional parsing, validation and PostgreSQL persistence benchmark."""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'scripts')]

database_url = os.environ.get('DATABASE_URL', '')
if not database_url.startswith('postgresql://enter:enter@127.0.0.1:5433/enter'):
    raise SystemExit('Use only the local PostgreSQL test connection.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['RESUME_AI_ENABLED'] = 'false'
os.environ['AWS_EC2_METADATA_DISABLED'] = 'true'

import django  # noqa: E402

django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.test.utils import setup_databases, teardown_databases  # noqa: E402
from replay_gemini_varied_benchmark_offline import (  # noqa: E402
    endpoint_correct,
    normal,
    provider_fixture,
)
from resume_accuracy_benchmark import run as parser_benchmark  # noqa: E402
from talent.employment_reconciliation import reconcile_employment, trusted_rows  # noqa: E402
from talent.models import CandidateProfile  # noqa: E402
from talent.resume_understanding import interpretation_text, validate_interpretation  # noqa: E402
from talent.services import parse_resume  # noqa: E402

MANIFEST = ROOT / '.local-benchmark/gemini-varied/manifest.json'
REPORT = ROOT / '.local-benchmark/resume-launch-benchmark.json'


def score_rows(expected, rows):
    actual = {(normal(row['company']), normal(row['role'])): row for row in rows}
    expected_keys = {(normal(row['company']), normal(row['title'])) for row in expected}
    matches = 0
    date_hits = 0
    date_total = 0
    for role in expected:
        row = actual.get((normal(role['company']), normal(role['title'])))
        if row:
            matches += 1
            date_hits += endpoint_correct(role['start'], row.get('start_date'),
                                          row.get('date_label') or '', 0)
            date_hits += endpoint_correct(role['end'], row.get('end_date'),
                                          row.get('date_label') or '', 1)
        date_total += 2
    return {
        'expected': len(expected), 'observed': len(rows), 'matched': matches,
        'false_positives': len(actual.keys() - expected_keys),
        'date_hits': date_hits, 'date_total': date_total,
    }


def summarize(rows):
    totals = defaultdict(int)
    for row in rows:
        for key in ('expected', 'observed', 'matched', 'false_positives',
                    'date_hits', 'date_total'):
            totals[key] += row[key]
    return {
        **totals,
        'precision': round(totals['matched'] / totals['observed'], 4)
        if totals['observed'] else 1.0,
        'recall': round(totals['matched'] / totals['expected'], 4)
        if totals['expected'] else 1.0,
        'date_accuracy': round(totals['date_hits'] / totals['date_total'], 4)
        if totals['date_total'] else 1.0,
    }


def main():
    manifest = json.loads(MANIFEST.read_text())
    parser_result = parser_benchmark()
    database_config = setup_databases(verbosity=0, interactive=False)
    results = []
    try:
        for index, case in enumerate(manifest['documents']):
            path = Path(case['path'])
            with path.open('rb') as source:
                parsed = parse_resume(source, path.name)
            expected = case['expected']['work_experiences']
            text = interpretation_text(parsed)
            provider_response = provider_fixture(case, text)
            schema_failure = False
            try:
                validated = validate_interpretation(provider_response, text)
                accepted = trusted_rows(validated)
            except Exception:
                schema_failure = True
                accepted = []
            user = User.objects.create_user(username=f'fictional-benchmark-{index}')
            profile = CandidateProfile.objects.create(
                user=user, full_name='Fictional Benchmark',
                email=f'fictional-benchmark-{index}@example.invalid',
            )
            reconcile_employment(profile, accepted)
            saved = list(profile.work_experiences.values(
                'company', 'role', 'start_date', 'end_date', 'date_label',
            ))
            for row in saved:
                for key in ('start_date', 'end_date'):
                    if row[key] is not None:
                        row[key] = row[key].isoformat()
            results.append({
                'case': case['slug'], 'kind': case['path'].rsplit('.', 1)[-1],
                'parsed': score_rows(expected, parsed['work_experiences']),
                'validated': score_rows(expected, accepted),
                'saved': score_rows(expected, saved),
                'schema_failure': schema_failure,
                'validation_rejection_categories': sorted({
                    rejection.get('category', '')
                    for rejection in validated.get('_validation_rejections', [])
                }) if not schema_failure else [],
            })
    finally:
        teardown_databases(database_config, verbosity=0)
    report = {
        'mode': 'fictional-offline-mocked-provider-local-postgresql',
        'external_ai_requests': 0,
        'parser_fixtures': parser_result['fixture_count'],
        'parser_precision': parser_result['employment_role_precision'],
        'parser_recall': parser_result['employment_role_recall'],
        'parser_date_accuracy': parser_result['date_accuracy'],
        'parser_false_positives': parser_result['unsupported_rows'],
        'mocked_gemini_fixtures': len(results),
        'schema_failures': sum(item['schema_failure'] for item in results),
        'stages': {stage: summarize([item[stage] for item in results])
                   for stage in ('parsed', 'validated', 'saved')},
        'cases': results,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'cases'}, indent=2))


if __name__ == '__main__':
    main()
