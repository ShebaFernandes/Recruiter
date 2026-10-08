import uuid

from django.contrib.auth.models import User
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.utils import timezone


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


class WorkExperience(models.Model):
    candidate = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="work_experiences"
    )
    company = models.CharField(max_length=180)
    role = models.CharField(max_length=180)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    gap_reason = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["start_date"]


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
