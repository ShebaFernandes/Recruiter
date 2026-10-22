"""Versioned legal evidence with a fail-closed unpublished review mode."""

import calendar
import hashlib
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import CandidateProfile, DeletionRequest, InactivityReminder, LegalAcceptance


def enabled():
    return settings.LEGAL_WORKFLOW_PREVIEW or settings.LEGAL_CONTENT_APPROVED


def published():
    return settings.LEGAL_CONTENT_APPROVED and not settings.LEGAL_WORKFLOW_PREVIEW


def _published_text(path):
    text = path.read_text()
    blocking_markers = (
        "UNAPPROVED AND UNPUBLISHED",
        "[D3",
        "[D4",
        "[D5",
        "[D6",
        "[D7",
        "[D8",
        "[D9",
        "[D10",
        "[D11",
        "[D13",
        "[D14",
        "[D15",
        "[D16",
        "REVIEW SIGN-OFF — NOT FOR THE PUBLIC PAGE",
    )
    if any(marker in text for marker in blocking_markers):
        raise ValidationError(
            "Approved legal document still contains internal review or unresolved clauses."
        )
    return text


def documents():
    root = Path(settings.LEGAL_DOCUMENT_ROOT)
    reader = _published_text if published() else lambda path: path.read_text()
    texts = {
        "terms": reader(root / "TERMS_FINAL_REVIEW.txt"),
        "privacy": reader(root / "PRIVACY_POLICY_FINAL_REVIEW.txt"),
        "age": "I confirm that I am at least 18 years old.",
        "submission": (
            "I confirm that I have reviewed my profile and ask ENTER to save it as submitted. "
            "Recruiter access is disabled. This does not authorize future recruiter sharing."
        ),
    }
    versions = {
        "terms": settings.LEGAL_TERMS_VERSION,
        "privacy": settings.LEGAL_PRIVACY_VERSION,
        "age": settings.LEGAL_AGE_VERSION,
        "submission": settings.LEGAL_SUBMISSION_VERSION,
    }
    expected_hashes = {
        "terms": settings.LEGAL_TERMS_SHA256,
        "privacy": settings.LEGAL_PRIVACY_SHA256,
        "age": settings.LEGAL_AGE_SHA256,
        "submission": settings.LEGAL_SUBMISSION_SHA256,
    }
    result = {}
    for purpose, text in texts.items():
        digest = hashlib.sha256(text.encode()).hexdigest()
        if published() and expected_hashes[purpose] != digest:
            raise ValidationError(
                f"Approved {purpose} document does not match its configured SHA-256."
            )
        result[purpose] = {
            "text": text,
            "sha256": digest,
            "version": (
                versions[purpose]
                if published()
                else f"unpublished-{purpose}-{digest[:16]}"
            ),
            "effective_date": settings.LEGAL_EFFECTIVE_DATE if published() else None,
            "unpublished": not published(),
        }
    return result


def validate_acceptance(data, purpose, doc=None):
    if doc is None:
        try:
            doc = documents()[purpose]
        except OSError:
            raise ValidationError("Legal documents unavailable; retry review.") from None
    if data.get(f"{purpose}_accepted") is not True:
        raise ValidationError({purpose: "Explicit confirmation is required."})
    if data.get(f"{purpose}_version") != doc["version"]:
        raise ValidationError({purpose: "Document changed. Review the current version."})
    return doc


def record(user, purpose, doc):
    return LegalAcceptance.objects.create(
        user=user,
        purpose=purpose,
        version=doc["version"],
        document_text=doc["text"],
        document_sha256=doc["sha256"],
        unpublished=doc["unpublished"],
    )


def require_terms(user):
    if not enabled():
        return
    try:
        docs = documents()
    except OSError:
        raise PermissionDenied("Legal documents unavailable; retry review.") from None
    if not all(
        LegalAcceptance.objects.filter(
            user=user,
            purpose=purpose,
            version=docs[purpose]["version"],
            unpublished=docs[purpose]["unpublished"],
        ).exists()
        for purpose in ["age", "terms"]
    ):
        raise PermissionDenied("Review and accept the current Terms first.")


def activity(profile):
    if enabled():
        CandidateProfile.objects.filter(pk=profile.pk).update(meaningful_activity_at=timezone.now())


def expiry(activity_at):
    # Calendar year, including leap-day clamping; not a 365-day approximation.
    year = activity_at.year + 1
    return activity_at.replace(
        year=year, day=min(activity_at.day, calendar.monthrange(year, activity_at.month)[1])
    )


