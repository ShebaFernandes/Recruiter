"""Process durable alerts for new hiring and employee-transition requests."""

import time

from django.core.management.base import BaseCommand

from talent.enquiry_notifications import process_pending_notifications


class Command(BaseCommand):
    help = "Send internal enquiry alerts, retrying failed deliveries."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process one batch and exit")
        parser.add_argument(
            "--interval", type=int, default=10, help="Idle poll interval in seconds",
        )

    def handle(self, *args, **options):
        interval = options["interval"]
        if interval < 1:
            raise ValueError("The poll interval must be at least one second.")
        while True:
            sent, failed = process_pending_notifications()
            if options["once"]:
                self.stdout.write(f"Sent {sent} alert(s); {failed} failed and will retry.")
                return
            if sent + failed == 0:
                try:
                    time.sleep(interval)
                except KeyboardInterrupt:
                    return
