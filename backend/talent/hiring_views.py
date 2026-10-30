"""Public hiring enquiries, separate from authenticated recruiter projects."""

import zipfile
from datetime import date
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
from .enquiry_uploads import scan_enquiry_upload
from .models import EnquiryNotification, HiringEnquiry, HiringEnquiryAttachment
from .storage_cleanup import store_private_upload
from .throttling import HiringEnquiryRateThrottle

MAX_JD_BYTES = 10 * 1024 * 1024
DEPARTMENTS = (
    "Engineering", "Product", "Marketing", "Sales", "HR", "Talent Acquisition", "Other"
)
PERSONAL_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "live.com",
    "icloud.com", "aol.com", "proton.me", "protonmail.com", "rediffmail.com",
}
FOUNDING_CATEGORIES = (
    "Founding Engineer", "Founding AI / ML",
    "Early Technical Leader (CTO / Head of Eng)", "Founding Designer",
)
LEADERSHIP_CATEGORIES = (
    "Engineering Leader", "Product Leader", "Functional Leader (Data, Design, GTM)",
)
PEOPLE_COUNTS = ("1", "2", "3", "4", "5", "6–10", "10+")
ROLE_TITLES = (
    "VP Engineering", "CTO", "Head of Engineering", "Chief Product Officer",
    "Head of Product", "Functional Head", "Other",
)
CASH_RANGES = (
    "₹20–40L", "₹40–60L", "₹60–90L", "₹90L–1.2Cr", "₹1.2–2Cr",
    "₹2Cr+", "Let’s discuss",
)
EQUITY_RANGES = ("0–0.5%", "0.5–1.5%", "1.5–3%", "3%+", "Let’s discuss")


def validate_attachment(uploaded, *, allow_text=False):
    suffix = Path(uploaded.name).suffix.lower()
    allowed = {".pdf", ".docx"} | ({".txt"} if allow_text else set())
    if suffix not in allowed:
        raise serializers.ValidationError(
            "Choose a PDF, DOCX, or TXT file." if allow_text else "Choose a PDF or DOCX file."
        )
    if uploaded.size > MAX_JD_BYTES:
        raise serializers.ValidationError("The attachment must be smaller than 10 MB.")
    try:
        if suffix == ".pdf" and uploaded.read(5) != b"%PDF-":
            raise serializers.ValidationError("Upload a valid PDF file.")
        if suffix == ".docx":
            with zipfile.ZipFile(uploaded) as document:
                names = set(document.namelist())
                if not {"[Content_Types].xml", "word/document.xml"}.issubset(names):
                    raise serializers.ValidationError("Upload a valid DOCX file.")
        if suffix == ".txt":
            uploaded.read().decode("utf-8")
    except zipfile.BadZipFile:
        raise serializers.ValidationError("Upload a valid DOCX file.") from None
    except UnicodeDecodeError:
        raise serializers.ValidationError("Upload a UTF-8 text file.") from None
    finally:
        uploaded.seek(0)
    return uploaded


class BaseHiringSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=HiringEnquiry.Kind.choices)
    company = serializers.CharField(max_length=180, trim_whitespace=True)
    full_name = serializers.CharField(max_length=180, trim_whitespace=True)
    work_email = serializers.EmailField()

    def validate_work_email(self, value):
        if value.rsplit("@", 1)[-1].lower() in PERSONAL_EMAIL_DOMAINS:
            raise serializers.ValidationError("Use your company or work email address.")
        return value


class DepartmentHiringSerializer(BaseHiringSerializer):
    how_soon = serializers.ChoiceField(choices=["2 weeks", "30 days", "Other"], required=False)
    self_description = serializers.CharField(
        max_length=240, required=False, allow_blank=True, trim_whitespace=True
    )
    headcount = serializers.IntegerField(min_value=1, max_value=10000)
    departments = serializers.ListField(
        child=serializers.ChoiceField(choices=DEPARTMENTS), allow_empty=False
    )
    notes = serializers.CharField(max_length=3000, required=False, allow_blank=True)
    jd = serializers.FileField(required=False)

    def validate_departments(self, value):
        return list(dict.fromkeys(value))

    def validate_jd(self, uploaded):
        return validate_attachment(uploaded)


class HireTalentSerializer(DepartmentHiringSerializer):
    role = serializers.CharField(max_length=240, trim_whitespace=True)
    location = serializers.CharField(
        max_length=160, trim_whitespace=True, required=False, allow_blank=True
    )


class BuildTeamSerializer(DepartmentHiringSerializer):
    team_focus = serializers.CharField(max_length=240, trim_whitespace=True)


