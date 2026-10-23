"""Read-only production checks for the candidate-only launch."""

import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from talent import legal


def runtime_errors():
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    require(settings.APP_ENV == "production", "APP_ENV must be production")
    require(settings.CANDIDATE_ONLY, "candidate-only mode must be enabled")
    require(
        settings.CANDIDATE_REGISTRATION_PAUSED,
        "registration must remain paused until final authorization",
    )
    require(
        settings.RESUME_UPLOADS_PAUSED,
        "resume uploads must remain paused until final authorization",
    )
    require(settings.CANDIDATE_REGISTRATION_COUNTRIES == {"IN"}, "registration must be India-only")
    require(settings.LEGAL_CONTENT_APPROVED, "legal publication must be explicitly approved")
    require(not settings.LEGAL_WORKFLOW_PREVIEW, "unpublished legal preview must be disabled")
    require(settings.AI_PROVIDER == "disabled", "recruiter AI must be disabled")
    require(not settings.RESUME_AI_ENABLED, "external resume AI must be disabled")

    storage = settings.STORAGES.get("default", {})
    storage_options = storage.get("OPTIONS", {})
    require(
        storage.get("BACKEND") == "storages.backends.s3.S3Storage",
        "candidate files must use private S3 storage",
    )
    require(
        storage_options.get("default_acl") is None,
        "candidate files must not have a public ACL",
    )
    require(storage_options.get("querystring_auth") is True, "candidate file URLs must be signed")
    require(
        storage_options.get("object_parameters", {}).get("ServerSideEncryption") == "AES256",
        "candidate files must be encrypted at rest",
    )
    require(
        getattr(settings, "AWS_S3_REGION_NAME", "") == "ap-southeast-2",
        "private file storage must match the disclosed Sydney region",
    )
    require(
        settings.AWS_SQS_REGION_NAME == "ap-southeast-2",
        "resume processing must match the disclosed Sydney region",
    )

    require(settings.SECURE_SSL_REDIRECT, "HTTPS redirect must be enabled")
    require(settings.AUTH_COOKIE_SECURE, "authentication cookies must be Secure")
    require(settings.SESSION_COOKIE_SECURE, "session cookies must be Secure")
    require(settings.CSRF_COOKIE_SECURE, "CSRF cookies must be Secure")
    require(settings.FRONTEND_URL == "https://enter.careers", "frontend URL must be enter.careers")
    require(
        settings.ALLOWED_HOSTS == ["enter.careers"],
        "allowed host must be exactly enter.careers",
    )
    require(
        settings.CORS_ALLOWED_ORIGINS == ["https://enter.careers"],
        "CORS origin must be exactly enter.careers",
    )
    require(
        settings.CSRF_TRUSTED_ORIGINS == ["https://enter.careers"],
        "CSRF origin must be exactly enter.careers",
    )

    require(
        settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend",
        "candidate verification requires the production SMTP backend",
    )
    require(
        settings.EMAIL_HOST == "email-smtp.ap-southeast-2.amazonaws.com",
        "transactional email must match the disclosed Sydney AWS service",
    )
    require(settings.EMAIL_USE_TLS or settings.EMAIL_USE_SSL, "SMTP transport must be encrypted")
    require(not settings.EXPOSE_LOCAL_EMAIL_LINKS, "local email shortcuts must be disabled")
    require(settings.EMAIL_VERIFICATION_TOKEN_TTL_SECONDS > 0, "email verification must be enabled")
    require(bool(settings.SUBMISSION_CONSENT_VERSION), "submission consent must be versioned")
    require(
        settings.SUBMISSION_CONSENT_VERSION == settings.LEGAL_SUBMISSION_VERSION,
        "submission consent and published submission text must use the same version",
    )

    try:
        documents = legal.documents()
        require(
            set(documents) == {"age", "terms", "privacy", "submission"},
            "all four legal documents must be available",
        )
        require(
            all(not document["unpublished"] for document in documents.values()),
            "only published legal documents may be used",
        )
    except Exception:
        errors.append("approved legal documents or immutable hashes are invalid")

    try:
        executor = MigrationExecutor(connection)
        require(
            not executor.migration_plan(executor.loader.graph.leaf_nodes()),
            "database migrations are not current",
        )
    except Exception:
        errors.append("database migration state could not be verified")

    return errors


class Command(BaseCommand):
    help = "Fail closed unless the deployed runtime is ready for candidate-only launch checking."

    def handle(self, *args, **options):
        errors = runtime_errors()
        if errors:
            self.stdout.write(json.dumps({"candidate_launch": "BLOCKED", "errors": errors}))
            raise CommandError("Candidate launch runtime check failed.")
        self.stdout.write(
            json.dumps(
                {
                    "candidate_launch": "PASS",
                    "mode": "candidate-only",
                    "registration": "paused",
                    "resume_uploads": "paused",
                }
            )
        )
