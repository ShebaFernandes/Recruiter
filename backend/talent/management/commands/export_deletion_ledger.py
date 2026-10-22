import hashlib
import json
import os

from django.core.management.base import BaseCommand, CommandError

from talent import legal
from talent.models import DeletionRequest


class Command(BaseCommand):
    help = "Export minimal local deletion ledger to a new private file; never print its contents."

    def add_arguments(self, parser):
        parser.add_argument("destination")

    def handle(self, *args, **options):
        if not legal.enabled():
            raise CommandError("Local legal preview must be explicitly enabled.")
        entries = [
            {
                "subject_user_id": row.subject_user_id,
                "subject_joined_at": row.subject_joined_at.isoformat(),
            }
            for row in DeletionRequest.objects.exclude(account_deleted_at=None)
        ]
        raw = json.dumps(entries, sort_keys=True).encode()
        try:
            fd = os.open(options["destination"], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError as exc:
            raise CommandError(
                "Cannot create new private ledger; existing paths are not replaced."
            ) from exc
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        self.stdout.write(f"Entries: {len(entries)}; SHA256: {hashlib.sha256(raw).hexdigest()}")
