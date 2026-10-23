import hashlib
import json
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone
from talent import legal
from talent.models import (
    CandidateProfile,
    DeletionRequest,
    InactivityReminder,
    LegalAcceptance,
    Resume,
)

pytestmark = pytest.mark.django_db


def test_acceptance_status_is_private_current_and_not_backfilled(client, candidate_account):
    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        url = "/api/v1/candidate/legal/accept/"
        response = client.get(url)
        assert response.data["accepted"] == {"age": False, "terms": False}
        assert response["Cache-Control"] == "no-store"
        assert not LegalAcceptance.objects.exists()
        assert client.post(url, acceptance("age", "terms"), format="json").status_code == 200
        assert client.get(url).data["accepted"] == {"age": True, "terms": True}
        LegalAcceptance.objects.filter(purpose="terms").update(version="outdated")
        assert client.get(url).data["accepted"] == {"age": True, "terms": False}
        client.credentials()
        assert client.get(url).status_code in {401, 403}


def test_documents_failure_blocks_acceptance(client, candidate_account, monkeypatch):
    def unavailable():
        raise OSError("private path must not be returned")

    monkeypatch.setattr(legal, "documents", unavailable)
    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        assert client.get("/api/v1/candidate/legal/accept/").status_code == 503
        response = client.post("/api/v1/candidate/legal/accept/", {}, format="json")
        assert response.status_code == 503
        assert b"private path" not in response.content
        assert not LegalAcceptance.objects.exists()


def test_completion_command_reports_counts_and_does_not_delete(candidate_account, monkeypatch):
    user = User.objects.get(pk=candidate_account["user"]["id"])
    row = legal.request_deletion(user)
    row.account_deleted_at = timezone.now()
    row.save()
    output = StringIO()
    with override_settings(LEGAL_WORKFLOW_PREVIEW=True, DEBUG=True, APP_ENV="test"):
        with pytest.raises(CommandError):
            call_command("reconcile_deletion_completion", stdout=output)
        assert "pending: 1" in output.getvalue()
        assert user.email not in output.getvalue()
        assert User.objects.filter(pk=user.pk).exists()
        user.delete()
        call_command("reconcile_deletion_completion", stdout=StringIO())
        row.refresh_from_db()
        assert row.storage_cleanup_verified_at
        assert row.acknowledgement_deadline_status == "karnataka_calendar_not_configured"


def test_restore_quarantines_all_identities_and_tokens(candidate_account):
    from rest_framework.authtoken.models import Token
    from talent.management.commands.reconcile_restored_deletions import quarantine_restore

    quarantine_restore()
    assert not User.objects.filter(is_active=True).exists()
    assert not Token.objects.exists()
    assert not CandidateProfile.objects.exclude(visibility="not_looking").exists()


def test_restore_http_is_blocked_even_without_preview(client, settings):
    from django.http import HttpResponse
    from django.test import RequestFactory
    from talent.legal_middleware import LocalLegalPreviewMiddleware

    databases = {
        **settings.DATABASES,
        "default": {**settings.DATABASES["default"], "NAME": "enter_restore_synthetic"},
    }
    with override_settings(DATABASES=databases, LEGAL_WORKFLOW_PREVIEW=False):
        response = LocalLegalPreviewMiddleware(lambda request: HttpResponse("unsafe"))(
            RequestFactory().get("/")
        )
        assert response.status_code == 503


@pytest.mark.parametrize("valid", [False, True])
def test_restore_apply_requires_ledger_and_never_reenables_accounts(
    candidate_account,
    tmp_path,
    settings,
    monkeypatch,
    valid,
):
    from unittest.mock import MagicMock

    from rest_framework.authtoken.models import Token
    from talent.management.commands import reconcile_restored_deletions as command

    # Only target-identity discovery is simulated; quarantine uses pytest's synthetic DB.
    target = "enter_restore_synthetic"
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (target,)
    monkeypatch.setattr(command, "connection", connection)
    databases = {
        **settings.DATABASES,
        "default": {**settings.DATABASES["default"], "NAME": target, "HOST": "127.0.0.1"},
    }
    ledger = tmp_path / "ledger.json"
    ledger.write_text("[]")
    ledger.chmod(0o600)
    checksum = hashlib.sha256(b"[]").hexdigest() if valid else "invalid"
    with override_settings(DATABASES=databases, DEBUG=True, APP_ENV="test"):
        if valid:
            output = StringIO()
            call_command(
                "reconcile_restored_deletions",
                str(ledger),
                sha256=checksum,
                apply=True,
                stdout=output,
            )
            assert "ALL restored accounts remain disabled" in output.getvalue()
        else:
            with pytest.raises(CommandError, match="checksum mismatch"):
                call_command(
                    "reconcile_restored_deletions", str(ledger), sha256=checksum, apply=True
                )
    assert not User.objects.filter(is_active=True).exists()
    assert not Token.objects.exists()


