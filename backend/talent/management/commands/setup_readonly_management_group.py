from django.core.management.base import BaseCommand, CommandError

from talent.admin_access import (
    READ_ONLY_MANAGEMENT_GROUP_NAME,
    configure_read_only_management_group,
)


class Command(BaseCommand):
    help = "Create or reconcile the exact view-only permission group for ENTER management."

    def handle(self, *args, **options):
        try:
            group, created = configure_read_only_management_group()
        except Exception as error:
            raise CommandError(str(error)) from error
        state = "created" if created else "reconciled"
        self.stdout.write(self.style.SUCCESS(f"{READ_ONLY_MANAGEMENT_GROUP_NAME}: {state}"))
        self.stdout.write(
            "Permissions: auth.view_user, talent.view_candidateprofile, "
            "talent.view_workexperience, talent.view_resume"
        )
