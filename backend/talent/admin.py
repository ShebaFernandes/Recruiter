from django import forms
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework.authtoken.models import Token

from .models import (
    CandidateProfile,
    CandidateStatus,
    CandidateUpdateNotification,
    EmployeeTransitionEnquiry,
    HiringEnquiry,
    ProfileView,
    Project,
    RecruiterProfile,
    Resume,
    Search,
    UserRole,
    WorkExperience,
)
from .throttling import LoginRateThrottle


@sensitive_post_parameters("password")
@csrf_protect
def protected_admin_login(request):
    # Reuse the public login quota; changing login URLs must not evade it.
    if request.method == "POST":
        throttle = LoginRateThrottle()
        if not throttle.allow_request(request, None):
            response = HttpResponse(
                "Too many login attempts. Please wait before trying again.",
                status=429,
                content_type="text/plain",
            )
            response["Retry-After"] = str(throttle.wait())
            return response
    return admin.site.login(request)


class SuperuserOnlyAdminMixin:
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    has_add_permission = has_view_permission
    has_change_permission = has_view_permission
    has_delete_permission = has_view_permission


class EnquiryFollowUpAdminMixin:
    @admin.display(description="Alert")
    def alert_status(self, obj):
        alert = getattr(obj, "alert", None)
        if alert is None:
            return "Not queued"
        if alert.sent_at:
            return "Sent"
        if alert.attempts:
            return "Retrying"
        return "Queued"

    def save_model(self, request, obj, form, change):
        if obj.status != "new" and obj.contacted_at is None:
            obj.contacted_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(EmployeeTransitionEnquiry)
class EmployeeTransitionEnquiryAdmin(
    EnquiryFollowUpAdminMixin, SuperuserOnlyAdminMixin, admin.ModelAdmin,
):
    list_display = [
        "created_at", "company", "full_name", "work_email", "reach_method",
        "status", "follow_up_due_at", "alert_status",
    ]
    list_filter = ["reach_method", "status", "created_at"]
    search_fields = ["company", "full_name", "work_email"]
    fields = [
        "created_at", "company", "full_name", "work_email", "role",
        "people_impacted", "last_working_day", "reach_method", "situation",
        "consent_confirmed_at", "original_filename", "download_list",
        "status", "internal_note", "follow_up_due_at", "contacted_at",
        "updated_at", "alert_status",
    ]
    readonly_fields = [
        field.name for field in EmployeeTransitionEnquiry._meta.fields
        if field.name not in {
            "employee_list", "status", "internal_note", "follow_up_due_at",
        }
    ] + ["download_list", "alert_status"]

    def get_urls(self):
        custom = [
            path(
                "<int:object_id>/list/",
                self.admin_site.admin_view(self.download_employee_list),
                name="talent_employeetransitionenquiry_list",
            ),
        ]
        return custom + super().get_urls()

    @admin.display(description="Employee list")
    def download_list(self, obj):
        if not obj.employee_list:
            return "No list uploaded"
        url = reverse("admin:talent_employeetransitionenquiry_list", args=[obj.pk])
        return format_html('<a href="{}">Download {}</a>', url, obj.original_filename)

    def download_employee_list(self, request, object_id):
        if not self.has_view_permission(request):
            raise PermissionDenied
        obj = self.get_object(request, object_id)
        if not obj or not obj.employee_list:
            raise Http404
        return FileResponse(
            obj.employee_list.open("rb"), as_attachment=True,
            filename=obj.original_filename or "employee-list",
        )

    def has_add_permission(self, request):
        return False

