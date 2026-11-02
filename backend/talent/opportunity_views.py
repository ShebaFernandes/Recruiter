from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import CandidateProfile, OpportunityApplication
from .permissions import IsCandidate

OPPORTUNITY_IDS = [
    "backend-engineer",
    "senior-ai-engineer",
    "founding-engineer",
    "product-manager",
    "director-engineering",
    "enterprise-sales-manager",
]


class ApplicationSerializer(serializers.Serializer):
    opportunity_id = serializers.ChoiceField(choices=OPPORTUNITY_IDS)
    note = serializers.CharField(max_length=5000, required=False, allow_blank=True)


@api_view(["POST"])
@permission_classes([IsCandidate])
def apply(request):
    serializer = ApplicationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    application, created = OpportunityApplication.objects.get_or_create(
        candidate=CandidateProfile.objects.get(user=request.user),
        opportunity_id=serializer.validated_data["opportunity_id"],
        defaults={"note": serializer.validated_data.get("note", "")},
    )
    return Response(
        {
            "id": application.pk,
            "detail": (
                "Your application has been received."
                if created
                else "You have already applied for this role."
            ),
        },
        status=201 if created else 200,
    )
