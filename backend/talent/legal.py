"""Versioned legal evidence with a fail-closed unpublished review mode."""

import calendar
import hashlib
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import CandidateProfile, DeletionRequest, InactivityReminder, LegalAcceptance


def enabled():
    return settings.LEGAL_WORKFLOW_PREVIEW or settings.LEGAL_CONTENT_APPROVED


def published():
    return settings.LEGAL_CONTENT_APPROVED and not settings.LEGAL_WORKFLOW_PREVIEW


def _published_text(path):
    source = path.read_text()
    status_lines = [
        line.strip() for line in source.splitlines() if line.startswith("PUBLICATION STATUS:")
    ]
    if status_lines != ["PUBLICATION STATUS: APPROVED"]:
        raise ValidationError(
            "Legal publication requires one explicit approved publication status."
        )
    start_marker = "PROPOSED PUBLIC COPY"
    end_marker = "END OF PROPOSED PUBLIC COPY"
    lines = source.splitlines(keepends=True)
    start_indexes = [index for index, line in enumerate(lines) if line.strip() == start_marker]
    end_indexes = [index for index, line in enumerate(lines) if line.strip() == end_marker]
    if len(start_indexes) != 1 or len(end_indexes) != 1 or end_indexes[0] <= start_indexes[0]:
        raise ValidationError("Approved legal document has no unique public-text boundary.")
    text = "".join(lines[start_indexes[0] + 1 : end_indexes[0]]).strip() + "\n"
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
        "proposed ",
        "must be confirmed before publication",
        "must be loaded into the operating configuration before",
    )
    if any(marker.lower() in text.lower() for marker in blocking_markers):
        raise ValidationError(
            "Approved legal document still contains internal review or unresolved clauses."
        )
    return text


