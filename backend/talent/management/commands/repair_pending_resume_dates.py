"""Evidence-only local repair for pending work-experience date proposals."""

import json
from copy import deepcopy

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from talent.models import Resume
from talent.resume_understanding import repair_pending_work_experience_dates
from talent.services import parse_resume


def _require_isolated_local_runtime():
    database = settings.DATABASES["default"]
    storage = settings.STORAGES["default"]["BACKEND"]
    if (
        not settings.DEBUG
        or database.get("HOST") not in {"127.0.0.1", "localhost"}
        or storage != "django.core.files.storage.FileSystemStorage"
        or settings.RESUME_QUEUE_BACKEND != "database"
        or settings.RESUME_AI_ENABLED
        or settings.RESUME_AI_EXTERNAL_PROCESSING_APPROVED
        or settings.RESUME_AI_ALLOW_PAID
    ):
        raise CommandError("Offline date repair requires isolated local resources and disabled AI.")


class Command(BaseCommand):
    help = "Repair evidence-backed dates in one local resume's pending Work Experience proposal."

    def add_arguments(self, parser):
        parser.add_argument("resume_id", type=int)
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist the repaired pending proposal; otherwise perform a dry run.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        _require_isolated_local_runtime()
        resume = Resume.objects.select_for_update().get(pk=options["resume_id"])
        data = deepcopy(resume.extracted_data)
        pending = data.get("_pending_fields", {}).get("work_experiences")
        if not isinstance(pending, list) or not pending:
            raise CommandError("This resume has no pending Work Experience proposal.")
        with resume.file.open("rb") as file_obj:
            document_text = parse_resume(file_obj, resume.original_name)["raw_text"]
        repaired, diagnostics = repair_pending_work_experience_dates(pending, document_text)
        result = {
            "resume_id": resume.pk,
            "mode": "apply" if options["apply"] else "dry-run",
            "roles": len(repaired),
            "changed_indexes": diagnostics["changed_indexes"],
            "unresolved_indexes": diagnostics["unresolved_indexes"],
            "validation_rejections": diagnostics["validation_rejections"],
        }
        if options["apply"]:
            if diagnostics["unresolved_indexes"] or diagnostics["validation_rejections"]:
                raise CommandError("Evidence validation did not support a complete repair.")
            repairs = data.setdefault("_offline_repairs", {})
            repair_key = "pending_work_experience_dates_v1"
            if repair_key not in repairs:
                repairs[repair_key] = {
                    "applied_at": timezone.now().isoformat(),
                    "source": "deterministic_resume_evidence",
                    "original_work_experiences": deepcopy(pending),
                }
            data["_pending_fields"]["work_experiences"] = repaired
            resume.extracted_data = data
            resume.save(update_fields=["extracted_data"])
        self.stdout.write(json.dumps(result, sort_keys=True))
