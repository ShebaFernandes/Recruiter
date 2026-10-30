from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from talent.enquiry_notifications import process_pending_notifications
from talent.models import EmployeeTransitionEnquiry, EnquiryNotification, HiringEnquiry

RECIPIENTS = ["dikshita@enterrecruitment.com", "sheba@enterrecruitment.com"]


def create_requests():
    hiring = APIClient().post(
        "/api/v1/hiring/enquiries/",
        {
            "kind": "hire", "company": "Private Company", "full_name": "Alex Private",
            "work_email": "alex@example.com", "role": "Senior Frontend Engineer",
            "location": "Bengaluru", "headcount": "1", "notes": "Confidential plan",
            "departments": ["Engineering"],
        },
        format="multipart",
    )
    transition = APIClient().post(
        "/api/v1/support/employee-transition/",
        {
            "company": "Sensitive Company", "full_name": "Taylor Private",
            "work_email": "taylor@example.com", "role": "People",
            "people_impacted": "11–40", "last_working_day": "2026-11-30",
            "reach_method": "talk", "consent": "true", "situation": "Private situation",
        },
        format="multipart",
    )
    assert hiring.status_code == 201, hiring.data
    assert transition.status_code == 201, transition.data
    return (
        HiringEnquiry.objects.get(pk=hiring.data["id"]),
        EmployeeTransitionEnquiry.objects.get(pk=transition.data["id"]),
    )


@pytest.mark.django_db
@override_settings(
    ENQUIRY_NOTIFICATION_EMAILS=RECIPIENTS,
    PRIVATE_ADMIN_ORIGIN="https://admin.enterrecruitment.com",
)
def test_both_public_requests_queue_and_send_private_alerts_once():
    hiring, transition = create_requests()
    assert EnquiryNotification.objects.count() == 2
    assert hiring.alert.sent_at is None
    assert transition.alert.sent_at is None

    assert process_pending_notifications() == (0, 0)
    assert EnquiryNotification.objects.filter(sent_at__isnull=True).count() == 2
    assert process_pending_notifications(allow_local_backend=True) == (2, 0)
    assert process_pending_notifications(allow_local_backend=True) == (0, 0)
    assert len(mail.outbox) == 2
    for message in mail.outbox:
        assert message.to == RECIPIENTS
        assert "https://admin.enterrecruitment.com/admin/talent/" in message.body
        assert "Alex Private" not in message.body
        assert "Taylor Private" not in message.body
        assert "Confidential plan" not in message.body
        assert "Private situation" not in message.body
        assert "alex@example.com" not in message.body
        assert "taylor@example.com" not in message.body
    assert EnquiryNotification.objects.filter(sent_at__isnull=False).count() == 2


@pytest.mark.django_db
@override_settings(ENQUIRY_NOTIFICATION_EMAILS=RECIPIENTS)
def test_failed_alert_retries_without_losing_request():
    hiring, _ = create_requests()
    # Leave only the hiring alert pending to make retry behaviour explicit.
    EnquiryNotification.objects.filter(transition_enquiry__isnull=False).delete()
    with patch("talent.enquiry_notifications.send_mail", side_effect=OSError("SMTP unavailable")):
        assert process_pending_notifications(allow_local_backend=True) == (0, 1)

    notification = hiring.alert
    notification.refresh_from_db()
    assert notification.sent_at is None
    assert notification.attempts == 1
    assert notification.last_error_code == "OSError"
    assert notification.available_at > timezone.now()
    assert process_pending_notifications(allow_local_backend=True) == (0, 0)

    notification.available_at = timezone.now()
    notification.save(update_fields=["available_at"])
    assert process_pending_notifications(allow_local_backend=True) == (1, 0)
    notification.refresh_from_db()
    assert notification.sent_at is not None
    assert notification.last_error_code == ""
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_follow_up_is_editable_only_by_superuser(settings):
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    hiring, transition = create_requests()
    staff = User.objects.create_user("staff", password="test", is_staff=True)
    staff_client = Client()
    staff_client.force_login(staff)
    admin_user = User.objects.create_superuser("admin", "admin@example.com", "test")
    admin_client = Client()
    admin_client.force_login(admin_user)

    for enquiry, model_name in (
        (hiring, "hiringenquiry"),
        (transition, "employeetransitionenquiry"),
    ):
        url = reverse(f"admin:talent_{model_name}_change", args=[enquiry.pk])
        assert staff_client.get(url).status_code == 403
        assert admin_client.get(url).status_code == 200
        response = admin_client.post(url, {
            "status": "contacted", "internal_note": "Call on Monday",
            "follow_up_due_at_0": "2026-11-02",
            "follow_up_due_at_1": "10:00:00",
            "_save": "Save",
        })
        assert response.status_code == 302
        enquiry.refresh_from_db()
        assert enquiry.status == "contacted"
        assert enquiry.internal_note == "Call on Monday"
        assert enquiry.follow_up_due_at is not None
        assert enquiry.contacted_at is not None
