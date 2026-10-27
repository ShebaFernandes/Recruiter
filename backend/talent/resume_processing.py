import json
import logging
import socket
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import boto3
from botocore.config import Config
from django.conf import settings
from django.core.files.base import File
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.module_loading import import_string

from .candidate_experience import (
    comparable,
    pending_fields,
    profile_values,
    proposed_fields,
    resume_identity_issue,
)
from .employment_reconciliation import (
    archive_omitted_employment,
    complete_employment_history,
    reconcile_employment,
    row_equivalent,
    trusted_rows,
)
from .models import (
    CandidateProfile,
    FileCleanupJob,
    RateLimitBucket,
    Resume,
    ResumeAIUsage,
    ResumeProcessingJob,
)
from .resume_understanding import understand_resume
from .services import parse_resume
from .storage_cleanup import schedule_cleanup

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
        if response.rstrip("\0\n") != "stream: OK":
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
    with transaction.atomic():
        ResumeProcessingJob.objects.select_for_update().get(pk=job_id)
        return _enqueue_locked_job(job_id, delay_seconds)


def _enqueue_locked_job(job_id, delay_seconds=0):
    job = ResumeProcessingJob.objects.get(pk=job_id)
    if job.state != ResumeProcessingJob.State.QUEUED:
        return "not_queued"
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
    for job_id in stale_ids:
        with transaction.atomic():
            job = ResumeProcessingJob.objects.select_for_update().filter(
                pk=job_id, state="processing", locked_at__lte=stale_before,
            ).first()
            if job:
                _retry_or_fail(job.pk, "Resume processing lease expired.", recover_stale=True)
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
        if job.state == ResumeProcessingJob.State.FAILED:
            return None, "failed"
        # A duplicate delivery during the last permitted attempt must not fail
        # a live lease. Only its owner (or stale-lease recovery) can finish it.
        if (
            job.state == ResumeProcessingJob.State.PROCESSING
            and job.locked_at
            and job.locked_at > stale_before
        ):
            return None, "busy"
        if job.attempts >= job.max_attempts:
            job.state = ResumeProcessingJob.State.FAILED
            job.locked_at = None
            job.last_error = "Resume processing attempt limit reached."
            job.save(update_fields=["state", "locked_at", "last_error", "updated_at"])
            Resume.objects.filter(pk=job.resume_id).update(
                processing_status="failed", processing_error=job.last_error,
                processing_updated_at=timezone.now(),
            )
            return None, "failed"
        if job.available_at > timezone.now():
            return None, "delayed"
        job.state = ResumeProcessingJob.State.PROCESSING
        job.attempts += 1
        job.locked_at = timezone.now()
        job.last_error = ""
        job.phase = (
            "extracting" if job.resume.scan_status == Resume.ScanStatus.CLEAN else "scanning"
        )
        job.save(update_fields=[
            "state", "attempts", "locked_at", "last_error", "phase", "updated_at",
        ])
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
    schedule_cleanup(old_name)


def _employment_outcome(extracted):
    """Return privacy-safe extraction state, separate from job completion."""
    roles = extracted.get("work_experiences")
    roles = roles if isinstance(roles, list) else []
    interpretation = extracted.get("_interpretation")
    interpretation = interpretation if isinstance(interpretation, dict) else {}
    parse = extracted.get("_employment_parse")
    parse = parse if isinstance(parse, dict) else {}
    source = str(interpretation.get("source") or "rules")
    if roles:
        status = "verified_ai" if source in {"ai", "ai_cached"} else "verified_fallback"
        reason = "evidence_roles_accepted"
    elif parse.get("explicit_no_employment"):
        status = "confirmed_no_employment"
        reason = "explicit_no_employment_statement"
    else:
        status = "review_required"
        fallback_reason = str(interpretation.get("reason") or "")
        if source in {"ai", "ai_cached"}:
            reason = "ai_no_supported_roles"
        elif fallback_reason == "malformed_response":
            reason = "provider_response_failed_and_fallback_empty"
        elif parse.get("section_detected"):
            reason = "employment_section_not_resolved"
        else:
            reason = "no_supported_roles_detected"
    return {
        "status": status,
        "source": "ai" if source in {"ai", "ai_cached"} else "rules",
        "reason_code": reason,
        "accepted_role_count": len(roles),
        "profile_state": "pending",
        "saved_role_count": 0,
        "stale_profile_preserved": False,
    }


