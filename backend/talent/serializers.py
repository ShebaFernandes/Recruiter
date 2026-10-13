from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import serializers

from .candidate_experience import LIST_FIELDS, MOTIVATORS, TEXT_FIELDS, proposed_fields
from .models import (
    CandidateProfile,
    CandidateUpdateNotification,
    Project,
    ProjectCandidate,
    Resume,
    Search,
    WorkExperience,
)


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    full_name = serializers.CharField(max_length=180)
    role = serializers.ChoiceField(choices=["candidate"])
    company = serializers.CharField(max_length=180, required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower()

    def validate(self, attrs):
        user = User(username=attrs["email"], email=attrs["email"])
        try:
            validate_password(attrs["password"], user)
        except ValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error
        return attrs


class WorkExperienceSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        if attrs.get("start_date") and attrs.get("end_date"):
            if attrs["end_date"] < attrs["start_date"]:
                raise serializers.ValidationError("End date must not be before start date.")
        return attrs

    class Meta:
        model = WorkExperience
        fields = [
            "id",
            "company",
            "role",
            "start_date",
            "end_date",
            "date_label",
            "description",
            "gap_reason",
        ]


class ResumeSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    can_retry = serializers.SerializerMethodField()

    class Meta:
        model = Resume
        # Parsed resume text stays server-side. The UI only needs safe metadata
        # plus the authenticated download endpoint.
        fields = [
            "id",
            "original_name",
            "version",
            "uploaded_at",
            "processing_status",
            "scan_status",
            "processing_error",
            "can_retry",
            "url",
        ]

    def get_url(self, obj):
        if (
            obj.processing_status != Resume.ProcessingStatus.COMPLETED
            or obj.scan_status != Resume.ScanStatus.CLEAN
        ):
            return None
        request = self.context.get("request")
        path = f"/api/v1/resumes/{obj.pk}/download/"
        return request.build_absolute_uri(path) if request else path

    def get_can_retry(self, obj):
        return (
            obj.processing_status == Resume.ProcessingStatus.FAILED
            and obj.scan_status != Resume.ScanStatus.INFECTED
        )


class CandidateProfileSerializer(serializers.ModelSerializer):
    work_experiences = WorkExperienceSerializer(many=True, required=False)
    latest_resume = serializers.SerializerMethodField()
    viewed = serializers.SerializerMethodField()
    stage = serializers.SerializerMethodField()
    resume_updated = serializers.SerializerMethodField()
    update_label = serializers.SerializerMethodField()
    missing_fields = serializers.SerializerMethodField()
    profile_completion = serializers.SerializerMethodField()
    submission_missing_fields = serializers.SerializerMethodField()
    can_submit = serializers.SerializerMethodField()
    discovery_status = serializers.SerializerMethodField()
    available_resume = serializers.SerializerMethodField()
    resume_review = serializers.SerializerMethodField()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if getattr(getattr(request, "user", None), "id", None) != instance.user_id:
            for field in ("career_preferences", "resume_review", "available_resume"):
                data.pop(field, None)
        return data

    def get_available_resume(self, obj):
        resume = obj.resumes.filter(processing_status="completed", scan_status="clean").first()
        return ResumeSerializer(resume, context=self.context).data if resume else None

    def get_resume_review(self, obj):
        resume = obj.resumes.first()
        if (
            resume
            and resume.processing_status == "completed"
            and resume.extracted_data.get("_needs_review")
        ):
            return {"resume_id": resume.pk, "fields": proposed_fields(resume.extracted_data)}
        return None

    def validate_career_preferences(self, value):
        if not isinstance(value, dict) or set(value) - LIST_FIELDS - TEXT_FIELDS:
            raise serializers.ValidationError("Choose valid career settings.")
        for key, item in value.items():
            if key in LIST_FIELDS:
                if (
                    not isinstance(item, list)
                    or len(item) > 100
                    or any(
                        not isinstance(text, str) or not text.strip() or len(text) > 240
                        for text in item
                    )
                ):
                    raise serializers.ValidationError("Use non-empty options up to 240 characters.")
                value[key] = list(dict.fromkeys(text.strip() for text in item))
            elif not isinstance(item, str) or len(item) > 1000:
                raise serializers.ValidationError("Keep career answers within 1,000 characters.")
        if set(value.get("motivators", [])) - MOTIVATORS:
            raise serializers.ValidationError("Choose a listed motivation.")
        if len(value.get("strongest_skills", [])) > 5:
            raise serializers.ValidationError("Choose up to five strongest skills.")
        if set(value.get("contact_preferences", [])) - {"Email", "WhatsApp", "Phone"}:
            raise serializers.ValidationError("Choose Email, WhatsApp or Phone.")
        if value.get("availability", "") not in {
            "",
            "Actively looking",
            "Open to the right opportunity",
            "Not looking right now",
        }:
            raise serializers.ValidationError("Choose a valid availability.")
        return value

    def validate(self, attrs):
        skills = attrs.get("skills", self.instance.skills if self.instance else [])
        preferences = attrs.get("career_preferences", {})
        if preferences.get("availability") == "Not looking right now":
            attrs["visibility"] = "not_looking"
        if set(preferences.get("strongest_skills", [])) - set(skills):
            raise serializers.ValidationError(
                {"career_preferences": "Strongest skills must be in your saved skills."}
            )
        return attrs

    PROFILE_FIELD_SPECS = [
        {
            "field": "headline",
            "label": "current role",
            "category": "required",
            "message": "We couldn't confidently find your current role.",
            "prompt": "What best describes your current role?",
        },
        {
            "field": "location",
            "label": "current location",
            "category": "required",
            "message": "Please confirm your current location.",
            "prompt": "Where are you currently based?",
        },
        {
            "field": "total_experience",
            "label": "total experience",
            "category": "required",
            "message": "We couldn't determine your total experience.",
            "prompt": "How many years of experience do you have?",
        },
        {
            "field": "notice_period_days",
            "label": "notice period",
            "category": "required",
            "message": "We couldn't find your notice period.",
            "prompt": "One quick thing — what's your current notice period?",
            "options": [0, 15, 30, 60, 90],
        },
        {
            "field": "skills",
            "label": "skills",
            "category": "required",
            "message": "Add a few skills that represent your strongest work.",
            "prompt": "Which skills should recruiters know you for?",
        },
        {
            "field": "work_preferences",
            "label": "preferred work setup",
            "category": "required",
            "message": "We couldn't determine your preferred work setup.",
            "prompt": "Great. What kind of work setup works for you?",
            "options": ["Flexible", "Remote", "Hybrid", "On-site"],
        },
        {
            "field": "visibility",
            "label": "profile visibility",
            "category": "required",
            "message": "Choose how recruiters can discover your profile.",
            "prompt": "How should recruiters find you?",
            "options": ["approved_recruiters", "matching_roles", "not_looking"],
        },
        {
            "field": "expected_salary_lpa",
            "label": "expected compensation",
            "category": "recommended",
            "message": "Expected compensation is missing.",
            "prompt": "What compensation range are you considering?",
        },
        {
            "field": "linkedin_url",
            "label": "LinkedIn profile",
            "category": "recommended",
            "message": "We couldn't find your LinkedIn profile.",
            "prompt": "Would you like to add your LinkedIn profile?",
        },
        {
            "field": "github_url",
            "label": "GitHub profile",
            "category": "recommended",
            "message": "We couldn't find your GitHub profile.",
            "prompt": "Would you like to add your GitHub profile?",
        },
        {
            "field": "meaningful_work",
            "label": "meaningful work",
            "category": "recommended",
            "message": "Tell recruiters about a piece of work you're proud of.",
            "prompt": "What's the most meaningful thing you've built?",
        },
        {
            "field": "work_experiences",
            "label": "work experience",
            "category": "recommended",
            "message": "We couldn't confidently build your work history.",
            "prompt": "Would you like to add your recent experience?",
        },
        {
            "field": "education",
            "label": "education",
            "category": "recommended",
            "message": "We couldn't confidently find your education.",
            "prompt": "Would you like to add your education?",
        },
    ]

    class Meta:
        model = CandidateProfile
        fields = [
            "id",
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
            "employment_type",
            "linkedin_url",
            "github_url",
            "summary",
            "meaningful_work",
            "career_preferences",
            "available_resume",
            "resume_review",
            "visibility",
            "work_preferences",
            "skills",
            "education",
            "profile_status",
            "email_verified_at",
            "submitted_at",
            "submission_consent_at",
            "submission_consent_version",
            "profile_updated_at",
            "work_experiences",
            "latest_resume",
            "viewed",
            "stage",
            "resume_updated",
            "update_label",
            "missing_fields",
            "profile_completion",
            "submission_missing_fields",
            "can_submit",
            "discovery_status",
        ]
        read_only_fields = [
            "id",
            "profile_updated_at",
            "viewed",
            "stage",
            "resume_updated",
            "update_label",
            "missing_fields",
            "profile_completion",
            "profile_status",
            "email_verified_at",
            "submitted_at",
            "submission_consent_at",
            "submission_consent_version",
            "submission_missing_fields",
            "can_submit",
            "discovery_status",
        ]

    def validate_work_preferences(self, value):
        allowed = {"Flexible", "Remote", "Hybrid", "On-site"}
        if not isinstance(value, list) or any(item not in allowed for item in value):
            raise serializers.ValidationError("Choose valid work preferences.")
        return list(dict.fromkeys(value))

    def validate_skills(self, value):
        if (
            not isinstance(value, list)
            or len(value) > 100
            or any(
                not isinstance(item, str) or not item.strip() or len(item) > 240 for item in value
            )
        ):
            raise serializers.ValidationError("Use a list of non-empty skill names.")
        return list(dict.fromkeys(item.strip() for item in value))

    def validate_education(self, value):
        if (
            not isinstance(value, list)
            or len(value) > 50
            or any(
                not isinstance(item, str) or not item.strip() or len(item) > 1000 for item in value
            )
        ):
            raise serializers.ValidationError("Use a list of education entries.")
        return list(dict.fromkeys(item.strip() for item in value))

    def _field_missing(self, obj, field):
        if field == "work_experiences":
            return not obj.work_experiences.exists()
        value = getattr(obj, field)
        if field == "total_experience":
            return value is None or float(value) <= 0
        return value in (None, "", [])

    def get_missing_fields(self, obj):
        return [
            spec for spec in self.PROFILE_FIELD_SPECS if self._field_missing(obj, spec["field"])
        ]

    def get_profile_completion(self, obj):
        relevant = [spec for spec in self.PROFILE_FIELD_SPECS if spec["category"] != "optional"]
        missing = [spec for spec in relevant if self._field_missing(obj, spec["field"])]
        completed = len(relevant) - len(missing)
        return {
            "percent": round((completed / len(relevant)) * 100),
            "remaining": len(missing),
            "required_missing": sum(spec["category"] == "required" for spec in missing),
            "recommended_missing": sum(spec["category"] == "recommended" for spec in missing),
        }

    def _submission_missing(self, obj):
        missing = [
            spec
            for spec in self.PROFILE_FIELD_SPECS
            if spec["category"] == "required" and self._field_missing(obj, spec["field"])
        ]
        if not obj.resumes.filter(
            processing_status=Resume.ProcessingStatus.COMPLETED,
            scan_status=Resume.ScanStatus.CLEAN,
        ).exists():
            missing.insert(
                0,
                {
                    "field": "resume",
                    "label": "resume",
                    "category": "required",
                    "message": "Upload your resume before submitting.",
                    "prompt": "Upload your resume to build your profile.",
                },
            )
        return missing

    def get_submission_missing_fields(self, obj):
        return self._submission_missing(obj)

    def get_can_submit(self, obj):
        return not self._submission_missing(obj)

    def get_discovery_status(self, obj):
        if obj.profile_status == CandidateProfile.ProfileStatus.DRAFT:
            return "draft"
        if obj.visibility == CandidateProfile.Visibility.NOT_LOOKING:
            return "not_looking"
        return "submitted"

    def get_latest_resume(self, obj):
        request = self.context.get("request")
        if getattr(getattr(request, "user", None), "recruiter_profile", None):
            resume = obj.resumes.filter(
                processing_status=Resume.ProcessingStatus.COMPLETED,
                scan_status=Resume.ScanStatus.CLEAN,
            ).first()
        else:
            resume = obj.resumes.first()
        return ResumeSerializer(resume, context=self.context).data if resume else None

    def _recruiter(self):
        request = self.context.get("request")
        return getattr(getattr(request, "user", None), "recruiter_profile", None)

    def get_viewed(self, obj):
        recruiter = self._recruiter()
        return bool(recruiter and obj.profileview_set.filter(recruiter=recruiter).exists())

    def get_stage(self, obj):
        recruiter = self._recruiter()
        status = obj.candidatestatus_set.filter(recruiter=recruiter).first() if recruiter else None
        return status.status if status else ""

    def get_resume_updated(self, obj):
        recruiter = self._recruiter()
        return bool(
            recruiter
            and obj.candidateupdatenotification_set.filter(
                recruiter=recruiter, is_read=False
            ).exists()
        )

    def get_update_label(self, obj):
        recruiter = self._recruiter()
        if not recruiter:
            return ""
        notification = (
            obj.candidateupdatenotification_set.filter(recruiter=recruiter, is_read=False)
            .order_by("-created_at")
            .first()
        )
        return notification.message if notification else ""

    def update(self, instance, validated_data):
        if "career_preferences" in validated_data:
            validated_data["career_preferences"] = {
                **instance.career_preferences,
                **validated_data["career_preferences"],
            }
        if "skills" in validated_data and "strongest_skills" in instance.career_preferences:
            preferences = validated_data.setdefault(
                "career_preferences", dict(instance.career_preferences)
            )
            preferences["strongest_skills"] = [
                skill
                for skill in preferences.get("strongest_skills", [])
                if skill in validated_data["skills"]
            ]
        experiences = validated_data.pop("work_experiences", None)
        instance = super().update(instance, validated_data)
        if experiences is not None:
            instance.work_experiences.all().delete()
            WorkExperience.objects.bulk_create(
                [WorkExperience(candidate=instance, **item) for item in experiences]
            )
        if (
            instance.profile_status == CandidateProfile.ProfileStatus.SUBMITTED
            and self._submission_missing(instance)
        ):
            instance.profile_status = CandidateProfile.ProfileStatus.DRAFT
            instance.submitted_at = None
            instance.save(update_fields=["profile_status", "submitted_at", "profile_updated_at"])
        return instance


class CandidateResultSerializer(serializers.Serializer):
    candidate = CandidateProfileSerializer()
    match_score = serializers.IntegerField()
    match_reasons = serializers.ListField(child=serializers.CharField())


class ProjectSerializer(serializers.ModelSerializer):
    candidate_count = serializers.IntegerField(read_only=True, default=0)
    search_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "candidate_count",
            "search_count",
            "created_at",
        ]
        read_only_fields = ["id", "candidate_count", "search_count", "created_at"]


