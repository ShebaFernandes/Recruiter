"""Fail-closed local recovery quarantine; never unblocks traffic or removes S3 data."""

import hashlib
import json
import stat
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from talent.legal import reconcile_deleted_subjects


class Command(BaseCommand):
    help = "Quarantine previously deleted users in a LOCAL ISOLATED restore from a private ledger."

    def add_arguments(self, parser):
        parser.add_argument("manifest")
        parser.add_argument("--sha256", required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        if (
            not settings.DEBUG
            or settings.APP_ENV not in {"test", "local"}
            or not str(db["NAME"]).startswith("enter_restore_")
            or db.get("HOST") not in {"127.0.0.1", "localhost"}
        ):
            raise CommandError(
                "Requires local isolated enter_restore_* database; live use refused."
            )
        if options["apply"]:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database()")
                if cursor.fetchone()[0] != db["NAME"]:
                    raise CommandError("Actual database differs from isolated target.")
            # Commit quarantine BEFORE validating the ledger: invalid evidence never leaves
            # restored identities active. This command never re-enables any account.
            quarantine_restore()
        path = Path(options["manifest"])
        if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise CommandError("Ledger must be a regular private 0600 file, not a symlink.")
        try:
            raw = path.read_bytes()
        except OSError:
            raise CommandError(
                "Cannot read private deletion ledger; recovery remains blocked."
            ) from None
        if hashlib.sha256(raw).hexdigest() != options["sha256"]:
            raise CommandError("Independently recorded ledger checksum mismatch.")
        try:
            entries = json.loads(raw)
            if not isinstance(entries, list):
                raise ValueError
            for item in entries:
                if (
                    set(item) != {"subject_user_id", "subject_joined_at"}
                    or type(item["subject_user_id"]) is not int
                    or not isinstance(item["subject_joined_at"], str)
                ):
                    raise ValueError
                stamp = parse_datetime(item["subject_joined_at"])
                if item["subject_user_id"] < 1 or stamp is None or timezone.is_naive(stamp):
                    raise ValueError
        except (ValueError, TypeError):
            raise CommandError("Invalid deletion ledger schema.") from None
        if not options["apply"]:
            self.stdout.write(f"Dry run: {len(entries)} deletion entries. No changes.")
            return
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            if cursor.fetchone()[0] != db["NAME"]:
                raise CommandError(
                    "Actual database differs from isolated target; refusing changes."
                )
        count = reconcile_deleted_subjects(entries)
        self.stdout.write(
            f"Ledger reconciliation succeeded for {count} deleted identities. "
            "ALL restored accounts remain disabled and HTTP access remains blocked; "
            "permanent erasure and object-version reconciliation require separate review."
        )


@transaction.atomic
def quarantine_restore():
    from django.contrib.auth.models import User
    from django.contrib.sessions.models import Session
    from rest_framework.authtoken.models import Token

    from talent.models import AccountActionToken, CandidateProfile

    User.objects.update(is_active=False)
    Token.objects.all().delete()
    AccountActionToken.objects.all().delete()
    Session.objects.all().delete()
    CandidateProfile.objects.update(
        profile_status=CandidateProfile.ProfileStatus.DRAFT,
        visibility=CandidateProfile.Visibility.NOT_LOOKING,
        submission_consent_at=None,
        submission_consent_version="",
    )
