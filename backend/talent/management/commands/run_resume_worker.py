import logging
import os
import socket
import time
import uuid

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import DatabaseError, close_old_connections

from talent.resume_processing import (
    acknowledge_sqs_message,
    dispatch_pending_jobs,
    next_database_job_id,
    receive_sqs_message,
)
from talent.storage_cleanup import drain_cleanup
from talent.worker_runtime import heartbeat, run_bounded_job

logger = logging.getLogger(__name__)
RECOVERABLE = (DatabaseError, OSError, BotoCoreError, ClientError)


class Command(BaseCommand):
    help = "Process durable resume extraction jobs from PostgreSQL or SQS."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--max-jobs", type=int, default=0)

    def handle(self, *args, **options):
        processed = 0
        failures = 0
        worker_id = f"{socket.gethostname()[:50]}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        try:
            while True:
                try:
                    close_old_connections()
                    heartbeat(worker_id)
                    drain_cleanup(limit=5)
                    if settings.RESUME_QUEUE_BACKEND == "sqs":
                        dispatch_pending_jobs()
                        message = receive_sqs_message()
                        if message:
                            heartbeat(worker_id, "processing")
                            outcome = run_bounded_job(message.job_id, message.idempotency_key)
                            # A live lease or future retry remains available for redelivery.
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
                    failures = 0
                except RECOVERABLE as error:
                    # Never include exception text, file paths or provider responses.
                    failures += 1
                    logger.warning("resume_worker_unavailable category=%s", type(error).__name__)
                    close_old_connections()
                    try:
                        heartbeat(worker_id, "unavailable")
                    except DatabaseError:
                        pass
                    if options["once"]:
                        raise
                    time.sleep(min(30, 2 ** min(failures, 5)))
                if options["once"] or (options["max_jobs"] and processed >= options["max_jobs"]):
                    break
        finally:
            try:
                heartbeat(worker_id, "stopped")
            except DatabaseError:
                pass
        self.stdout.write(self.style.SUCCESS(f"Processed {processed} resume job(s)."))
