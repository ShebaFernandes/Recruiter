from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import legal
from .permissions import IsCandidate


@api_view(["GET"])
@permission_classes([AllowAny])
def legal_documents(request):
    if not legal.enabled():
        return Response({"enabled": False})
    try:
        documents = legal.documents()
    except ValidationError:
        return Response({"detail": "Legal documents are not publication-ready."}, status=503)
    except OSError:
        return Response({"detail": "Legal documents unavailable."}, status=503)
    return Response(
        {"enabled": True, "documents": documents},
        headers={
            "Cache-Control": "no-store",
            "X-Robots-Tag": (
                "noindex, nofollow" if not legal.published() else "index, follow"
            ),
        },
    )


@api_view(["GET", "POST"])
@permission_classes([IsCandidate])
@transaction.atomic
def accept_terms(request):
    if not legal.enabled():
        return Response(status=404)
    try:
        current_documents = legal.documents()
    except ValidationError:
        return Response({"detail": "Legal documents are not publication-ready."}, status=503)
    except OSError:
        return Response({"detail": "Legal documents unavailable; retry review."}, status=503)
    if request.method == "GET":
        docs = current_documents
        from .models import LegalAcceptance

        accepted = {
            p: LegalAcceptance.objects.filter(
                user=request.user,
                purpose=p,
                version=docs[p]["version"],
                unpublished=docs[p]["unpublished"],
            ).exists()
            for p in ["age", "terms"]
        }
        return Response(
            {"accepted": accepted, "versions": {p: docs[p]["version"] for p in accepted}},
            headers={"Cache-Control": "no-store"},
        )
    docs = {
        purpose: legal.validate_acceptance(request.data, purpose, current_documents[purpose])
        for purpose in ["age", "terms"]
    }
    for purpose, doc in docs.items():
        legal.record(request.user, purpose, doc)
    return Response({"detail": "Current legal confirmations recorded."})


@api_view(["POST"])
@permission_classes([IsCandidate])
def renew_activity(request):
    if not legal.enabled():
        return Response(status=404)
    legal.activity(request.user.candidate_profile)
    return Response({"detail": "Profile activity renewed."})
