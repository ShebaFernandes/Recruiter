from pathlib import Path

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .account_security import (
    consume_account_token,
    inspect_account_token,
    recently_issued,
    send_password_reset_email,
    send_verification_email,
)
from .models import (
    AccountActionToken,
    CandidateProfile,
    CandidateStatus,
    CandidateUpdateNotification,
    ProfileView,
    Project,
    ProjectCandidate,
    RecruiterProfile,
    Resume,
    Search,
    UserRole,
    WorkExperience,
)
from .permissions import IsCandidate, IsRecruiter
from .serializers import (
    CandidateProfileSerializer,
    NotificationSerializer,
    ProjectCandidateSerializer,
    ProjectSerializer,
    SearchSerializer,
    SignupSerializer,
)
from .services import (
    apply_search_answer,
    calculate_match,
    next_search_question,
    parse_date,
    parse_resume,
    parse_search_query,
)


def _identity(user):
    role = user.role_profile.role
    profile = user.candidate_profile if role == UserRole.Role.CANDIDATE else user.recruiter_profile
    return {"id": user.id, "email": user.email, "role": role, "full_name": profile.full_name}


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def signup(request):
    serializer = SignupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    with transaction.atomic():
        is_candidate = data["role"] == UserRole.Role.CANDIDATE
        user = User.objects.create_user(
            username=data["email"],
            email=data["email"],
            password=data["password"],
            is_active=not is_candidate,
        )
        UserRole.objects.create(user=user, role=data["role"])
        if is_candidate:
            CandidateProfile.objects.create(
                user=user, full_name=data["full_name"], email=data["email"]
            )
        else:
            RecruiterProfile.objects.create(
                user=user, full_name=data["full_name"], company=data.get("company", "")
            )
    if is_candidate:
        try:
            send_verification_email(user)
        except Exception:
            return Response(
                {
                    "detail": (
                        "Your account was created, but the verification email could not be sent. "
                        "Use resend verification to try again."
                    ),
                    "requires_email_verification": True,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {
                "detail": "Check your email to verify your candidate account.",
                "requires_email_verification": True,
            },
            status=status.HTTP_201_CREATED,
        )
    token = Token.objects.create(user=user)
    return Response({"token": token.key, "user": _identity(user)}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login(request):
    email = str(request.data.get("email", "")).strip().lower()
    password = request.data.get("password", "")
    user = authenticate(request, username=email, password=password)
    if not user:
        inactive = User.objects.filter(username__iexact=email, is_active=False).first()
        if inactive and inactive.check_password(password):
            return Response(
                {
                    "detail": "Verify your email before logging in.",
                    "code": "email_not_verified",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            {"detail": "Invalid email or password."}, status=status.HTTP_400_BAD_REQUEST
        )
    Token.objects.filter(user=user).delete()
    token = Token.objects.create(user=user)
    return Response({"token": token.key, "user": _identity(user)})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def verify_email(request):
    user = consume_account_token(
        request.data.get("token"), AccountActionToken.Purpose.VERIFY_EMAIL
    )
    if not user or not hasattr(user, "candidate_profile"):
        return Response(
            {"detail": "This verification link is invalid or has expired."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    user.is_active = True
    user.save(update_fields=["is_active"])
    profile = user.candidate_profile
    profile.email_verified_at = timezone.now()
    profile.save(update_fields=["email_verified_at", "profile_updated_at"])
    Token.objects.filter(user=user).delete()
    token = Token.objects.create(user=user)
    return Response({"token": token.key, "user": _identity(user)})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def resend_verification(request):
    email = str(request.data.get("email", "")).strip().lower()
    user = User.objects.filter(username__iexact=email, is_active=False).first()
    if (
        user
        and hasattr(user, "candidate_profile")
        and not recently_issued(user, AccountActionToken.Purpose.VERIFY_EMAIL)
    ):
        try:
            send_verification_email(user)
        except Exception:
            pass
    return Response(
        {"detail": "If an unverified candidate account exists, a verification email is on its way."}
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def request_password_reset(request):
    email = str(request.data.get("email", "")).strip().lower()
    user = User.objects.filter(username__iexact=email, is_active=True).first()
    if user and not recently_issued(user, AccountActionToken.Purpose.RESET_PASSWORD):
        try:
            send_password_reset_email(user)
        except Exception:
            pass
    return Response(
        {
            "detail": (
                "If an account exists for that email, password-reset instructions are on the way."
            )
        }
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def confirm_password_reset(request):
    raw_token = request.data.get("token")
    action_token = inspect_account_token(raw_token, AccountActionToken.Purpose.RESET_PASSWORD)
    if not action_token:
        return Response(
            {"detail": "This password-reset link is invalid or has expired."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    password = str(request.data.get("password", ""))
    try:
        validate_password(password, action_token.user)
    except ValidationError as error:
        return Response({"password": list(error.messages)}, status=status.HTTP_400_BAD_REQUEST)
    user = consume_account_token(raw_token, AccountActionToken.Purpose.RESET_PASSWORD)
    if not user:
        return Response(
            {"detail": "This password-reset link is invalid or has expired."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    user.set_password(password)
    user.save(update_fields=["password"])
    Token.objects.filter(user=user).delete()
    AccountActionToken.objects.filter(
        user=user,
        purpose=AccountActionToken.Purpose.RESET_PASSWORD,
        used_at__isnull=True,
    ).update(used_at=timezone.now())
    return Response({"detail": "Your password has been reset. You can now log in."})


@api_view(["POST"])
def logout(request):
    Token.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def me(request):
    return Response(_identity(request.user))


def _notify_recruiters_of_candidate_update(profile, change_type, resume=None, message=""):
    recruiters = [
        recruiter
        for recruiter in RecruiterProfile.objects.all()
        if _recruiter_can_access_candidate(recruiter, profile)
    ]
    if change_type == CandidateUpdateNotification.ChangeType.PROFILE:
        CandidateUpdateNotification.objects.filter(
            recruiter__in=recruiters,
            candidate=profile,
            resume__isnull=True,
            change_type=CandidateUpdateNotification.ChangeType.PROFILE,
            is_read=False,
        ).delete()
        message = message or "Profile updated"
    else:
        message = "Updated resume"
    CandidateUpdateNotification.objects.bulk_create(
        [
            CandidateUpdateNotification(
                recruiter=recruiter,
                candidate=profile,
                resume=resume,
                change_type=change_type,
                message=message,
            )
            for recruiter in recruiters
        ],
        ignore_conflicts=True,
    )


@api_view(["GET", "PATCH"])
@permission_classes([IsCandidate])
def candidate_profile(request):
    profile = request.user.candidate_profile
    if request.method == "PATCH":
        was_submitted = profile.profile_status == CandidateProfile.ProfileStatus.SUBMITTED
        previous_experience_count = profile.work_experiences.count()
        serializer = CandidateProfileSerializer(
            profile, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if (
            was_submitted
            and profile.profile_status == CandidateProfile.ProfileStatus.SUBMITTED
            and serializer.validated_data
        ):
            changed_fields = set(serializer.validated_data)
            if "work_experiences" in changed_fields:
                message = (
                    "New experience added"
                    if profile.work_experiences.count() > previous_experience_count
                    else "Experience updated"
                )
            elif changed_fields.intersection(
                {"notice_period_days", "work_preferences", "visibility", "employment_type"}
            ):
                message = "Availability changed"
            else:
                message = "Profile updated"
            _notify_recruiters_of_candidate_update(
                profile, change_type="profile", message=message
            )
    return Response(CandidateProfileSerializer(profile, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsCandidate])
def submit_candidate_profile(request):
    profile = request.user.candidate_profile
    serializer = CandidateProfileSerializer(profile, context={"request": request})
    missing = serializer.data["submission_missing_fields"]
    if missing:
        return Response(
            {
                "detail": "Complete the required profile details before submitting.",
                "missing_fields": missing,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if request.data.get("consent") is not True and not profile.submission_consent_at:
        return Response(
            {"detail": "Confirm profile-sharing consent before submitting."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if profile.profile_status != CandidateProfile.ProfileStatus.SUBMITTED:
        now = timezone.now()
        profile.profile_status = CandidateProfile.ProfileStatus.SUBMITTED
        profile.submitted_at = now
        profile.submission_consent_at = now
        profile.submission_consent_version = settings.SUBMISSION_CONSENT_VERSION
        profile.save(
            update_fields=[
                "profile_status",
                "submitted_at",
                "submission_consent_at",
                "submission_consent_version",
                "profile_updated_at",
            ]
        )
    return Response(CandidateProfileSerializer(profile, context={"request": request}).data)


@api_view(["DELETE"])
@permission_classes([IsCandidate])
def delete_candidate_account(request):
    if request.data.get("confirmation") != "DELETE":
        return Response(
            {"detail": "Type DELETE to confirm permanent account deletion."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not request.user.check_password(str(request.data.get("password", ""))):
        return Response(
            {"detail": "Your password is incorrect."}, status=status.HTTP_400_BAD_REQUEST
        )
    resumes = list(request.user.candidate_profile.resumes.all())
    try:
        for resume in resumes:
            resume.file.delete(save=False)
    except Exception:
        return Response(
            {"detail": "We could not remove your stored resume. Your account was not deleted."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    with transaction.atomic():
        request.user.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsCandidate])
@parser_classes([MultiPartParser, FormParser])
def resume_upload(request):
    uploaded = request.FILES.get("file")
    if not uploaded:
        return Response({"detail": "Choose a resume file."}, status=status.HTTP_400_BAD_REQUEST)
    extension = Path(uploaded.name).suffix.lower()
    if extension not in {".pdf", ".docx"}:
        return Response(
            {"detail": "Unsupported resume format. Upload a PDF or DOCX file."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    signature = uploaded.read(5)
    uploaded.seek(0)
    expected_signature = b"%PDF-" if extension == ".pdf" else b"PK"
    if not signature.startswith(expected_signature):
        return Response(
            {"detail": "The uploaded file content does not match its PDF or DOCX extension."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if uploaded.size > settings.RESUME_MAX_BYTES:
        max_megabytes = settings.RESUME_MAX_BYTES // (1024 * 1024)
        return Response(
            {"detail": f"Resume exceeds the {max_megabytes} MB limit."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        extracted = parse_resume(uploaded, uploaded.name)
    except Exception:
        return Response(
            {
                "detail": (
                    "We could not read this resume. Check that the file is valid and try again."
                )
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if not extracted.get("raw_text", "").strip():
        return Response(
            {"detail": "No readable text was found in this resume."},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    uploaded.seek(0)
    profile = request.user.candidate_profile
    with transaction.atomic():
        version = (profile.resumes.first().version + 1) if profile.resumes.exists() else 1
        resume = Resume.objects.create(
            candidate=profile,
            file=uploaded,
            original_name=Path(uploaded.name).name[:255],
            extracted_data=extracted,
            version=version,
        )
        scalar_fields = [
            "full_name",
            "headline",
            "current_company",
            "email",
            "phone",
            "location",
            "total_experience",
            "notice_period_days",
            "current_salary_lpa",
            "expected_salary_lpa",
            "linkedin_url",
            "github_url",
            "work_preferences",
            "skills",
            "education",
            "summary",
        ]
        for field in scalar_fields:
            value = extracted.get(field)
            if value not in (None, "", [], 0):
                setattr(profile, field, value)
        profile.save()
        if extracted.get("work_experiences"):
            profile.work_experiences.all().delete()
            WorkExperience.objects.bulk_create(
                [
                    WorkExperience(
                        candidate=profile,
                        company=item["company"],
                        role=item["role"],
                        start_date=parse_date(item["start_date"]),
                        end_date=parse_date(item.get("end_date")),
                        description=item.get("description", ""),
                    )
                    for item in extracted["work_experiences"]
                ]
            )
        if version > 1:
            _notify_recruiters_of_candidate_update(
                profile, change_type="resume", resume=resume
            )
    return Response(
        CandidateProfileSerializer(profile, context={"request": request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
def resume_download(request, resume_id):
    try:
        resume = Resume.objects.select_related("candidate__user").get(pk=resume_id)
    except Resume.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    is_owner = resume.candidate.user_id == request.user.id
    recruiter = getattr(request.user, "recruiter_profile", None)
    if not is_owner and not (
        recruiter and _recruiter_can_access_candidate(recruiter, resume.candidate)
    ):
        # Match the unknown-ID response so this endpoint cannot be used to
        # enumerate private resume records.
        return Response(status=status.HTTP_404_NOT_FOUND)
    response = FileResponse(
        resume.file.open("rb"), as_attachment=True, filename=resume.original_name
    )
    response["Cache-Control"] = "private, no-store"
    return response


@api_view(["GET", "POST"])
@permission_classes([IsRecruiter])
def projects(request):
    recruiter = request.user.recruiter_profile
    if request.method == "POST":
        serializer = ProjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(recruiter=recruiter)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    items = recruiter.projects.annotate(
        candidate_count=Count("memberships", distinct=True),
        search_count=Count("search", distinct=True),
    ).order_by("-created_at")
    return Response(ProjectSerializer(items, many=True).data)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsRecruiter])
def project_detail(request, project_id):
    try:
        project = request.user.recruiter_profile.projects.get(pk=project_id)
    except Project.DoesNotExist:
        return Response(status=404)
    if request.method == "DELETE":
        project.delete()
        return Response(status=204)
    if request.method == "PATCH":
        serializer = ProjectSerializer(project, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
    memberships = project.memberships.select_related("candidate").prefetch_related(
        "candidate__work_experiences", "candidate__resumes"
    )
    memberships = [
        item
        for item in memberships
        if _recruiter_can_access_candidate(request.user.recruiter_profile, item.candidate)
    ]
    return Response(
        {
            "project": ProjectSerializer(
                Project.objects.annotate(
                    candidate_count=Count("memberships", distinct=True),
                    search_count=Count("search", distinct=True),
                ).get(pk=project.pk)
            ).data,
            "candidates": ProjectCandidateSerializer(
                memberships, many=True, context={"request": request}
            ).data,
            "searches": SearchSerializer(project.search_set.all()[:20], many=True).data,
        }
    )


@api_view(["POST", "DELETE"])
@permission_classes([IsRecruiter])
def project_candidate(request, project_id, candidate_id=None):
    try:
        project = request.user.recruiter_profile.projects.get(pk=project_id)
    except Project.DoesNotExist:
        return Response(status=404)
    target_id = candidate_id or request.data.get("candidate_id")
    try:
        candidate = CandidateProfile.objects.get(pk=target_id)
    except (CandidateProfile.DoesNotExist, TypeError, ValueError):
        return Response(status=404)
    if not _recruiter_can_access_candidate(request.user.recruiter_profile, candidate):
        return Response(status=404)
    if request.method == "DELETE":
        deleted, _ = ProjectCandidate.objects.filter(
            project=project, candidate=candidate
        ).delete()
        return Response(status=204 if deleted else 404)
    membership, created = ProjectCandidate.objects.get_or_create(
        project=project, candidate=candidate
    )
    return Response(
        ProjectCandidateSerializer(membership, context={"request": request}).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["GET", "POST"])
@permission_classes([IsRecruiter])
def searches(request):
    recruiter = request.user.recruiter_profile
    if request.method == "GET":
        return Response(SearchSerializer(recruiter.searches.all()[:20], many=True).data)
    query = str(request.data.get("query", "")).strip()
    if not query:
        return Response({"detail": "Describe the candidate you are looking for."}, status=400)
    criteria, question = parse_search_query(query)
    search = Search.objects.create(
        recruiter=recruiter,
        project_id=request.data.get("project") or None,
        query=query,
        criteria=criteria,
        state=Search.State.NEEDS_CLARIFICATION if question else Search.State.COMPLETE,
        follow_up_question=question,
    )
    return Response(SearchSerializer(search).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsRecruiter])
def search_answer(request, search_id):
    try:
        search = request.user.recruiter_profile.searches.get(pk=search_id)
    except Search.DoesNotExist:
        return Response(status=404)
    answer = str(request.data.get("answer", "")).strip()
    if not answer:
        return Response({"detail": "Answer the clarification question to continue."}, status=400)
    search.criteria = apply_search_answer(search.criteria, answer)
    search.follow_up_question = next_search_question(search.criteria)
    search.state = (
        Search.State.NEEDS_CLARIFICATION
        if search.follow_up_question
        else Search.State.COMPLETE
    )
    search.save(update_fields=["criteria", "state", "follow_up_question", "updated_at"])
    return Response(SearchSerializer(search).data)


def _filtered_candidates(criteria, params):
    candidates = CandidateProfile.objects.select_related("user").prefetch_related(
        "work_experiences", "resumes"
    ).filter(
        profile_status=CandidateProfile.ProfileStatus.SUBMITTED,
        submission_consent_at__isnull=False,
    ).exclude(
        Q(visibility="") | Q(visibility=CandidateProfile.Visibility.NOT_LOOKING)
    )
    explicit_location = str(params.get("location") or "").strip()
    location = explicit_location or str(criteria.get("location") or "").strip()
    if location and (explicit_location or not criteria.get("remote_ok")):
        candidates = candidates.filter(location__iexact=location)
    minimum = _numeric_filter(
        params.get("min_experience") or criteria.get("min_experience"), "minimum experience"
    )
    maximum = _numeric_filter(
        params.get("max_experience") or criteria.get("max_experience"), "maximum experience"
    )
    notice = _numeric_filter(
        params.get("notice_period_days") or criteria.get("notice_period_days"),
        "notice period",
    )
    minimum_salary = _numeric_filter(params.get("min_salary_lpa"), "minimum compensation")
    salary = _numeric_filter(
        params.get("max_salary_lpa") or criteria.get("max_salary_lpa"),
        "maximum compensation",
    )
    if minimum not in (None, ""):
        candidates = candidates.filter(total_experience__gte=minimum)
    if maximum not in (None, ""):
        candidates = candidates.filter(total_experience__lte=maximum)
    if notice not in (None, ""):
        candidates = candidates.filter(notice_period_days__lte=notice)
    if minimum_salary is not None:
        candidates = candidates.filter(expected_salary_lpa__gte=minimum_salary)
    if salary not in (None, ""):
        candidates = candidates.filter(expected_salary_lpa__lte=salary)
    role = str(params.get("role") or criteria.get("role") or "").strip()
    if role:
        role = role.replace(" Engineer", "")
        candidates = candidates.filter(Q(headline__icontains=role) | Q(summary__icontains=role))
    employment_type = str(
        params.get("employment_type") or criteria.get("employment_type") or ""
    ).strip()
    if employment_type:
        candidates = candidates.filter(employment_type__iexact=employment_type)

    skills_value = params.get("skills") or params.get("skill")
    requested_skills = (
        [item.strip() for item in str(skills_value).split(",") if item.strip()]
        if skills_value
        else criteria.get("skills") or []
    )
    preference_value = params.get("work_preferences") or params.get("work_preference")
    requested_preferences = (
        [item.strip() for item in str(preference_value).split(",") if item.strip()]
        if preference_value
        else criteria.get("work_preferences") or []
    )
    candidate_list = list(candidates)
    if requested_skills:
        requested = {value.casefold() for value in requested_skills}
        candidate_list = [
            candidate
            for candidate in candidate_list
            if requested.issubset({value.casefold() for value in candidate.skills})
        ]
    if requested_preferences:
        requested = {value.casefold() for value in requested_preferences}
        candidate_list = [
            candidate
            for candidate in candidate_list
            if requested.intersection(
                {value.casefold() for value in candidate.work_preferences}
            )
        ]
    return candidate_list


def _numeric_filter(value, label):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Enter a valid number for {label}.") from exc
    if number < 0:
        raise ValueError(f"{label.title()} cannot be negative.")
    return number


def _recruiter_can_access_candidate(recruiter, candidate):
    """Apply candidate-controlled discovery rules to direct recruiter access."""
    if candidate.profile_status != CandidateProfile.ProfileStatus.SUBMITTED:
        return False
    if not candidate.submission_consent_at:
        return False
    if candidate.visibility == CandidateProfile.Visibility.NOT_LOOKING:
        return False
    if candidate.visibility == CandidateProfile.Visibility.APPROVED_RECRUITERS:
        return True
    if candidate.visibility != CandidateProfile.Visibility.MATCHING_ROLES:
        return False
    return any(
        any(item.pk == candidate.pk for item in _filtered_candidates(search.criteria, {}))
        for search in recruiter.searches.filter(state=Search.State.COMPLETE)
    )


@api_view(["GET"])
@permission_classes([IsRecruiter])
def search_results(request, search_id):
    try:
        search = request.user.recruiter_profile.searches.get(pk=search_id)
    except Search.DoesNotExist:
        return Response(status=404)
    if search.state != Search.State.COMPLETE:
        return Response({"detail": "This search needs clarification first."}, status=409)
    try:
        candidates = _filtered_candidates(search.criteria, request.query_params)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    stage_filter = str(request.query_params.get("stage", "")).strip()
    if stage_filter:
        recruiter = request.user.recruiter_profile
        if stage_filter == "viewed":
            candidates = [
                candidate
                for candidate in candidates
                if candidate.profileview_set.filter(recruiter=recruiter).exists()
            ]
        elif stage_filter == "unviewed":
            candidates = [
                candidate
                for candidate in candidates
                if not candidate.profileview_set.filter(recruiter=recruiter).exists()
            ]
        elif stage_filter in CandidateStatus.Status.values:
            candidates = [
                candidate
                for candidate in candidates
                if candidate.candidatestatus_set.filter(
                    recruiter=recruiter, status=stage_filter
                ).exists()
            ]
        else:
            return Response({"detail": "Choose a valid recruiting stage filter."}, status=400)
    data = []
    for candidate in candidates:
        score, reasons = calculate_match(candidate, search.criteria)
        data.append(
            {
                "candidate": CandidateProfileSerializer(
                    candidate, context={"request": request}
                ).data,
                "match_score": score,
                "match_reasons": reasons,
            }
        )
    data.sort(key=lambda row: row["match_score"], reverse=True)
    return Response({"search": SearchSerializer(search).data, "count": len(data), "results": data})


@api_view(["GET"])
@permission_classes([IsRecruiter])
def candidate_detail(request, candidate_id):
    try:
        candidate = CandidateProfile.objects.prefetch_related(
            "work_experiences", "resumes"
        ).get(pk=candidate_id)
    except CandidateProfile.DoesNotExist:
        return Response(status=404)
    if not _recruiter_can_access_candidate(request.user.recruiter_profile, candidate):
        return Response(status=404)
    ProfileView.objects.update_or_create(
        recruiter=request.user.recruiter_profile, candidate=candidate
    )
    return Response(CandidateProfileSerializer(candidate, context={"request": request}).data)


@api_view(["PUT", "DELETE"])
@permission_classes([IsRecruiter])
def candidate_status(request, candidate_id):
    try:
        candidate = CandidateProfile.objects.get(pk=candidate_id)
    except CandidateProfile.DoesNotExist:
        return Response(status=404)
    recruiter = request.user.recruiter_profile
    if not _recruiter_can_access_candidate(recruiter, candidate):
        return Response(status=404)
    if request.method == "DELETE":
        CandidateStatus.objects.filter(recruiter=recruiter, candidate=candidate).delete()
        return Response(status=204)
    value = request.data.get("status")
    if value not in CandidateStatus.Status.values:
        return Response({"detail": "Choose a valid recruiting stage."}, status=400)
    item, _ = CandidateStatus.objects.update_or_create(
        recruiter=recruiter,
        candidate=candidate,
        defaults={
            "status": value,
            "reason": request.data.get("reason", "")[:180],
            "note": request.data.get("note", ""),
        },
    )
    return Response({"candidate": candidate.id, "status": item.status})


@api_view(["POST"])
@permission_classes([IsRecruiter])
def candidate_compare(request):
    ids = request.data.get("candidate_ids", [])
    if not isinstance(ids, list) or not 2 <= len(ids) <= 4:
        return Response({"detail": "Choose between 2 and 4 candidates."}, status=400)
    candidates = CandidateProfile.objects.filter(id__in=ids).prefetch_related(
        "work_experiences", "resumes"
    )
    candidates = [
        candidate
        for candidate in candidates
        if _recruiter_can_access_candidate(request.user.recruiter_profile, candidate)
    ]
    return Response(
        CandidateProfileSerializer(candidates, many=True, context={"request": request}).data
    )


@api_view(["GET"])
@permission_classes([IsRecruiter])
def notifications(request):
    recruiter = request.user.recruiter_profile
    items = [
        item
        for item in recruiter.notifications.select_related("candidate")[:100]
        if _recruiter_can_access_candidate(recruiter, item.candidate)
    ][:50]
    return Response(NotificationSerializer(items, many=True).data)


@api_view(["POST"])
@permission_classes([IsRecruiter])
def notification_read(request, notification_id):
    updated = request.user.recruiter_profile.notifications.filter(pk=notification_id).update(
        is_read=True
    )
    return Response(status=204 if updated else 404)
