from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from docx import Document
from talent.models import CandidateProfile, ResumeProcessingJob
from talent.resume_processing import process_resume_job

from .test_candidate_experience import upload
from .test_candidate_flow import resume_docx, resume_pdf
from .test_resume_promotions import promotion_lines

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def private_storage(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def patch(client, data):
    response = client.patch("/api/v1/candidate/profile/", data, format="json")
    assert response.status_code == 200, response.data
    return response.data


def test_initial_and_safe_replacement_open_saved_profile_without_review(client, candidate_account):
    initial = upload(client).data
    assert initial["resume_review"] is None
    history_ids = [row["id"] for row in initial["work_experiences"]]
    updated = upload(client, resume_docx(role="Staff Engineer")).data
    assert updated["headline"] == "Staff Engineer"
    assert updated["resume_review"] is None
    assert [row["id"] for row in updated["work_experiences"]] == history_ids
    updated = upload(client, resume_docx(extra=(
        "Experience: Advisor|New Studio|2025-01-01|Present|Advises engineers"
    ))).data
    assert len(updated["work_experiences"]) == 3
    assert updated["resume_review"] is None
    job = ResumeProcessingJob.objects.get(resume_id=updated["latest_resume"]["id"])
    assert process_resume_job(job.pk) == "duplicate"
    assert CandidateProfile.objects.get().work_experiences.count() == 3


def test_manual_clears_zero_and_beyond_cv_survive_multiple_replacements(client, candidate_account):
    upload(client)
    patch(client, {
        "headline": "My corrected role", "location": "", "notice_period_days": 0,
        "meaningful_work": "My own contribution",
        "career_preferences": {"motivators": ["Founder"], "exclusions": ["Travel"],
                               "custom_exclusions": ["Travel"], "standout_signal": ""},
    })
    data = upload(
        client, resume_docx(role="Principal Engineer", extra="Achievement: Built APIs")
    ).data
    assert data["headline"] == "My corrected role"
    assert data["location"] == ""
    assert data["notice_period_days"] == 0
    assert data["career_preferences"]["standout_signal"] == ""
    first_pending = data["resume_review"]["resume_id"]
    data = upload(client, resume_pdf(["Name: Asha Rao"]), "replacement.pdf").data
    assert data["resume_review"]["resume_id"] == first_pending
    assert data["meaningful_work"] == "My own contribution"
    assert data["career_preferences"]["custom_exclusions"] == ["Travel"]
    assert data["career_preferences"]["motivators"] == ["Founder"]
    # Accept one conflict; the other conflicts remain, including on an older resume.
    result = client.post(f"/api/v1/candidate/resumes/{first_pending}/review/", {
        "fields": ["headline"], "keep_pending": True,
        "profile_updated_at": data["profile_updated_at"],
    }, format="json")
    assert result.status_code == 200, result.data
    assert result.data["headline"] == "Principal Engineer"
    assert "headline" not in result.data["resume_review"]["fields"]
    assert "location" in result.data["resume_review"]["fields"]
    assert result.data["latest_resume"]["original_name"] == "replacement.pdf"


def test_zero_role_replacement_marks_previous_history_as_stale_not_verified(
    client, candidate_account,
):
    initial = upload(client).data
    saved_roles = len(initial["work_experiences"])

    replacement = upload(
        client,
        resume_pdf([
            "Name: Asha Rao",
            "Skills: Python",
            "Career details available on request.",
        ]),
        "fictional-unresolved.pdf",
    ).data

    assert len(replacement["work_experiences"]) == saved_roles
    assert {key: replacement["employment_extraction"][key] for key in (
        "status", "source", "reason_code", "accepted_role_count", "saved_role_count",
        "profile_state", "stale_profile_preserved",
    )} == {
        "status": "review_required",
        "source": "rules",
        "reason_code": "no_supported_roles_detected",
        "accepted_role_count": 0,
        "saved_role_count": saved_roles,
        "profile_state": "previous_history_preserved",
        "stale_profile_preserved": True,
    }


def test_one_role_replacement_keeps_omitted_history_without_false_conflict(
    client, candidate_account,
):
    initial = upload(client).data
    original_ids = [row['id'] for row in initial['work_experiences']]
    replacement = upload(client, resume_pdf([
        'Name: Asha Rao',
        'Work Experience',
        'Experience: Senior Backend Engineer|SignalWorks|2022-01-01|Present|Owned payments APIs',
    ]), 'fictional-one-role.pdf').data
    latest = CandidateProfile.objects.get().resumes.first()

    assert [row['id'] for row in replacement['work_experiences']] == original_ids
    assert replacement['resume_review'] is None
    assert replacement['employment_extraction']['accepted_role_count'] == 1
    assert len(replacement['employment_extraction']['verified_role_ids']) == 1
    assert len(replacement['employment_extraction']['unverified_role_ids']) == 1
    assert replacement['employment_extraction']['profile_state'] == 'previous_history_preserved'
    assert latest.extracted_data['_employment_outcome']['profile_state'] == (
        'previous_history_preserved'
    )
    assert latest.extracted_data['_employment_outcome']['stale_profile_preserved'] is True


def test_manual_role_conflict_is_optional_and_other_roles_stay_saved(client, candidate_account):
    first = upload(client).data
    edited = [dict(row) for row in first['work_experiences']]
    edited[0]['role'] = 'Candidate corrected role'
    patch(client, {'work_experiences': edited})
    replacement = upload(client).data
    assert len(replacement['work_experiences']) == 2
    assert any(row['role'] == 'Candidate corrected role'
               for row in replacement['work_experiences'])
    assert replacement['resume_review'] is not None
    assert len(replacement['resume_review']['fields']['work_experiences']) == 1
    saved_ids = {row['id'] for row in replacement['work_experiences']}
    accepted = client.post(
        f"/api/v1/candidate/resumes/{replacement['resume_review']['resume_id']}/review/",
        {'fields': ['work_experiences'], 'keep_pending': True,
         'profile_updated_at': replacement['profile_updated_at']}, format='json',
    )
    assert accepted.status_code == 200, accepted.data
    assert {row['id'] for row in accepted.data['work_experiences']} == saved_ids
    assert accepted.data['resume_review'] is None


def test_legacy_provenance_is_not_assumed(client, candidate_account):
    upload(client)
    profile = CandidateProfile.objects.get()
    resume = profile.resumes.first()
    resume.extracted_data.pop("_auto_applied")
    resume.save(update_fields=["extracted_data"])
    data = upload(client, resume_docx(role="Principal Engineer")).data
    assert data["headline"] == "Senior Backend Engineer"
    assert set(data["resume_review"]["fields"]) == {"headline"}


def test_edit_during_processing_is_preserved(client, candidate_account):
    upload(client)
    accepted = client.post("/api/v1/candidate/resumes/", {
        "file": SimpleUploadedFile("next.docx", resume_docx(role="Staff Engineer")),
    }, format="multipart")
    assert accepted.status_code == 202
    patch(client, {"headline": "Edit made while queued"})
    job = ResumeProcessingJob.objects.get(resume_id=accepted.data["latest_resume"]["id"])
    assert process_resume_job(job.pk) == "completed"
    data = client.get("/api/v1/candidate/profile/").data
    assert data["headline"] == "Edit made while queued"
    assert data["resume_review"]["fields"]["headline"] == "Staff Engineer"


def test_out_of_order_completion_cannot_overwrite_newer_profile(client, candidate_account):
    upload(client)
    jobs = []
    for role in ("Staff Engineer", "Principal Engineer"):
        response = client.post("/api/v1/candidate/resumes/", {
            "file": SimpleUploadedFile("resume.docx", resume_docx(role=role)),
        }, format="multipart")
        jobs.append(ResumeProcessingJob.objects.get(resume_id=response.data["latest_resume"]["id"]))
    assert process_resume_job(jobs[1].pk) == "completed"
    assert process_resume_job(jobs[0].pk) == "completed"
    data = client.get("/api/v1/candidate/profile/").data
    assert data["headline"] == "Principal Engineer"
    assert data["resume_review"]["fields"]["headline"] == "Staff Engineer"


def test_pending_conflicts_do_not_block_submission(client, candidate_account):
    upload(client)
    patch(client, {
        "headline": "My corrected title", "work_preferences": ["Remote"],
        "visibility": "approved_recruiters", "meaningful_work": "Built reliable systems.",
    })
    data = upload(client, resume_docx(role="Staff Engineer")).data
    assert data["resume_review"] is not None
    assert data["can_submit"] is True
    response = client.post("/api/v1/candidate/profile/submit/", {"consent": True}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["resume_review"] is not None
    assert response.data["headline"] == "My corrected title"


def test_new_supported_roles_apply_while_unrelated_candidate_correction_survives(
    client, candidate_account,
):
    initial = upload(client).data
    initial["work_experiences"][0]["role"] = "Candidate corrected role"
    patch(client, {
        "work_experiences": initial["work_experiences"],
        "meaningful_work": "My saved Beyond the CV answer",
    })
    document = Document()
    lines = promotion_lines()
    lines[0] = "Name: Asha Rao"
    for line in lines:
        document.add_paragraph(line)
    content = SimpleUploadedFile(
        "complete-career.docx", _document_bytes(document),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    accepted = client.post("/api/v1/candidate/resumes/", {"file": content}, format="multipart")
    assert accepted.status_code == 202, accepted.data
    job = ResumeProcessingJob.objects.get(resume_id=accepted.data["latest_resume"]["id"])
    assert process_resume_job(job.pk, str(job.idempotency_key)) == "completed"
    pending = client.get("/api/v1/candidate/profile/").data
    assert pending["resume_review"] is None
    assert len(pending["work_experiences"]) == 9
    assert len({row["id"] for row in pending["work_experiences"]}) == 9
    assert any(row["role"] == "Candidate corrected role"
               for row in pending["work_experiences"])
    assert any(row["is_current"] and row["end_date"] is None
               for row in pending["work_experiences"])
    assert pending["meaningful_work"] == "My saved Beyond the CV answer"


def _document_bytes(document):
    content = BytesIO()
    document.save(content)
    return content.getvalue()
