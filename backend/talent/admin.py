from django.contrib import admin

from .models import (
    CandidateProfile,
    CandidateStatus,
    CandidateUpdateNotification,
    ProfileView,
    Project,
    RecruiterProfile,
    Resume,
    Search,
    UserRole,
    WorkExperience,
)


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = [
        "full_name",
        "profile_status",
        "visibility",
        "email_verified_at",
        "submission_consent_at",
        "submitted_at",
        "profile_updated_at",
    ]
    list_filter = ["profile_status", "visibility"]
    search_fields = ["full_name", "email", "headline"]


admin.site.register(
    [
        UserRole,
        RecruiterProfile,
        WorkExperience,
        Resume,
        Project,
        Search,
        ProfileView,
        CandidateStatus,
        CandidateUpdateNotification,
    ]
)
