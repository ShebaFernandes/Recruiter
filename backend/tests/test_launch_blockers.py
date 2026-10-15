import json
import subprocess
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient
from talent.models import FileCleanupJob, Resume, ResumeProcessingJob, WorkerHeartbeat
from talent.resume_processing import ClamAVResumeScanner, ResumeScanError
from talent.search_understanding import SearchUnderstandingUnavailable, understand_search
from talent.storage_cleanup import drain_cleanup, schedule_cleanup, store_private_upload
from talent.worker_runtime import run_bounded_job, worker_available

from .test_candidate_flow import resume_pdf


def test_disabled_ai_never_constructs_provider(settings):
    settings.AI_PROVIDER = "disabled"
    with patch("talent.search_understanding.get_ai_provider") as provider:
        with pytest.raises(SearchUnderstandingUnavailable) as error:
            understand_search("backend engineer")
    provider.assert_not_called()
    assert error.value.code == "search_ai_disabled"


@pytest.mark.django_db
def test_status_is_small_owner_only_and_no_store(client, candidate_account):
    profile = User.objects.get(pk=candidate_account["user"]["id"]).candidate_profile
    resume = Resume.objects.create(candidate=profile, file="quarantine/fictional.pdf",
                                   extracted_data={"raw_text": "PRIVATE RESUME TEXT"})
    response = client.get("/api/v1/candidate/resume-status/")
    assert response.status_code == 200
    assert response.data["resume"]["id"] == resume.pk
    assert "PRIVATE" not in json.dumps(response.data)
    assert "file" not in response.data["resume"]
    assert response["Cache-Control"] == "private, no-store"
    assert APIClient().get("/api/v1/candidate/resume-status/").status_code == 401
    WorkerHeartbeat.objects.create(worker_id="test", state="idle")
    assert worker_available()
    WorkerHeartbeat.objects.update(seen_at=timezone.now() - timedelta(hours=1))
    assert not worker_available()


@pytest.mark.django_db
def test_status_never_returns_another_candidates_resume(client, candidate_account):
    from talent.models import CandidateProfile

    other = User.objects.create_user("other-status@example.com", password="fictional-password")
    profile = CandidateProfile.objects.create(user=other, full_name="Other Test")
    Resume.objects.create(candidate=profile, file="quarantine/other-private.pdf")
    response = client.get("/api/v1/candidate/resume-status/")
    assert response.status_code == 200
    assert response.data["resume"] is None


@pytest.mark.django_db
def test_recruiter_cannot_use_candidate_status(client, recruiter_account):
    assert client.get("/api/v1/candidate/resume-status/").status_code == 403


@pytest.mark.django_db
def test_cleanup_retries_and_retains_live_objects(client, candidate_account, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    name = default_storage.save("private/fictional.pdf", ContentFile(b"fictional"))
    profile = User.objects.get(pk=candidate_account["user"]["id"]).candidate_profile
    resume = Resume.objects.create(candidate=profile, file=name)
    schedule_cleanup(name)
    assert drain_cleanup() == 0
    assert default_storage.exists(name)
    resume.delete()
    with patch.object(default_storage, "delete", side_effect=OSError("private error")):
        assert drain_cleanup() == 0
    job = FileCleanupJob.objects.get(name=name)
    assert job.attempts == 1
    FileCleanupJob.objects.update(available_at=timezone.now())
    assert drain_cleanup() == 1
    assert not default_storage.exists(name)


@pytest.mark.django_db(transaction=True)
def test_upload_journal_survives_profile_transaction_rollback(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    name = store_private_upload(ContentFile(b"fictional"), "quarantine", "test.pdf")
    with pytest.raises(RuntimeError), transaction.atomic():
        schedule_cleanup(name)
        raise RuntimeError("rollback")
    assert FileCleanupJob.objects.filter(name=name).exists()
    FileCleanupJob.objects.update(available_at=timezone.now())
    drain_cleanup()
    assert not default_storage.exists(name)


@pytest.mark.django_db
def test_account_delete_revokes_access_even_during_storage_outage(
    client, candidate_account, settings, tmp_path,
):
    settings.MEDIA_ROOT = tmp_path
    profile = User.objects.get(pk=candidate_account["user"]["id"]).candidate_profile
    name = default_storage.save("quarantine/test.pdf", ContentFile(b"fictional"))
    Resume.objects.create(candidate=profile, file=name)
    with patch.object(default_storage, "delete", side_effect=OSError):
        response = client.delete("/api/v1/candidate/account/", {
            "confirmation": "DELETE", "password": "strong-pass-123",
        }, format="json")
    assert response.status_code == 204
    assert not User.objects.filter(pk=candidate_account["user"]["id"]).exists()
    assert FileCleanupJob.objects.filter(name=name).exists()
    assert client.get("/api/v1/candidate/profile/").status_code == 401
    drain_cleanup()
    assert not default_storage.exists(name)


@pytest.mark.django_db
def test_supervisor_timeout_is_bounded_retryable_and_exhausts(client, candidate_account):
    response = client.post("/api/v1/candidate/resumes/", {
        "file": SimpleUploadedFile("synthetic.pdf", resume_pdf()),
    }, format="multipart")
    job = ResumeProcessingJob.objects.get(resume_id=response.data["latest_resume"]["id"])
    with patch("talent.worker_runtime.subprocess.run",
               side_effect=subprocess.TimeoutExpired("parser", 240)) as child:
        assert run_bounded_job(job.pk) == "retry"
        assert child.call_args.kwargs["timeout"] == 240
        from django.conf import settings

        assert settings.DATABASES["default"]["NAME"] in (
            child.call_args.kwargs["env"]["DATABASE_URL"]
        )
        for _ in range(2):
            ResumeProcessingJob.objects.filter(pk=job.pk).update(available_at=timezone.now())
            result = run_bounded_job(job.pk)
    assert result == "failed"
    job.refresh_from_db()
    assert job.attempts == 3
    assert job.resume.processing_status == "failed"


@pytest.mark.django_db(transaction=True)
def test_real_worker_child_uses_isolated_database(client, candidate_account):
    response = client.post("/api/v1/candidate/resumes/", {
        "file": SimpleUploadedFile("synthetic.pdf", resume_pdf()),
    }, format="multipart")
    job = ResumeProcessingJob.objects.get(resume_id=response.data["latest_resume"]["id"])
    assert run_bounded_job(job.pk) == "completed"
    assert run_bounded_job(job.pk) == "duplicate"
    job.resume.refresh_from_db()
    assert job.resume.scan_status == "clean"


def test_scanner_rejects_non_success_response():
    with patch("talent.resume_processing.socket.create_connection") as connect:
        connect.return_value.__enter__.return_value.recv.return_value = b"NOT OK\0"
        with pytest.raises(ResumeScanError):
            ClamAVResumeScanner().scan(ContentFile(b"fictional"))
