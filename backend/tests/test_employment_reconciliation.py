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


def test_equivalent_candidate_correction_keeps_deliberately_blank_fields(candidate_account):
    profile = CandidateProfile.objects.get()
    saved = WorkExperience.objects.create(
        candidate=profile, company='Example Labs', role='Engineer',
        start_date='2024-01-01', end_date=None, is_current=False,
        date_label='Jan 2024 — End not specified',
        confidence_status='candidate_confirmed',
    )
    incoming = role('Example Labs', 'Engineer', '2024-01-01', current=True)
    assert reconcile_employment(profile, [incoming]) == []
    saved.refresh_from_db()
    assert saved.is_current is False
    assert saved.end_date is None
    assert saved.date_label == 'Jan 2024 — End not specified'
    assert row_equivalent(saved, incoming)


def test_shortened_employer_does_not_duplicate_candidate_correction(candidate_account):
    profile = CandidateProfile.objects.get()
    WorkExperience.objects.create(
        candidate=profile, company='Alpha Platform and Distributed Infrastructure Engineering',
        role='Candidate corrected role', start_date='2018-01-01', end_date='2022-12-01',
        confidence_status='candidate_confirmed',
    )
    incoming = role('Alpha', 'Engineer', '2018-01-01', '2022-12-01')
    assert reconcile_employment(profile, [incoming]) == [incoming]
    assert profile.work_experiences.count() == 1


def test_shortened_employer_matches_same_role_without_recreating_it(candidate_account):
    profile = CandidateProfile.objects.get()
    saved = WorkExperience.objects.create(
        candidate=profile, company='Alpha Platform and Distributed Infrastructure Engineering',
        role='Engineer', start_date='2018-01-01', end_date='2022-12-01',
        confidence_status='supported',
    )
    assert reconcile_employment(profile, [role('Alpha', 'Engineer', '2018-01-01',
                                               '2022-12-01')]) == []
    assert list(profile.work_experiences.values_list('id', flat=True)) == [saved.id]


def test_undated_short_name_does_not_assume_same_employer(candidate_account):
    profile = CandidateProfile.objects.get()
    WorkExperience.objects.create(candidate=profile, company='Alpha Platform', role='Engineer')
    assert reconcile_employment(profile, [role('Alpha', 'Engineer', None)]) == []
    assert profile.work_experiences.count() == 2
