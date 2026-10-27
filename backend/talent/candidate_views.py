from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.decorators import api_view, parser_classes, permission_classes, throttle_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .candidate_experience import pending_fields, record_candidate_edits, resume_identity_issue
from .models import CandidatePhoto, CandidateProfile, Resume, WorkExperience
from .permissions import IsCandidate
from .resume_processing import can_retry_resume
from .serializers import CandidateProfileSerializer, ResumeSerializer
from .services import read_docx
from .storage_cleanup import schedule_cleanup, store_private_upload
from .throttling import DatabaseRateThrottle
from .worker_runtime import worker_available


class ResumePreviewThrottle(DatabaseRateThrottle):
    scope = "candidate_resume_preview"
    rate = "30/min"

    def get_rate(self):
        return self.rate


class CandidatePhotoThrottle(DatabaseRateThrottle):
    scope = "candidate_photo"
    rate = "30/min"

    def get_rate(self):
        return self.rate


PHOTO_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}


@api_view(["GET"])
@permission_classes([IsCandidate])
def processing_status(request):
    # Do not load raw extraction, work history, old resume versions or private URLs.
    resume = Resume.objects.select_related("processing_job").filter(
        candidate__user=request.user,
    ).only(
        "id", "processing_status", "scan_status", "processing_error", "processing_job__phase"
    ).first()
    data = None if not resume else {
        "id": resume.pk,
        "processing_status": resume.processing_status,
        "processing_stage": ResumeSerializer().get_processing_stage(resume),
        "scan_status": resume.scan_status,
        "processing_error": resume.processing_error,
        "can_retry": can_retry_resume(resume),
    }
    response = Response({"resume": data, "worker_available": worker_available()})
    response["Cache-Control"] = "private, no-store"
    return response


@api_view(["POST"])
@permission_classes([IsCandidate])
@transaction.atomic
def restore_archived_employment(request, experience_id):
    profile = CandidateProfile.objects.select_for_update().get(user=request.user)
    row = get_object_or_404(
        WorkExperience.all_objects.select_for_update(), pk=experience_id,
        candidate=profile, archived_at__isnull=False,
    )
    row.archived_at = None
    row.archived_by_resume_id = None
    row.origin = "candidate"
    row.confidence_status = WorkExperience.ConfidenceStatus.CANDIDATE_CONFIRMED
    row.save(update_fields=[
        "archived_at", "archived_by_resume_id", "origin", "confidence_status",
    ])
    profile.save(update_fields=["profile_updated_at"])
    from .candidate_experience import record_candidate_edits

    record_candidate_edits(profile, {"work_experiences"})
    response = Response(CandidateProfileSerializer(profile, context={"request": request}).data)
    response["Cache-Control"] = "private, no-store"
    return response


def _normalized_photo(uploaded):
    if uploaded.size > settings.PROFILE_PHOTO_MAX_BYTES:
        limit = settings.PROFILE_PHOTO_MAX_BYTES // (1024 * 1024)
        raise ValueError(f"Photo exceeds the {limit} MB limit.")
    try:
        uploaded.seek(0)
        with Image.open(uploaded, formats=list(PHOTO_FORMATS)) as image:
            if image.width * image.height > 20_000_000:
                raise ValueError("This image is too large to process safely.")
            image.verify()
        uploaded.seek(0)
        with Image.open(uploaded, formats=list(PHOTO_FORMATS)) as image:
            if image.format not in PHOTO_FORMATS:
                raise ValueError("Upload a JPG, PNG or WebP image.")
            image_format = image.format
            if getattr(image, "is_animated", False):
                raise ValueError("Animated images are not supported.")
            if image.width < 64 or image.height < 64:
                raise ValueError("Choose an image at least 64 × 64 pixels.")
            if image.width > 12000 or image.height > 12000:
                raise ValueError("This image is too large to process safely.")
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
            extension, content_type = PHOTO_FORMATS[image_format]
            if image_format == "JPEG":
                image = image.convert("RGB")
            elif image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
            output = BytesIO()
            options = {"quality": 88} if image_format in {"JPEG", "WEBP"} else {"optimize": True}
            image.save(output, format=image_format, **options)
            return ContentFile(output.getvalue()), extension, content_type
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as error:
        raise ValueError("The uploaded file is not a valid image.") from error


