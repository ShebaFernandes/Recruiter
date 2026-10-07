import hashlib

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.throttling import SimpleRateThrottle

from .models import RateLimitBucket


class DatabaseRateThrottle(SimpleRateThrottle):
    """A shared fixed-window throttle backed by PostgreSQL, not process memory."""

    def get_cache_key(self, request, view):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        # With an AWS ALB in append mode, the right-most address is the one the
        # ALB observed. Never trust a client-supplied left-most value.
        trusted_forwarded = (
            forwarded.split(",")[-1].strip()
            if settings.RATE_LIMIT_TRUST_X_FORWARDED_FOR and forwarded
            else ""
        )
        ip = trusted_forwarded or request.META.get("REMOTE_ADDR", "unknown")
        if request.user and request.user.is_authenticated:
            subject = f"user:{request.user.pk}"
        else:
            # Public auth endpoints are limited by observed client address so
            # rotating arbitrary email values cannot bypass the limit.
            subject = f"ip:{ip}"
        digest = hashlib.sha256(f"{self.scope}:{subject}".encode()).hexdigest()
        return digest

    def allow_request(self, request, view):
        self.rate = self.get_rate()
        if self.rate is None:
            return True
        self.num_requests, self.duration = self.parse_rate(self.rate)
        key = self.get_cache_key(request, view)
        now = timezone.now()
        while True:
            try:
                with transaction.atomic():
                    bucket = RateLimitBucket.objects.select_for_update().filter(key=key).first()
                    if not bucket:
                        RateLimitBucket.objects.create(
                            key=key, window_started_at=now, count=1
                        )
                        self._remaining_seconds = self.duration
                        return True
                    elapsed = (now - bucket.window_started_at).total_seconds()
                    if elapsed >= self.duration:
                        bucket.window_started_at = now
                        bucket.count = 1
                        bucket.save(
                            update_fields=["window_started_at", "count", "updated_at"]
                        )
                        self._remaining_seconds = self.duration
                        return True
                    self._remaining_seconds = max(1, int(self.duration - elapsed))
                    if bucket.count >= self.num_requests:
                        return False
                    bucket.count += 1
                    bucket.save(update_fields=["count", "updated_at"])
                    return True
            except IntegrityError:
                continue

    def wait(self):
        return getattr(self, "_remaining_seconds", None)


class LoginRateThrottle(DatabaseRateThrottle):
    scope = "login"


class SignupRateThrottle(DatabaseRateThrottle):
    scope = "signup"


class VerificationRateThrottle(DatabaseRateThrottle):
    scope = "verification"


class VerificationConsumeRateThrottle(DatabaseRateThrottle):
    scope = "verification_consume"


class PasswordResetRateThrottle(DatabaseRateThrottle):
    scope = "password_reset"


class PasswordResetConfirmRateThrottle(DatabaseRateThrottle):
    scope = "password_reset_confirm"


class ResumeUploadRateThrottle(DatabaseRateThrottle):
    scope = "resume_upload"


class RecruiterSearchRateThrottle(DatabaseRateThrottle):
    scope = "recruiter_search"
