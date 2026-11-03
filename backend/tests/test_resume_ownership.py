"""Fictional ownership declarations; no provider or private production files."""

from io import BytesIO
from unittest.mock import Mock

import pytest
from docx import Document
from talent.models import CandidateProfile, Resume, ResumeProcessingJob
from talent.resume_processing import process_resume_job

from .test_candidate_experience import upload

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def private_storage(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def fictional_resume(*lines):
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def ambiguous_resume():
    return fictional_resume(
        'Platform Engineer', 'Email: former-address@example.test',
        'Work Experience',
        'Work: Platform Engineer|Fictional Harbor|2020-01-01|2022-01-01|Built systems',
    )


def confirm(client, resume, password='strong-pass-123', **other):
    return client.post(f'/api/v1/candidate/resumes/{resume.pk}/confirm-ownership/', {
        'version': resume.version, 'password': password, 'confirmation': True, **other,
    }, format='json')


def test_unverified_ownership_is_version_hash_bound_and_retry_is_offline(
    client, candidate_account, monkeypatch,
):
    first = upload(client).data
    previous_ids = {row['id'] for row in first['work_experiences']}
    second = upload(client, ambiguous_resume(), 'fictional-ambiguous.docx').data
    resume = CandidateProfile.objects.get().resumes.first()
    assert second['resume_identity_warning']['code'] == 'identity_unverified'
    assert second['resume_identity_warning']['can_confirm'] is True
    assert len(resume.file_sha256) == 64
    assert {row['id'] for row in second['work_experiences']} == previous_ids
    assert resume.ownership_confirmed_at is None

    wrong = confirm(client, resume, password='incorrect-password')
    assert wrong.status_code == 400
    resume.refresh_from_db()
    assert resume.ownership_confirmed_at is None

    accepted = confirm(client, resume)
    assert accepted.status_code == 200
    assert accepted.data['resume_identity_warning'] is None
    assert {row['id'] for row in accepted.data['work_experiences']} == previous_ids
    resume.refresh_from_db()
    assert resume.ownership_confirmed_at is not None
    assert resume.ownership_confirmed_file_sha256 == resume.file_sha256
    assert accepted.data['employment_extraction']['reason_code'] == (
        'identity_confirmed_offline_retry_available'
    )

    paid = Mock(side_effect=AssertionError('No provider request belongs in an offline retry'))
    monkeypatch.setattr('talent.resume_understanding.resume_provider', paid)
    queued = client.post(f'/api/v1/candidate/resumes/{resume.pk}/retry/')
    assert queued.status_code == 202
    job = ResumeProcessingJob.objects.get(resume=resume)
    assert process_resume_job(job.pk, str(job.idempotency_key)) == 'completed'
    refreshed = client.get('/api/v1/candidate/profile/').data
    assert refreshed['resume_identity_warning'] is None
    assert ('Fictional Harbor', 'Platform Engineer') in {
        (row['company'], row['role']) for row in refreshed['work_experiences']
    }
    assert previous_ids <= {row['id'] for row in refreshed['work_experiences']}
    assert refreshed['archived_work_experiences'] == []
    resume.refresh_from_db()
    assert resume.extracted_data.get('_ai_requests', 0) == 0
    paid.assert_not_called()


def test_confirmation_rejects_changed_file_old_version_and_other_candidate(
    client, candidate_account,
):
    upload(client)
    upload(client, ambiguous_resume(), 'fictional-ambiguous.docx')
    resume = CandidateProfile.objects.get().resumes.first()
    original_hash = resume.file_sha256
    resume.file_sha256 = '0' * 64
    resume.save(update_fields=['file_sha256'])
    assert confirm(client, resume).status_code == 409
    resume.refresh_from_db()
    assert resume.ownership_confirmed_at is None
    resume.file_sha256 = original_hash
    resume.save(update_fields=['file_sha256'])
    assert confirm(client, resume, version=resume.version + 1).status_code == 409
    upload(client, fictional_resume('Name: Asha Rao', 'Skills: Python'), 'newer.docx')
    assert confirm(client, resume).status_code == 409

    from rest_framework.test import APIClient

    stranger = APIClient()
    assert stranger.post(
        f'/api/v1/candidate/resumes/{resume.pk}/confirm-ownership/',
        {'version': resume.version, 'password': 'strong-pass-123', 'confirmation': True},
        format='json',
    ).status_code in {401, 403}


def test_explicit_other_person_cannot_be_confirmed(client, candidate_account):
    upload(client)
    second = upload(client, fictional_resume(
        'Name: Other Person', 'Email: other@example.test',
        'Work: Engineer|Fictional Harbor|2020-01-01|2022-01-01|Built systems',
    ), 'other-person.docx').data
    resume = Resume.objects.get(pk=second['latest_resume']['id'])
    assert second['resume_identity_warning']['code'] == 'identity_mismatch'
    assert second['resume_identity_warning']['can_confirm'] is False
    assert confirm(client, resume).status_code == 409
    resume.refresh_from_db()
    assert resume.ownership_confirmed_at is None


def test_plausible_other_header_name_is_not_ownership_confirmable(
    client, candidate_account,
):
    upload(client)
    second = upload(client, fictional_resume(
        'Other Person', 'Email: other@example.test',
        'Work: Engineer|Fictional Harbor|2020-01-01|2022-01-01|Built systems',
    ), 'ambiguous-other-person.docx').data
    resume = Resume.objects.get(pk=second['latest_resume']['id'])
    assert second['resume_identity_warning']['code'] == 'identity_unverified'
    assert second['resume_identity_warning']['can_confirm'] is False
    assert confirm(client, resume).status_code == 409


def test_zero_role_profile_recovers_only_after_candidate_retry(client, candidate_account):
    first = upload(client, fictional_resume(
        'Name: Asha Rao', 'Skills: Python',
    ), 'fictional-fresher.docx').data
    assert first['work_experiences'] == []
    blocked = upload(client, ambiguous_resume(), 'fictional-ambiguous.docx').data
    resume = Resume.objects.get(pk=blocked['latest_resume']['id'])
    assert blocked['work_experiences'] == []
    assert confirm(client, resume).status_code == 200
    assert client.get('/api/v1/candidate/profile/').data['work_experiences'] == []
    assert client.post(f'/api/v1/candidate/resumes/{resume.pk}/retry/').status_code == 202
    job = ResumeProcessingJob.objects.get(resume=resume)
    assert process_resume_job(job.pk, str(job.idempotency_key)) == 'completed'
    refreshed = client.get('/api/v1/candidate/profile/').data
    assert [(row['company'], row['role']) for row in refreshed['work_experiences']] == [
        ('Fictional Harbor', 'Platform Engineer')
    ]
    assert refreshed['resume_review'] is None


def test_confirmation_requires_explicit_declaration_and_rate_limits_password_guesses(
    client, candidate_account,
):
    upload(client)
    upload(client, ambiguous_resume(), 'fictional-ambiguous.docx')
    resume = CandidateProfile.objects.get().resumes.first()
    assert confirm(client, resume, confirmation=False).status_code == 400
    statuses = [confirm(client, resume, password='wrong').status_code for _ in range(5)]
    assert statuses[-1] == 429
    resume.refresh_from_db()
    assert resume.ownership_confirmed_at is None
