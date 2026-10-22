from django.core.management.base import BaseCommand, CommandError

from talent import legal


class Command(BaseCommand):
    help = "Prepare unpublished local reminder outbox. Does not send emails or delete records."

    def add_arguments(self, parser):
        parser.add_argument("--deliver-in-memory", action="store_true")

    def handle(self, *args, **options):
        if not legal.enabled():
            raise CommandError("Local legal preview must be explicitly enabled.")
        self.stdout.write(f"Queued local reminders: {legal.prepare_reminders()}; emails sent: 0")
        if options["deliver_in_memory"]:
            self.stdout.write(f"In-memory test messages: {legal.deliver_local_reminders()}")
