"""Public employee-transition enquiries, kept separate from candidate records."""

import csv
import io
import zipfile
from pathlib import Path

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status
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
from .models import EmployeeTransitionEnquiry, EnquiryNotification
from .storage_cleanup import store_private_upload
from .throttling import EmployeeTransitionRateThrottle
from .upload_security import scan_public_upload

MAX_LIST_BYTES = 2 * 1024 * 1024


class EmployeeTransitionEnquirySerializer(serializers.Serializer):
    company = serializers.CharField(max_length=180, trim_whitespace=True)
    full_name = serializers.CharField(max_length=180, trim_whitespace=True)
    work_email = serializers.EmailField()
    role = serializers.ChoiceField(choices=["HR", "People", "Founder", "Other"])
    people_impacted = serializers.ChoiceField(
        choices=["1–10", "11–40", "41–100", "More than 100"]
    )
    last_working_day = serializers.DateField()
    reach_method = serializers.ChoiceField(choices=EmployeeTransitionEnquiry.ReachMethod.choices)
    employee_list = serializers.FileField(required=False)
    situation = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    consent = serializers.BooleanField()

    def validate_employee_list(self, uploaded):
        suffix = Path(uploaded.name).suffix.lower()
        if suffix not in {".csv", ".xlsx"}:
            raise serializers.ValidationError("Upload a CSV or Excel (.xlsx) file.")
        if uploaded.size > MAX_LIST_BYTES:
            raise serializers.ValidationError("The list must be smaller than 2 MB.")
        try:
            if suffix == ".csv":
                rows = csv.reader(io.StringIO(uploaded.read().decode("utf-8-sig")))
                header = {column.strip().lower() for column in next(rows, [])}
                if not {"name", "role", "email"}.issubset(header):
                    raise serializers.ValidationError(
                        "The CSV must include name, role and email columns."
                    )
            else:
                with zipfile.ZipFile(uploaded) as workbook:
                    names = set(workbook.namelist())
                    if "xl/workbook.xml" not in names or not any(
                        name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
                        for name in names
                    ):
                        raise serializers.ValidationError("Upload a valid Excel workbook.")
        except (UnicodeError, csv.Error, zipfile.BadZipFile):
            raise serializers.ValidationError("The selected list could not be read.") from None
        finally:
            uploaded.seek(0)
        return scan_public_upload(uploaded)

    def validate(self, attrs):
        if not attrs["consent"]:
            raise serializers.ValidationError({"consent": "Please confirm employee consent."})
        if attrs["reach_method"] == EmployeeTransitionEnquiry.ReachMethod.LIST:
            if not attrs.get("employee_list"):
                raise serializers.ValidationError({"employee_list": "Choose a CSV or Excel list."})
        elif attrs.get("employee_list"):
            raise serializers.ValidationError(
                {"employee_list": "A list is not needed when you choose to talk first."}
            )
        return attrs


@api_view(["POST"])
@authentication_classes([CsrfProtectedPublicAuthentication])
@permission_classes([AllowAny])
@throttle_classes([EmployeeTransitionRateThrottle])
@parser_classes([MultiPartParser, FormParser])
def employee_transition_enquiry(request):
    serializer = EmployeeTransitionEnquirySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    uploaded = data.get("employee_list")
    stored_name = ""
    if uploaded:
        stored_name = store_private_upload(uploaded, "employee-transition", uploaded.name)
    with transaction.atomic():
        enquiry = EmployeeTransitionEnquiry.objects.create(
            company=data["company"],
            full_name=data["full_name"],
            work_email=data["work_email"],
            role=data["role"],
            people_impacted=data["people_impacted"],
            last_working_day=data["last_working_day"],
            reach_method=data["reach_method"],
            employee_list=stored_name,
            original_filename=uploaded.name if uploaded else "",
            situation=data.get("situation", ""),
            consent_confirmed_at=timezone.now(),
        )
        EnquiryNotification.objects.create(transition_enquiry=enquiry)
    return Response(
        {"id": enquiry.pk, "detail": "Thank you. Your request has been received."},
        status=status.HTTP_201_CREATED,
    )