class RecruitmentDriveSerializer(DepartmentHiringSerializer):
    role = serializers.CharField(max_length=240, trim_whitespace=True)
    location = serializers.CharField(max_length=160, trim_whitespace=True)
    deadline = serializers.DateField()

    def validate_deadline(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("Choose today or a future date.")
        return value


class FoundingTeamSerializer(BaseHiringSerializer):
    founder_role = serializers.ChoiceField(choices=("Founder", "CEO", "CTO", "Other"))
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    website = serializers.CharField(max_length=300, required=False, allow_blank=True)
    product = serializers.CharField(max_length=3000)
    categories = serializers.ListField(
        child=serializers.ChoiceField(choices=FOUNDING_CATEGORIES), allow_empty=False
    )
    people_count = serializers.ChoiceField(choices=PEOPLE_COUNTS)
    attachment = serializers.FileField(required=False)
    cash_range = serializers.ChoiceField(choices=CASH_RANGES, required=False, allow_blank=True)
    equity_range = serializers.ChoiceField(
        choices=EQUITY_RANGES, required=False, allow_blank=True
    )
    location = serializers.CharField(max_length=160)
    start_month = serializers.CharField(max_length=7)

    def validate_categories(self, value):
        return list(dict.fromkeys(value))

    def validate_attachment(self, uploaded):
        return validate_attachment(uploaded, allow_text=True)

    def validate_start_month(self, value):
        try:
            if len(value) != 7 or value[4] != "-":
                raise ValueError
            selected = date.fromisoformat(f"{value}-01")
        except ValueError:
            raise serializers.ValidationError("Choose a valid start month.") from None
        today = timezone.localdate()
        if selected < today.replace(day=1):
            raise serializers.ValidationError("Choose this month or a future month.")
        return value


class LeadershipSerializer(BaseHiringSerializer):
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    website = serializers.CharField(max_length=300, required=False, allow_blank=True)
    categories = serializers.ListField(
        child=serializers.ChoiceField(choices=LEADERSHIP_CATEGORIES), allow_empty=False
    )
    role_title = serializers.ChoiceField(choices=ROLE_TITLES)
    outcome = serializers.CharField(max_length=3000)
    confidential = serializers.BooleanField()
    compensation = serializers.ChoiceField(
        choices=CASH_RANGES, required=False, allow_blank=True
    )
    location_mode = serializers.CharField(max_length=160)

    def validate_categories(self, value):
        return list(dict.fromkeys(value))


SERIALIZERS = {
    HiringEnquiry.Kind.HIRE: HireTalentSerializer,
    HiringEnquiry.Kind.TEAM: BuildTeamSerializer,
    HiringEnquiry.Kind.DRIVE: RecruitmentDriveSerializer,
    HiringEnquiry.Kind.FOUNDING: FoundingTeamSerializer,
    HiringEnquiry.Kind.LEADERSHIP: LeadershipSerializer,
}


def enquiry_details(kind, data):
    if kind == HiringEnquiry.Kind.HIRE:
        fields = ("role", "location", "headcount", "departments")
    elif kind == HiringEnquiry.Kind.TEAM:
        fields = ("team_focus", "headcount", "departments")
    elif kind == HiringEnquiry.Kind.DRIVE:
        fields = ("role", "location", "headcount", "deadline", "departments")
    elif kind == HiringEnquiry.Kind.FOUNDING:
        fields = (
            "founder_role", "phone", "website", "product", "categories", "people_count",
            "cash_range", "equity_range", "location", "start_month",
        )
    else:
        fields = (
            "phone", "website", "categories", "role_title", "outcome", "confidential",
            "compensation", "location_mode",
        )
    if kind in {HiringEnquiry.Kind.HIRE, HiringEnquiry.Kind.TEAM, HiringEnquiry.Kind.DRIVE}:
        fields = (*fields, "self_description", "how_soon")
    return {
        field: value.isoformat() if isinstance(value, date) else value
        for field in fields if (value := data.get(field)) is not None
    }


@api_view(["POST"])
@authentication_classes([CsrfProtectedPublicAuthentication])
@permission_classes([AllowAny])
@throttle_classes([HiringEnquiryRateThrottle])
@parser_classes([MultiPartParser, FormParser])
def hiring_enquiry(request):
    kind = request.data.get("kind")
    serializer_class = SERIALIZERS.get(kind)
    if serializer_class is None:
        raise serializers.ValidationError({"kind": "Choose a valid enquiry type."})
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    uploaded = data.get("jd") or data.get("attachment")
    stored_name = ""
    if uploaded:
        scan_enquiry_upload(uploaded)
        stored_name = store_private_upload(uploaded, "hiring-enquiries", uploaded.name)
    with transaction.atomic():
        enquiry = HiringEnquiry.objects.create(
            kind=kind,
            company=data["company"],
            full_name=data["full_name"],
            work_email=data["work_email"],
            details=enquiry_details(kind, data),
            notes=data.get("notes", ""),
        )
        if uploaded:
            HiringEnquiryAttachment.objects.create(
                enquiry=enquiry,
                file=stored_name,
                original_filename=Path(uploaded.name).name[:255],
                size=uploaded.size,
            )
        EnquiryNotification.objects.create(hiring_enquiry=enquiry)
    return Response(
        {"id": enquiry.pk, "detail": "Thank you. Your request has been received."},
        status=status.HTTP_201_CREATED,
    )
