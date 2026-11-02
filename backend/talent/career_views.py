"""Public career applications with private resume storage."""

from pathlib import Path

from rest_framework import serializers
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .authentication import CsrfProtectedPublicAuthentication
from .hiring_views import validate_attachment
from .models import CareerApplication
from .storage_cleanup import store_private_upload
from .throttling import HiringEnquiryRateThrottle


class CareerApplicationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=180)
    email = serializers.EmailField()
    phone = serializers.RegexField(r"^[+()0-9 .-]{7,40}$")
    linkedin = serializers.URLField(max_length=500)
    motivation = serializers.CharField(max_length=5000)
    resume = serializers.FileField()

    def validate_resume(self, value):
        return validate_attachment(value)


@api_view(["POST"])
@authentication_classes([CsrfProtectedPublicAuthentication])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser])
@throttle_classes([HiringEnquiryRateThrottle])
def career_application(request):
    serializer = CareerApplicationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = dict(serializer.validated_data)
    resume = data.pop("resume")
    stored_name = store_private_upload(resume, "career-applications", resume.name)
    application = CareerApplication.objects.create(
        **data,
        resume=stored_name,
        original_filename=Path(resume.name).name[:255],
    )
    return Response(
        {"id": application.pk, "detail": "Thank you. Your application has been received."},
        status=201,
    )
