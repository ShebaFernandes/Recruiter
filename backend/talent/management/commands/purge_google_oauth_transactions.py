from django.core.management.base import BaseCommand
from django.utils import timezone

from talent.models import GoogleOAuthTransaction


class Command(BaseCommand):
    help = "Delete expired OAuth state and temporary identity information without logging it."

    def handle(self, *args, **options):
        deleted, _ = GoogleOAuthTransaction.objects.filter(expires_at__lte=timezone.now()).delete()
        self.stdout.write(f"Deleted {deleted} expired OAuth transactions.")