def test_completion_storage_failure_never_marks_success(candidate_account, monkeypatch):
    user = User.objects.get(pk=candidate_account["user"]["id"])
    row = legal.request_deletion(user)
    row.account_deleted_at = timezone.now()
    row.save()

    def failure(record):
        raise OSError("secret-object-key")

    monkeypatch.setattr(legal, "verify_active_file_cleanup", failure)
    output = StringIO()
    with override_settings(LEGAL_WORKFLOW_PREVIEW=True, DEBUG=True, APP_ENV="test"):
        with pytest.raises(CommandError):
            call_command("reconcile_deletion_completion", stdout=output)
    assert "failed: 1" in output.getvalue()
    assert "secret-object-key" not in output.getvalue()
    row.refresh_from_db()
    assert row.storage_cleanup_verified_at is None


def acceptance(*purposes):
    result = {}
    for purpose in purposes:
        result[f"{purpose}_accepted"] = True
        result[f"{purpose}_version"] = legal.documents()[purpose]["version"]
    return result


def published_legal_settings(tmp_path):
    privacy = "ENTER Candidate Privacy Policy v1.0\nEffective 2026-10-22."
    terms = "ENTER Candidate Terms of Use v1.0\nEffective 2026-10-22."
    (tmp_path / "PRIVACY_POLICY_PUBLICATION.txt").write_text(
        "PUBLICATION STATUS: APPROVED\n"
        f"PROPOSED PUBLIC COPY\n{privacy}\nEND OF PROPOSED PUBLIC COPY\n"
    )
    (tmp_path / "TERMS_PUBLICATION.txt").write_text(
        "PUBLICATION STATUS: APPROVED\n"
        f"PROPOSED PUBLIC COPY\n{terms}\nEND OF PROPOSED PUBLIC COPY\n"
    )
    privacy = f"{privacy}\n"
    terms = f"{terms}\n"
    age = "I confirm that I am at least 18 years old."
    submission = (
        "I confirm that I have reviewed my profile and ask ENTER to save it as submitted. "
        "Recruiter access is currently disabled. ENTER will ask for my separate, explicit "
        "permission before sharing my profile or resume with approved recruiters."
    )
    return {
        "LEGAL_CONTENT_APPROVED": True,
        "LEGAL_WORKFLOW_PREVIEW": False,
        "LEGAL_DOCUMENT_ROOT": tmp_path,
        "LEGAL_EFFECTIVE_DATE": "2026-10-22",
        "LEGAL_PRIVACY_SHA256": hashlib.sha256(privacy.encode()).hexdigest(),
        "LEGAL_TERMS_SHA256": hashlib.sha256(terms.encode()).hexdigest(),
        "LEGAL_AGE_SHA256": hashlib.sha256(age.encode()).hexdigest(),
        "LEGAL_SUBMISSION_SHA256": hashlib.sha256(submission.encode()).hexdigest(),
        "CANDIDATE_REGISTRATION_COUNTRIES": {"IN"},
    }


def test_published_documents_and_existing_account_acceptance(client, candidate_account, tmp_path):
    with override_settings(**published_legal_settings(tmp_path)):
        result = client.get("/api/v1/legal/documents/")
        assert result.status_code == 200
        assert result["X-Robots-Tag"] == "index, follow"
        assert result.data["documents"]["terms"]["version"] == "enter-candidate-terms-v1.0"
        assert result.data["documents"]["terms"]["unpublished"] is False
        assert client.get("/api/v1/candidate/legal/accept/").data["accepted"] == {
            "age": False,
            "terms": False,
        }
        assert client.post(
            "/api/v1/candidate/legal/accept/", acceptance("age", "terms"), format="json"
        ).status_code == 200
        assert LegalAcceptance.objects.count() == 2
        assert not LegalAcceptance.objects.filter(unpublished=True).exists()
        assert client.get("/api/v1/candidate/legal/accept/").data["accepted"] == {
            "age": True,
            "terms": True,
        }


