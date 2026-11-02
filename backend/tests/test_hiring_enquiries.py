from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from talent.models import HiringEnquiry, HiringEnquiryAttachment

URL = "/api/v1/hiring/enquiries/"


def hire_data():
    return {
        "kind": "hire",
        "company": "Example Co",
        "full_name": "Alex Example",
        "work_email": "alex@example.com",
        "role": "Senior Frontend Engineer",
        "location": "Hyderabad",
        "headcount": "1",
        "departments": ["Engineering", "Product"],
        "notes": "Experience with accessibility matters.",
    }


@pytest.mark.django_db
def test_find_talent_saves_selected_context_and_private_jd(tmp_path):
    data = hire_data()
    data["jd"] = SimpleUploadedFile(
        "frontend-role.pdf", b"%PDF-1.4\nexample", content_type="application/pdf"
    )
    with override_settings(MEDIA_ROOT=tmp_path):
        response = APIClient().post(URL, data, format="multipart")
        assert response.status_code == 201
        enquiry = HiringEnquiry.objects.get(pk=response.data["id"])
        assert enquiry.kind == "hire"
        assert enquiry.status == "new"
        assert enquiry.details == {
            "role": "Senior Frontend Engineer",
            "location": "Hyderabad",
            "headcount": 1,
            "departments": ["Engineering", "Product"],
        }
        assert enquiry.notes == "Experience with accessibility matters."
        attachment = enquiry.attachments.get()
        assert attachment.original_filename == "frontend-role.pdf"
        assert attachment.file.name.startswith("hiring-enquiries/")
        assert attachment.file.storage.exists(attachment.file.name)

        download_url = reverse(
            "admin:talent_hiringenquiry_attachment", args=[enquiry.pk, attachment.pk]
        )
        assert Client().get(download_url).status_code == 302
        staff = User.objects.create_user("staff", password="test", is_staff=True)
        staff_client = Client()
        staff_client.force_login(staff)
        assert staff_client.get(download_url).status_code == 403
        admin = User.objects.create_superuser("administrator", "admin@example.com", "test")
        admin_client = Client()
        admin_client.force_login(admin)
        download = admin_client.get(download_url)
        assert download.status_code == 200
        assert b"".join(download.streaming_content) == b"%PDF-1.4\nexample"
        assert "attachment" in download["Content-Disposition"]


@pytest.mark.django_db
def test_invalid_jd_and_personal_email_are_rejected():
    data = hire_data()
    data["work_email"] = "alex@gmail.com"
    data["jd"] = SimpleUploadedFile("role.pdf", b"not a PDF")
    response = APIClient().post(URL, data, format="multipart")
    assert response.status_code == 400
    assert "work_email" in response.data
    assert "jd" in response.data
    assert HiringEnquiry.objects.count() == 0
    assert HiringEnquiryAttachment.objects.count() == 0


