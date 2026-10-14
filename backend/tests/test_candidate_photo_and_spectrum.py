from io import BytesIO
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient

from .recruiter_helpers import provision_recruiter


def image_file(name="profile.jpg", image_format="JPEG", size=(180, 140), private_note=True):
    output = BytesIO()
    image = Image.new("RGB", size, "#6d4aff")
    options = {}
    if private_note:
        exif = Image.Exif()
        exif[0x010E] = "PRIVATE CAMERA NOTE"
        options["exif"] = exif
    image.save(output, image_format, **options)
    return SimpleUploadedFile(
        name,
        output.getvalue(),
        content_type={"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[image_format],
    )


@pytest.mark.django_db(transaction=True)
def test_candidate_photo_is_normalized_private_replaceable_and_removable(
    client, candidate_account, tmp_path
):
    with override_settings(MEDIA_ROOT=tmp_path):
        uploaded = client.post(
            "/api/v1/candidate/photo/", {"file": image_file()}, format="multipart"
        )
        assert uploaded.status_code == 200
        assert uploaded.data["profile_photo_url"].startswith("/api/v1/candidate/photo/?v=")
        photo = User.objects.get(username="asha@example.com").candidate_profile.photo
        first_name = photo.file.name
        first_path = Path(photo.file.path)
        assert first_path.exists()
        assert first_name.startswith(f"candidate-photos/{photo.candidate_id}/")

        response = client.get("/api/v1/candidate/photo/")
        content = b"".join(response.streaming_content)
        assert response.status_code == 200
        assert response["Cache-Control"] == "private, no-store"
        assert response["X-Content-Type-Options"] == "nosniff"
        assert response["Cross-Origin-Resource-Policy"] == "same-site"
        assert b"PRIVATE CAMERA NOTE" not in content
        with Image.open(BytesIO(content)) as normalized:
            assert normalized.format == "JPEG"
            assert normalized.size == (180, 140)

        replacement = client.post(
            "/api/v1/candidate/photo/",
            {"file": image_file("replacement.webp", "WEBP", (96, 96), False)},
            format="multipart",
        )
        assert replacement.status_code == 200
        photo.refresh_from_db()
        assert photo.content_type == "image/webp"
        assert photo.file.name != first_name
        assert not first_path.exists()

        removed = client.delete("/api/v1/candidate/photo/")
        assert removed.status_code == 200
        assert removed.data["profile_photo_url"] is None
        assert not Path(photo.file.path).exists()
        assert client.get("/api/v1/candidate/photo/").status_code == 404


@pytest.mark.django_db
def test_candidate_photo_rejects_invalid_content_and_is_owner_only(
    client, candidate_account, tmp_path
):
    with override_settings(MEDIA_ROOT=tmp_path, PROFILE_PHOTO_MAX_BYTES=100):
        fake = SimpleUploadedFile("fake.png", b"not an image", content_type="image/png")
        assert client.post(
            "/api/v1/candidate/photo/", {"file": fake}, format="multipart"
        ).status_code == 400
        oversized = SimpleUploadedFile("large.jpg", b"x" * 101, content_type="image/jpeg")
        response = client.post(
            "/api/v1/candidate/photo/", {"file": oversized}, format="multipart"
        )
        assert response.status_code == 400
        assert "limit" in response.data["detail"]

    recruiter = APIClient()
    recruiter_account = provision_recruiter(
        recruiter,
        {
            "email": "photo-recruiter@company.example",
            "password": "strong-pass-123",
            "full_name": "Photo Recruiter",
            "company": "Enter Labs",
            "role": "recruiter",
        },
    )
    assert recruiter_account.status_code == 200
    recruiter.credentials(HTTP_AUTHORIZATION=f"Token {recruiter_account.data['token']}")
    assert recruiter.get("/api/v1/candidate/photo/").status_code == 403
    assert APIClient().get("/api/v1/candidate/photo/").status_code in {401, 403}


@pytest.mark.django_db
def test_build_lead_preference_is_explicit_bounded_and_persistent(client, candidate_account):
    url = "/api/v1/candidate/profile/"
    assert client.get(url).data["build_lead_preference"] is None
    for value in (0, 50, 100):
        response = client.patch(url, {"build_lead_preference": value}, format="json")
        assert response.status_code == 200
        assert response.data["build_lead_preference"] == value
        assert client.get(url).data["build_lead_preference"] == value
    for value in (-1, 101):
        assert client.patch(url, {"build_lead_preference": value}, format="json").status_code == 400