def test_published_signup_records_exact_version_without_backfill(client, tmp_path):
    with override_settings(**published_legal_settings(tmp_path)):
        payload = {
            "email": "published-synthetic@example.test",
            "full_name": "Published Synthetic Candidate",
            "password": "Strong-password-254!",
            "role": "candidate",
            "country_code": "IN",
            **acceptance("age", "terms"),
        }
        assert client.post(
            "/api/v1/auth/signup/", {**payload, "terms_version": "stale"}, format="json"
        ).status_code == 400
        assert not User.objects.exists()
        assert client.post("/api/v1/auth/signup/", payload, format="json").status_code == 201
        records = LegalAcceptance.objects.order_by("purpose")
        assert [(record.purpose, record.version, record.unpublished) for record in records] == [
            ("age", "enter-candidate-age-v1.0", False),
            ("terms", "enter-candidate-terms-v1.0", False),
        ]


def test_india_first_signup_is_enforced_server_side(client):
    with override_settings(
        LEGAL_WORKFLOW_PREVIEW=True,
        CANDIDATE_REGISTRATION_COUNTRIES={"IN"},
    ):
        payload = {
            "email": "india-first@example.test",
            "full_name": "India First Candidate",
            "password": "Strong-password-254!",
            "role": "candidate",
            **acceptance("age", "terms"),
        }
        assert client.post("/api/v1/auth/signup/", payload, format="json").status_code == 400
        assert (
            client.post(
                "/api/v1/auth/signup/", {**payload, "country_code": "US"}, format="json"
            ).status_code
            == 400
        )
        response = client.post(
            "/api/v1/auth/signup/", {**payload, "country_code": "in"}, format="json"
        )
        assert response.status_code == 201
        assert CandidateProfile.objects.get().registration_country_code == "IN"


@pytest.mark.parametrize("failure", ["status", "placeholder", "hash"])
def test_published_documents_fail_closed(client, tmp_path, failure):
    configured = published_legal_settings(tmp_path)
    if failure == "status":
        path = tmp_path / "PRIVACY_POLICY_PUBLICATION.txt"
        path.write_text(path.read_text().replace(
            "PUBLICATION STATUS: APPROVED",
            "PUBLICATION STATUS: PENDING — QUALIFIED REVIEW REQUIRED",
        ))
    elif failure == "placeholder":
        text = "ENTER Privacy\n[D3: unresolved legal clause]\n"
        (tmp_path / "PRIVACY_POLICY_PUBLICATION.txt").write_text(
            "PUBLICATION STATUS: APPROVED\n"
            f"PROPOSED PUBLIC COPY\n{text}END OF PROPOSED PUBLIC COPY\n"
        )
        configured["LEGAL_PRIVACY_SHA256"] = hashlib.sha256(text.encode()).hexdigest()
    else:
        configured["LEGAL_PRIVACY_SHA256"] = "0" * 64
    with override_settings(**configured):
        response = client.get("/api/v1/legal/documents/")
        assert response.status_code == 503
        assert response.data == {"detail": "Legal documents are not publication-ready."}
        readiness = client.get("/api/v1/health/ready/")
        assert readiness.status_code == 503
        assert readiness.data == {"status": "not_ready", "legal_documents": "unavailable"}


@pytest.mark.parametrize("bad", [None, False, "true", 1])
def test_age_requires_explicit_boolean(client, bad):
    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        payload = {
            "email": "synthetic@example.test",
            "full_name": "Fictional Candidate",
            "password": "Strong-password-254!",
            "role": "candidate",
            **acceptance("age", "terms"),
            "age_accepted": bad,
        }
        response = client.post("/api/v1/auth/signup/", payload, format="json")
        assert response.status_code == 400
        assert not User.objects.exists()
        assert not LegalAcceptance.objects.exists()


def test_signup_versions_hashes_and_no_sharing(client):
    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        payload = {
            "email": "synthetic@example.test",
            "full_name": "Fictional Candidate",
            "password": "Strong-password-254!",
            "role": "candidate",
            **acceptance("age", "terms"),
        }
        stale = dict(payload, terms_version="outdated")
        assert client.post("/api/v1/auth/signup/", stale, format="json").status_code == 400
        assert client.post("/api/v1/auth/signup/", payload, format="json").status_code == 201
        assert LegalAcceptance.objects.count() == 2
        for event in LegalAcceptance.objects.all():
            assert event.unpublished
            assert event.accepted_at <= timezone.now()
            assert event.document_sha256 == hashlib.sha256(event.document_text.encode()).hexdigest()
        profile = CandidateProfile.objects.get()
        assert profile.meaningful_activity_at is None
        assert profile.submission_consent_at is None


