import json
import logging
import socket
import struct
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import boto3
from botocore.config import Config
from django.conf import settings
from django.core.files.base import File
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.module_loading import import_string

from .models import CandidateProfile, Resume, ResumeProcessingJob, WorkExperience
from .services import parse_date, parse_resume

logger = logging.getLogger(__name__)


class ResumeScanError(Exception):
    pass


class ResumeInfectedError(Exception):
    pass


class DevelopmentResumeScanner:
    """Format validation only. Production settings reject this backend."""

    def scan(self, file_object):
        file_object.seek(0)
        file_object.read(1)
        file_object.seek(0)
        return "clean"


class ClamAVResumeScanner:
    """Scan a private object with ClamAV's streaming protocol."""

    def scan(self, file_object):
        try:
            with socket.create_connection(
                (settings.CLAMAV_HOST, settings.CLAMAV_PORT),
                timeout=settings.RESUME_SCAN_TIMEOUT_SECONDS,
            ) as connection:
                connection.settimeout(settings.RESUME_SCAN_TIMEOUT_SECONDS)
                connection.sendall(b"zINSTREAM\0")
                while chunk := file_object.read(1024 * 64):
                    connection.sendall(struct.pack("!I", len(chunk)))
                    connection.sendall(chunk)
                connection.sendall(struct.pack("!I", 0))
                response = connection.recv(4096).decode("utf-8", errors="replace")
        except (OSError, TimeoutError) as exc:
            raise ResumeScanError("The malware scanner is temporarily unavailable.") from exc
        finally:
            file_object.seek(0)
        if " FOUND" in response:
            raise ResumeInfectedError("The uploaded file did not pass the security scan.")
        if not response.rstrip("\0\n").endswith("OK"):
            raise ResumeScanError("The malware scanner returned an invalid result.")
        return "clean"


def get_resume_scanner():
    backend = settings.RESUME_SCANNER_BACKEND
    if backend == "development":
        return DevelopmentResumeScanner()
    if backend == "clamav":
        return ClamAVResumeScanner()
    scanner_class = import_string(backend)
    return scanner_class()


def _sqs_client():
    return boto3.client(
        "sqs",
        region_name=settings.AWS_SQS_REGION_NAME,
        endpoint_url=settings.AWS_SQS_ENDPOINT_URL or None,
        config=Config(
            connect_timeout=settings.AWS_SQS_CONNECT_TIMEOUT_SECONDS,
            read_timeout=settings.AWS_SQS_READ_TIMEOUT_SECONDS,
            retries={"max_attempts": settings.AWS_SQS_MAX_ATTEMPTS, "mode": "standard"},
        ),
    )


def enqueue_resume_job(job_id, delay_seconds=0):
    job = ResumeProcessingJob.objects.get(pk=job_id)
    if settings.RESUME_QUEUE_BACKEND == "database":
        job.enqueued_at = timezone.now()
        job.save(update_fields=["enqueued_at", "updated_at"])
        Resume.objects.filter(pk=job.resume_id).update(
            processing_status=Resume.ProcessingStatus.QUEUED,
            processing_updated_at=timezone.now(),
        )
        return "database"
    response = _sqs_client().send_message(
        QueueUrl=settings.RESUME_SQS_QUEUE_URL,
        MessageBody=json.dumps({"job_id": job.pk, "idempotency_key": str(job.idempotency_key)}),
        DelaySeconds=min(max(int(delay_seconds), 0), 900),
    )
    job.queue_message_id = response["MessageId"]
    job.enqueued_at = timezone.now()
    job.save(update_fields=["queue_message_id", "enqueued_at", "updated_at"])
    Resume.objects.filter(pk=job.resume_id).update(
        processing_status=Resume.ProcessingStatus.QUEUED,
        processing_updated_at=timezone.now(),
    )
    return response["MessageId"]


def dispatch_pending_jobs(limit=100):
    stale_before = timezone.now() - timedelta(seconds=settings.RESUME_PROCESSING_TIMEOUT_SECONDS)
    stale_ids = list(
        ResumeProcessingJob.objects.filter(
            state=ResumeProcessingJob.State.PROCESSING,
            locked_at__lte=stale_before,
        ).values_list("id", flat=True)[:limit]
    )
    if stale_ids:
        ResumeProcessingJob.objects.filter(id__in=stale_ids).update(
            state=ResumeProcessingJob.State.QUEUED,
            available_at=timezone.now(),
            locked_at=None,
            enqueued_at=None,
        )
        Resume.objects.filter(processing_job__id__in=stale_ids).update(
            processing_status=Resume.ProcessingStatus.QUEUED,
            processing_updated_at=timezone.now(),
        )
    job_ids = list(
        ResumeProcessingJob.objects.filter(
            state=ResumeProcessingJob.State.QUEUED,
            enqueued_at__isnull=True,
            available_at__lte=timezone.now(),
        ).values_list("id", flat=True)[:limit]
    )
    sent = 0
    for job_id in job_ids:
        try:
            enqueue_resume_job(job_id)
            sent += 1
        except Exception:
            # The durable database record remains available for the next dispatcher run.
            continue
    return sent


