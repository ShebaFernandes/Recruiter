from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ExpiringTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        expires_before = timezone.now() - timedelta(seconds=settings.AUTH_TOKEN_TTL_SECONDS)
        if token.created <= expires_before:
            token.delete()
            raise AuthenticationFailed("Authentication session has expired.")
        return user, token
