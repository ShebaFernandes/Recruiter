from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import CandidateProfile, OpportunityApplication
from .permissions import IsCandidate

OPPORTUNITY_IDS = [
    "backend-engineer",
    "senior-backend-engineer",
    "frontend-engineer-sde-iii",
    "mobile-engineer-flutter",
    "senior-sre-devops-engineer",
    "ai-ml-engineer",
    "deep-learning-engineer",
    "ml-engineer-voice-ai",
    "voice-ai-engineer",
    "ai-ml-engineer-speech-models",
    "data-scientist",
    "lead-data-scientist-recommendations",
    "founding-ai-evals-engineer",
    "ai-evaluation-engineer-healthtech",
    "lead-product-manager-consumer",
    "lead-product-manager-consumer-healthtech",
    "ai-product-manager-agentic-ai",
    "product-manager-internal-tools-ai-platform",
    "product-manager-ai-products",
    "lead-product-manager-b2b-growth",
    "senior-product-designer-b2c",
    "senior-product-designer-b2b-saas",
    "product-designer-ai-products",
    "founding-backend-engineer",
    "founding-full-stack-engineer",
    "senior-engineering-manager-ai-ml",
    "director-of-engineering-ai-platform",
    "vp-engineering-enterprise-ai",
    "head-of-data-ai-lending",
    "engineering-manager-enterprise-saas",
]


class ApplicationSerializer(serializers.Serializer):
    opportunity_id = serializers.ChoiceField(choices=OPPORTUNITY_IDS)
    note = serializers.CharField(max_length=5000, required=False, allow_blank=True)


@api_view(["GET", "POST"])
@permission_classes([IsCandidate])
def apply(request):
    if request.method == 'GET':
        rows = OpportunityApplication.objects.filter(
            candidate__user=request.user
        ).order_by('-created_at').values('id', 'opportunity_id', 'created_at')
        return Response(list(rows))
    profile = CandidateProfile.objects.get(user=request.user)
    latest = profile.resumes.first()
    if not latest or latest.processing_status != 'completed' or latest.scan_status != 'clean':
        return Response({'detail': 'Upload and process your resume before applying.'}, status=400)
    if latest.extracted_data.get('_identity_issue'):
        return Response({'detail': 'Confirm resume ownership before applying.'}, status=400)
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