def _apply_extracted_resume(resume, extracted):
    profile = resume.candidate
    outcome = extracted.setdefault("_employment_outcome", _employment_outcome(extracted))
    issue = resume_identity_issue(resume, profile)
    if issue:
        extracted["_identity_issue"] = issue
        extracted["_blocked_proposals"] = proposed_fields(extracted)
        extracted["_needs_review"] = False
        outcome.update({
            "status": "review_required",
            "reason_code": "resume_identity_mismatch",
            "profile_state": "unchanged",
            "saved_role_count": profile.work_experiences.count(),
        })
        return
    previous = next((item for item in profile.resumes.filter(
        version__lt=resume.version, processing_status="completed"
    ) if not resume_identity_issue(item, profile)), None)
    baseline = previous.extracted_data.get("_auto_applied", {}) if previous else {}
    protected = set()
    for older in profile.resumes.all():
        protected.update(older.extracted_data.get("_candidate_edited_fields", []))
        if older.pk != resume.pk:
            protected.update(pending_fields(older, profile))
    saved = profile_values(profile)
    proposals = proposed_fields(extracted)
    safe, conflicts = {}, {}
    latest = profile.resumes.first().pk == resume.pk
    for field, value in proposals.items():
        if field == 'work_experiences':
            continue
        if comparable(field, value) == saved[field]:
            continue
        if latest and field not in protected and (
            previous is None or (field in baseline and saved[field] == baseline[field])
        ):
            safe[field] = value
        else:
            conflicts[field] = value
    # Employment is reconciled by row. A previous edit to one role does not block
    # safe additions or equivalent roles elsewhere in the journey.
    if latest:
        role_conflicts = reconcile_employment(profile, trusted_rows(extracted))
        if role_conflicts:
            conflicts['work_experiences'] = role_conflicts
        complete = complete_employment_history(extracted)
        archived_ids = archive_omitted_employment(
            profile, trusted_rows(extracted), resume
        ) if complete else []
        outcome['archive_complete'] = complete
        outcome['archived_role_count'] = len(archived_ids)
    # Keep raw extraction and pending proposals durable. Missing values never erase data.
    extracted["_pending_fields"] = conflicts
    extracted["_needs_review"] = bool(conflicts)
    extracted["_candidate_edited_fields"] = sorted(protected)
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
        value = safe.get(field)
        if value not in (None, "", []):
            setattr(profile, field, value)
    profile.save()
    signal_baseline = previous.extracted_data.get("_auto_signals", {}) if previous else {}
    signals = dict(profile.career_preferences)
    for key in ("standout_signal", "strongest_skills", "likely_directions"):
        if latest and extracted.get(key) and (
            key not in signals or (key in signal_baseline and signals[key] == signal_baseline[key])
        ):
            value = extracted[key]
            if key == "strongest_skills":
                value = [skill for skill in value if skill in profile.skills][:5]
            signals[key] = value
            signal_baseline[key] = value
    profile.career_preferences = signals
    profile.save(update_fields=["career_preferences", "profile_updated_at"])
    extracted["_auto_signals"] = signal_baseline
    current = profile_values(profile)
    extracted["_auto_applied"] = (
        current if previous is None and latest else
        {**baseline, **{field: current[field] for field in safe}}
    )
    saved_role_count = profile.work_experiences.count()
    accepted_role_count = int(outcome.get("accepted_role_count") or 0)
    pending_history = "work_experiences" in conflicts
    accepted_rows = trusted_rows(extracted)
    stale_profile = any(
        not any(row_equivalent(saved_row, item) for item in accepted_rows)
        for saved_row in profile.work_experiences.all()
    )
    if pending_history:
        profile_state = "pending_candidate_review"
    elif stale_profile:
        profile_state = "previous_history_preserved"
    elif accepted_role_count and saved_role_count >= accepted_role_count:
        profile_state = "applied"
    elif accepted_role_count:
        profile_state = "not_applied"
    else:
        profile_state = "empty"
    outcome.update({
        "profile_state": profile_state,
        "saved_role_count": saved_role_count,
        "stale_profile_preserved": stale_profile,
    })
    logger.info(
        "Resume employment outcome status=%s reason=%s source=%s accepted_roles=%s "
        "saved_roles=%s profile_state=%s",
        outcome["status"],
        outcome["reason_code"],
        outcome["source"],
        accepted_role_count,
        saved_role_count,
        profile_state,
    )


