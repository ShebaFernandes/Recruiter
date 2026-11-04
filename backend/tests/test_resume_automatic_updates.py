import pytest
from django.test import override_settings

from .test_candidate_experience import upload
from .test_candidate_flow import resume_docx

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolated_resume_storage(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.RESUME_AI_ENABLED = False


def test_latest_resume_preserves_manual_profile_correction(client, candidate_account):
    upload(client)
    response = client.patch('/api/v1/candidate/profile/', {
        'headline': 'Manually corrected title',
    }, format='json')
    assert response.status_code == 200
    updated = upload(client, resume_docx(role='Principal Engineer')).data
    assert updated['headline'] == 'Manually corrected title'
    assert 'headline' in updated['resume_review']['fields']


@override_settings(RESUME_AI_ENABLED=False)
def test_new_resume_adds_career_role_without_review(client, candidate_account):
    upload(client)
    updated = upload(client, resume_docx(role='Principal Engineer', extra=(
        'Experience: Advisor|New Studio|2025-01-01|Present|Advises engineers'
    ))).data
    assert updated['headline'] == 'Principal Engineer'
    assert updated['resume_review'] is None
    assert any(row['company'] == 'New Studio' for row in updated['work_experiences'])


def test_unchanged_replacement_does_not_duplicate_jobs(client, candidate_account):
    first = upload(client).data
    second = upload(client).data
    assert [r['id'] for r in second['work_experiences']] == [
        r['id'] for r in first['work_experiences']
    ]


def test_modified_confirmed_role_requires_review(client, candidate_account):
    from talent.models import CandidateProfile
    upload(client)
    row = CandidateProfile.objects.get().work_experiences.get(company='SignalWorks')
    row.role = 'Candidate corrected engineer'
    row.confidence_status = 'candidate_confirmed'
    row.save()
    updated = upload(client, resume_docx(role='Principal Engineer')).data
    row.refresh_from_db()
    assert row.role == 'Candidate corrected engineer'
    assert row.archived_at is None
    assert len([r for r in updated['work_experiences'] if r['company'] == 'SignalWorks']) == 1
    assert 'work_experiences' in updated['resume_review']['fields']


def test_ambiguous_new_employment_requires_review(client, candidate_account):
    from talent.employment_reconciliation import reconcile_employment
    from talent.models import CandidateProfile
    upload(client)
    profile = CandidateProfile.objects.get()
    proposed = {
        'company': 'Uncertain Studio', 'role': 'Engineer', 'start_date': None,
        'end_date': None, 'confidence_status': 'partial',
        'source_evidence': 'Engineer at Uncertain Studio',
    }
    assert reconcile_employment(profile, [proposed]) == [proposed]
    assert not profile.work_experiences.filter(company='Uncertain Studio').exists()
