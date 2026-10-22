from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from talent import legal
from talent.models import DeletionRequest


class Command(BaseCommand):
    help = "Verify local deletion completion; never delete records or storage objects."

    def handle(self, *args, **options):
        if not legal.enabled() or not settings.DEBUG or settings.APP_ENV not in {"local", "test"}:
            raise CommandError("Requires explicit local/test legal preview.")
        verified = pending = failed = 0
        for row in DeletionRequest.objects.filter(
            account_deleted_at__isnull=False,
            storage_cleanup_verified_at=None,
        ).iterator():
            try:
                if legal.verify_active_file_cleanup(row):
                    verified += 1
                else:
                    pending += 1
            except Exception:
                # Storage exceptions may contain private object keys. Report counts only.
                failed += 1
        self.stdout.write(
            f"Verified: {verified}; pending: {pending}; failed: {failed}. "
            "Current objects only; not historical backup/version erasure. "
            "Acknowledgement deadlines are provisional weekdays only."
        )
        if pending or failed:
            raise CommandError(
                "Deletion completion remains unverified; no additional data deleted."
            )
