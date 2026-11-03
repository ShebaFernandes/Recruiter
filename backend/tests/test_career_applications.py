import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from talent.models import CareerApplication, FileCleanupJob
from talent.storage_cleanup import drain_cleanup

URL = "/api/v1/careers/applications/"


def data():
    return dict(
        name="Test Applicant",
        email="applicant@example.com",
        phone="+91 9000000000",
        linkedin="https://www.linkedin.com/in/test-applicant",
        motivation="Build better hiring",
        resume=SimpleUploadedFile("resume.pdf", b"%PDF-1.4\nTest resume"),
    )


@pytest.mark.django_db
def test_application_persistence_private_download_and_cleanup(tmp_path):
    with override_settings(MEDIA_ROOT=tmp_path):
        response = APIClient().post(URL, data(), format="multipart")
        assert response.status_code == 201
        obj = CareerApplication.objects.get(pk=response.data["id"])
        assert obj.name == "Test Applicant"
        assert obj.email == "applicant@example.com"
        assert obj.phone == "+91 9000000000"
        assert obj.linkedin == "https://www.linkedin.com/in/test-applicant"
        assert obj.motivation == "Build better hiring"
        name = obj.resume.name
        assert obj.resume.storage.exists(name)
        assert "resume" not in response.data
        FileCleanupJob.objects.update(available_at="2020-01-01T00:00:00Z")
        drain_cleanup()
        assert obj.resume.storage.exists(name)
        url = reverse("admin:talent_careerapplication_resume", args=[obj.pk])
        client = Client()
        assert client.get(url).status_code == 302
        staff = User.objects.create_user("staff", is_staff=True)
        client.force_login(staff)
        assert client.get(url).status_code == 403
        admin = User.objects.create_superuser("admin", "admin@example.com", "test")
        client.force_login(admin)
        result = client.get(url)
        assert result.status_code == 200
        assert b"".join(result.streaming_content) == b"%PDF-1.4\nTest resume"
        obj.delete()
        drain_cleanup()
        assert not obj.resume.storage.exists(name)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field,value", [("email", "bad"), ("phone", "abc"), ("linkedin", "bad"), ("motivation", "")]
)
def test_invalid_application(field, value):
    body = data()
    body[field] = value
    assert APIClient().post(URL, body, format="multipart").status_code == 400
    assert not CareerApplication.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "filename,content",
    [
        ("resume.pdf", b"not pdf"),
        ("resume.docx", b"not docx"),
        ("resume.exe", b"file"),
        ("resume.pdf", b"%PDF-" + b"x" * (10 * 1024 * 1024)),
    ],
)
def test_invalid_resume(filename, content):
    body = data()
    body["resume"] = SimpleUploadedFile(filename, content)
    assert APIClient().post(URL, body, format="multipart").status_code == 400
    assert not CareerApplication.objects.exists()
    assert not FileCleanupJob.objects.exists()


@pytest.mark.django_db
def test_csrf_and_read_access():
    client = APIClient(enforce_csrf_checks=True)
    assert client.post(URL, data(), format="multipart").status_code == 403
    token = client.get("/api/v1/auth/csrf/").data["csrfToken"]
    body = data()
    del body["resume"]
    assert client.post(URL, body, format="multipart", HTTP_X_CSRFTOKEN=token).status_code == 400
    assert client.get(URL).status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize("failure,status", [("infected", 400), ("unavailable", 503)])
def test_resume_scan_failure_never_saves_application(monkeypatch, failure, status):
    from unittest.mock import Mock

    from talent.resume_processing import ResumeInfectedError, ResumeScanError

    scanner = Mock()
    scanner.scan.side_effect = ResumeInfectedError() if failure == "infected" else ResumeScanError()
    monkeypatch.setattr("talent.enquiry_uploads.get_resume_scanner", lambda: scanner)
    response = APIClient().post(URL, data(), format="multipart")
    assert response.status_code == status
    assert not CareerApplication.objects.exists()
    assert not FileCleanupJob.objects.exists()
