import time

from django.conf import settings
from django.core.management.base import BaseCommand

from talent.resume_processing import (
    acknowledge_sqs_message,
    dispatch_pending_jobs,
    next_database_job_id,
    process_resume_job,
    receive_sqs_message,
)


class Command(BaseCommand):
    help = "Process durable resume extraction jobs from PostgreSQL or SQS."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--max-jobs", type=int, default=0)

    def handle(self, *args, **options):
        processed = 0
        while True:
            if settings.RESUME_QUEUE_BACKEND == "sqs":
                dispatch_pending_jobs()
                message = receive_sqs_message()
                if message:
                    outcome = process_resume_job(message.job_id, message.idempotency_key)
                    # A message can arrive just before its PostgreSQL retry time.
                    # Leaving it unacknowledged lets SQS redeliver it after the
                    # visibility timeout without losing the durable job.
                    if outcome != "delayed":
                        acknowledge_sqs_message(message)
                    processed += 1
            else:
                job_id = next_database_job_id()
                if job_id:
                    process_resume_job(job_id)
                    processed += 1
                elif not options["once"]:
                    time.sleep(settings.RESUME_WORKER_POLL_SECONDS)

            if options["once"] or (options["max_jobs"] and processed >= options["max_jobs"]):
                break

        self.stdout.write(self.style.SUCCESS(f"Processed {processed} resume job(s)."))
