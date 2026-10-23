from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction

READ_ONLY_MANAGEMENT_GROUP_NAME = "ENTER Management Read Only"
READ_ONLY_MANAGEMENT_PERMISSIONS = frozenset(
    {
        ("auth", "view_user"),
        ("talent", "view_candidateprofile"),
        ("talent", "view_workexperience"),
        ("talent", "view_resume"),
    }
)


@transaction.atomic
def configure_read_only_management_group():
    permissions = list(
        Permission.objects.filter(
            content_type__app_label__in={
                app_label for app_label, _ in READ_ONLY_MANAGEMENT_PERMISSIONS
            },
            codename__in={codename for _, codename in READ_ONLY_MANAGEMENT_PERMISSIONS},
        ).select_related("content_type")
    )
    selected = {
        (permission.content_type.app_label, permission.codename): permission
        for permission in permissions
        if (permission.content_type.app_label, permission.codename)
        in READ_ONLY_MANAGEMENT_PERMISSIONS
    }
    missing = READ_ONLY_MANAGEMENT_PERMISSIONS - selected.keys()
    if missing:
        labels = ", ".join(f"{app}.{codename}" for app, codename in sorted(missing))
        raise ImproperlyConfigured(f"Required management permissions are missing: {labels}")

    group, created = Group.objects.get_or_create(name=READ_ONLY_MANAGEMENT_GROUP_NAME)
    group.permissions.set(selected.values())
    return group, created