@admin.register(HiringEnquiry)
class HiringEnquiryAdmin(
    EnquiryFollowUpAdminMixin, SuperuserOnlyAdminMixin, admin.ModelAdmin,
):
    list_display = [
        "created_at", "kind", "company", "full_name", "work_email", "status",
        "follow_up_due_at", "alert_status",
    ]
    list_filter = ["kind", "status", "created_at"]
    search_fields = ["company", "full_name", "work_email"]
    readonly_fields = [
        "kind", "company", "full_name", "work_email", "details", "notes",
        "created_at", "updated_at", "contacted_at", "download_links", "alert_status",
    ]

    def get_urls(self):
        custom = [
            path(
                "<int:object_id>/attachment/<int:attachment_id>/",
                self.admin_site.admin_view(self.download_attachment),
                name="talent_hiringenquiry_attachment",
            ),
        ]
        return custom + super().get_urls()

    @admin.display(description="Attachments")
    def download_links(self, obj):
        attachments = list(obj.attachments.all())
        if not attachments:
            return "No attachment uploaded"
        links = [
            (
                reverse("admin:talent_hiringenquiry_attachment", args=[obj.pk, item.pk]),
                item.original_filename,
            )
            for item in attachments
        ]
        return format_html_join("", '<div><a href="{}">Download {}</a></div>', links)

    def download_attachment(self, request, object_id, attachment_id):
        if not self.has_view_permission(request):
            raise PermissionDenied
        obj = self.get_object(request, object_id)
        if not obj:
            raise Http404
        attachment = obj.attachments.filter(pk=attachment_id).first()
        if not attachment:
            raise Http404
        return FileResponse(
            attachment.file.open("rb"), as_attachment=True,
            filename=attachment.original_filename,
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyForStaffAdminMixin:
    """Allow delegated staff to view records, while reserving mutations for superusers."""

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_delete_permission(request, obj)

    def get_actions(self, request):
        return super().get_actions(request) if request.user.is_superuser else {}

    def history_view(self, request, object_id, extra_context=None):
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().history_view(request, object_id, extra_context)


class RecruiterAdminForm(forms.ModelForm):
    email = forms.EmailField(
        required=False, max_length=150, help_text="For a new recruiter account only."
    )
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Set an initial password for a new account. Never send it by email.",
    )

    class Meta:
        model = RecruiterProfile
        fields = ["user", "email", "password", "full_name", "company", "is_approved"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].required = False
        if self.instance.pk:
            self.fields["user"].disabled = True
            self.fields.pop("email")
            self.fields.pop("password")

    def clean(self):
        data = super().clean()
        user = data.get("user")
        if user:
            if hasattr(user, "candidate_profile") or (
                hasattr(user, "role_profile") and user.role_profile.role != UserRole.Role.RECRUITER
            ):
                raise forms.ValidationError("Candidate accounts cannot be converted to recruiters.")
            if not self.instance.pk and (data.get("email") or data.get("password")):
                raise forms.ValidationError("Select an existing user OR enter new account details.")
        elif not self.instance.pk:
            email = (data.get("email") or "").lower()
            password = data.get("password")
            if not email or not password:
                raise forms.ValidationError(
                    "Enter an email and password, or select an existing user."
                )
            if User.objects.filter(username__iexact=email).exists():
                raise forms.ValidationError("This account exists. Select its user instead.")
            validate_password(password, User(username=email, email=email))
            data["email"] = email
        return data


@admin.register(RecruiterProfile)
class RecruiterProfileAdmin(SuperuserOnlyAdminMixin, admin.ModelAdmin):
    form = RecruiterAdminForm
    list_display = ["full_name", "user", "is_approved", "approved_at", "approved_by"]
    list_filter = ["is_approved", "user__is_active"]
    search_fields = ["full_name", "user__email"]
    readonly_fields = ["approved_at", "approved_by"]

    def get_fields(self, request, obj=None):
        fields = ["user", "full_name", "company", "is_approved", "approved_at", "approved_by"]
        return fields if obj else ["email", "password", *fields]

    def has_delete_permission(self, request, obj=None):
        # Revoke rather than cascading away saved recruiter work.
        return False

    def save_model(self, request, obj, form, change):
        old_approval = RecruiterProfile.objects.get(pk=obj.pk).is_approved if change else False
        if not obj.user_id:
            obj.user = User.objects.create_user(
                username=form.cleaned_data["email"],
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
            )
        UserRole.objects.get_or_create(user=obj.user, defaults={"role": UserRole.Role.RECRUITER})
        if obj.is_approved and not old_approval:
            obj.approved_by = request.user
            obj.approved_at = timezone.now()
        elif not obj.is_approved:
            obj.approved_by = None
            obj.approved_at = None
            Token.objects.filter(user=obj.user).delete()
        super().save_model(request, obj, form, change)