def prepare_reminders(now=None):
    """Local outbox only. Unknown activity remains unknown; expired users are not deleted."""
    now = now or timezone.now()
    created = 0
    for profile in CandidateProfile.objects.exclude(meaningful_activity_at=None):
        remaining = expiry(profile.meaningful_activity_at) - now
        # Never queue stale 30-day notices at the seven-day boundary or after expiry.
        days = 7 if timedelta(0) < remaining <= timedelta(days=7) else 30
        if not timedelta(0) < remaining <= timedelta(days=30):
            continue
        _, new = InactivityReminder.objects.get_or_create(
            candidate=profile,
            activity_at=profile.meaningful_activity_at,
            days_before=days,
        )
        created += new
    return created


def deliver_local_reminders(now=None):
    """Exercise delivery only against Django's in-memory backend, never SMTP."""
    from django.core.mail import send_mail

    if not enabled() or settings.EMAIL_BACKEND != "django.core.mail.backends.locmem.EmailBackend":
        raise PermissionDenied("Reminder delivery is limited to unpublished in-memory tests.")
    now = now or timezone.now()
    sent = 0
    for reminder in InactivityReminder.objects.filter(sent_at=None).select_related("candidate"):
        with transaction.atomic():
            current = InactivityReminder.objects.select_for_update().get(pk=reminder.pk)
            candidate = CandidateProfile.objects.select_for_update().get(pk=current.candidate_id)
            if current.sent_at or candidate.meaningful_activity_at != current.activity_at:
                continue
            remaining = expiry(current.activity_at) - now
            lower = timedelta(days=7) if current.days_before == 30 else timedelta(0)
            if not lower < remaining <= timedelta(days=current.days_before):
                continue
            accepted = send_mail(
                "UNPUBLISHED LOCAL TEST: profile inactivity reminder",
                f"Local test only. Profile expiry: {expiry(current.activity_at).isoformat()}. "
                "No automatic deletion is enabled.",
                settings.DEFAULT_FROM_EMAIL,
                [candidate.email],
                fail_silently=False,
            )
            if accepted != 1:
                raise RuntimeError("Reminder was not accepted; outbox remains pending.")
            current.sent_at = now
            current.save(update_fields=["sent_at"])
            sent += 1
    return sent


def verify_active_file_cleanup(deletion):
    """Read-only verification of current objects, NOT historical-version/backup erasure."""
    from django.contrib.auth.models import User
    from django.core.files.storage import default_storage

    from .models import FileCleanupJob

    if User.objects.filter(
        pk=deletion.subject_user_id, date_joined=deletion.subject_joined_at
    ).exists():
        return False
    if FileCleanupJob.objects.filter(name__in=deletion.storage_keys).exists():
        return False
    # Storage errors propagate; an unavailable bucket must never count as successful erasure.
    if any(default_storage.exists(key) for key in deletion.storage_keys):
        return False
    deletion.storage_cleanup_verified_at = timezone.now()
    deletion.save(update_fields=["storage_cleanup_verified_at"])
    return True


def request_deletion(user):
    now = timezone.now()
    due = now
    count = 0
    # Provisional weekday calculation, explicitly not a jurisdictional holiday calendar.
    while count < 2:
        due += timedelta(days=1)
        count += due.weekday() < 5
    profile = user.candidate_profile
    keys = list(profile.resumes.values_list("file", flat=True))
    if hasattr(profile, "photo"):
        keys.append(profile.photo.file.name)
    return DeletionRequest.objects.create(
        subject_user_id=user.pk,
        subject_joined_at=user.date_joined,
        requested_at=now,
        acknowledged_at=now,
        acknowledgement_due_at=due,
        active_deletion_target_at=now + timedelta(days=7),
        storage_keys=keys,
    )


@transaction.atomic
def reconcile_deleted_subjects(entries):
    """Called only by isolated-restore command; never invokes storage deletion signals."""
    from django.contrib.auth.hashers import make_password
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token

    from .models import AccountActionToken

    count = 0
    for entry in entries:
        # Quarantine restored identities, not the live objects referenced by their resumes.
        users = User.objects.filter(
            pk=entry["subject_user_id"],
            date_joined=entry["subject_joined_at"],
        )
        CandidateProfile.objects.filter(user__in=users).update(
            profile_status=CandidateProfile.ProfileStatus.DRAFT,
            visibility=CandidateProfile.Visibility.NOT_LOOKING,
            submission_consent_at=None,
            submission_consent_version="",
        )
        AccountActionToken.objects.filter(user__in=users).delete()
        Token.objects.filter(user__in=users).delete()
        count += users.update(is_active=False, password=make_password(None))
    return count
