from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib.auth.models import Group, Permission, User
from django.core.management import call_command
from django.test import Client, RequestFactory
from django.utils import timezone
from talent.admin_access import (
    READ_ONLY_MANAGEMENT_GROUP_NAME,
    READ_ONLY_MANAGEMENT_PERMISSIONS,
)
from talent.models import CandidateProfile, Resume, UserRole, WorkExperience

pytestmark = pytest.mark.django_db
PASSWORD = "Read-only-manager-password-123!"


def permission_labels(group):
    return {
        (permission.content_type.app_label, permission.codename)
        for permission in group.permissions.select_related("content_type")
    }


def create_manager():
    call_command("setup_readonly_management_group")
    manager = User.objects.create_user(
        "manager@enter.example",
        email="manager@enter.example",
        password=PASSWORD,
        is_active=True,
        is_staff=True,
    )
    manager.groups.add(Group.objects.get(name=READ_ONLY_MANAGEMENT_GROUP_NAME))
    return manager


def create_candidate(email="candidate@example.com"):
    user = User.objects.create_user(email, email=email, password=PASSWORD, is_active=True)
    UserRole.objects.create(user=user, role=UserRole.Role.CANDIDATE)
    profile = CandidateProfile.objects.create(
        user=user,
        full_name="Candidate Example",
        email=email,
        email_verified_at=timezone.now(),
    )
    experience = WorkExperience.objects.create(
        candidate=profile,
        company="Example Company",
        role="Engineer",
        date_label="2020 - Present",
        is_current=True,
        source_evidence="Private resume evidence must not appear in management admin.",
    )
    resume = Resume.objects.create(
        candidate=profile,
        file="quarantine/private-storage-key.pdf",
        original_name="candidate-resume.pdf",
        processing_status=Resume.ProcessingStatus.COMPLETED,
        scan_status=Resume.ScanStatus.CLEAN,
        extracted_data={"private": "resume contents"},
    )
    return user, profile, experience, resume


def use_plain_static_storage(settings):
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


def test_group_command_reconciles_exact_view_permissions():
    group = Group.objects.create(name=READ_ONLY_MANAGEMENT_GROUP_NAME)
    group.permissions.add(Permission.objects.get(codename="add_candidateprofile"))

    call_command("setup_readonly_management_group")

    group.refresh_from_db()
    assert permission_labels(group) == READ_ONLY_MANAGEMENT_PERMISSIONS
    assert not any(
        codename.startswith(("add_", "change_", "delete_"))
        for _, codename in permission_labels(group)
    )


def test_provision_command_creates_named_non_superuser_with_no_direct_permissions():
    with patch(
        "talent.management.commands.provision_readonly_manager.getpass.getpass",
        side_effect=[PASSWORD, PASSWORD],
    ):
        call_command(
            "provision_readonly_manager",
            email="named.manager@enter.example",
            name="Named Manager",
        )

    user = User.objects.get(username="named.manager@enter.example")
    assert user.is_active and user.is_staff and not user.is_superuser
    assert user.first_name == "Named Manager"
    assert not user.user_permissions.exists()
    assert list(user.groups.values_list("name", flat=True)) == [READ_ONLY_MANAGEMENT_GROUP_NAME]
    assert permission_labels(user.groups.get()) == READ_ONLY_MANAGEMENT_PERMISSIONS


def test_management_admin_is_view_only_and_never_links_private_resume(settings):
    use_plain_static_storage(settings)
    manager = create_manager()
    candidate_user, profile, experience, resume = create_candidate()
    client = Client()
    client.force_login(manager)

    pages = [
        "/admin/auth/user/",
        f"/admin/auth/user/{candidate_user.pk}/change/",
        "/admin/talent/candidateprofile/",
        f"/admin/talent/candidateprofile/{profile.pk}/change/",
        "/admin/talent/workexperience/",
        f"/admin/talent/workexperience/{experience.pk}/change/",
        "/admin/talent/resume/",
        f"/admin/talent/resume/{resume.pk}/change/",
    ]
    for page in pages:
        assert client.get(page).status_code == 200

    user_page = client.get(f"/admin/auth/user/{candidate_user.pk}/change/").content.decode()
    for sensitive_field in (
        "field-password",
        "field-is_staff",
        "field-is_superuser",
        "field-groups",
        "field-user_permissions",
    ):
        assert sensitive_field not in user_page
    assert client.get("/admin/auth/user/add/").status_code == 403
    assert client.post(
        f"/admin/auth/user/{candidate_user.pk}/change/", {"_save": "Save"}
    ).status_code == 403
    assert client.post(f"/admin/auth/user/{candidate_user.pk}/delete/").status_code == 403
    assert client.get(f"/admin/auth/user/{candidate_user.pk}/history/").status_code == 403

    resume_page = client.get(f"/admin/talent/resume/{resume.pk}/change/").content.decode()
    assert "candidate-resume.pdf" in resume_page
    assert "private-storage-key.pdf" not in resume_page
    assert "resume contents" not in resume_page
    assert "href=\"/media/" not in resume_page
    experience_page = client.get(
        f"/admin/talent/workexperience/{experience.pk}/change/"
    ).content.decode()
    assert "Private resume evidence" not in experience_page

    for model_path, instance in [
        ("candidateprofile", profile),
        ("workexperience", experience),
        ("resume", resume),
    ]:
        assert client.get(f"/admin/talent/{model_path}/add/").status_code == 403
        assert client.post(
            f"/admin/talent/{model_path}/{instance.pk}/change/", {"_save": "Save"}
        ).status_code == 403
        assert client.post(f"/admin/talent/{model_path}/{instance.pk}/delete/").status_code == 403
        assert client.get(
            f"/admin/talent/{model_path}/{instance.pk}/history/"
        ).status_code == 403
        assert client.post(
            f"/admin/talent/{model_path}/",
            {"action": "delete_selected", "_selected_action": instance.pk},
        ).status_code == 200
        assert type(instance).objects.filter(pk=instance.pk).exists()

    request = RequestFactory().get("/admin/")
    request.user = manager
    for model in (User, CandidateProfile, WorkExperience, Resume):
        assert admin.site._registry[model].get_actions(request) == {}


def test_management_search_filters_and_restricted_models(settings):
    use_plain_static_storage(settings)
    manager = create_manager()
    create_candidate("searchable@example.com")
    client = Client()
    client.force_login(manager)

    assert client.get("/admin/talent/candidateprofile/?q=searchable@example.com").status_code == 200
    assert (
        client.get("/admin/talent/candidateprofile/?profile_status__exact=draft").status_code
        == 200
    )
    assert client.get("/admin/auth/user/?q=searchable@example.com").status_code == 200
    for path in ("auth/group/", "talent/recruiterprofile/", "talent/userrole/"):
        assert client.get(f"/admin/{path}").status_code == 403


def test_ordinary_candidate_cannot_enter_admin_or_see_another_candidate(settings):
    use_plain_static_storage(settings)
    first_user, first_profile, _, _ = create_candidate("first@example.com")
    second_user, second_profile, _, _ = create_candidate("second@example.com")
    client = Client()
    client.force_login(first_user)

    response = client.get("/admin/")
    assert response.status_code == 302
    assert response.url.startswith("/admin/login/")
    assert first_profile.user_id != second_profile.user_id
    assert not first_user.is_staff and not second_user.is_staff