def test_existing_user_not_backfilled_and_can_refuse(client, candidate_account):
    assert not LegalAcceptance.objects.exists()
    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        assert client.get("/api/v1/candidate/profile/").status_code == 200
        assert client.post("/api/v1/candidate/legal/accept/", {}, format="json").status_code == 400
        assert client.post("/api/v1/candidate/resumes/", {}, format="json").status_code == 403
        assert not LegalAcceptance.objects.exists()
        assert (
            client.post(
                "/api/v1/candidate/legal/accept/", acceptance("age", "terms"), format="json"
            ).status_code
            == 200
        )
        # Validation reaches file requirements only after acceptance.
        assert client.post("/api/v1/candidate/resumes/", {}, format="multipart").status_code == 400


def test_submission_cannot_reuse_legacy_consent(client, candidate_account):
    profile = CandidateProfile.objects.get()
    profile.submission_consent_at = timezone.now()
    profile.submission_consent_version = "candidate-profile-sharing-v1"
    profile.save()
    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        client.post("/api/v1/candidate/legal/accept/", acceptance("age", "terms"), format="json")
        assert (
            client.post(
                "/api/v1/candidate/profile/submit/", {"consent": True}, format="json"
            ).status_code
            == 400
        )
        assert not LegalAcceptance.objects.filter(purpose="submission").exists()


def test_recruiter_sessions_denied_in_preview(client, recruiter_account):
    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        assert client.get("/api/v1/projects/").status_code in {401, 403}
        assert client.post("/api/v1/searches/", {"query": "Python"}, format="json").status_code in {
            401,
            403,
        }


def test_draft_pages_not_exposed_when_disabled(client):
    assert client.get("/api/v1/legal/documents/").json() == {"enabled": False}
    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        result = client.get("/api/v1/legal/documents/")
        assert result["Cache-Control"] == "no-store"
        assert result["X-Robots-Tag"] == "noindex, nofollow"
        assert result.json()["documents"]["terms"]["unpublished"] is True


def test_activity_only_candidate_actions(client, candidate_account):
    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        client.get("/api/v1/candidate/profile/")
        assert CandidateProfile.objects.get().meaningful_activity_at is None
        client.patch(
            "/api/v1/candidate/profile/", {"headline": "Synthetic engineer"}, format="json"
        )
        stamp = CandidateProfile.objects.get().meaningful_activity_at
        assert stamp is not None
        client.get("/api/v1/candidate/profile/")
        assert CandidateProfile.objects.get().meaningful_activity_at == stamp


def test_reminder_boundaries_and_unknown_activity(candidate_account):
    start = datetime(2024, 2, 29, tzinfo=dt_timezone.utc)
    assert legal.expiry(start) == datetime(2025, 2, 28, tzinfo=dt_timezone.utc)
    assert legal.prepare_reminders() == 0
    profile = CandidateProfile.objects.get()
    profile.meaningful_activity_at = start
    profile.save()
    due = legal.expiry(start)
    assert legal.prepare_reminders(due - timedelta(days=31)) == 0
    assert legal.prepare_reminders(due - timedelta(days=30)) == 1
    assert legal.prepare_reminders(due - timedelta(days=29)) == 0
    assert legal.prepare_reminders(due - timedelta(days=7)) == 1
    assert legal.prepare_reminders(due) == 0
    assert InactivityReminder.objects.count() == 2
    assert not InactivityReminder.objects.exclude(sent_at=None).exists()
    assert CandidateProfile.objects.filter(pk=profile.pk).exists()


def test_existing_account_transition_is_explicit_and_not_fabricated(candidate_account):
    now = timezone.now()
    profile = CandidateProfile.objects.get()
    assert legal.start_existing_account_transitions(now) == 1
    profile.refresh_from_db()
    assert profile.meaningful_activity_at is None
    assert profile.retention_transition_started_at == now
    reminder = InactivityReminder.objects.get()
    assert reminder.notice_kind == "transition"
    assert reminder.deadline_at == now + timedelta(days=30)
    assert legal.start_existing_account_transitions(now) == 0