class ProjectCandidateSerializer(serializers.ModelSerializer):
    candidate = CandidateProfileSerializer(read_only=True)

    class Meta:
        model = ProjectCandidate
        fields = ["id", "candidate", "added_at"]
        read_only_fields = fields


class SearchSerializer(serializers.ModelSerializer):
    criteria = serializers.SerializerMethodField()

    def get_criteria(self, obj):
        from .search_grounding import ground_saved_search

        return ground_saved_search(obj)[0]

    def to_representation(self, instance):
        from .search_grounding import ground_saved_search

        data = super().to_representation(instance)
        _, clarification = ground_saved_search(instance)
        if clarification and instance.state == Search.State.COMPLETE:
            data.update(
                state=Search.State.NEEDS_CLARIFICATION,
                follow_up_question=clarification,
                follow_up_options=["Let me type it"],
            )
        return data

    project_name = serializers.CharField(source="project.name", read_only=True, default="")

    class Meta:
        model = Search
        fields = [
            "id",
            "project",
            "project_name",
            "query",
            "criteria",
            "state",
            "follow_up_question",
            "follow_up_options",
            "understanding_source",
            "understanding_model",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "criteria",
            "state",
            "follow_up_question",
            "project_name",
            "follow_up_options",
            "understanding_source",
            "understanding_model",
            "created_at",
            "updated_at",
        ]


class NotificationSerializer(serializers.ModelSerializer):
    candidate_name = serializers.CharField(source="candidate.full_name", read_only=True)

    class Meta:
        model = CandidateUpdateNotification
        fields = [
            "id",
            "candidate",
            "candidate_name",
            "change_type",
            "message",
            "is_read",
            "created_at",
        ]
        read_only_fields = fields
