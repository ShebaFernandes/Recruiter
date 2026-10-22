"""Fail-closed retention enforcement. Dry-run unless every destructive gate is present."""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from talent import legal
from talent.models import CandidateProfile, InactivityReminder, ResumeProcessingJob


def profile_is_eligible(profile, now):
    if profile.resumes.filter(
        processing_job__state__in=[
            ResumeProcessingJob.State.QUEUED,
            ResumeProcessingJob.State.PROCESSING,
        ]
    ).exists():
        return False
    if profile.meaningful_activity_at:
        if legal.expiry(profile.meaningful_activity_at) > now:
            return False
        notices = InactivityReminder.objects.filter(
            candidate=profile,
            activity_at=profile.meaningful_activity_at,
            notice_kind=InactivityReminder.NoticeKind.INACTIVITY,
            sent_at__isnull=False,
        ).values_list("days_before", flat=True)
        return set(notices) >= {30, 7}
    started = profile.retention_transition_started_at
    return bool(
        started
        and started + timedelta(days=30) <= now
        and InactivityReminder.objects.filter(
            candidate=profile,
            activity_at=started,
            notice_kind=InactivityReminder.NoticeKind.TRANSITION,
            days_before=30,
            sent_at__isnull=False,
        ).exists()
    )


def eligible_profile_ids(now):
    return [
        profile.pk
        for profile in CandidateProfile.objects.select_related("user").iterator()
        if profile_is_eligible(profile, now)
    ]


class Command(BaseCommand):
    help = "Dry-run candidate retention; --apply requires explicit production safeguards."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--confirm", default="")

    def handle(self, *args, **options):
        now = timezone.now()
        ids = eligible_profile_ids(now)
        self.stdout.write(f"Eligible candidates: {len(ids)}; no personal data displayed.")
        if not options["apply"]:
            self.stdout.write("Dry run only; no records or files changed.")
            return
        if not legal.published() or not settings.RETENTION_DELETION_ENABLED:
            raise CommandError("Published legal content and retention deletion must be enabled.")
        if not settings.LEGAL_BUSINESS_HOLIDAYS:
            raise CommandError("Approved Karnataka holiday calendar is required.")
        if options["confirm"] != "DELETE-EXPIRED-CANDIDATES":
            raise CommandError("Exact destructive confirmation is required.")
        deleted = 0
        for profile_id in ids:
            with transaction.atomic():
                profile = CandidateProfile.objects.select_for_update().get(pk=profile_id)
                user = User.objects.select_for_update().get(pk=profile.user_id)
                # Re-evaluate this identity inside the lock; stale dry-run state never deletes.
                if not profile_is_eligible(profile, timezone.now()):
                    continue
                deletion = legal.request_deletion(user)
                user.delete()
                deletion.account_deleted_at = timezone.now()
                deletion.save(update_fields=["account_deleted_at"])
                deleted += 1
        self.stdout.write(
            f"Deleted active accounts: {deleted}; private-file cleanup remains in the "
            "durable outbox."
        )
