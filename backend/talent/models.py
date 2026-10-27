import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver
from django.utils import timezone


def candidate_photo_path(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"candidate-photos/{instance.candidate_id}/{uuid.uuid4().hex}{extension}"


class UserRole(models.Model):
    class Role(models.TextChoices):
        RECRUITER = "recruiter", "Recruiter"
        CANDIDATE = "candidate", "Candidate"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="role_profile")
    role = models.CharField(max_length=20, choices=Role.choices)


class AccountActionToken(models.Model):
    class Purpose(models.TextChoices):
        VERIFY_EMAIL = "verify_email", "Verify email"
        RESET_PASSWORD = "reset_password", "Reset password"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="account_action_tokens")
    purpose = models.CharField(max_length=30, choices=Purpose.choices)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "purpose", "created_at"])]


class RecruiterProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="recruiter_profile")
    full_name = models.CharField(max_length=180)
    company = models.CharField(max_length=180, blank=True)
    is_approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="approved_recruiters",
    )


class CandidateProfile(models.Model):
    class Visibility(models.TextChoices):
        APPROVED_RECRUITERS = "approved_recruiters", "Visible to approved recruiters"
        MATCHING_ROLES = "matching_roles", "Only matching roles"
        NOT_LOOKING = "not_looking", "Not looking right now"

    class ProfileStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="candidate_profile")
    full_name = models.CharField(max_length=180)
    headline = models.CharField(max_length=240, blank=True)
    current_company = models.CharField(max_length=180, blank=True)
    email = models.EmailField(blank=True)
    registration_country_code = models.CharField(max_length=2, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    location = models.CharField(max_length=120, blank=True)
    total_experience = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    notice_period_days = models.PositiveIntegerField(null=True, blank=True)
    current_salary_lpa = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    expected_salary_lpa = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    employment_type = models.CharField(max_length=80, default="Full-time")
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    summary = models.TextField(blank=True)
    meaningful_work = models.TextField(blank=True)
    # Owner-only career answers; never used as recruiter search constraints.
    career_preferences = models.JSONField(default=dict, blank=True)
    build_lead_preference = models.PositiveSmallIntegerField(null=True, blank=True)
    visibility = models.CharField(
        max_length=30,
        choices=Visibility.choices,
        blank=True,
        default="",
    )
    work_preferences = models.JSONField(default=list, blank=True)
    skills = models.JSONField(default=list, blank=True)
    education = models.JSONField(default=list, blank=True)
    profile_status = models.CharField(
        max_length=20,
        choices=ProfileStatus.choices,
        default=ProfileStatus.DRAFT,
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    submission_consent_at = models.DateTimeField(null=True, blank=True)
    submission_consent_version = models.CharField(max_length=80, blank=True)
    profile_updated_at = models.DateTimeField(auto_now=True)
    meaningful_activity_at = models.DateTimeField(null=True, blank=True)
    retention_transition_started_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["profile_status", "visibility"]),
            models.Index(fields=["headline"]),
            models.Index(fields=["location"]),
            models.Index(fields=["total_experience"]),
            models.Index(fields=["notice_period_days"]),
            models.Index(fields=["expected_salary_lpa"]),
            models.Index(fields=["employment_type"]),
            GinIndex(fields=["skills"], name="candidate_skills_gin"),
            GinIndex(fields=["work_preferences"], name="candidate_workprefs_gin"),
        ]


class LegalAcceptance(models.Model):
    """Separate immutable-text evidence; never synthesized for existing accounts."""

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    subject_user_id = models.PositiveBigIntegerField(null=True, blank=True)
    subject_joined_at = models.DateTimeField(null=True, blank=True)
    purpose = models.CharField(max_length=30)
    version = models.CharField(max_length=100)
    document_text = models.TextField()
    document_sha256 = models.CharField(max_length=64)
    accepted_at = models.DateTimeField(default=timezone.now, editable=False)
    account_closed_at = models.DateTimeField(null=True, blank=True)
    earliest_disposition_at = models.DateTimeField(null=True, blank=True)
    unpublished = models.BooleanField(default=True)


class InactivityReminder(models.Model):
    class NoticeKind(models.TextChoices):
        INACTIVITY = "inactivity", "Inactivity"
        TRANSITION = "transition", "Existing-account transition"

    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE)
    activity_at = models.DateTimeField()
    days_before = models.PositiveSmallIntegerField()
    notice_kind = models.CharField(
        max_length=20, choices=NoticeKind.choices, default=NoticeKind.INACTIVITY
    )
    deadline_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivery_attempts = models.PositiveSmallIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "activity_at", "days_before"], name="unique_inactivity_notice"
            )
        ]


