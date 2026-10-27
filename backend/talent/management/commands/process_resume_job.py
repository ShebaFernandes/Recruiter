import json
import resource
import sys

from django.conf import settings
from django.core.management.base import BaseCommand

from talent.models import ResumeProcessingJob
from talent.resume_processing import _owns_attempt, process_resume_job


def _tighten_resource_limit(kind, requested):
    """Respect a stricter hard limit inherited from the worker supervisor."""
    _, inherited_hard = resource.getrlimit(kind)
    ceiling = (requested if inherited_hard == resource.RLIM_INFINITY
               else min(requested, inherited_hard))
    resource.setrlimit(kind, (ceiling, ceiling))


class Command(BaseCommand):
    help = "Internal worker child: process one job with CPU/address-space limits."

    def add_arguments(self, parser):
        parser.add_argument("job_id", type=int)
        parser.add_argument("--attempt", type=int, required=True)
        parser.add_argument("--locked-at", required=True)

    def handle(self, *args, **options):
        cpu = settings.RESUME_PROCESS_HARD_TIMEOUT_SECONDS
        _tighten_resource_limit(resource.RLIMIT_CPU, cpu)
        if sys.platform.startswith("linux"):
            memory = settings.RESUME_PROCESS_MEMORY_MB * 1024 * 1024
            _tighten_resource_limit(resource.RLIMIT_AS, memory)
        job = ResumeProcessingJob.objects.filter(pk=options["job_id"]).first()
        if not job:
            outcome = "missing"
        elif (job.attempts != options["attempt"]
              or not job.locked_at or job.locked_at.isoformat() != options["locked_at"]
              or not _owns_attempt(job, job)):
            outcome = "superseded"
        else:
            outcome = process_resume_job(job.pk, claimed=job)
        self.stdout.write(json.dumps({"outcome": outcome}))
