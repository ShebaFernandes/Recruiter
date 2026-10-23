import getpass

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from talent.admin_access import configure_read_only_management_group
from talent.models import UserRole


class Command(BaseCommand):
    help = "Create one named, non-superuser ENTER management account with view-only access."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument(
            "--username",
            help=(
                "Distinct Django Admin username. Defaults to the email address; use a "
                "management- prefix only with --allow-shared-inactive-candidate-email."
            ),
        )
        parser.add_argument(
            "--allow-shared-inactive-candidate-email",
            action="store_true",
            help=(
                "Allow the mailbox to be shared with exactly one existing inactive, "
                "non-staff candidate while keeping the authentication usernames distinct."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        email = User.objects.normalize_email(options["email"]).lower()
        username = (options.get("username") or email).strip().lower()
        name = options["name"].strip()
        if not name:
            raise CommandError("A named individual is required; no account was created.")
        if not username:
            raise CommandError("A username is required; no account was created.")

        shared_email_users = list(
            User.objects.filter(email__iexact=email).select_related("candidate_profile")
        )
        allow_shared_email = options["allow_shared_inactive_candidate_email"]
        if allow_shared_email and username.casefold() == email.casefold():
            raise CommandError(
                "A shared mailbox requires a distinct management username; no account was "
                "created."
            )
        if allow_shared_email and not username.startswith("management-"):
            raise CommandError(
                "A shared mailbox management username must start with 'management-'; no account "
                "was created."
            )
        if User.objects.filter(username__iexact=username).exists():
            raise CommandError(
                "An account with this username already exists; no changes were made."
            )
        if shared_email_users and not allow_shared_email:
            raise CommandError(
                "An account with this email already exists. Use a different mailbox, or the "
                "explicit shared inactive-candidate option after reviewing that identity."
            )
        if allow_shared_email:
            if len(shared_email_users) != 1:
                raise CommandError(
                    "The shared mailbox must belong to exactly one existing account; no account "
                    "was created."
                )
            candidate = shared_email_users[0]
            if (
                candidate.username.casefold() != email.casefold()
                or not hasattr(candidate, "candidate_profile")
                or candidate.candidate_profile.email.casefold() != email.casefold()
                or not hasattr(candidate, "role_profile")
                or candidate.role_profile.role != UserRole.Role.CANDIDATE
                or candidate.is_active
                or candidate.is_staff
                or candidate.is_superuser
            ):
                raise CommandError(
                    "The shared mailbox is not attached only to an inactive candidate account; "
                    "no account was created."
                )

        user = User(
            username=username,
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