class DeletionRequest(models.Model):
    @property
    def acknowledgement_deadline_status(self):
        return (
            "approved_karnataka_calendar_configured"
            if settings.LEGAL_BUSINESS_HOLIDAYS
            else "karnataka_calendar_not_configured"
        )

    # Deliberately independent of User: deletion must not erase the recovery ledger.
    subject_user_id = models.PositiveBigIntegerField()
    subject_joined_at = models.DateTimeField()
    requested_at = models.DateTimeField(default=timezone.now)
    acknowledgement_due_at = models.DateTimeField()
    active_deletion_target_at = models.DateTimeField()
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    account_deleted_at = models.DateTimeField(null=True, blank=True)
    storage_keys = models.JSONField(default=list)
    storage_cleanup_verified_at = models.DateTimeField(null=True, blank=True)
    earliest_disposition_at = models.DateTimeField(null=True, blank=True)


@receiver(pre_delete, sender=User)
def preserve_legal_acceptance_evidence(sender, instance, **kwargs):
    """Retain genuine acceptance evidence; never synthesize a missing event."""
    closed_at = timezone.now()
    LegalAcceptance.objects.filter(user=instance).update(
        subject_user_id=instance.pk,
        subject_joined_at=instance.date_joined,
        account_closed_at=closed_at,
        earliest_disposition_at=closed_at + timedelta(days=365),
    )


class CandidatePhoto(models.Model):
    candidate = models.OneToOneField(
        CandidateProfile, on_delete=models.CASCADE, related_name="photo"
    )
    file = models.FileField(upload_to=candidate_photo_path)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=40)
    updated_at = models.DateTimeField(auto_now=True)


@receiver(post_delete, sender=CandidatePhoto)
def delete_candidate_photo_file(sender, instance, **kwargs):
    if instance.file:
        from .storage_cleanup import schedule_cleanup

        schedule_cleanup(instance.file.name)


class ActiveWorkExperienceManager(models.Manager):
    use_in_migrations = True

    def get_queryset(self):
        return super().get_queryset().filter(archived_at__isnull=True)


class WorkExperience(models.Model):
    class ConfidenceStatus(models.TextChoices):
        SUPPORTED = "supported", "Supported by resume evidence"
        PARTIAL = "partial", "Some fields need candidate review"
        CANDIDATE_CONFIRMED = "candidate_confirmed", "Confirmed by candidate"

    candidate = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="work_experiences"
    )
    company = models.CharField(max_length=180)
    role = models.CharField(max_length=180)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    date_label = models.CharField(max_length=100, blank=True)
    employment_type = models.CharField(max_length=80, blank=True)
    location = models.CharField(max_length=180, blank=True)
    description = models.TextField(blank=True)
    source_evidence = models.TextField(blank=True)
    confidence_status = models.CharField(
        max_length=30,
        choices=ConfidenceStatus.choices,
        default=ConfidenceStatus.PARTIAL,
    )
    gap_reason = models.CharField(max_length=240, blank=True)
    # Preserve provenance when complete replacements archive older history.
    # Unknown legacy and candidate-confirmed corrections remain recoverable.
    origin = models.CharField(max_length=20, default="unknown")
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by_resume_id = models.PositiveIntegerField(null=True, blank=True)

    objects = ActiveWorkExperienceManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["start_date"]
        base_manager_name = "all_objects"
        default_manager_name = "objects"


class Resume(models.Model):
    class ProcessingStatus(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class ScanStatus(models.TextChoices):
        QUARANTINED = "quarantined", "Quarantined"
        SCANNING = "scanning", "Scanning"
        CLEAN = "clean", "Clean"
        INFECTED = "infected", "Infected"
        FAILED = "failed", "Scan failed"

    candidate = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="resumes"
    )
    file = models.FileField(upload_to="quarantine/%Y/%m/")
    original_name = models.CharField(max_length=255)
    extracted_data = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=1)
    processing_status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.UPLOADED,
    )
    scan_status = models.CharField(
        max_length=20,
        choices=ScanStatus.choices,
        default=ScanStatus.QUARANTINED,
    )
    processing_error = models.CharField(max_length=255, blank=True)
    ai_processing_consent_at = models.DateTimeField(null=True, blank=True)
    ai_processing_consent_version = models.CharField(max_length=100, blank=True)
    ai_processing_consent_sha256 = models.CharField(max_length=64, blank=True)
    processing_updated_at = models.DateTimeField(auto_now=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version"]






class ResumeProcessingJob(models.Model):
    class State(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"




    resume = models.OneToOneField(
        Resume, on_delete=models.CASCADE, related_name="processing_job"
    )
    state = models.CharField(max_length=20, choices=State.choices, default=State.QUEUED)
    # Informational only; terminal success still requires the atomic profile commit.
    phase = models.CharField(max_length=20, blank=True)
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    available_at = models.DateTimeField(default=timezone.now)
    locked_at = models.DateTimeField(null=True, blank=True)
    enqueued_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    queue_message_id = models.CharField(max_length=180, blank=True)
    last_error = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        indexes = [models.Index(fields=["state", "available_at"])]


class ResumeAIUsage(models.Model):
    class Outcome(models.TextChoices):
        RESERVED = "reserved", "Reserved"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    # Budget consumption must survive candidate/resume deletion. The detached row
    # contains billing/diagnostic aggregates only, never resume text or identity.
    resume = models.ForeignKey(
        Resume,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_usage",
    )
    attempt = models.PositiveSmallIntegerField()
    provider = models.CharField(max_length=40)
    model = models.CharField(max_length=120)
    outcome = models.CharField(max_length=20, choices=Outcome.choices)
    failure_category = models.CharField(max_length=40, blank=True)
    failure_stage = models.CharField(max_length=40, blank=True)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    provider_error_code = models.CharField(max_length=80, blank=True)
    provider_error_status = models.CharField(max_length=80, blank=True)
    stop_reason = models.CharField(max_length=60, blank=True)
    request_id = models.CharField(max_length=180, blank=True)
    reserved_input_tokens = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    validation_rejections = models.JSONField(default=list)
    # This is the maximum request reservation used by the application budget gate.
    estimated_cost_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    # Null means provider billing was not confirmed by a response with token usage.
    actual_cost_usd = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True
    )
    latency_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["resume", "attempt"], name="unique_resume_ai_attempt"
            )
        ]
        indexes = [
            models.Index(
                fields=["created_at", "outcome"], name="resume_ai_created_outcome_idx"
            )
        ]