@admin.register(UserRole)
class UserRoleAdmin(SuperuserOnlyAdminMixin, admin.ModelAdmin):
    pass


# Prevent delegated staff from acquiring approval privileges via User/Group edits.
admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class EnterUserAdmin(ReadOnlyForStaffAdminMixin, UserAdmin):
    list_display = ["username", "email", "is_active", "date_joined", "last_login"]
    list_filter = ["is_active", "date_joined"]
    search_fields = ["username", "email"]

    management_fields = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_active",
        "date_joined",
        "last_login",
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(role_profile__role=UserRole.Role.CANDIDATE)

    def get_fields(self, request, obj=None):
        if request.user.is_superuser:
            return super().get_fields(request, obj)
        return self.management_fields

    def get_fieldsets(self, request, obj=None):
        if request.user.is_superuser:
            return super().get_fieldsets(request, obj)
        return ((None, {"fields": self.management_fields}),)

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return super().get_readonly_fields(request, obj)
        return self.management_fields


@admin.register(Group)
class EnterGroupAdmin(SuperuserOnlyAdminMixin, GroupAdmin):
    pass


@admin.register(CandidateProfile)
class CandidateProfileAdmin(ReadOnlyForStaffAdminMixin, admin.ModelAdmin):
    list_display = [
        "full_name",
        "profile_status",
        "visibility",
        "email_verified_at",
        "submission_consent_at",
        "submitted_at",
        "profile_updated_at",
    ]
    list_filter = ["profile_status", "visibility"]
    search_fields = ["full_name", "email", "user__email", "headline"]


@admin.register(WorkExperience)
class WorkExperienceAdmin(ReadOnlyForStaffAdminMixin, admin.ModelAdmin):
    list_display = [
        "candidate",
        "company",
        "role",
        "date_label",
        "is_current",
        "confidence_status",
    ]
    list_filter = ["is_current", "confidence_status"]
    search_fields = ["candidate__full_name", "candidate__user__email", "company", "role"]
    management_fields = (
        "candidate",
        "company",
        "role",
        "start_date",
        "end_date",
        "is_current",
        "date_label",
        "employment_type",
        "location",
        "description",
        "confidence_status",
        "gap_reason",
    )

    def get_fields(self, request, obj=None):
        if request.user.is_superuser:
            return super().get_fields(request, obj)
        return self.management_fields


@admin.register(Resume)
class ResumeAdmin(ReadOnlyForStaffAdminMixin, admin.ModelAdmin):
    list_display = [
        "candidate",
        "original_name",
        "version",
        "processing_status",
        "scan_status",
        "uploaded_at",
        "processing_updated_at",
    ]
    list_filter = ["processing_status", "scan_status", "uploaded_at"]
    search_fields = ["candidate__full_name", "candidate__user__email", "original_name"]
    management_fields = (
        "candidate",
        "original_name",
        "version",
        "processing_status",
        "scan_status",
        "uploaded_at",
        "processing_updated_at",
    )

    def get_fields(self, request, obj=None):
        if request.user.is_superuser:
            return super().get_fields(request, obj)
        return self.management_fields


admin.site.register(
    [
        Project,
        Search,
        ProfileView,
        CandidateStatus,
        CandidateUpdateNotification,
    ]
)
