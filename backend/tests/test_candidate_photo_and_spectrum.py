from io import BytesIO
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient
from talent.storage_cleanup import drain_cleanup

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


@pytest.mark.parametrize("image_format", ["JPEG", "PNG", "WEBP"])
def test_photo_thumbnail_preserves_orientation_and_strips_exif(image_format):
    from talent.candidate_views import _normalized_photo

    source = Image.new("RGB", (1600, 800), "red")
    source.paste("blue", (800, 0, 1600, 800))
    exif = Image.Exif()
    exif[274] = 6  # Rotate 90 degrees clockwise.
    exif[270] = "PRIVATE CAMERA NOTE"
    buffer = BytesIO()
    source.save(buffer, image_format, exif=exif)
    upload = SimpleUploadedFile("photo", buffer.getvalue())
    content, _, _ = _normalized_photo(upload)
    normalized_bytes = content.read()
    with Image.open(BytesIO(normalized_bytes)) as result:
        result.load()
        assert result.format == image_format
        assert result.size == (600, 1200)
        top = result.convert("RGB").getpixel((300, 100))
        bottom = result.convert("RGB").getpixel((300, 1100))
        assert top[0] > top[2] and bottom[2] > bottom[0]
        assert not result.getexif()
    assert b"PRIVATE CAMERA NOTE" not in normalized_bytes


@pytest.mark.parametrize("image_format", ["TIFF", "GIF", "PPM"])
def test_photo_rejects_unsupported_formats_even_with_jpeg_filename(image_format):
    from talent.candidate_views import _normalized_photo

    buffer = BytesIO()
    Image.new("RGB", (100, 100)).save(buffer, image_format)
    with pytest.raises(ValueError, match="not a valid image"):
        _normalized_photo(SimpleUploadedFile("fake.jpg", buffer.getvalue()))


def test_photo_rejects_truncated_and_decompression_bomb_inputs(monkeypatch):
    from talent.candidate_views import _normalized_photo

    valid = image_file(size=(180, 140))
    with pytest.raises(ValueError):
        _normalized_photo(SimpleUploadedFile("truncated.jpg", valid.read()[:100]))
    # Exercise the real decoder guard without allocating a huge malicious image.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(ValueError, match="not a valid image"):
        _normalized_photo(image_file())


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
        drain_cleanup()
        assert not first_path.exists()

        removed = client.delete("/api/v1/candidate/photo/")
        assert removed.status_code == 200
        assert removed.data["profile_photo_url"] is None
        drain_cleanup()
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