def _owns_attempt(current, claimed):
    return (
        current.state == ResumeProcessingJob.State.PROCESSING
        and current.attempts == claimed.attempts
        and current.locked_at == claimed.locked_at
        and current.locked_at is not None
        and current.locked_at > timezone.now() - timedelta(
            seconds=settings.RESUME_PROCESSING_TIMEOUT_SECONDS
        )
    )


def _resume_ai_allowed(resume):
    """Require current per-resume permission and the configured rollout boundary."""
    if (
        not resume.ai_processing_consent_at
        or resume.ai_processing_consent_version != settings.LEGAL_RESUME_AI_VERSION
        or resume.ai_processing_consent_sha256 != settings.LEGAL_RESUME_AI_SHA256
    ):
        return False
    if settings.RESUME_AI_ROLLOUT_MODE == "canary":
        return resume.pk in settings.RESUME_AI_CANARY_RESUME_IDS
    return settings.RESUME_AI_ROLLOUT_MODE == "consenting"


def _resume_ai_budget_enforced():
    return settings.RESUME_AI_ALLOW_PAID or (
        settings.RESUME_AI_PROVIDER == "gemini"
        and settings.RESUME_AI_GEMINI_FREE_TIER_APPROVED
    )


def _reserve_ai_attempt(claimed, reserved_input_tokens):
    with transaction.atomic():
        lock, _ = RateLimitBucket.objects.get_or_create(
            key="resume-ai-budget",
            defaults={"window_started_at": timezone.now(), "count": 0},
        )
        RateLimitBucket.objects.select_for_update().get(pk=lock.pk)
        current = ResumeProcessingJob.objects.select_for_update().get(pk=claimed.pk)
        if not _owns_attempt(current, claimed):
            return False
        resume = Resume.objects.select_for_update().get(pk=current.resume_id)
        used = max(
            resume.extracted_data.get("_ai_requests", 0),
            resume.ai_usage.count(),
        )
        if used >= settings.RESUME_AI_MAX_ATTEMPTS:
            return False
        reserved_cost = Decimal("0")
        reserved_input_tokens = max(0, int(reserved_input_tokens))
        if _resume_ai_budget_enforced():
            reserved_cost = (
                Decimal(reserved_input_tokens)
                * settings.RESUME_AI_INPUT_USD_PER_MILLION
                + Decimal(settings.RESUME_AI_MAX_OUTPUT_TOKENS)
                * settings.RESUME_AI_OUTPUT_USD_PER_MILLION
            ) / Decimal("1000000")
            now = timezone.now()
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            month_start = datetime(now.year, now.month, 1, tzinfo=now.tzinfo)
            daily_values = ResumeAIUsage.objects.filter(created_at__gte=day_start).aggregate(
                actual=Sum("actual_cost_usd"),
                reserved=Sum(
                    "estimated_cost_usd",
                    filter=Q(outcome=ResumeAIUsage.Outcome.RESERVED),
                ),
            )
            monthly_values = ResumeAIUsage.objects.filter(
                created_at__gte=month_start
            ).aggregate(
                actual=Sum("actual_cost_usd"),
                reserved=Sum(
                    "estimated_cost_usd",
                    filter=Q(outcome=ResumeAIUsage.Outcome.RESERVED),
                ),
            )
            daily = (daily_values["actual"] or Decimal("0")) + (
                daily_values["reserved"] or Decimal("0")
            )
            monthly = (monthly_values["actual"] or Decimal("0")) + (
                monthly_values["reserved"] or Decimal("0")
            )
            if (
                daily + reserved_cost > settings.RESUME_AI_DAILY_BUDGET_USD
                or monthly + reserved_cost > settings.RESUME_AI_MONTHLY_BUDGET_USD
            ):
                return False
        usage = ResumeAIUsage.objects.create(
            resume=resume,
            attempt=used + 1,
            provider=settings.RESUME_AI_PROVIDER,
            model=settings.RESUME_AI_MODEL,
            outcome=ResumeAIUsage.Outcome.RESERVED,
            reserved_input_tokens=reserved_input_tokens,
            estimated_cost_usd=reserved_cost,
        )
        resume.extracted_data["_ai_requests"] = used + 1
        resume.save(update_fields=["extracted_data"])
        return usage.pk


