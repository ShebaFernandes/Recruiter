from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import (
    SessionAuthentication,
    TokenAuthentication,
    get_authorization_header,
)
from rest_framework.exceptions import AuthenticationFailed

from .permissions import is_approved_recruiter, is_verified_candidate


class CsrfProtectedPublicAuthentication(SessionAuthentication):
    """Require CSRF on anonymous auth POSTs without authenticating a session."""

    def authenticate(self, request):
        self.enforce_csrf(request)
        return None


class ExpiringTokenAuthentication(TokenAuthentication):
    def authenticate(self, request):
        header = get_authorization_header(request)
        if header:
            return super().authenticate(request)
        cookie_token = request.COOKIES.get(settings.AUTH_COOKIE_NAME)
        if not cookie_token:
            return None
        user_auth_tuple = self.authenticate_credentials(cookie_token)
        SessionAuthentication().enforce_csrf(request)
        return user_auth_tuple

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if hasattr(user, "candidate_profile") and not is_verified_candidate(user):
            raise AuthenticationFailed("Verify your email before accessing your account.")
        if hasattr(user, "recruiter_profile") and not is_approved_recruiter(user):
            raise AuthenticationFailed(
                "Recruiter access is not approved. Contact ENTER administration."
            )
        expires_before = timezone.now() - timedelta(seconds=settings.AUTH_TOKEN_TTL_SECONDS)
        if token.created <= expires_before:
            token.delete()
            raise AuthenticationFailed("Authentication session has expired.")
        return user, token
