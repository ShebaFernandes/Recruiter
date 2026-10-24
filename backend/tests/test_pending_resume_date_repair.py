"""Synthetic-only coverage for the local, evidence-derived pending proposal repair."""

from copy import deepcopy
from io import BytesIO, StringIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from docx import Document
from talent.models import CandidateProfile, Resume, WorkExperience
from talent.resume_understanding import validate_interpretation

from .test_resume_understanding import PROMOTION_TEXT, promotion_response


def _document_bytes():
    document = Document()
    for line in PROMOTION_TEXT.splitlines():
        if line.strip():
            document.add_paragraph(line)
    content = BytesIO()
    document.save(content)
    return content.getvalue()


def _partial_rows():
    rows = validate_interpretation(
        promotion_response(), PROMOTION_TEXT
    )["work_experiences"]
    rows[0].update(
        start_date=None,
        end_date=None,
        date_label="Unknown — Unknown",
        confidence_status="partial",
    )
    rows[1].update(
        end_date=None,
        date_label="2012 — Unknown",
        confidence_status="partial",
    )
    rows[2].update(
        end_date=None,
        date_label="2014 — Unknown",
        confidence_status="partial",
    )
    return rows


@pytest.mark.django_db
def test_local_command_repairs_only_pending_dates_and_preserves_profile(
    settings, tmp_path, candidate_account
):
    settings.DEBUG = True
    settings.MEDIA_ROOT = tmp_path
    settings.RESUME_QUEUE_BACKEND = "database"
    settings.RESUME_AI_ENABLED = False
    settings.RESUME_AI_EXTERNAL_PROCESSING_APPROVED = False
    settings.RESUME_AI_ALLOW_PAID = False
    profile = CandidateProfile.objects.get(user__email="asha@example.com")
    WorkExperience.objects.create(
        candidate=profile,
        company="Candidate Confirmed Studio",
        role="Candidate Confirmed Role",
        date_label="Candidate confirmed dates",
        confidence_status="candidate_confirmed",
    )
    original_pending = _partial_rows()
    resume = Resume.objects.create(
        candidate=profile,
        file=SimpleUploadedFile(
            "fictional-seven-role-history.docx",
            _document_bytes(),
            content_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
        ),
        original_name="fictional-seven-role-history.docx",
        version=2,
        processing_status=Resume.ProcessingStatus.COMPLETED,
        scan_status=Resume.ScanStatus.CLEAN,
        extracted_data={
            "work_experiences": deepcopy(original_pending),
            "_pending_fields": {"work_experiences": deepcopy(original_pending)},
            "_needs_review": True,
        },
    )

    call_command("repair_pending_resume_dates", resume.pk, stdout=StringIO())
    resume.refresh_from_db()
    assert resume.extracted_data["_pending_fields"]["work_experiences"] == original_pending

    call_command(
        "repair_pending_resume_dates", resume.pk, apply=True, stdout=StringIO()
    )
    resume.refresh_from_db()
    pending = resume.extracted_data["_pending_fields"]["work_experiences"]
    assert sum(
        endpoint != "Unknown"
        for row in pending
        for endpoint in row["date_label"].split(" — ")
    ) == 14
    assert resume.extracted_data["work_experiences"] == original_pending
    repair = resume.extracted_data["_offline_repairs"][
        "pending_work_experience_dates_v1"
    ]
    assert repair["source"] == "deterministic_resume_evidence"
    assert repair["original_work_experiences"] == original_pending
    assert list(profile.work_experiences.values_list("company", "role")) == [
        ("Candidate Confirmed Studio", "Candidate Confirmed Role")
    ]

    call_command(
        "repair_pending_resume_dates", resume.pk, apply=True, stdout=StringIO()
    )
    profile.refresh_from_db()
    assert profile.work_experiences.count() == 1