@receiver(post_delete, sender=Resume)
def delete_resume_file(sender, instance, **kwargs):
    if instance.file:
        from .storage_cleanup import schedule_cleanup

        schedule_cleanup(instance.file.name)


class FileCleanupJob(models.Model):
    # No FK: deletion must survive deletion of the candidate and every resume record.
    name = models.CharField(max_length=1024, unique=True)
    attempts = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)


class WorkerHeartbeat(models.Model):
    worker_id = models.CharField(max_length=120, primary_key=True)
    seen_at = models.DateTimeField(default=timezone.now, db_index=True)
    state = models.CharField(max_length=30, default="starting")


class RateLimitBucket(models.Model):
    key = models.CharField(max_length=64, unique=True)
    window_started_at = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["updated_at"])]


class Project(models.Model):
    recruiter = models.ForeignKey(
        RecruiterProfile, on_delete=models.CASCADE, related_name="projects"
    )
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    candidates = models.ManyToManyField(
        CandidateProfile,
        through="ProjectCandidate",
        related_name="recruiter_projects",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)


class ProjectCandidate(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    candidate = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="project_memberships"
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-added_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "candidate"], name="unique_project_candidate"
            )
        ]


class Search(models.Model):
    class State(models.TextChoices):
        NEEDS_CLARIFICATION = "needs_clarification", "Needs clarification"
        COMPLETE = "complete", "Complete"

    recruiter = models.ForeignKey(
        RecruiterProfile, on_delete=models.CASCADE, related_name="searches"
    )
    project = models.ForeignKey(Project, null=True, blank=True, on_delete=models.SET_NULL)
    query = models.TextField()
    criteria = models.JSONField(default=dict)
    state = models.CharField(max_length=30, choices=State.choices)
    follow_up_question = models.TextField(blank=True)
    follow_up_options = models.JSONField(default=list, blank=True)
    understanding_source = models.CharField(max_length=32, default="deterministic")
    understanding_model = models.CharField(max_length=100, blank=True)
    clarification_history = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class ProfileView(models.Model):
    recruiter = models.ForeignKey(RecruiterProfile, on_delete=models.CASCADE)
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["recruiter", "viewed_at"])]
        constraints = [
            models.UniqueConstraint(fields=["recruiter", "candidate"], name="unique_profile_view")
        ]


class CandidateStatus(models.Model):
    class Status(models.TextChoices):
        SOURCED = "sourced", "Sourced"
        SHORTLISTED = "shortlisted", "Shortlisted"
        CONTACTED = "contacted", "Contacted"
        SCREENING = "screening", "Screening"
        INTERVIEWING = "interviewing", "Interviewing"
        OFFERED = "offered", "Offered"
        REJECTED = "rejected", "Rejected"
        NON_RELEVANT = "non_relevant", "Not relevant"
        HIRED = "hired", "Hired"

    recruiter = models.ForeignKey(RecruiterProfile, on_delete=models.CASCADE)
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE)
    status = models.CharField(max_length=30, choices=Status.choices)
    reason = models.CharField(max_length=180, blank=True)
    note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["recruiter", "status"])]
        constraints = [
            models.UniqueConstraint(
                fields=["recruiter", "candidate"], name="unique_candidate_status"
            )
        ]


class CandidateUpdateNotification(models.Model):
    class ChangeType(models.TextChoices):
        RESUME = "resume", "Resume"
        PROFILE = "profile", "Profile"

    recruiter = models.ForeignKey(
        RecruiterProfile, on_delete=models.CASCADE, related_name="notifications"
    )
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE)
    resume = models.ForeignKey(Resume, null=True, blank=True, on_delete=models.CASCADE)
    change_type = models.CharField(
        max_length=20, choices=ChangeType.choices, default=ChangeType.RESUME
    )
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["recruiter", "resume"], name="unique_recruiter_resume_notification"
            )
        ]
