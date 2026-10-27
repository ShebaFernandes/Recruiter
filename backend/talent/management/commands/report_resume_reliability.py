import json
from collections import Counter

from django.core.management.base import BaseCommand

from talent.models import ResumeAIUsage, ResumeProcessingJob


class Command(BaseCommand):
    help = "Print de-identified aggregate resume extraction reliability metrics."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        limit = min(500, max(1, options["limit"]))
        jobs = list(
            ResumeProcessingJob.objects.select_related("resume")
            .order_by("-created_at")[:limit]
        )
        usage_by_resume = {}
        for usage in ResumeAIUsage.objects.filter(
            resume_id__in=[job.resume_id for job in jobs]
        ):
            usage_by_resume.setdefault(usage.resume_id, []).append(usage)

        metrics = Counter()
        reason_codes = Counter()
        failure_stages = Counter()
        rejection_categories = Counter()
        for job in jobs:
            resume = job.resume
            data = resume.extracted_data if isinstance(resume.extracted_data, dict) else {}
            roles = data.get("work_experiences")
            roles = roles if isinstance(roles, list) else []
            interpretation = data.get("_interpretation")
            interpretation = interpretation if isinstance(interpretation, dict) else {}
            source = str(interpretation.get("source") or "unknown")
            outcome = data.get("_employment_outcome")
            outcome = outcome if isinstance(outcome, dict) else {}
            usages = usage_by_resume.get(resume.pk, [])

            metrics["jobs"] += 1
            metrics["consented" if resume.ai_processing_consent_at else "not_consented"] += 1
            metrics[f"source_{source}"] += 1
            if usages:
                metrics["gemini_attempted_jobs"] += 1
            if source in {"ai", "ai_cached"} and roles:
                metrics["gemini_accepted_jobs"] += 1
            if source == "rules":
                metrics["fallback_jobs"] += 1
            if not roles:
                metrics["zero_role_jobs"] += 1
            if outcome.get("stale_profile_preserved"):
                metrics["stale_history_preserved_jobs"] += 1
            if outcome.get("reason_code"):
                reason_codes[str(outcome["reason_code"])] += 1

            for usage in usages:
                if usage.failure_stage:
                    failure_stages[usage.failure_stage] += 1
                rejections = usage.validation_rejections
                if isinstance(rejections, list):
                    for rejection in rejections:
                        if isinstance(rejection, dict) and rejection.get("category"):
                            rejection_categories[str(rejection["category"])] += 1

        self.stdout.write(json.dumps({
            "window_jobs": len(jobs),
            "metrics": dict(sorted(metrics.items())),
            "reason_codes": dict(sorted(reason_codes.items())),
            "failure_stages": dict(sorted(failure_stages.items())),
            "validation_rejections": dict(sorted(rejection_categories.items())),
        }, sort_keys=True))