def _claim_job(job_id, idempotency_key=None):
    stale_before = timezone.now() - timedelta(seconds=settings.RESUME_PROCESSING_TIMEOUT_SECONDS)
    with transaction.atomic():
        try:
            job = (
                ResumeProcessingJob.objects.select_for_update()
                .select_related("resume__candidate")
                .get(pk=job_id)
            )
        except ResumeProcessingJob.DoesNotExist:
            # An account may be deleted after SQS delivery. Treat its stale
            # message as handled so it cannot crash or poison the worker.
            return None, "missing"
        if idempotency_key and str(job.idempotency_key) != str(idempotency_key):
            return None, "invalid"
        if job.state == ResumeProcessingJob.State.COMPLETED:
            return None, "duplicate"
        if job.state == ResumeProcessingJob.State.FAILED and job.attempts >= job.max_attempts:
            return None, "failed"
        if (
            job.state == ResumeProcessingJob.State.PROCESSING
            and job.locked_at
            and job.locked_at > stale_before
        ):
            return None, "busy"
        if job.available_at > timezone.now():
            return None, "delayed"
        job.state = ResumeProcessingJob.State.PROCESSING
        job.attempts += 1
        job.locked_at = timezone.now()
        job.last_error = ""
        job.save(update_fields=["state", "attempts", "locked_at", "last_error", "updated_at"])
        resume_updates = {
            "processing_status": Resume.ProcessingStatus.PROCESSING,
            "processing_error": "",
            "processing_updated_at": timezone.now(),
        }
        if job.resume.scan_status != Resume.ScanStatus.CLEAN:
            resume_updates["scan_status"] = Resume.ScanStatus.SCANNING
        Resume.objects.filter(pk=job.resume_id).update(
            **resume_updates,
        )
        return job, "claimed"


def _promote_clean_file(resume):
    old_name = resume.file.name
    safe_name = Path(resume.original_name).name
    target = f"resumes/{resume.candidate_id}/{resume.pk}/{safe_name}"
    storage = resume.file.storage
    if old_name == target:
        return
    if not storage.exists(target):
        with resume.file.open("rb") as source:
            storage.save(target, File(source))
    resume.file.name = target
    resume.save(update_fields=["file", "processing_updated_at"])
    if storage.exists(old_name):
        storage.delete(old_name)


def _apply_extracted_resume(resume, extracted):
    profile = resume.candidate
    scalar_fields = [
        "full_name",
        "headline",
        "current_company",
        "email",
        "phone",
        "location",
        "total_experience",
        "notice_period_days",
        "current_salary_lpa",
        "expected_salary_lpa",
        "linkedin_url",
        "github_url",
        "work_preferences",
        "skills",
        "education",
        "summary",
    ]
    for field in scalar_fields:
        value = extracted.get(field)
        if value not in (None, "", [], 0):
            setattr(profile, field, value)
    profile.save()
    if extracted.get("work_experiences"):
        profile.work_experiences.all().delete()
        WorkExperience.objects.bulk_create(
            [
                WorkExperience(
                    candidate=profile,
                    company=item["company"],
                    role=item["role"],
                    start_date=parse_date(item["start_date"]),
                    end_date=parse_date(item["end_date"]) if item.get("end_date") else None,
                    description=item.get("description", ""),
                )
                for item in extracted["work_experiences"]
            ]
        )


def _retry_or_fail(job_id, message, scan_failed=False):
    with transaction.atomic():
        job = (
            ResumeProcessingJob.objects.select_for_update().select_related("resume").get(pk=job_id)
        )
        terminal = job.attempts >= job.max_attempts
        delay = min(settings.RESUME_RETRY_BASE_SECONDS * (2 ** max(job.attempts - 1, 0)), 900)
        job.state = (
            ResumeProcessingJob.State.FAILED if terminal else ResumeProcessingJob.State.QUEUED
        )
        job.available_at = timezone.now() + timedelta(seconds=delay)
        job.locked_at = None
        job.enqueued_at = None
        job.last_error = message[:255]
        job.save(
            update_fields=[
                "state",
                "available_at",
                "locked_at",
                "enqueued_at",
                "last_error",
                "updated_at",
            ]
        )
        job.resume.processing_status = (
            Resume.ProcessingStatus.FAILED if terminal else Resume.ProcessingStatus.QUEUED
        )
        if scan_failed:
            job.resume.scan_status = (
                Resume.ScanStatus.FAILED
                if terminal
                else Resume.ScanStatus.QUARANTINED
            )
        job.resume.processing_error = message[:255] if terminal else ""
        job.resume.save(
            update_fields=[
                "processing_status",
                "scan_status",
                "processing_error",
                "processing_updated_at",
            ]
        )
    if not terminal:
        try:
            enqueue_resume_job(job_id, delay)
        except Exception:
            pass
    return "failed" if terminal else "retry"


