from django.db import transaction
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response

from .candidate_experience import proposed_fields
from .models import CandidateProfile, Resume
from .permissions import IsCandidate
from .serializers import CandidateProfileSerializer
from .services import read_docx
from .throttling import DatabaseRateThrottle


class ResumePreviewThrottle(DatabaseRateThrottle):
    scope = "candidate_resume_preview"
    rate = "30/min"

    def get_rate(self):
        return self.rate


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
    if not resume or profile.resumes.first().pk != resume.pk:
        return Response({"detail": "This resume is no longer the latest upload."}, status=409)
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
    proposed = proposed_fields(resume.extracted_data)
    if not isinstance(fields, list) or any(
        not isinstance(field, str) or field not in proposed for field in fields
    ):
        return Response({"detail": "Choose valid resume fields."}, status=400)
    serializer = CandidateProfileSerializer(
        profile,
        data={field: proposed[field] for field in fields},
        partial=True,
        context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    resume.extracted_data["_needs_review"] = False
    resume.save(update_fields=["extracted_data"])
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