def documents():
    root = Path(settings.LEGAL_DOCUMENT_ROOT)
    reader = _published_text if published() else lambda path: path.read_text()
    texts = {
        "terms": reader(root / "TERMS_PUBLICATION.txt"),
        "privacy": reader(root / "PRIVACY_POLICY_PUBLICATION.txt"),
        "age": "I confirm that I am at least 18 years old.",
        "submission": (
            "I confirm that I have reviewed my profile and ask ENTER to save it as submitted. "
            "Recruiter access is currently disabled. ENTER will ask for my separate, explicit "
            "permission before sharing my profile or resume with approved recruiters."
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
        subject_user_id=user.pk,
        subject_joined_at=user.date_joined,
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
    """Create a durable outbox without sending mail or deleting candidates."""
    now = now or timezone.now()
    created = 0
    for profile in CandidateProfile.objects.exclude(meaningful_activity_at=None).iterator():
        deadline = expiry(profile.meaningful_activity_at)
        remaining = deadline - now
        # Never queue stale 30-day notices at the seven-day boundary or after expiry.
        days = 7 if timedelta(0) < remaining <= timedelta(days=7) else 30
        if not timedelta(0) < remaining <= timedelta(days=30):
            continue
        _, new = InactivityReminder.objects.get_or_create(
            candidate=profile,
            activity_at=profile.meaningful_activity_at,
            days_before=days,
            defaults={"deadline_at": deadline, "next_attempt_at": now},
        )
        created += new
    return created


def start_existing_account_transitions(now=None):
    """Start the approved one-time window without fabricating meaningful activity."""
    now = now or timezone.now()
    created = 0
    with transaction.atomic():
        profiles = list(
            CandidateProfile.objects.select_for_update().filter(
                meaningful_activity_at=None,
                retention_transition_started_at=None,
            )
        )
        for profile in profiles:
            profile.retention_transition_started_at = now
            profile.save(update_fields=["retention_transition_started_at"])
            _, new = InactivityReminder.objects.get_or_create(
                candidate=profile,
                activity_at=now,
                days_before=30,
                defaults={
                    "notice_kind": InactivityReminder.NoticeKind.TRANSITION,
                    "deadline_at": now + timedelta(days=30),
                    "next_attempt_at": now,
                },
            )
            created += new
    return created


def _reminder_is_current(reminder, candidate, now):
    deadline = reminder.deadline_at or expiry(reminder.activity_at)
    remaining = deadline - now
    if reminder.notice_kind == InactivityReminder.NoticeKind.TRANSITION:
        return (
            candidate.meaningful_activity_at is None
            and candidate.retention_transition_started_at == reminder.activity_at
            and timedelta(0) < remaining <= timedelta(days=30)
        )
    lower = timedelta(days=7) if reminder.days_before == 30 else timedelta(0)
    return (
        candidate.meaningful_activity_at == reminder.activity_at
        and lower < remaining <= timedelta(days=reminder.days_before)
    )


def deliver_reminders(now=None, *, require_enabled=True):
    """Deliver the durable outbox with bounded, non-PII failure evidence."""
    from django.core.mail import send_mail

    if require_enabled and not settings.RETENTION_REMINDER_DELIVERY_ENABLED:
        raise PermissionDenied("Retention reminder delivery is not enabled.")
    now = now or timezone.now()
    sent = failed = 0
    pending_ids = InactivityReminder.objects.filter(sent_at=None).filter(
        Q(next_attempt_at=None) | Q(next_attempt_at__lte=now)
    ).values_list("pk", flat=True)
    for reminder_id in pending_ids.iterator():
        with transaction.atomic():
            reminder = InactivityReminder.objects.select_for_update().get(pk=reminder_id)
            candidate = CandidateProfile.objects.select_for_update().get(
                pk=reminder.candidate_id
            )
            if reminder.sent_at or not _reminder_is_current(reminder, candidate, now):
                continue
            if reminder.delivery_attempts >= settings.RETENTION_REMINDER_MAX_ATTEMPTS:
                continue
            reminder.delivery_attempts += 1
            reminder.last_attempt_at = now
            reminder.last_error_code = ""
            reminder.save(
                update_fields=["delivery_attempts", "last_attempt_at", "last_error_code"]
            )
        deadline = reminder.deadline_at or expiry(reminder.activity_at)
        try:
            subject_prefix = "" if published() else "UNPUBLISHED LOCAL TEST — "
            accepted = send_mail(
                f"{subject_prefix}Action needed: keep your ENTER candidate profile",
                (
                    f"Your ENTER candidate profile is scheduled to expire on "
                    f"{deadline.date().isoformat()}. Sign in and explicitly renew or update "
                    "your profile if you want to keep it. This message does not enable "
                    "recruiter sharing."
                ),
                settings.DEFAULT_FROM_EMAIL,
                [candidate.email],
                fail_silently=False,
            )
            if accepted != 1:
                raise RuntimeError("email_not_accepted")
        except Exception:
            retry_hours = (1, 24, 72, 168)
            next_attempt = (
                now + timedelta(hours=retry_hours[reminder.delivery_attempts - 1])
                if reminder.delivery_attempts <= len(retry_hours)
                else None
            )
            InactivityReminder.objects.filter(pk=reminder_id, sent_at=None).update(
                last_error_code="delivery_failed", next_attempt_at=next_attempt
            )
            failed += 1
            continue
        InactivityReminder.objects.filter(pk=reminder_id, sent_at=None).update(
            sent_at=now, last_error_code="", next_attempt_at=None
        )
        sent += 1
    return sent, failed


def deliver_local_reminders(now=None):
    """Exercise delivery only against Django's in-memory backend, never SMTP."""
    if not enabled() or settings.EMAIL_BACKEND != "django.core.mail.backends.locmem.EmailBackend":
        raise PermissionDenied("Reminder delivery is limited to unpublished in-memory tests.")
    sent, failed = deliver_reminders(now, require_enabled=False)
    if failed:
        raise RuntimeError("Reminder delivery failed; outbox remains pending.")
    return sent


def business_due(start, business_days):
    due = start
    counted = 0
    while counted < business_days:
        due += timedelta(days=1)
        if due.weekday() < 5 and due.date() not in settings.LEGAL_BUSINESS_HOLIDAYS:
            counted += 1
    return due


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
    due = business_due(now, 2)
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
        earliest_disposition_at=expiry(now),
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