@pytest.mark.django_db
def test_hiring_enquiry_requires_csrf():
    client = APIClient(enforce_csrf_checks=True)
    assert client.post(URL, hire_data(), format="multipart").status_code == 403
    token = client.get("/api/v1/auth/csrf/").data["csrfToken"]
    response = client.post(URL, hire_data(), format="multipart", HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 201


@pytest.mark.django_db
def test_build_team_saves_team_focus_and_selected_departments(tmp_path):
    data = hire_data()
    data.update(kind="team", team_focus="Backend Engineering", headcount="6")
    data.pop("role")
    data.pop("location")
    data["jd"] = SimpleUploadedFile("team.pdf", b"%PDF-1.4\nteam", content_type="application/pdf")
    with override_settings(MEDIA_ROOT=tmp_path):
        response = APIClient().post(URL, data, format="multipart")
        assert response.status_code == 201
        enquiry = HiringEnquiry.objects.get(pk=response.data["id"])
        assert enquiry.kind == "team"
        assert enquiry.details == {
            "team_focus": "Backend Engineering",
            "headcount": 6,
            "departments": ["Engineering", "Product"],
        }
        assert enquiry.attachments.get().original_filename == "team.pdf"


@pytest.mark.django_db
def test_recruitment_drive_saves_target_date_and_context():
    data = hire_data()
    deadline = timezone.localdate() + timedelta(days=14)
    data.update(
        kind="drive",
        role="Backend Engineers",
        headcount="12",
        deadline=deadline.isoformat(),
    )
    response = APIClient().post(URL, data, format="multipart")
    assert response.status_code == 201
    enquiry = HiringEnquiry.objects.get(pk=response.data["id"])
    assert enquiry.kind == "drive"
    assert enquiry.details == {
        "role": "Backend Engineers",
        "location": "Hyderabad",
        "headcount": 12,
        "deadline": deadline.isoformat(),
        "departments": ["Engineering", "Product"],
    }


@pytest.mark.django_db
def test_founding_team_saves_all_details_and_private_notes(tmp_path):
    data = {
        "kind": "founding",
        "company": "Example Co",
        "full_name": "Alex Example",
        "work_email": "alex@example.com",
        "founder_role": "Founder",
        "phone": "+91 9876543210",
        "website": "example.com",
        "product": "A better way to build teams.",
        "categories": ["Founding Engineer", "Founding AI / ML"],
        "people_count": "6–10",
        "cash_range": "₹40–60L",
        "equity_range": "0.5–1.5%",
        "location": "Bengaluru, Hybrid",
        "start_month": timezone.localdate().strftime("%Y-%m"),
        "attachment": SimpleUploadedFile(
            "founding-notes.txt", b"Early team notes", content_type="text/plain"
        ),
    }
    with override_settings(MEDIA_ROOT=tmp_path):
        response = APIClient().post(URL, data, format="multipart")
        assert response.status_code == 201
        enquiry = HiringEnquiry.objects.get(pk=response.data["id"])
        assert enquiry.kind == "founding"
        assert enquiry.details == {
            "founder_role": "Founder",
            "phone": "+91 9876543210",
            "website": "example.com",
            "product": "A better way to build teams.",
            "categories": ["Founding Engineer", "Founding AI / ML"],
            "people_count": "6–10",
            "cash_range": "₹40–60L",
            "equity_range": "0.5–1.5%",
            "location": "Bengaluru, Hybrid",
            "start_month": timezone.localdate().strftime("%Y-%m"),
        }
        attachment = enquiry.attachments.get()
        assert attachment.original_filename == "founding-notes.txt"
        assert attachment.file.storage.exists(attachment.file.name)


@pytest.mark.django_db
def test_leadership_saves_outcome_and_confidential_choice():
    data = {
        "kind": "leadership",
        "company": "Example Co",
        "full_name": "Alex Example",
        "work_email": "alex@example.com",
        "phone": "+91 9876543210",
        "website": "example.com",
        "categories": ["Engineering Leader"],
        "role_title": "VP Engineering",
        "outcome": "Raise the bar and improve delivery.",
        "confidential": "false",
        "compensation": "₹1.2–2Cr",
        "location_mode": "Bengaluru, Hybrid",
    }
    response = APIClient().post(URL, data, format="multipart")
    assert response.status_code == 201
    enquiry = HiringEnquiry.objects.get(pk=response.data["id"])
    assert enquiry.kind == "leadership"
    assert enquiry.details["outcome"] == "Raise the bar and improve delivery."
    assert enquiry.details["confidential"] is False
    assert enquiry.details["categories"] == ["Engineering Leader"]
    assert enquiry.details["compensation"] == "₹1.2–2Cr"


@pytest.mark.django_db
def test_invalid_kind_dates_and_missing_categories_are_rejected():
    client = APIClient()
    assert client.post(URL, {"kind": "unknown"}, format="multipart").status_code == 400
    drive = hire_data()
    drive.update(kind="drive", deadline=(timezone.localdate() - timedelta(days=1)).isoformat())
    response = client.post(URL, drive, format="multipart")
    assert response.status_code == 400
    assert "deadline" in response.data
    founding = {
        "kind": "founding",
        "company": "Example Co",
        "full_name": "Alex Example",
        "work_email": "alex@example.com",
        "founder_role": "Founder",
        "product": "A useful product",
        "people_count": "2",
        "location": "Bengaluru",
        "start_month": "2020-01",
    }
    response = client.post(URL, founding, format="multipart")
    assert response.status_code == 400
    assert "categories" in response.data
    assert "start_month" in response.data
    assert HiringEnquiry.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "kind,extra",
    [
        (
            "founding",
            {
                "founder_role": "HR team",
                "product": "Build a product",
                "categories": ["Founding Designer", "Infrastructure"],
                "location": "Pune",
            },
        ),
        (
            "leadership",
            {
                "categories": ["Business Leader", "Operations"],
                "role_title": "Business Leader, Operations",
                "outcome": "Grow the team",
                "confidential": "true",
            },
        ),
    ],
)
def test_current_growth_forms_save_without_removed_fields(kind, extra):
    data = {
        "kind": kind,
        "company": "Example Co",
        "full_name": "Test Person",
        "work_email": "test@example.com",
        **extra,
    }
    response = APIClient().post(URL, data, format="multipart")
    assert response.status_code == 201, response.data
    enquiry = HiringEnquiry.objects.get(pk=response.data["id"])
    assert enquiry.details["categories"] == extra["categories"]
    assert "start_month" not in enquiry.details
    assert "people_count" not in enquiry.details
