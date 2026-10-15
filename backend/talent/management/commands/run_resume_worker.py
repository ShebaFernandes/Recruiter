import socket
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from talent.resume_processing import (
    acknowledge_sqs_message,
    dispatch_pending_jobs,
    next_database_job_id,
    receive_sqs_message,
)
from talent.storage_cleanup import drain_cleanup
from talent.worker_runtime import heartbeat, run_bounded_job


class Command(BaseCommand):
    help = "Process durable resume extraction jobs from PostgreSQL or SQS."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--max-jobs", type=int, default=0)

    def handle(self, *args, **options):
        processed = 0
        worker_id = socket.gethostname()
        while True:
            heartbeat(worker_id)
            drain_cleanup(limit=5)
            if settings.RESUME_QUEUE_BACKEND == "sqs":
                dispatch_pending_jobs()
                message = receive_sqs_message()
                if message:
                    heartbeat(worker_id, "processing")
                    outcome = run_bounded_job(message.job_id, message.idempotency_key)
                    # A message can arrive just before its PostgreSQL retry time.
                    # Leaving it unacknowledged lets SQS redeliver it after the
                    # visibility timeout without losing the durable job.
                    if outcome not in {"delayed", "busy", "superseded"}:
                        acknowledge_sqs_message(message)
                    processed += 1
            else:
                job_id = next_database_job_id()
                if job_id:
                    heartbeat(worker_id, "processing")
                    run_bounded_job(job_id)
                    processed += 1
                elif not options["once"]:
                    time.sleep(settings.RESUME_WORKER_POLL_SECONDS)

            if options["once"] or (options["max_jobs"] and processed >= options["max_jobs"]):
                heartbeat(worker_id, "stopped")
                break

        self.stdout.write(self.style.SUCCESS(f"Processed {processed} resume job(s)."))
