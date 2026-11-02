"""Deliver internal enquiry alerts without delaying or losing form submissions."""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .models import EnquiryNotification

logger = logging.getLogger(__name__)
CLAIM_SECONDS = 120
NON_DELIVERING_BACKENDS = {
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.filebased.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
}


def _message(notification):
    if notification.hiring_enquiry_id:
        enquiry = notification.hiring_enquiry
        subject = f"New {enquiry.get_kind_display()} request #{enquiry.pk}"
        path = reverse("admin:talent_hiringenquiry_change", args=[enquiry.pk])
        label = "Hiring enquiries"
    else:
        enquiry = notification.transition_enquiry
        subject = f"New employee transition request #{enquiry.pk}"
        path = reverse("admin:talent_employeetransitionenquiry_change", args=[enquiry.pk])
        label = "Employee transition enquiries"

    # Keep personal details and uploaded files in the protected admin, not email.
    origin = settings.PRIVATE_ADMIN_ORIGIN or (
        "http://127.0.0.1:8010" if settings.DEBUG else ""
    )
    location = (
        f"{origin.rstrip('/')}{path}" if origin
        else f"Django admin → {label} → #{enquiry.pk}"
    )
    body = f"A new request is waiting for review.\n\nOpen it in admin: {location}\n"
    return subject, body


def process_pending_notifications(limit=20, *, allow_local_backend=False):
    """Claim, send, and retry pending alerts. Returns (sent, failed)."""
    if not settings.ENQUIRY_NOTIFICATION_EMAILS:
        return 0, 0
    if settings.EMAIL_BACKEND in NON_DELIVERING_BACKENDS and not allow_local_backend:
        return 0, 0

    sent_count = failed_count = 0
    for _ in range(limit):
        now = timezone.now()
        with transaction.atomic():
            notification = (
                EnquiryNotification.objects.select_for_update(skip_locked=True)
                .filter(sent_at__isnull=True, available_at__lte=now)
                .filter(Q(locked_until__isnull=True) | Q(locked_until__lte=now))
                .order_by("available_at", "pk")
                .first()
            )
            if notification is None:
                break
            notification.locked_until = now + timedelta(seconds=CLAIM_SECONDS)
            notification.save(update_fields=["locked_until"])

        try:
            subject, body = _message(notification)
            delivered = send_mail(
                subject, body, settings.DEFAULT_FROM_EMAIL,
                settings.ENQUIRY_NOTIFICATION_EMAILS, fail_silently=False,
            )
            if delivered != 1:
                raise RuntimeError("Email backend did not accept the notification")
        except Exception as exc:
            notification.attempts += 1
            notification.available_at = timezone.now() + timedelta(
                seconds=min(30 * 2 ** min(notification.attempts, 7), 3600)
            )
            notification.locked_until = None
            notification.last_error_code = type(exc).__name__[:60]
            notification.save(update_fields=[
                "attempts", "available_at", "locked_until", "last_error_code",
            ])
            logger.warning(
                "enquiry_notification_failed notification_id=%s error_type=%s",
                notification.pk, type(exc).__name__,
            )
            failed_count += 1
        else:
            notification.sent_at = timezone.now()
            notification.locked_until = None
            notification.last_error_code = ""
            notification.save(update_fields=["sent_at", "locked_until", "last_error_code"])
            sent_count += 1
    return sent_count, failed_count
