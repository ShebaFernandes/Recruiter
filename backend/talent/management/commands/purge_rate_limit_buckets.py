from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from talent.models import RateLimitBucket


class Command(BaseCommand):
    help = "Delete expired database-backed throttle buckets."

    def add_arguments(self, parser):
        parser.add_argument("--older-than-hours", type=int, default=48)

    def handle(self, *args, **options):
        hours = options["older_than_hours"]
        if hours < 1:
            raise CommandError("--older-than-hours must be at least 1")
        cutoff = timezone.now() - timedelta(hours=hours)
        deleted, _ = RateLimitBucket.objects.filter(updated_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} expired rate-limit bucket(s)."))