def test_business_deadline_uses_configured_karnataka_holidays():
    start = datetime(2026, 10, 23, 12, tzinfo=dt_timezone.utc)  # Friday
    with override_settings(LEGAL_BUSINESS_HOLIDAYS={date(2026, 10, 26)}):
        assert legal.business_due(start, 2) == datetime(
            2026, 10, 28, 12, tzinfo=dt_timezone.utc
        )


def test_deletion_evidence_survives_without_false_cleanup_claim(client, candidate_account):
    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        assert (
            client.delete(
                "/api/v1/candidate/account/",
                {"password": "wrong", "confirmation": "DELETE"},
                format="json",
            ).status_code
            == 400
        )
        assert not DeletionRequest.objects.exists()
        assert (
            client.delete(
                "/api/v1/candidate/account/",
                {"password": "strong-pass-123", "confirmation": "DELETE"},
                format="json",
            ).status_code
            == 204
        )
        record = DeletionRequest.objects.get()
        assert record.acknowledged_at == record.requested_at
        assert record.account_deleted_at
        assert record.active_deletion_target_at - record.requested_at == timedelta(days=7)
        assert record.acknowledgement_due_at.weekday() < 5
        assert record.storage_cleanup_verified_at is None
        assert not User.objects.filter(pk=record.subject_user_id).exists()


def test_restore_quarantine_matches_identity_not_id_alone(candidate_account):
    from rest_framework.authtoken.models import Token

    user = User.objects.get(pk=candidate_account["user"]["id"])
    assert (
        legal.reconcile_deleted_subjects(
            [
                {
                    "subject_user_id": user.pk,
                    "subject_joined_at": (user.date_joined - timedelta(days=1)).isoformat(),
                }
            ]
        )
        == 0
    )
    assert (
        legal.reconcile_deleted_subjects(
            [{"subject_user_id": user.pk, "subject_joined_at": user.date_joined.isoformat()}]
        )
        == 1
    )
    user.refresh_from_db()
    assert not user.is_active
    assert not user.has_usable_password()
    assert not Token.objects.filter(user=user).exists()
    assert CandidateProfile.objects.filter(user=user).exists()


def test_restore_refuses_normal_database(tmp_path):
    ledger = tmp_path / "ledger.json"
    ledger.write_text("[]")
    ledger.chmod(0o600)
    with pytest.raises(CommandError, match="isolated"):
        call_command(
            "reconcile_restored_deletions", str(ledger), sha256=hashlib.sha256(b"[]").hexdigest()
        )


def test_ledger_export_private_no_overwrite(client, candidate_account, tmp_path):
    path = tmp_path / "ledger.json"
    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        client.delete(
            "/api/v1/candidate/account/",
            {"password": "strong-pass-123", "confirmation": "DELETE"},
            format="json",
        )
        output = StringIO()
        call_command("export_deletion_ledger", str(path), stdout=output)
        assert path.stat().st_mode & 0o777 == 0o600
        assert len(json.loads(path.read_text())) == 1
        assert "asha" not in output.getvalue()
        with pytest.raises(CommandError):
            call_command("export_deletion_ledger", str(path))


def test_local_reminder_delivery_stale_suppression_and_failures(candidate_account, monkeypatch):
    from django.core import mail
    from rest_framework.exceptions import PermissionDenied

    profile = CandidateProfile.objects.get()
    now = timezone.now()
    profile.meaningful_activity_at = now.replace(year=now.year - 1) + timedelta(days=20)
    profile.save()
    assert legal.prepare_reminders(now) == 1
    with override_settings(
        LEGAL_WORKFLOW_PREVIEW=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    ):
        monkeypatch.setattr(mail, "send_mail", lambda *a, **k: 0)
        with pytest.raises(RuntimeError):
            legal.deliver_local_reminders(now)
        reminder = InactivityReminder.objects.get()
        assert reminder.sent_at is None
        assert reminder.delivery_attempts == 1
        assert reminder.last_error_code == "delivery_failed"
        assert reminder.next_attempt_at == now + timedelta(hours=1)
        monkeypatch.undo()
        assert legal.deliver_local_reminders(now) == 0
        assert legal.deliver_local_reminders(now + timedelta(hours=1)) == 1
        reminder.refresh_from_db()
        assert reminder.delivery_attempts == 2
        assert reminder.last_error_code == ""
        assert legal.deliver_local_reminders(now) == 0
        assert sum(m.subject.startswith("UNPUBLISHED LOCAL TEST") for m in mail.outbox) == 1
    with override_settings(
        LEGAL_WORKFLOW_PREVIEW=True, EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend"
    ):
        with pytest.raises(PermissionDenied):
            legal.deliver_local_reminders(now)


