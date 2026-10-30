import io
import zipfile

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from talent.models import EmployeeTransitionEnquiry

URL = "/api/v1/support/employee-transition/"


def request_data(method="talk"):
    return {
        "company": "Example Co",
        "full_name": "Taylor Example",
        "work_email": "taylor@example.com",
        "role": "People",
        "people_impacted": "11–40",
        "last_working_day": "2026-11-30",
        "reach_method": method,
        "consent": "true",
        "situation": "We would like to discuss next steps.",
    }


def workbook_upload():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as workbook:
        workbook.writestr("xl/workbook.xml", "<workbook />")
        workbook.writestr("xl/worksheets/sheet1.xml", "<worksheet />")
    return SimpleUploadedFile(
        "employees.xlsx", buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@pytest.mark.django_db
def test_talk_to_us_persists_without_list():
    response = APIClient().post(URL, request_data(), format="multipart")
    assert response.status_code == 201
    enquiry = EmployeeTransitionEnquiry.objects.get(pk=response.data["id"])
    assert enquiry.reach_method == "talk"
    assert enquiry.situation == "We would like to discuss next steps."
    assert not enquiry.employee_list


@pytest.mark.django_db
def test_excel_list_is_stored_privately(tmp_path):
    data = request_data("list")
    data.pop("situation")
    data["employee_list"] = workbook_upload()
    with override_settings(MEDIA_ROOT=tmp_path):
        response = APIClient().post(URL, data, format="multipart")
        assert response.status_code == 201
        enquiry = EmployeeTransitionEnquiry.objects.get(pk=response.data["id"])
        assert enquiry.original_filename == "employees.xlsx"
        assert enquiry.employee_list.name.startswith("employee-transition/")
        assert enquiry.employee_list.storage.exists(enquiry.employee_list.name)
        download_url = reverse(
            "admin:talent_employeetransitionenquiry_list", args=[enquiry.pk]
        )
        assert Client().get(download_url).status_code == 302
        admin = User.objects.create_superuser("administrator", "admin@example.com", "test")
        client = Client()
        client.force_login(admin)
        download = client.get(download_url)
        assert download.status_code == 200
        assert b"".join(download.streaming_content).startswith(b"PK")


@pytest.mark.django_db
def test_list_requires_file_and_consent():
    response = APIClient().post(URL, request_data("list"), format="multipart")
    assert response.status_code == 400
    assert "employee_list" in response.data

    data = request_data()
    data["consent"] = "false"
    response = APIClient().post(URL, data, format="multipart")
    assert response.status_code == 400
    assert "consent" in response.data
    assert EmployeeTransitionEnquiry.objects.count() == 0


@pytest.mark.django_db
def test_public_submission_requires_csrf():
    client = APIClient(enforce_csrf_checks=True)
    assert client.post(URL, request_data(), format="multipart").status_code == 403
    token = client.get("/api/v1/auth/csrf/").data["csrfToken"]
    assert client.post(
        URL, request_data(), format="multipart", HTTP_X_CSRFTOKEN=token
    ).status_code == 201
