import pytest
from talent.employment_reconciliation import reconcile_employment, row_equivalent
from talent.models import CandidateProfile, WorkExperience

pytestmark = pytest.mark.django_db


def role(company, title, start, end=None, current=False):
    return {
        'company': company, 'role': title, 'start_date': start,
        'end_date': end, 'is_current': current,
        'date_label': f'{start} — {end or ("Present" if current else "End not specified")}',
        'employment_type': 'Internship' if 'intern' in title.casefold() else '',
        'source_evidence': f'{title} at {company}', 'confidence_status': 'supported',
    }


def test_equivalent_reordered_roles_and_present_enrichment(candidate_account):
    profile = CandidateProfile.objects.get()
    first = role('NewSpace Research & Technologies', 'AI Intern / SDE Intern - AI',
                 '2026-01-01', '2026-07-01')
    second = role('Enter Recruitment', 'AI Full Stack Developer', '2026-09-01')
    assert reconcile_employment(profile, [first, second]) == []
    original = list(profile.work_experiences.values_list('id', flat=True))
    second['is_current'] = True
    second['date_label'] = 'Sep 2026 — Present'
    assert reconcile_employment(profile, [second, first]) == []
    assert list(profile.work_experiences.values_list('id', flat=True)) == original
    assert profile.work_experiences.get(company='Enter Recruitment').is_current


def test_additions_promotions_and_omissions_preserve_saved_rows(candidate_account):
    profile = CandidateProfile.objects.get()
    intern = role('Example Labs', 'Engineering Intern', '2023-01-01', '2023-06-01')
    engineer = role('Example Labs', 'Engineer', '2023-07-01', '2024-08-01')
    senior = role('Example Labs', 'Senior Engineer', '2024-09-01', current=True)
    assert reconcile_employment(profile, [intern, engineer]) == []
    assert reconcile_employment(profile, [senior, engineer]) == []
    assert profile.work_experiences.count() == 3
    assert reconcile_employment(profile, []) == []
    assert profile.work_experiences.count() == 3


def test_manual_title_and_material_end_date_are_reviewed(candidate_account):
    profile = CandidateProfile.objects.get()
    saved = WorkExperience.objects.create(
        candidate=profile, company='Example Labs', role='Candidate corrected title',
        start_date='2024-01-01', end_date='2024-12-01',
        confidence_status='candidate_confirmed',
    )
    saved.refresh_from_db()
    proposed = role('Example Labs', 'Engineer', '2024-01-01', '2024-12-01')
    assert reconcile_employment(profile, [proposed]) == [proposed]
    assert profile.work_experiences.count() == 1
    proposed['role'] = saved.role
    proposed['is_current'] = True
    proposed['end_date'] = None
    assert not row_equivalent(saved, proposed)
    assert reconcile_employment(profile, [proposed]) == [proposed]
    assert profile.work_experiences.get().end_date.isoformat() == '2024-12-01'
