"""Transactional deletion outbox. Failed private-object deletions remain retryable."""
import logging
import uuid
from datetime import timedelta
from pathlib import Path

from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from .models import CandidatePhoto, FileCleanupJob, Resume

logger = logging.getLogger(__name__)


def schedule_cleanup(name):
    if name:
        FileCleanupJob.objects.update_or_create(
            name=name, defaults={"available_at": timezone.now()},
        )


def store_private_upload(content, prefix, filename):
    """Journal the random key BEFORE storage I/O, outside the profile transaction.

    A crash after upload or a later DB rollback leaves a durable cleanup job.
    Live references protect successful uploads when the job is examined.
    """
    name = f"{prefix}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
    FileCleanupJob.objects.create(
        name=name, available_at=timezone.now() + timedelta(days=1),
    )
    saved = default_storage.save(name, content)
    if saved != name:
        # UUID paths should never collide; retain any unexpected backend-renamed key too.
        FileCleanupJob.objects.get_or_create(
            name=saved, defaults={"available_at": timezone.now() + timedelta(days=1)},
        )
    return saved


def drain_cleanup(limit=20):
    completed = 0
    for _ in range(limit):
        with transaction.atomic():
            job = (FileCleanupJob.objects.select_for_update(skip_locked=True)
                   .filter(available_at__lte=timezone.now()).order_by("available_at").first())
            if not job:
                break
            # Never remove an object still referenced by a live profile/resume.
            if (Resume.objects.filter(file=job.name).exists()
                    or CandidatePhoto.objects.filter(file=job.name).exists()):
                job.delete()
                continue
            try:
                # Delete is idempotent for both S3 and local storage.
                default_storage.delete(job.name)
            except Exception:
                job.attempts += 1
                job.available_at = timezone.now() + timedelta(
                    seconds=min(30 * 2 ** min(job.attempts, 10), 86400)
                )
                job.save(update_fields=["attempts", "available_at"])
                logger.warning("private_file_cleanup_failed job_id=%s", job.pk)
            else:
                job.delete()
                completed += 1
    return completed
