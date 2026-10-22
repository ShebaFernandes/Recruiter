from django.conf import settings
from rest_framework.permissions import BasePermission

from .models import CandidateProfile, RecruiterProfile, UserRole


def is_verified_candidate(user):
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and CandidateProfile.objects.filter(
            user_id=user.pk,
            user__is_active=True,
            email_verified_at__isnull=False,
        ).exists()
    )


def is_approved_recruiter(user):
    # Read current state: revocation must block existing sessions too.
    return bool(
        not settings.CANDIDATE_ONLY
        and not settings.LEGAL_WORKFLOW_PREVIEW
        and user
        and user.is_authenticated
        and user.is_active
        and RecruiterProfile.objects.filter(
            user_id=user.pk,
            user__is_active=True,
            is_approved=True,
            user__role_profile__role=UserRole.Role.RECRUITER,
            user__candidate_profile__isnull=True,
        ).exists()
    )


class IsRecruiter(BasePermission):
    message = "Recruiter access requires approval from an ENTER administrator."

    def has_permission(self, request, view):
        return is_approved_recruiter(request.user)


class IsCandidate(BasePermission):
    def has_permission(self, request, view):
        return is_verified_candidate(request.user)
