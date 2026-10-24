from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from talent.candidate_experience import profile_values
from talent.models import CandidateProfile, Resume, ResumeProcessingJob
from talent.resume_processing import (
    _claim_job,
    _reserve_ai_attempt,
    dispatch_pending_jobs,
    process_resume_job,
)

from .test_candidate_experience import upload
from .test_candidate_flow import resume_docx, resume_pdf

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def storage(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def queued(client):
    result = client.post("/api/v1/candidate/resumes/", {
        "file": SimpleUploadedFile("synthetic.docx", resume_docx()),
    }, format="multipart")
    assert result.status_code == 202
    return ResumeProcessingJob.objects.get(resume_id=result.data["latest_resume"]["id"])


def test_different_person_cannot_merge_or_trigger_ai(client, candidate_account, monkeypatch):
    upload(client)
    client.patch("/api/v1/candidate/profile/", {
        "headline": "My corrected title", "meaningful_work": "My own answer",
        "career_preferences": {"exclusions": ["Travel"]},
    }, format="json")
    before = profile_values(CandidateProfile.objects.get())
    ai = Mock(side_effect=AssertionError("Mismatched identity must not leave the server"))
    monkeypatch.setattr("talent.resume_processing.understand_resume", ai)
    result = upload(client, resume_pdf(), "different-person.pdf").data
    assert result["resume_identity_warning"]["code"] == "identity_mismatch"
    assert result["resume_review"] is None
    assert profile_values(CandidateProfile.objects.get()) == before
    assert result["meaningful_work"] == "My own answer"
    assert result["career_preferences"]["exclusions"] == ["Travel"]
    resume_id = result["latest_resume"]["id"]
    assert result["available_resume"]["id"] == resume_id  # Owner can inspect the actual document.
    blocked = client.post(f"/api/v1/candidate/resumes/{resume_id}/review/", {
        "fields": ["work_experiences"], "profile_updated_at": result["profile_updated_at"],
    }, format="json")
    assert blocked.status_code == 409
    assert Resume.objects.get(pk=resume_id).extracted_data["_blocked_proposals"]
    ai.assert_not_called()


def test_correct_document_recovers_after_mismatch_without_duplicate_jobs(client, candidate_account):
    upload(client)
    upload(client, resume_pdf(), "different.pdf")
    result = upload(client, resume_docx(role="Staff Engineer")).data
    assert result["resume_identity_warning"] is None
    assert result["headline"] == "Staff Engineer"
    assert len(result["work_experiences"]) == 2
    assert result["resume_review"] is None


def test_identity_blocked_file_is_owner_only_even_for_approved_recruiter(
    client, candidate_account,
):
    from rest_framework.test import APIClient

    from .recruiter_helpers import provision_recruiter

    first = upload(client).data
    profile = CandidateProfile.objects.get()
    profile.profile_status = "submitted"
    profile.visibility = "approved_recruiters"
    profile.submission_consent_at = timezone.now()
    profile.save()
    result = upload(client, resume_pdf(), "different.pdf").data
    blocked = result["latest_resume"]["id"]
    assert client.get(f"/api/v1/resumes/{blocked}/download/").status_code == 200
    recruiter = APIClient()
    login = provision_recruiter(recruiter, {
        "email": "reviewer@example.test", "password": "strong-pass-123",
        "full_name": "Test Recruiter", "company": "Example", "role": "recruiter",
    })
    recruiter.credentials(HTTP_AUTHORIZATION=f"Token {login.data['token']}")
    assert recruiter.get(f"/api/v1/resumes/{blocked}/download/").status_code == 404
    assert recruiter.get(
        f"/api/v1/resumes/{first['latest_resume']['id']}/download/"
    ).status_code == 200
    assert APIClient().get(f"/api/v1/resumes/{blocked}/download/").status_code in {401, 403}


def test_legacy_mismatch_is_blocked_without_modifying_existing_records(client, candidate_account):
    upload(client)
    result = upload(client, resume_pdf(), "different.pdf").data
    resume = Resume.objects.get(pk=result["latest_resume"]["id"])
    resume.extracted_data.pop("_identity_issue")
    resume.extracted_data["_needs_review"] = True
    resume.save()
    result = client.get("/api/v1/candidate/profile/").data
    assert result["resume_identity_warning"]["code"] == "identity_mismatch"
    assert result["resume_review"] is None


@pytest.mark.parametrize("fail_old", [False, True])
def test_old_attempt_cannot_complete_or_fail_new_owner(
    client, candidate_account, monkeypatch, fail_old,
):
    from talent import resume_processing as processing

    job = queued(client)
    parse = processing.parse_resume
    entered = False

    def interrupted(file, name):
        nonlocal entered
        parsed = parse(file, name)
        if entered:
            parsed["headline"] = "New owner result"
            return parsed
        entered = True
        ResumeProcessingJob.objects.filter(pk=job.pk).update(
            locked_at=timezone.now() - timedelta(hours=1),
        )
        assert process_resume_job(job.pk) == "completed"
        if fail_old:
            raise ValueError("Sensitive document content must not be logged")
        parsed["headline"] = "Stale result"
        return parsed

    monkeypatch.setattr(processing, "parse_resume", interrupted)
    assert process_resume_job(job.pk) == "superseded"
    assert CandidateProfile.objects.get().headline == "New owner result"
    job.refresh_from_db()
    assert job.state == "completed"
    assert job.attempts == 2


def test_stale_attempt_budget_is_bounded(client, candidate_account):
    job = queued(client)
    job.state = "processing"
    job.attempts = job.max_attempts
    job.locked_at = timezone.now() - timedelta(hours=1)
    job.save()
    assert dispatch_pending_jobs() == 0
    job.refresh_from_db()
    assert job.state == "failed"
    assert process_resume_job(job.pk) == "failed"
    assert job.resume.processing_status == "failed"


def test_ai_request_budget_survives_attempt_recovery(client, candidate_account):
    job = queued(client)
    claimed, _ = _claim_job(job.pk)
    assert _reserve_ai_attempt(claimed, 1000)
    assert _reserve_ai_attempt(claimed, 1000)
    assert not _reserve_ai_attempt(claimed, 1000)
    ResumeProcessingJob.objects.filter(pk=job.pk).update(
        locked_at=timezone.now() - timedelta(hours=1),
    )
    newer, _ = _claim_job(job.pk)
    assert not _reserve_ai_attempt(claimed, 1000)
    assert not _reserve_ai_attempt(newer, 1000)
