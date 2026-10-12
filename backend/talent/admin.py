from django import forms
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework.authtoken.models import Token

from .models import (
    CandidateProfile,
    CandidateStatus,
    CandidateUpdateNotification,
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
class EnterUserAdmin(SuperuserOnlyAdminMixin, UserAdmin):
    pass


@admin.register(Group)
class EnterGroupAdmin(SuperuserOnlyAdminMixin, GroupAdmin):
    pass


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
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
    search_fields = ["full_name", "email", "headline"]


admin.site.register(
    [
        WorkExperience,
        Resume,
        Project,
        Search,
        ProfileView,
        CandidateStatus,
        CandidateUpdateNotification,
    ]
)
