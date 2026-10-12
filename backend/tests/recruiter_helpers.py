"""Test-only provisioning through the real superuser admin form, never signup."""

from types import SimpleNamespace

from django.contrib import admin
from django.contrib.auth.models import User
from talent.admin import RecruiterAdminForm
from talent.models import RecruiterProfile


def provision_recruiter(client, data, format="json", **headers):
    administrator, _ = User.objects.get_or_create(
        username="test-provisioning-admin", defaults={"is_staff": True, "is_superuser": True}
    )
    form = RecruiterAdminForm(data={**data, "is_approved": True})
    assert form.is_valid(), form.errors
    admin.site._registry[RecruiterProfile].save_model(
        SimpleNamespace(user=administrator), form.save(commit=False), form, False
    )
    return client.post(
        "/api/v1/auth/login/",
        {"email": data["email"], "password": data["password"]},
        format=format,
        **headers,
    )