def process_resume_job(job_id, idempotency_key=None):
    job, outcome = _claim_job(job_id, idempotency_key)
    if not job:
        return outcome
    resume = Resume.objects.select_related("candidate").get(pk=job.resume_id)
    try:
        if resume.scan_status != Resume.ScanStatus.CLEAN:
            with resume.file.open("rb") as file_object:
                get_resume_scanner().scan(file_object)
            resume.scan_status = Resume.ScanStatus.CLEAN
            resume.save(update_fields=["scan_status", "processing_updated_at"])
            _promote_clean_file(resume)
            # FieldFile retains a closed handle after the scanner/promote pass.
            # Reload it so local and remote storage backends open a fresh stream.
            resume = Resume.objects.select_related("candidate").get(pk=resume.pk)
        with resume.file.open("rb") as file_object:
            extracted = parse_resume(file_object, resume.original_name)
        if not extracted.get("raw_text", "").strip():
            raise ValueError("No readable text was found in this resume.")
        with transaction.atomic():
            locked_job = ResumeProcessingJob.objects.select_for_update().get(pk=job.pk)
            if locked_job.state == ResumeProcessingJob.State.COMPLETED:
                return "duplicate"
            locked_resume = (
                Resume.objects.select_for_update().select_related("candidate").get(pk=resume.pk)
            )
            locked_resume.extracted_data = extracted
            _apply_extracted_resume(locked_resume, extracted)
            locked_resume.processing_status = Resume.ProcessingStatus.COMPLETED
            locked_resume.scan_status = Resume.ScanStatus.CLEAN
            locked_resume.processing_error = ""
            locked_resume.save(
                update_fields=[
                    "extracted_data",
                    "processing_status",
                    "scan_status",
                    "processing_error",
                    "processing_updated_at",
                ]
            )
            locked_job.state = ResumeProcessingJob.State.COMPLETED
            locked_job.completed_at = timezone.now()
            locked_job.locked_at = None
            locked_job.last_error = ""
            locked_job.save(
                update_fields=[
                    "state",
                    "completed_at",
                    "locked_at",
                    "last_error",
                    "updated_at",
                ]
            )
        if resume.version > 1:
            # Imported lazily to avoid coupling the worker module to API startup.
            from .views import _notify_recruiters_of_candidate_update

            refreshed_profile = CandidateProfile.objects.get(pk=resume.candidate_id)
            _notify_recruiters_of_candidate_update(
                refreshed_profile, change_type="resume", resume=resume
            )
        return "completed"
    except ResumeInfectedError as exc:
        with transaction.atomic():
            failed_job = ResumeProcessingJob.objects.select_for_update().get(pk=job.pk)
            failed_job.state = ResumeProcessingJob.State.FAILED
            failed_job.attempts = failed_job.max_attempts
            failed_job.locked_at = None
            failed_job.last_error = str(exc)
            failed_job.save(
                update_fields=["state", "attempts", "locked_at", "last_error", "updated_at"]
            )
            Resume.objects.filter(pk=resume.pk).update(
                processing_status=Resume.ProcessingStatus.FAILED,
                scan_status=Resume.ScanStatus.INFECTED,
                processing_error=str(exc),
                processing_updated_at=timezone.now(),
            )
        return "infected"
    except ResumeScanError:
        logger.warning("Resume job %s could not reach the configured scanner", job.pk)
        return _retry_or_fail(job.pk, "Security scanning could not be completed.", scan_failed=True)
    except Exception:
        logger.exception("Resume job %s failed without logging resume content", job.pk)
        return _retry_or_fail(job.pk, "Resume processing could not be completed.")


def next_database_job_id():
    stale_before = timezone.now() - timedelta(seconds=settings.RESUME_PROCESSING_TIMEOUT_SECONDS)
    return (
        ResumeProcessingJob.objects.filter(
            Q(state=ResumeProcessingJob.State.QUEUED, available_at__lte=timezone.now())
            | Q(state=ResumeProcessingJob.State.PROCESSING, locked_at__lte=stale_before)
        )
        .order_by("available_at", "created_at")
        .values_list("id", flat=True)
        .first()
    )


@dataclass
class QueueMessage:
    job_id: int
    idempotency_key: str
    receipt_handle: str = ""


def receive_sqs_message():
    response = _sqs_client().receive_message(
        QueueUrl=settings.RESUME_SQS_QUEUE_URL,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=settings.RESUME_SQS_WAIT_SECONDS,
        VisibilityTimeout=settings.RESUME_SQS_VISIBILITY_TIMEOUT_SECONDS,
    )
    messages = response.get("Messages", [])
    if not messages:
        return None
    message = messages[0]
    try:
        body = json.loads(message["Body"])
        return QueueMessage(
            job_id=int(body["job_id"]),
            idempotency_key=str(body["idempotency_key"]),
            receipt_handle=message["ReceiptHandle"],
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        _sqs_client().delete_message(
            QueueUrl=settings.RESUME_SQS_QUEUE_URL,
            ReceiptHandle=message["ReceiptHandle"],
        )
        return None


def acknowledge_sqs_message(message):
    _sqs_client().delete_message(
        QueueUrl=settings.RESUME_SQS_QUEUE_URL,
        ReceiptHandle=message.receipt_handle,
    )
