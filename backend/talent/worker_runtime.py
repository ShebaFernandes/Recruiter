"""Run untrusted parsing in a disposable process, never in the supervisor."""
import json
import logging
import os
import resource
import subprocess
import sys
from datetime import timedelta
from urllib.parse import quote, urlsplit, urlunsplit

from django.conf import settings
from django.utils import timezone

from .models import ResumeProcessingJob, WorkerHeartbeat
from .resume_processing import _claim_job, _retry_or_fail

logger = logging.getLogger(__name__)


def _limit_child_resources():
    # Applied after fork and before Django/PDF libraries start in the child.
    memory = settings.RESUME_WORKER_CHILD_MEMORY_MB * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    cpu = max(10, settings.RESUME_PROCESS_HARD_TIMEOUT_SECONDS - 5)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))


def heartbeat(worker_id, state="idle"):
    WorkerHeartbeat.objects.update_or_create(
        worker_id=worker_id, defaults={"seen_at": timezone.now(), "state": state}
    )


def worker_available():
    return WorkerHeartbeat.objects.filter(
        seen_at__gte=timezone.now() - timedelta(seconds=settings.RESUME_WORKER_HEALTH_SECONDS),
        state__in=["idle", "processing"],
    ).exists()


def run_bounded_job(job_id, idempotency_key=None):
    claimed, outcome = _claim_job(job_id, idempotency_key)
    if not claimed:
        return outcome
    command = [sys.executable, str(settings.BASE_DIR / "manage.py"),
               "process_resume_job", str(job_id), "--attempt", str(claimed.attempts),
               "--locked-at", claimed.locked_at.isoformat()]
    environment = dict(os.environ)
    # Tests and isolated staging may override the connection's database name. The child
    # must NEVER fall back to the parent's development database URL in that case.
    database = settings.DATABASES["default"]
    database_url = urlsplit(environment.get("DATABASE_URL", "postgresql://"))
    credentials = quote(str(database.get("USER", "")), safe="")
    credentials += ":" + quote(str(database.get("PASSWORD", "")), safe="")
    host = str(database.get("HOST") or "localhost")
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = str(database.get("PORT") or 5432)
    environment["DATABASE_URL"] = urlunsplit(database_url._replace(
        scheme="postgresql", netloc=f"{credentials}@{host}:{port}",
        path="/" + quote(str(database["NAME"]), safe=""),
    ))
    environment["MEDIA_ROOT"] = str(settings.MEDIA_ROOT)
    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=True,
            env=environment,
            timeout=settings.RESUME_PROCESS_HARD_TIMEOUT_SECONDS,
            preexec_fn=_limit_child_resources if sys.platform.startswith('linux') else None,
        )
        if sys.platform.startswith('linux'):
            peak_kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
            logger.info('resume_child_peak_kb job_id=%s peak_kb=%s', job_id, peak_kb)
        return json.loads(result.stdout.strip().splitlines()[-1])["outcome"]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError) as error:
        # No stdout/stderr here: parser diagnostics may contain document contents.
        logger.warning("resume_child_failed job_id=%s", job_id)
        job = ResumeProcessingJob.objects.filter(pk=job_id).first()
        if not job:
            return "missing"
        if job.state == "completed":
            return "duplicate"
        if job.state == "processing":
            message = (
                "The processing worker could not start. Your file is saved; please retry."
                if isinstance(error, OSError)
                else "Processing could not finish safely. Your file is saved; please retry."
            )
            if isinstance(error, subprocess.TimeoutExpired):
                message = "Processing exceeded its safe resource limit."
            return _retry_or_fail(
                job_id, message, claimed=claimed,
            )
        # Startup failures leave the message outstanding for redelivery.
        return "busy"