def test_new_activity_cancels_old_reminder(candidate_account):
    profile = CandidateProfile.objects.get()
    now = timezone.now()
    profile.meaningful_activity_at = now.replace(year=now.year - 1) + timedelta(days=5)
    profile.save()
    assert legal.prepare_reminders(now) == 1
    with override_settings(
        LEGAL_WORKFLOW_PREVIEW=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    ):
        legal.activity(profile)
        assert legal.deliver_local_reminders(now) == 0


def test_active_cleanup_not_claimed_on_storage_failure(client, candidate_account, monkeypatch):
    from django.core.files.storage import default_storage
    from talent.models import FileCleanupJob

    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        client.delete(
            "/api/v1/candidate/account/",
            {"password": "strong-pass-123", "confirmation": "DELETE"},
            format="json",
        )
    record = DeletionRequest.objects.get()
    record.storage_keys = ["synthetic/sample.pdf"]
    record.save()
    job = FileCleanupJob.objects.create(name=record.storage_keys[0])
    assert not legal.verify_active_file_cleanup(record)
    job.delete()
    monkeypatch.setattr(default_storage, "exists", lambda name: True)
    assert not legal.verify_active_file_cleanup(record)

    def unavailable(name):
        raise OSError("synthetic storage outage")

    monkeypatch.setattr(default_storage, "exists", unavailable)
    with pytest.raises(OSError):
        legal.verify_active_file_cleanup(record)
    record.refresh_from_db()
    assert record.storage_cleanup_verified_at is None
    monkeypatch.setattr(default_storage, "exists", lambda name: False)
    assert legal.verify_active_file_cleanup(record)


def test_new_terms_never_infer_sharing_even_after_preview_disabled(client, candidate_account):
    from talent.views import _filtered_candidates

    profile = CandidateProfile.objects.get()
    profile.profile_status = "submitted"
    profile.visibility = "approved_recruiters"
    profile.submission_consent_at = timezone.now()
    profile.save()
    legal.record(profile.user, "terms", legal.documents()["terms"])
    with override_settings(LEGAL_WORKFLOW_PREVIEW=False):
        assert profile.pk not in [p.pk for p in _filtered_candidates({}, {})]


def test_successful_submission_records_only_new_purpose(client, candidate_account):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from .test_candidate_flow import complete_resume_upload, resume_docx

    upload = client.post(
        "/api/v1/candidate/resumes/",
        {"file": SimpleUploadedFile("synthetic.docx", resume_docx())},
        format="multipart",
    )
    complete_resume_upload(client, upload)
    client.patch("/api/v1/candidate/profile/", {"work_preferences": ["Remote"]}, format="json")
    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        client.post("/api/v1/candidate/legal/accept/", acceptance("age", "terms"), format="json")
        response = client.post(
            "/api/v1/candidate/profile/submit/", acceptance("submission"), format="json"
        )
        assert response.status_code == 200, response.data
        profile = CandidateProfile.objects.get()
        assert profile.profile_status == "submitted"
        assert profile.submission_consent_at is None
        assert profile.submission_consent_version == ""
        assert LegalAcceptance.objects.filter(purpose="submission").count() == 1
        assert profile.meaningful_activity_at


def test_preview_refuses_remote_and_forwarded_requests(client):
    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        assert client.get("/api/v1/legal/documents/", REMOTE_ADDR="203.0.113.7").status_code == 403
        assert (
            client.get("/api/v1/legal/documents/", HTTP_X_FORWARDED_FOR="127.0.0.1").status_code
            == 403
        )


