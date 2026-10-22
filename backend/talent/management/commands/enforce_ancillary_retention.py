"""Dry-run-first enforcement for approved ancillary candidate-data periods."""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from talent import legal
from talent.models import CandidateProfile, Resume, ResumeProcessingJob, UserRole


def candidates(now):
    unverified_cutoff = now - timedelta(days=30)
    unverified = User.objects.filter(
        role_profile__role=UserRole.Role.CANDIDATE,
        candidate_profile__email_verified_at=None,
        date_joined__lte=unverified_cutoff,
    ).exclude(
        candidate_profile__resumes__processing_job__state__in=[
            ResumeProcessingJob.State.QUEUED,
            ResumeProcessingJob.State.PROCESSING,
        ]
    )

    seven_day_cutoff = now - timedelta(days=7)
    thirty_day_cutoff = now - timedelta(days=30)
    resume_ids = []
    for profile in CandidateProfile.objects.prefetch_related("resumes").iterator(chunk_size=200):
        resumes = list(profile.resumes.all())
        latest_version = max((resume.version for resume in resumes), default=0)
        for resume in resumes:
            active = hasattr(resume, "processing_job") and resume.processing_job.state in {
                ResumeProcessingJob.State.QUEUED,
                ResumeProcessingJob.State.PROCESSING,
            }
            if active:
                continue
            infected_expired = (
                resume.scan_status == Resume.ScanStatus.INFECTED
                and resume.uploaded_at <= thirty_day_cutoff
            )
            failed_expired = (
                resume.processing_status == Resume.ProcessingStatus.FAILED
                and resume.scan_status != Resume.ScanStatus.INFECTED
                and resume.uploaded_at <= seven_day_cutoff
            )
            replaced_expired = (
                resume.version < latest_version
                and resume.uploaded_at <= seven_day_cutoff
            )
            if infected_expired or failed_expired or replaced_expired:
                resume_ids.append(resume.pk)
    return list(unverified.values_list("pk", flat=True).distinct()), resume_ids


class Command(BaseCommand):
    help = "Dry-run approved ancillary retention; --apply is independently gated."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--confirm", default="")

    def handle(self, *args, **options):
        user_ids, resume_ids = candidates(timezone.now())
        self.stdout.write(
            f"Eligible unverified accounts: {len(user_ids)}; eligible stale resumes: "
            f"{len(resume_ids)}; no personal data displayed."
        )
        if not options["apply"]:
            self.stdout.write("Dry run only; no records or files changed.")
            return
        if not legal.published() or not settings.ANCILLARY_RETENTION_ENABLED:
            raise CommandError("Published legal content and ancillary retention must be enabled.")
        if options["confirm"] != "APPLY-ANCILLARY-RETENTION":
            raise CommandError("Exact destructive confirmation is required.")

        deleted_users = deleted_resumes = 0
        for user_id in user_ids:
            with transaction.atomic():
                user = User.objects.select_for_update().filter(pk=user_id).first()
                if not user or user_id not in candidates(timezone.now())[0]:
                    continue
                deletion = legal.request_deletion(user)
                user.delete()
                deletion.account_deleted_at = timezone.now()
                deletion.save(update_fields=["account_deleted_at"])
                deleted_users += 1
        for resume_id in resume_ids:
            with transaction.atomic():
                resume = Resume.objects.select_for_update().filter(pk=resume_id).first()
                if not resume or resume_id not in candidates(timezone.now())[1]:
                    continue
                resume.delete()
                deleted_resumes += 1
        self.stdout.write(
            f"Deleted active unverified accounts: {deleted_users}; removed stale resume "
            f"records: {deleted_resumes}; private-file cleanup remains in the durable outbox."
        )