def _record_ai_attempt(
    usage_id,
    response,
    failure_category,
    latency_ms,
    error=None,
    validation_rejections=None,
):
    with transaction.atomic():
        usage = ResumeAIUsage.objects.select_for_update().get(pk=usage_id)
        if usage.outcome != ResumeAIUsage.Outcome.RESERVED:
            return
        metadata = response or error
        provider_latency_ms = getattr(metadata, "latency_ms", 0) if metadata else 0
        usage.latency_ms = max(0, int(provider_latency_ms or latency_ms))
        usage.completed_at = timezone.now()
        if metadata:
            usage.provider = getattr(metadata, "provider", "") or usage.provider
            usage.model = getattr(metadata, "model", "") or usage.model
            usage.request_id = str(getattr(metadata, "request_id", "") or "")[:180]
            http_status = getattr(metadata, "http_status", None)
            usage.http_status = int(http_status) if http_status is not None else None
            usage.provider_error_code = str(
                getattr(metadata, "provider_error_code", "") or ""
            )[:80]
            usage.provider_error_status = str(
                getattr(metadata, "provider_error_status", "") or ""
            )[:80]
            usage.input_tokens = max(0, int(getattr(metadata, "input_tokens", 0) or 0))
            usage.output_tokens = max(0, int(getattr(metadata, "output_tokens", 0) or 0))
            usage.stop_reason = str(getattr(metadata, "stop_reason", "") or "")[:60]
        usage.failure_stage = str(getattr(error, "stage", "") or "")[:40]
        usage.validation_rejections = list(validation_rejections or [])
        if response or getattr(error, "usage_confirmed", False):
            if (
                usage.provider == "gemini"
                and settings.RESUME_AI_GEMINI_FREE_TIER_APPROVED
                and not settings.RESUME_AI_ALLOW_PAID
            ):
                # Reserve against current paid rates even on the Free tier, but do not
                # report that conservative reservation as provider-billed spend.
                usage.actual_cost_usd = Decimal("0")
            else:
                usage.actual_cost_usd = (
                    Decimal(usage.input_tokens) * settings.RESUME_AI_INPUT_USD_PER_MILLION
                    + Decimal(usage.output_tokens) * settings.RESUME_AI_OUTPUT_USD_PER_MILLION
                ) / Decimal("1000000")
        if failure_category:
            usage.failure_category = failure_category[:40]
            usage.outcome = ResumeAIUsage.Outcome.FAILED
        else:
            usage.outcome = ResumeAIUsage.Outcome.SUCCEEDED
        usage.save()


def _cache_ai_result(claimed, usage_id, interpreted, response, latency_ms):
    with transaction.atomic():
        _record_ai_attempt(
            usage_id,
            response,
            None,
            latency_ms,
            validation_rejections=interpreted.get("_validation_rejections", []),
        )
        resume = Resume.objects.select_for_update().get(pk=claimed.resume_id)
        data = dict(resume.extracted_data)
        data["_ai_cached_result"] = interpreted
        data["_ai_cached_provider"] = {
            "provider": response.provider,
            "model": response.model,
        }
        resume.extracted_data = data
        resume.save(update_fields=["extracted_data"])


def _retry_or_fail(job_id, message, scan_failed=False, claimed=None, recover_stale=False):
    with transaction.atomic():
        job = (
            ResumeProcessingJob.objects.select_for_update().select_related("resume").get(pk=job_id)
        )
        if claimed and not _owns_attempt(job, claimed):
            return "superseded"
        terminal = job.attempts >= job.max_attempts
        delay = min(settings.RESUME_RETRY_BASE_SECONDS * (2 ** max(job.attempts - 1, 0)), 900)
        if recover_stale:
            delay = 0
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
    if not terminal and not recover_stale:
        try:
            enqueue_resume_job(job_id, delay)
        except Exception:
            pass
    return "failed" if terminal else "retry"