def test_recovery_manifest_validation_and_dry_run(tmp_path):
    path = tmp_path / "private.json"
    path.write_text("[]")
    path.chmod(0o600)
    db = {"default": {"NAME": "enter_restore_synthetic", "HOST": "127.0.0.1"}}
    with override_settings(DATABASES=db, DEBUG=True, APP_ENV="test"):
        with pytest.raises(CommandError, match="checksum"):
            call_command("reconcile_restored_deletions", str(path), sha256="wrong")
        path.chmod(0o644)
        with pytest.raises(CommandError, match="0600"):
            call_command("reconcile_restored_deletions", str(path), sha256="wrong")
        path.chmod(0o600)
        path.write_text('[{"subject_user_id": 1, "subject_joined_at": "invalid"}]')
        with pytest.raises(CommandError, match="schema"):
            call_command(
                "reconcile_restored_deletions",
                str(path),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        path.write_text("[]")
        output = StringIO()
        call_command(
            "reconcile_restored_deletions",
            str(path),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            stdout=output,
        )
        assert "No changes" in output.getvalue()


def test_acceptance_evidence_survives_account_deletion(client, candidate_account):
    user = User.objects.get(pk=candidate_account["user"]["id"])
    user_id = user.pk
    with override_settings(LEGAL_WORKFLOW_PREVIEW=True):
        client.post("/api/v1/candidate/legal/accept/", acceptance("age", "terms"), format="json")
    accepted_ids = list(LegalAcceptance.objects.values_list("pk", flat=True))
    user.delete()
    evidence = LegalAcceptance.objects.filter(pk__in=accepted_ids)
    assert evidence.count() == 2
    assert not evidence.exclude(user=None).exists()
    assert not evidence.exclude(subject_user_id=user_id).exists()
    assert not evidence.filter(account_closed_at=None).exists()
    assert not evidence.filter(earliest_disposition_at=None).exists()


def test_legal_release_manifest_uses_exact_public_copy(tmp_path):
    configured = published_legal_settings(tmp_path)
    output = StringIO()
    with override_settings(**configured):
        call_command("legal_release_manifest", stdout=output)
    manifest = json.loads(output.getvalue())
    assert manifest["privacy"]["sha256"] == configured["LEGAL_PRIVACY_SHA256"]
    assert manifest["submission"]["sha256"] == configured["LEGAL_SUBMISSION_SHA256"]


def test_retention_enforcement_is_dry_run_and_fail_closed(candidate_account):
    from talent.management.commands.enforce_candidate_retention import eligible_profile_ids

    now = timezone.now()
    profile = CandidateProfile.objects.get()
    profile.meaningful_activity_at = now.replace(year=now.year - 1) - timedelta(days=1)
    profile.save()
    deadline = legal.expiry(profile.meaningful_activity_at)
    for days in (30, 7):
        InactivityReminder.objects.create(
            candidate=profile,
            activity_at=profile.meaningful_activity_at,
            days_before=days,
            deadline_at=deadline,
            sent_at=now - timedelta(days=days),
        )
    assert eligible_profile_ids(now) == [profile.pk]
    output = StringIO()
    call_command("enforce_candidate_retention", stdout=output)
    assert "Dry run only" in output.getvalue()
    assert CandidateProfile.objects.filter(pk=profile.pk).exists()
    with pytest.raises(CommandError, match="retention deletion"):
        call_command(
            "enforce_candidate_retention",
            apply=True,
            confirm="DELETE-EXPIRED-CANDIDATES",
        )


def test_ancillary_retention_classifies_without_changing_data(candidate_account):
    from talent.management.commands.enforce_ancillary_retention import candidates

    now = timezone.now()
    user = User.objects.get(pk=candidate_account["user"]["id"])
    profile = CandidateProfile.objects.get(user=user)
    profile.email_verified_at = None
    profile.save(update_fields=["email_verified_at"])
    User.objects.filter(pk=user.pk).update(date_joined=now - timedelta(days=31))
    old = Resume.objects.create(
        candidate=profile,
        file="quarantine/synthetic-old.pdf",
        original_name="synthetic-old.pdf",
        version=1,
        processing_status=Resume.ProcessingStatus.FAILED,
        scan_status=Resume.ScanStatus.FAILED,
    )
    Resume.objects.filter(pk=old.pk).update(uploaded_at=now - timedelta(days=8))
    user_ids, resume_ids = candidates(now)
    assert user.pk in user_ids
    assert old.pk in resume_ids
    output = StringIO()
    call_command("enforce_ancillary_retention", stdout=output)
    assert "Dry run only" in output.getvalue()
    assert User.objects.filter(pk=user.pk).exists()
    assert Resume.objects.filter(pk=old.pk).exists()
    with pytest.raises(CommandError, match="ancillary retention"):
        call_command(
            "enforce_ancillary_retention",
            apply=True,
            confirm="APPLY-ANCILLARY-RETENTION",
        )