@api_view(["GET", "POST", "DELETE"])
@permission_classes([IsCandidate])
@parser_classes([MultiPartParser, FormParser])
@throttle_classes([CandidatePhotoThrottle])
def candidate_photo(request):
    profile = CandidateProfile.objects.get(user=request.user)
    if request.method == "GET":
        try:
            photo = profile.photo
        except CandidatePhoto.DoesNotExist:
            return Response(status=404)
        response = FileResponse(
            photo.file.open("rb"), content_type=photo.content_type,
            as_attachment=False, filename=Path(photo.original_name).name,
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Cross-Origin-Resource-Policy"] = "same-site"
        return response
    if request.method == "DELETE":
        try:
            profile.photo.delete()
        except CandidatePhoto.DoesNotExist:
            pass
        profile._state.fields_cache.pop("photo", None)
        return Response(CandidateProfileSerializer(profile, context={"request": request}).data)

    uploaded = request.FILES.get("file")
    if not uploaded:
        return Response({"detail": "Choose a profile photo."}, status=400)
    try:
        content, extension, content_type = _normalized_photo(uploaded)
    except ValueError as error:
        return Response({"detail": str(error)}, status=400)
    stored_name = store_private_upload(
        content, f"candidate-photos/{profile.pk}", f"profile{extension}",
    )
    with transaction.atomic():
        profile = CandidateProfile.objects.select_for_update().get(pk=profile.pk)
        photo, _ = CandidatePhoto.objects.get_or_create(
            candidate=profile,
            defaults={"original_name": "", "content_type": content_type},
        )
        previous_name = photo.file.name
        photo.original_name = Path(uploaded.name).name[:255]
        photo.content_type = content_type
        photo.file.name = stored_name
        photo.save()
        if previous_name and previous_name != photo.file.name:
            schedule_cleanup(previous_name)
    return Response(CandidateProfileSerializer(profile, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsCandidate])
@transaction.atomic
def review_resume(request, resume_id):
    profile = CandidateProfile.objects.select_for_update().get(user=request.user)
    resume = (
        profile.resumes.select_for_update()
        .filter(pk=resume_id, processing_status="completed", scan_status="clean")
        .first()
    )
    if not resume:
        return Response({"detail": "This resume is not available for review."}, status=409)
    if resume_identity_issue(resume, profile):
        return Response({"detail": "This resume's identity could not be matched. Upload your own "
                         "resume with your correct name; no profile changes were applied."},
                        status=409)
    if not resume.extracted_data.get("_needs_review"):
        return Response(CandidateProfileSerializer(profile, context={"request": request}).data)
    try:
        supplied_time = parse_datetime(str(request.data.get("profile_updated_at", "")))
    except ValueError:
        supplied_time = None
    if supplied_time != profile.profile_updated_at:
        return Response(
            {"detail": "Your profile changed. Reload before applying updates."}, status=409
        )
    fields = request.data.get("fields")
    proposed = pending_fields(resume, profile)
    if not isinstance(fields, list) or any(
        not isinstance(field, str) or field not in proposed for field in fields
    ):
        return Response({"detail": "Choose valid resume fields."}, status=400)
    from .employment_reconciliation import apply_reviewed_employment

    selected_history = proposed.get('work_experiences') if 'work_experiences' in fields else None
    serializer = CandidateProfileSerializer(
        profile,
        data={field: proposed[field] for field in fields if field != 'work_experiences'},
        partial=True,
        context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    if selected_history:
        apply_reviewed_employment(profile, selected_history)
    keep_pending = request.data.get("keep_pending") is True
    remaining = {key: value for key, value in proposed.items() if key not in fields}
    resume.extracted_data["_pending_fields"] = remaining if keep_pending else {}
    resume.extracted_data["_needs_review"] = bool(remaining) if keep_pending else False
    resume.extracted_data["_candidate_edited_fields"] = sorted(
        set(resume.extracted_data.get("_candidate_edited_fields", []))
        | set(fields if keep_pending else proposed)
    )
    resume.save(update_fields=["extracted_data"])
    record_candidate_edits(profile, fields if keep_pending else proposed)
    if fields and profile.profile_status == "submitted":
        from .views import _notify_recruiters_of_candidate_update

        _notify_recruiters_of_candidate_update(
            profile, change_type="profile", message="Profile updated"
        )
    return Response(CandidateProfileSerializer(profile, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([IsCandidate])
@throttle_classes([ResumePreviewThrottle])
def preview_docx(request, resume_id):
    resume = Resume.objects.filter(
        pk=resume_id,
        candidate__user=request.user,
        processing_status="completed",
        scan_status="clean",
    ).first()
    if not resume:
        return Response(status=404)
    if not resume.original_name.lower().endswith(".docx"):
        return Response({"detail": "Use the secure PDF viewer for this document."}, status=400)
    try:
        with resume.file.open("rb") as file:
            document = read_docx(file)
            blocks = []
            for block in document.iter_inner_content():
                if hasattr(block, "runs"):
                    blocks.append(
                        {
                            "type": "paragraph",
                            "runs": [
                                {
                                    "text": run.text,
                                    "bold": bool(run.bold),
                                    "italic": bool(run.italic),
                                }
                                for run in block.runs
                            ],
                        }
                    )
                else:
                    blocks.append(
                        {
                            "type": "table",
                            "rows": [[cell.text for cell in row.cells] for row in block.rows],
                        }
                    )
    except (ValueError, OSError, KeyError):
        return Response(
            {"detail": "Preview unavailable. Download the original resume."}, status=422
        )
    response = Response({"blocks": blocks})
    response["Cache-Control"] = "private, no-store"
    return response
