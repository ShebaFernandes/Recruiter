from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from talent import legal


class Command(BaseCommand):
    help = "Prepare the durable retention-reminder outbox and optionally deliver it."

    def add_arguments(self, parser):
        parser.add_argument("--deliver-in-memory", action="store_true")
        parser.add_argument("--deliver", action="store_true")
        parser.add_argument("--start-existing-transition", action="store_true")
        parser.add_argument("--confirm", default="")

    def handle(self, *args, **options):
        if not legal.enabled():
            raise CommandError("The legal workflow must be explicitly enabled.")
        transition_count = 0
        if options["start_existing_transition"]:
            if options["confirm"] != "START-30-DAY-TRANSITION":
                raise CommandError(
                    "Starting existing-account transitions requires exact confirmation."
                )
            transition_count = legal.start_existing_account_transitions()
        queued = legal.prepare_reminders()
        self.stdout.write(
            f"Queued inactivity reminders: {queued}; transition reminders: {transition_count}."
        )
        if options["deliver_in_memory"]:
            self.stdout.write(f"In-memory test messages: {legal.deliver_local_reminders()}")
        if options["deliver"]:
            if settings.LEGAL_WORKFLOW_PREVIEW:
                raise CommandError("Use --deliver-in-memory for unpublished preview.")
            sent, failed = legal.deliver_reminders()
            self.stdout.write(f"Delivered: {sent}; failed: {failed}.")
            if failed:
                raise CommandError("One or more reminders remain pending after delivery failure.")
