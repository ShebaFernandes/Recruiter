from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import (
    SessionAuthentication,
    TokenAuthentication,
    get_authorization_header,
)
from rest_framework.exceptions import AuthenticationFailed


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
        expires_before = timezone.now() - timedelta(seconds=settings.AUTH_TOKEN_TTL_SECONDS)
        if token.created <= expires_before:
            token.delete()
            raise AuthenticationFailed("Authentication session has expired.")
        return user, token
