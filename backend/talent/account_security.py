import hashlib
import secrets
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import AccountActionToken


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
    token = issue_account_token(user, AccountActionToken.Purpose.VERIFY_EMAIL)
    link = f"{settings.FRONTEND_URL.rstrip('/')}/?verify-email={quote(token)}"
    send_mail(
        "Verify your Enter candidate account",
        (
            "Welcome to Enter. Verify your email to start building your candidate profile.\n\n"
            f"{link}\n\n"
            "This link expires in 24 hours. If you did not create this account, ignore this email."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
    return link


def send_password_reset_email(user):
    token = issue_account_token(user, AccountActionToken.Purpose.RESET_PASSWORD)
    link = f"{settings.FRONTEND_URL.rstrip('/')}/?reset-password={quote(token)}"
    send_mail(
        "Reset your Enter password",
        (
            "Use the secure link below to choose a new Enter password.\n\n"
            f"{link}\n\n"
            "This link expires in one hour and can only be used once. "
            "If you did not request this, ignore this email."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
