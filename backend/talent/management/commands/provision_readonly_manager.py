import getpass

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from talent.admin_access import configure_read_only_management_group


class Command(BaseCommand):
    help = "Create one named, non-superuser ENTER management account with view-only access."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        email = User.objects.normalize_email(options["email"]).lower()
        name = options["name"].strip()
        if not name:
            raise CommandError("A named individual is required; no account was created.")
        if User.objects.filter(username__iexact=email).exists():
            raise CommandError("An account with this email already exists; no changes were made.")

        user = User(
            username=email,
            email=email,
            first_name=name,
            is_active=True,
            is_staff=True,
            is_superuser=False,
        )
        password = getpass.getpass("Password: ")
        confirmation = getpass.getpass("Password (again): ")
        if password != confirmation:
            raise CommandError("Passwords do not match; no account was created.")
        try:
            user.full_clean(exclude=["password"])
            validate_password(password, user)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error

        group, _ = configure_read_only_management_group()
        user.set_password(password)
        user.save()
        user.groups.set([group])
        user.user_permissions.clear()
        self.stdout.write(self.style.SUCCESS("Read-only management account created."))
