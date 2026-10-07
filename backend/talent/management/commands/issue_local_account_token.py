from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from talent.account_security import issue_account_token
from talent.models import AccountActionToken


class Command(BaseCommand):
    help = "Issue a one-time account token for local browser tests only."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument(
            "purpose",
            choices=[
                AccountActionToken.Purpose.VERIFY_EMAIL,
                AccountActionToken.Purpose.RESET_PASSWORD,
            ],
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Local account-token issuance is disabled outside DEBUG mode.")
        try:
            user = User.objects.get(username__iexact=options["email"])
        except User.DoesNotExist as error:
            raise CommandError("Account not found.") from error
        if (
            options["purpose"] == AccountActionToken.Purpose.VERIFY_EMAIL
            and not hasattr(user, "candidate_profile")
        ):
            raise CommandError("Email verification tokens are candidate-only.")
        self.stdout.write(issue_account_token(user, options["purpose"]))
