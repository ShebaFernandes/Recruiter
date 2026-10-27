"""Non-public operational check for a timer/monitor; no document data or object keys."""
import json
import socket
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from talent.models import FileCleanupJob, ResumeProcessingJob, WorkerHeartbeat
from talent.worker_runtime import worker_available


class Command(BaseCommand):
    help = "Check worker heartbeat, queue age, failed jobs and pending file cleanup."

    def add_arguments(self, parser):
        parser.add_argument("--local-worker", action="store_true")

    def handle(self, *args, **options):
        if options["local_worker"]:
            host = socket.gethostname()[:50]
            healthy = WorkerHeartbeat.objects.filter(
                Q(worker_id=host) | Q(worker_id__startswith=f"{host}:"),
                state__in=["idle", "processing"],
                seen_at__gte=timezone.now() - timedelta(
                    seconds=settings.RESUME_WORKER_HEALTH_SECONDS),
            ).exists()
            if not healthy:
                raise CommandError("Local worker heartbeat unavailable.")
            return
        now = timezone.now()
        threshold = now - timedelta(seconds=settings.RESUME_QUEUE_ALERT_SECONDS)
        cleanup_retry_age = now - timedelta(hours=24)
        report = {
            "worker_available": worker_available(),
            "queued": ResumeProcessingJob.objects.filter(state="queued").count(),
            "overdue": ResumeProcessingJob.objects.filter(
                state__in=["queued", "processing"], created_at__lt=threshold).count(),
            "failed": ResumeProcessingJob.objects.filter(state="failed").count(),
            "cleanup_pending": FileCleanupJob.objects.count(),
            "cleanup_overdue": FileCleanupJob.objects.filter(
                Q(available_at__lt=threshold)
                | Q(attempts__gt=0, created_at__lt=cleanup_retry_age)
            ).count(),
        }
        self.stdout.write(json.dumps(report))
        if (not report["worker_available"] or report["overdue"] or report["failed"]
                or report["cleanup_overdue"]):
            raise CommandError("Resume operations require attention; inspect counts above.")