def _set_job_phase(job, phase):
    # A stale child cannot change the status of a replacement attempt.
    return ResumeProcessingJob.objects.filter(
        pk=job.pk, state="processing", attempts=job.attempts, locked_at=job.locked_at,
        locked_at__gt=timezone.now() - timedelta(
            seconds=settings.RESUME_PROCESSING_TIMEOUT_SECONDS,
        ),
    ).update(phase=phase, updated_at=timezone.now())


def process_resume_job(job_id, idempotency_key=None, claimed=None):
    job, outcome = (claimed, "claimed") if claimed else _claim_job(job_id, idempotency_key)
    if not job:
        return outcome
    resume = Resume.objects.select_related("candidate").get(pk=job.resume_id)
    resume_ai_allowed = _resume_ai_allowed(resume)
    try:
        if resume.scan_status != Resume.ScanStatus.CLEAN:
            with resume.file.open("rb") as file_object:
                get_resume_scanner().scan(file_object)
            # Journal the future clean key outside the merge transaction. A rollback or
            # killed child after S3 copy must not strand a private object indefinitely.
            FileCleanupJob.objects.get_or_create(
                name=f"resumes/{resume.candidate_id}/{resume.pk}/{Path(resume.original_name).name}",
                defaults={"available_at": timezone.now() + timedelta(days=1)},
            )
            with transaction.atomic():
                current = ResumeProcessingJob.objects.select_for_update().get(pk=job.pk)
                if not _owns_attempt(current, job):
                    return "superseded"
                resume.scan_status = Resume.ScanStatus.CLEAN
                resume.save(update_fields=["scan_status", "processing_updated_at"])
                _promote_clean_file(resume)
            # FieldFile retains a closed handle after the scanner/promote pass.
            # Reload it so local and remote storage backends open a fresh stream.
            resume = Resume.objects.select_related("candidate").get(pk=resume.pk)
        if not _set_job_phase(job, "extracting"):
            return "superseded"
        with resume.file.open("rb") as file_object:
            extracted = parse_resume(file_object, resume.original_name)
        if not extracted.get("raw_text", "").strip():
            raise ValueError("No readable text was found in this resume.")
        previous_private = resume.extracted_data
        if previous_private.get("_ai_cached_result"):
            extracted["_ai_cached_result"] = previous_private["_ai_cached_result"]
        resume.extracted_data = extracted
        if not resume_identity_issue(resume, resume.candidate):
            extracted = understand_resume(
                extracted,
                lambda reserved_input_tokens: _reserve_ai_attempt(
                    job, reserved_input_tokens
                ),
                _record_ai_attempt,
                lambda usage_id, result, response, latency_ms: _cache_ai_result(
                    job, usage_id, result, response, latency_ms
                ),
                ai_allowed=resume_ai_allowed,
                candidate_requested_ai=resume_ai_allowed,
            )
        else:
            extracted["_interpretation"] = {"source": "rules", "reason": "identity_check"}
        extracted["_employment_outcome"] = _employment_outcome(extracted)
        if not _set_job_phase(job, "validating"):
            return "superseded"
        with transaction.atomic():
            locked_job = ResumeProcessingJob.objects.select_for_update().get(pk=job.pk)
            if not _owns_attempt(locked_job, job):
                return "superseded"
            # Serialize candidate edits, uploads and review with the worker merge.
            profile = CandidateProfile.objects.select_for_update().get(pk=resume.candidate_id)
            locked_resume = (
                Resume.objects.select_for_update().select_related("candidate").get(pk=resume.pk)
            )
            locked_resume.candidate = profile
            extracted["_ai_requests"] = locked_resume.extracted_data.get("_ai_requests", 0)
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
        if resume.version > 1 and not extracted.get("_identity_issue"):
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
            if not _owns_attempt(failed_job, job):
                return "superseded"
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
        return _retry_or_fail(job.pk, "Security scanning could not be completed.",
                              scan_failed=True, claimed=job)
    except Exception:
        # Never log parser/provider exception strings or tracebacks containing document data.
        logger.warning("Resume processing failed job_id=%s category=processing_error", job.pk)
        return _retry_or_fail(job.pk, "Resume processing could not be completed.", claimed=job)


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
