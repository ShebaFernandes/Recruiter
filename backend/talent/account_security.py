import hashlib
import logging
import secrets
import smtplib
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import AccountActionToken

logger = logging.getLogger(__name__)


class AccountEmailDeliveryError(Exception):
    """Safe error with no SMTP response, address, credential, or token attached."""


def local_email_shortcuts_enabled():
    return (
        settings.DEBUG
        and settings.APP_ENV in {"local", "test"}
        and settings.EXPOSE_LOCAL_EMAIL_LINKS
        and settings.EMAIL_BACKEND in {
            "django.core.mail.backends.locmem.EmailBackend",
            "django.core.mail.backends.console.EmailBackend",
            "django.core.mail.backends.filebased.EmailBackend",
        }
    )


def _expiry_wording(seconds):
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60), ("second", 1)):
        if seconds % size == 0:
            count = seconds // size
            return f"{count} {unit}{'' if count == 1 else 's'}"


def _send_account_email(user, purpose, parameter, subject, introduction, ttl):
    try:
        token = issue_account_token(user, purpose)
        link = f"{settings.FRONTEND_URL.rstrip('/')}/?{parameter}={quote(token)}"
        sent = send_mail(
            subject,
            f"{introduction}\n\n{link}\n\n"
            f"This link expires in {_expiry_wording(ttl)} and can only be used once. "
            "If you did not request this, ignore this email.",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        if sent != 1:
            raise smtplib.SMTPException("No message accepted")
        return link
    except Exception as error:
        if isinstance(error, smtplib.SMTPAuthenticationError):
            category = "smtp_authentication"
        elif isinstance(error, TimeoutError):
            category = "timeout"
        elif isinstance(error, smtplib.SMTPException):
            category = "smtp_failure"
        elif isinstance(error, OSError):
            category = "connection_failure"
        else:
            category = "internal_failure"
        # Never log the exception/body/recipient: provider responses can contain secrets.
        logger.warning("account_email_delivery_failed purpose=%s category=%s", purpose, category)
        raise AccountEmailDeliveryError("Account email delivery failed.") from None


def _token_hash(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_account_token(user, purpose):
    ttl = (
        settings.EMAIL_VERIFICATION_TOKEN_TTL_SECONDS
        if purpose == AccountActionToken.Purpose.VERIFY_EMAIL
        else settings.PASSWORD_RESET_TOKEN_TTL_SECONDS
    )
    raw_token = secrets.token_urlsafe(32)
    now = timezone.now()
    with transaction.atomic():
        AccountActionToken.objects.filter(
            user=user, purpose=purpose, used_at__isnull=True
        ).update(used_at=now)
        AccountActionToken.objects.create(
            user=user,
            purpose=purpose,
            token_hash=_token_hash(raw_token),
            expires_at=now + timedelta(seconds=ttl),
        )
    return raw_token


def consume_account_token(raw_token, purpose):
    digest = _token_hash(str(raw_token or ""))
    with transaction.atomic():
        token = (
            AccountActionToken.objects.select_for_update()
            .select_related("user")
            .filter(token_hash=digest, purpose=purpose)
            .first()
        )
        if not token or token.used_at or token.expires_at <= timezone.now():
            return None
        token.used_at = timezone.now()
        token.save(update_fields=["used_at"])
        return token.user


def inspect_account_token(raw_token, purpose):
    digest = _token_hash(str(raw_token or ""))
    return (
        AccountActionToken.objects.select_related("user")
        .filter(
            token_hash=digest,
            purpose=purpose,
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .first()
    )


def recently_issued(user, purpose):
    threshold = timezone.now() - timedelta(seconds=settings.ACCOUNT_EMAIL_RESEND_COOLDOWN_SECONDS)
    return AccountActionToken.objects.filter(
        user=user, purpose=purpose, created_at__gte=threshold
    ).exists()


def send_verification_email(user):
    return _send_account_email(
        user,
        AccountActionToken.Purpose.VERIFY_EMAIL,
        "verify-email",
        "Verify your Enter candidate account",
        "Welcome to Enter. Verify your email to start building your candidate profile.",
        settings.EMAIL_VERIFICATION_TOKEN_TTL_SECONDS,
    )


def send_password_reset_email(user):
    return _send_account_email(
        user,
        AccountActionToken.Purpose.RESET_PASSWORD,
        "reset-password",
        "Reset your Enter password",
        "Use the secure link below to choose a new Enter password.",
        settings.PASSWORD_RESET_TOKEN_TTL_SECONDS,
    )
