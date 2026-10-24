import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

import dj_database_url
from botocore.config import Config
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_local_env(path):
    """Load simple local dotenv values without executing them or overriding the shell."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if (
            not separator
            or not key
            or key[0].isdigit()
            or not key.replace("_", "").isalnum()
        ):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


_testing_boot = "pytest" in sys.modules or os.getenv("TESTING", "false").lower() == "true"
_explicit_app_env = os.getenv("APP_ENV", "").lower()
if not _testing_boot and _explicit_app_env not in {"staging", "production"}:
    _load_local_env(BASE_DIR.parent / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "enter-local-development-key")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
TESTING = "pytest" in sys.modules or os.getenv("TESTING", "false").lower() == "true"
APP_ENV = os.getenv("APP_ENV", "local" if DEBUG else "production").lower()
if APP_ENV not in {"local", "test", "staging", "production"}:
    raise ImproperlyConfigured("APP_ENV must be local, test, staging, or production.")
if APP_ENV in {"staging", "production"} and (DEBUG or TESTING):
    raise ImproperlyConfigured("Staging and production must disable DEBUG and TESTING.")
if os.getenv("EXPOSE_LOCAL_EMAIL_LINKS", "false").lower() == "true" and (
    not DEBUG or APP_ENV not in {"local", "test"}
):
    raise ImproperlyConfigured("Local email shortcuts are forbidden outside local/test DEBUG mode.")


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def secret_value(name, file_name):
    """Read a secret from a mounted file without exposing it in container metadata."""
    path = os.getenv(file_name, "").strip()
    if not path:
        return os.getenv(name, "")
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError as error:
        message = f"Unable to read configured secret file: {file_name}."
        raise ImproperlyConfigured(message) from error


ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "127.0.0.1,localhost,testserver")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "whitenoise.runserver_nostatic",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "talent",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "talent.legal_middleware.LocalLegalPreviewMiddleware",
    "talent.launch_controls.LaunchControlMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=60,
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]



LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(BASE_DIR / "media")))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
FILE_UPLOAD_PERMISSIONS = 0o600
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
)
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
)
PRIVATE_ADMIN_ORIGIN = os.getenv("PRIVATE_ADMIN_ORIGIN", "").strip()
if PRIVATE_ADMIN_ORIGIN and PRIVATE_ADMIN_ORIGIN not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(PRIVATE_ADMIN_ORIGIN)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173")
CORS_ALLOW_CREDENTIALS = True
AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "enter_session")
AUTH_COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "Lax")
AUTH_COOKIE_DOMAIN = os.getenv("AUTH_COOKIE_DOMAIN") or None
AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "false" if DEBUG else "true").lower() == "true"
RATE_LIMIT_TRUST_X_FORWARDED_FOR = (
    os.getenv("RATE_LIMIT_TRUST_X_FORWARDED_FOR", "false").lower() == "true"
)

if os.getenv("AWS_STORAGE_BUCKET_NAME"):
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "default_acl": None,
            "querystring_auth": True,
            "object_parameters": {"ServerSideEncryption": "AES256"},
        },
    }
    AWS_STORAGE_BUCKET_NAME = os.environ["AWS_STORAGE_BUCKET_NAME"]
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "auto")
    AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL") or None
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True
    AWS_QUERYSTRING_EXPIRE = 300
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_CLIENT_CONFIG = Config(
        connect_timeout=3, read_timeout=15,
        retries={"max_attempts": 2, "mode": "standard"},
    )

if not DEBUG and not os.getenv("AWS_STORAGE_BUCKET_NAME"):
    raise ImproperlyConfigured(
        "Production resume storage requires AWS_STORAGE_BUCKET_NAME and private S3 credentials."
    )

if not DEBUG:
    required_production_variables = [
        "DJANGO_SECRET_KEY",
        "DATABASE_URL",
        "ALLOWED_HOSTS",
        "CORS_ALLOWED_ORIGINS",
        "CSRF_TRUSTED_ORIGINS",
        "FRONTEND_URL",
        "AWS_STORAGE_BUCKET_NAME",
        "AWS_S3_REGION_NAME",
    ]
    missing_production_variables = [
        name for name in required_production_variables if not os.getenv(name)
    ]
    if missing_production_variables:
        raise ImproperlyConfigured(
            "Production configuration is missing: "
            + ", ".join(missing_production_variables)
        )
    if SECRET_KEY == "enter-local-development-key" or len(SECRET_KEY) < 50:
        raise ImproperlyConfigured(
            "Production DJANGO_SECRET_KEY must be explicitly configured "
            "with at least 50 characters."
        )
    if not AUTH_COOKIE_SECURE:
        raise ImproperlyConfigured("Production authentication cookies must be Secure.")
    if AUTH_COOKIE_SAMESITE not in {"Lax", "Strict", "None"}:
        raise ImproperlyConfigured("AUTH_COOKIE_SAMESITE must be Lax, Strict, or None.")
    public_origins = [*CORS_ALLOWED_ORIGINS, *CSRF_TRUSTED_ORIGINS, FRONTEND_URL]
    if any(not origin.startswith("https://") for origin in public_origins):
        raise ImproperlyConfigured("Production frontend, CORS, and CSRF origins must use HTTPS.")
    if any("*" in host or host.startswith(".") for host in ALLOWED_HOSTS):
        raise ImproperlyConfigured("Production ALLOWED_HOSTS must contain exact host names.")
    for origin in public_origins:
        parsed = urlsplit(origin)
        if (not parsed.hostname or parsed.username or parsed.password or "*" in origin
                or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
            raise ImproperlyConfigured("Production origins must be exact HTTPS origins.")
    if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
        raise ImproperlyConfigured("Production requires PostgreSQL.")

RESUME_QUEUE_BACKEND = os.getenv("RESUME_QUEUE_BACKEND", "database")
RESUME_SQS_QUEUE_URL = os.getenv("RESUME_SQS_QUEUE_URL", "")
AWS_SQS_REGION_NAME = os.getenv("AWS_SQS_REGION_NAME", os.getenv("AWS_S3_REGION_NAME", "auto"))
AWS_SQS_ENDPOINT_URL = os.getenv("AWS_SQS_ENDPOINT_URL", "")
RESUME_JOB_MAX_ATTEMPTS = int(os.getenv("RESUME_JOB_MAX_ATTEMPTS", "3"))
RESUME_RETRY_BASE_SECONDS = int(os.getenv("RESUME_RETRY_BASE_SECONDS", "30"))
RESUME_PROCESSING_TIMEOUT_SECONDS = int(os.getenv("RESUME_PROCESSING_TIMEOUT_SECONDS", "300"))
RESUME_WORKER_POLL_SECONDS = float(os.getenv("RESUME_WORKER_POLL_SECONDS", "1"))
RESUME_SQS_WAIT_SECONDS = int(os.getenv("RESUME_SQS_WAIT_SECONDS", "20"))
RESUME_SQS_VISIBILITY_TIMEOUT_SECONDS = int(
    os.getenv("RESUME_SQS_VISIBILITY_TIMEOUT_SECONDS", "360")
)
AWS_SQS_CONNECT_TIMEOUT_SECONDS = int(os.getenv("AWS_SQS_CONNECT_TIMEOUT_SECONDS", "2"))
AWS_SQS_READ_TIMEOUT_SECONDS = int(os.getenv("AWS_SQS_READ_TIMEOUT_SECONDS", "25"))
AWS_SQS_MAX_ATTEMPTS = int(os.getenv("AWS_SQS_MAX_ATTEMPTS", "2"))
RESUME_SCANNER_BACKEND = os.getenv("RESUME_SCANNER_BACKEND", "development")
RESUME_SCAN_TIMEOUT_SECONDS = int(os.getenv("RESUME_SCAN_TIMEOUT_SECONDS", "30"))
CLAMAV_HOST = os.getenv("CLAMAV_HOST", "127.0.0.1")
CLAMAV_PORT = int(os.getenv("CLAMAV_PORT", "3310"))
RESUME_PROCESS_HARD_TIMEOUT_SECONDS = int(os.getenv("RESUME_PROCESS_HARD_TIMEOUT_SECONDS", "240"))
RESUME_PROCESS_MEMORY_MB = int(os.getenv("RESUME_PROCESS_MEMORY_MB", "768"))
RESUME_WORKER_HEALTH_SECONDS = RESUME_PROCESS_HARD_TIMEOUT_SECONDS + 60
RESUME_QUEUE_ALERT_SECONDS = int(os.getenv("RESUME_QUEUE_ALERT_SECONDS", "600"))
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024

if not DEBUG:
    if RESUME_QUEUE_BACKEND != "sqs" or not RESUME_SQS_QUEUE_URL:
        raise ImproperlyConfigured(
            "Production resume processing requires RESUME_QUEUE_BACKEND=sqs and "
            "RESUME_SQS_QUEUE_URL."
        )
    if not os.getenv("AWS_SQS_REGION_NAME"):
        raise ImproperlyConfigured("Production SQS requires AWS_SQS_REGION_NAME.")
    if AWS_SQS_READ_TIMEOUT_SECONDS <= RESUME_SQS_WAIT_SECONDS:
        raise ImproperlyConfigured("SQS read timeout must exceed the long-poll wait time.")
    if RESUME_SQS_VISIBILITY_TIMEOUT_SECONDS <= RESUME_PROCESSING_TIMEOUT_SECONDS:
        raise ImproperlyConfigured(
            "SQS visibility timeout must exceed the resume processing timeout."
        )
    if RESUME_SCANNER_BACKEND != "clamav":
        raise ImproperlyConfigured(
            "Production resume processing requires a real malware scanner backend."
        )
    if not 10 <= RESUME_PROCESS_HARD_TIMEOUT_SECONDS < RESUME_PROCESSING_TIMEOUT_SECONDS:
        raise ImproperlyConfigured("Worker hard timeout must be shorter than its lease.")
    if not 256 <= RESUME_PROCESS_MEMORY_MB <= 2048:
        raise ImproperlyConfigured("Worker memory limit must be between 256 and 2048 MB.")

SECURE_SSL_REDIRECT = (
    os.getenv("SECURE_SSL_REDIRECT", "false" if DEBUG else "true").lower() == "true"
)
if not DEBUG and not SECURE_SSL_REDIRECT:
    raise ImproperlyConfigured("Production must enforce HTTPS.")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.locmem.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@enter.example")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "false").lower() == "true"
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))
if not 1 <= EMAIL_TIMEOUT <= 60:
    raise ImproperlyConfigured("EMAIL_TIMEOUT must be between 1 and 60 seconds.")
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured("Choose either SMTP STARTTLS or implicit SSL, not both.")
EXPOSE_LOCAL_EMAIL_LINKS = (
    DEBUG and APP_ENV in {"local", "test"}
    and os.getenv("EXPOSE_LOCAL_EMAIL_LINKS", "false").lower() == "true"
)
if not DEBUG and EMAIL_BACKEND in {
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.filebased.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
}:
    raise ImproperlyConfigured("Production requires a transactional email backend.")
if not DEBUG and EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
    if not (EMAIL_USE_TLS or EMAIL_USE_SSL):
        raise ImproperlyConfigured("Production SMTP requires STARTTLS or implicit SSL.")
    missing_email_variables = [
        name
        for name in ("EMAIL_HOST", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD", "DEFAULT_FROM_EMAIL")
        if not os.getenv(name)
    ]
    if missing_email_variables:
        raise ImproperlyConfigured(
            "Production SMTP configuration is missing: " + ", ".join(missing_email_variables)
        )
RESUME_MAX_BYTES = int(os.getenv("RESUME_MAX_BYTES", str(5 * 1024 * 1024)))
PROFILE_PHOTO_MAX_BYTES = int(os.getenv("PROFILE_PHOTO_MAX_BYTES", str(4 * 1024 * 1024)))
EMAIL_VERIFICATION_TOKEN_TTL_SECONDS = int(
    os.getenv("EMAIL_VERIFICATION_TOKEN_TTL_SECONDS", "86400")
)
PASSWORD_RESET_TOKEN_TTL_SECONDS = int(os.getenv("PASSWORD_RESET_TOKEN_TTL_SECONDS", "3600"))
ACCOUNT_EMAIL_RESEND_COOLDOWN_SECONDS = int(
    os.getenv("ACCOUNT_EMAIL_RESEND_COOLDOWN_SECONDS", "60")
)
if EMAIL_VERIFICATION_TOKEN_TTL_SECONDS <= 0 or PASSWORD_RESET_TOKEN_TTL_SECONDS <= 0:
    raise ImproperlyConfigured("Account token lifetimes must be positive.")
AUTH_TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "604800"))
SUBMISSION_CONSENT_VERSION = os.getenv(
    "SUBMISSION_CONSENT_VERSION", "candidate-profile-sharing-v1"
)

AI_PROVIDER = os.getenv(
    "AI_PROVIDER",
    "deterministic" if TESTING else "disabled",
).lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_SEARCH_MODEL = os.getenv("OPENAI_SEARCH_MODEL", "gpt-4o-mini")
OPENAI_API_BASE_URL = os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_SEARCH_MODEL = os.getenv("ANTHROPIC_SEARCH_MODEL", "claude-sonnet-5-5")
ANTHROPIC_API_BASE_URL = os.getenv("ANTHROPIC_API_BASE_URL", "https://api.anthropic.com/v1")
ANTHROPIC_API_VERSION = os.getenv("ANTHROPIC_API_VERSION", "2023-06-01")
ANTHROPIC_SEARCH_MAX_OUTPUT_TOKENS = int(
    os.getenv("ANTHROPIC_SEARCH_MAX_OUTPUT_TOKENS", "2048")
)
# Resume interpretation is independent of recruiter search and requires explicit approval.
RESUME_AI_ENABLED = os.getenv("RESUME_AI_ENABLED", "false").lower() == "true"
RESUME_AI_EXTERNAL_PROCESSING_APPROVED = (
    os.getenv("RESUME_AI_EXTERNAL_PROCESSING_APPROVED", "false").lower() == "true"
)
RESUME_AI_ALLOW_PAID = os.getenv("RESUME_AI_ALLOW_PAID", "false").lower() == "true"
RESUME_AI_OPENAI_ZDR_APPROVED = (
    os.getenv("RESUME_AI_OPENAI_ZDR_APPROVED", "false").lower() == "true"
)
RESUME_AI_GEMINI_FREE_TIER_APPROVED = (
    os.getenv("RESUME_AI_GEMINI_FREE_TIER_APPROVED", "false").lower() == "true"
)
RESUME_AI_PROVIDER = os.getenv("RESUME_AI_PROVIDER", "anthropic")
RESUME_AI_MODEL = os.getenv("RESUME_AI_MODEL", "")
RESUME_AI_API_KEY = secret_value("RESUME_AI_API_KEY", "RESUME_AI_API_KEY_FILE")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_BASE_URL = os.getenv(
    "GEMINI_API_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
)
RESUME_AI_FALLBACK = os.getenv("RESUME_AI_FALLBACK", "rules")
RESUME_AI_MAX_ATTEMPTS = int(os.getenv("RESUME_AI_MAX_ATTEMPTS", "2"))
RESUME_AI_TIMEOUT_SECONDS = float(os.getenv("RESUME_AI_TIMEOUT_SECONDS", "60"))
RESUME_AI_MAX_INPUT_TOKENS = int(os.getenv("RESUME_AI_MAX_INPUT_TOKENS", "4000"))
RESUME_AI_MAX_INPUT_CHARS = RESUME_AI_MAX_INPUT_TOKENS * 4
RESUME_AI_MAX_OUTPUT_TOKENS = int(os.getenv("RESUME_AI_MAX_OUTPUT_TOKENS", "8000"))
RESUME_AI_DAILY_BUDGET_USD = Decimal(os.getenv("RESUME_AI_DAILY_BUDGET_USD", "0"))
RESUME_AI_MONTHLY_BUDGET_USD = Decimal(os.getenv("RESUME_AI_MONTHLY_BUDGET_USD", "0"))
RESUME_AI_INPUT_USD_PER_MILLION = Decimal(
    os.getenv("RESUME_AI_INPUT_USD_PER_MILLION", "0")
)
RESUME_AI_OUTPUT_USD_PER_MILLION = Decimal(
    os.getenv("RESUME_AI_OUTPUT_USD_PER_MILLION", "0")
)
RESUME_AI_ROLLOUT_MODE = os.getenv("RESUME_AI_ROLLOUT_MODE", "disabled").lower()
try:
    RESUME_AI_CANARY_RESUME_IDS = {
        int(value) for value in env_list("RESUME_AI_CANARY_RESUME_IDS")
    }
except ValueError as error:
    raise ImproperlyConfigured("RESUME_AI_CANARY_RESUME_IDS must contain integers.") from error
if (
    RESUME_AI_FALLBACK not in {"rules", "fail"}
    or RESUME_AI_PROVIDER not in {"anthropic", "openai", "gemini"}
    or RESUME_AI_ROLLOUT_MODE not in {"disabled", "canary", "consenting"}
    or not 256 <= ANTHROPIC_SEARCH_MAX_OUTPUT_TOKENS <= 20_000
    or not 1 <= RESUME_AI_MAX_ATTEMPTS <= 2
    or not 1 <= RESUME_AI_TIMEOUT_SECONDS <= 60
    or not 256 <= RESUME_AI_MAX_INPUT_TOKENS <= 100_000
    or not 256 <= RESUME_AI_MAX_OUTPUT_TOKENS <= 20_000
    or min(
        RESUME_AI_DAILY_BUDGET_USD,
        RESUME_AI_MONTHLY_BUDGET_USD,
        RESUME_AI_INPUT_USD_PER_MILLION,
        RESUME_AI_OUTPUT_USD_PER_MILLION,
    ) < 0
):
    raise ImproperlyConfigured("Invalid bounded resume AI configuration.")
RESUME_AI_BUDGET_ENFORCED = RESUME_AI_ALLOW_PAID or (
    RESUME_AI_PROVIDER == "gemini" and RESUME_AI_GEMINI_FREE_TIER_APPROVED
)
if APP_ENV == "production" and RESUME_AI_GEMINI_FREE_TIER_APPROVED:
    raise ImproperlyConfigured(
        "Production candidate resumes must never use Gemini unpaid services."
    )
if (
    APP_ENV == "production"
    and RESUME_AI_ENABLED
    and RESUME_AI_PROVIDER == "gemini"
    and not RESUME_AI_ALLOW_PAID
):
    raise ImproperlyConfigured(
        "Production Gemini resume AI requires an approved paid service account."
    )
if RESUME_AI_ENABLED and RESUME_AI_BUDGET_ENFORCED and (
    not RESUME_AI_DAILY_BUDGET_USD
    or not RESUME_AI_MONTHLY_BUDGET_USD
    or not (RESUME_AI_INPUT_USD_PER_MILLION or RESUME_AI_OUTPUT_USD_PER_MILLION)
):
    raise ImproperlyConfigured(
        "Resume AI requires daily/monthly budgets and configured token prices."
    )
if RESUME_AI_ENABLED and not RESUME_AI_MODEL:
    raise ImproperlyConfigured("RESUME_AI_MODEL must be an explicitly verified model ID.")
if RESUME_AI_ENABLED and (
    RESUME_AI_MAX_ATTEMPTS * RESUME_AI_TIMEOUT_SECONDS + RESUME_SCAN_TIMEOUT_SECONDS + 30
    >= RESUME_PROCESSING_TIMEOUT_SECONDS
):
    raise ImproperlyConfigured("Resume worker lease must exceed the bounded AI/scan budget.")
AI_REQUEST_TIMEOUT_SECONDS = float(
    os.getenv("AI_REQUEST_TIMEOUT_SECONDS", os.getenv("SEARCH_AI_TIMEOUT_SECONDS", "12"))
)
AI_ALLOW_DETERMINISTIC_FALLBACK = (
    os.getenv(
        "AI_ALLOW_DETERMINISTIC_FALLBACK",
        os.getenv("SEARCH_AI_ALLOW_FALLBACK", "false"),
    ).lower()
    == "true"
)

if not DEBUG:
    if AI_PROVIDER not in {"anthropic", "disabled", "openai"}:
        raise ImproperlyConfigured("Production AI_PROVIDER must be disabled, anthropic or openai.")
    provider_key = OPENAI_API_KEY if AI_PROVIDER == "openai" else ANTHROPIC_API_KEY
    if AI_PROVIDER != "disabled" and not provider_key:
        raise ImproperlyConfigured(
            f"Production AI_PROVIDER={AI_PROVIDER} requires its server-side API key."
        )

    if AI_ALLOW_DETERMINISTIC_FALLBACK:
        raise ImproperlyConfigured(
            "Production AI search must fail clearly instead of silently using "
            "deterministic fallback."
        )

# Disabled by default: existing staging behavior is unchanged.
CANDIDATE_ONLY = APP_ENV == "production" and os.getenv("CANDIDATE_ONLY", "false").lower() == "true"
CANDIDATE_REGISTRATION_PAUSED = (
    os.getenv("CANDIDATE_REGISTRATION_PAUSED", "false").lower() == "true"
)
RESUME_UPLOADS_PAUSED = os.getenv("RESUME_UPLOADS_PAUSED", "false").lower() == "true"

# India-first registration is self-declared and enforced server-side. It reduces
# unsupported registrations but is not represented as proof of physical location.
_registration_countries = os.getenv(
    "CANDIDATE_REGISTRATION_COUNTRIES", "IN" if APP_ENV == "production" else ""
)
CANDIDATE_REGISTRATION_COUNTRIES = {
    code.strip().upper() for code in _registration_countries.split(",") if code.strip()
}
if any(len(code) != 2 or not code.isalpha() for code in CANDIDATE_REGISTRATION_COUNTRIES):
    raise ImproperlyConfigured("CANDIDATE_REGISTRATION_COUNTRIES must contain ISO alpha-2 codes.")

# Supply the approved Karnataka calendar as comma-separated YYYY-MM-DD values.
# Empty is permitted while automation is disabled; production enforcement fails closed.
_business_holidays = os.getenv("LEGAL_BUSINESS_HOLIDAYS", "")
try:
    LEGAL_BUSINESS_HOLIDAYS = {
        date.fromisoformat(value.strip())
        for value in _business_holidays.split(",")
        if value.strip()
    }
except ValueError as error:
    raise ImproperlyConfigured("LEGAL_BUSINESS_HOLIDAYS must contain ISO dates.") from error
RETENTION_REMINDER_DELIVERY_ENABLED = (
    os.getenv("RETENTION_REMINDER_DELIVERY_ENABLED", "false").lower() == "true"
)
RETENTION_DELETION_ENABLED = (
    os.getenv("RETENTION_DELETION_ENABLED", "false").lower() == "true"
)
ANCILLARY_RETENTION_ENABLED = (
    os.getenv("ANCILLARY_RETENTION_ENABLED", "false").lower() == "true"
)
RETENTION_REMINDER_MAX_ATTEMPTS = int(os.getenv("RETENTION_REMINDER_MAX_ATTEMPTS", "5"))

# This is a release gate, not legal text. Approval must refer to the actual published documents.
LEGAL_CONTENT_APPROVED = os.getenv("LEGAL_CONTENT_APPROVED", "false").lower() == "true"
LEGAL_WORKFLOW_PREVIEW = os.getenv("LEGAL_WORKFLOW_PREVIEW", "false").lower() == "true"
LEGAL_WORKFLOW_ENABLED = LEGAL_WORKFLOW_PREVIEW or LEGAL_CONTENT_APPROVED
LEGAL_DOCUMENT_ROOT = Path(
    os.getenv("LEGAL_DOCUMENT_ROOT", str(BASE_DIR.parent / "deploy"))
)
LEGAL_PRIVACY_VERSION = os.getenv(
    "LEGAL_PRIVACY_VERSION", "enter-candidate-privacy-v1.0"
)
LEGAL_TERMS_VERSION = os.getenv("LEGAL_TERMS_VERSION", "enter-candidate-terms-v1.0")
LEGAL_AGE_VERSION = os.getenv("LEGAL_AGE_VERSION", "enter-candidate-age-v1.0")
LEGAL_SUBMISSION_VERSION = os.getenv(
    "LEGAL_SUBMISSION_VERSION", "enter-candidate-submission-v1.0"
)
LEGAL_RESUME_AI_APPROVED = (
    os.getenv("LEGAL_RESUME_AI_APPROVED", "false").lower() == "true"
)
LEGAL_RESUME_AI_VERSION = os.getenv(
    "LEGAL_RESUME_AI_VERSION", "enter-resume-ai-consent-v1.0"
)
LEGAL_EFFECTIVE_DATE = os.getenv("LEGAL_EFFECTIVE_DATE", "")
LEGAL_PRIVACY_SHA256 = os.getenv("LEGAL_PRIVACY_SHA256", "")
LEGAL_TERMS_SHA256 = os.getenv("LEGAL_TERMS_SHA256", "")
LEGAL_AGE_SHA256 = os.getenv("LEGAL_AGE_SHA256", "")
LEGAL_SUBMISSION_SHA256 = os.getenv("LEGAL_SUBMISSION_SHA256", "")
LEGAL_RESUME_AI_SHA256 = os.getenv("LEGAL_RESUME_AI_SHA256", "")
if RESUME_AI_ENABLED and (
    not LEGAL_RESUME_AI_APPROVED
    or not LEGAL_RESUME_AI_VERSION
    or not LEGAL_RESUME_AI_SHA256
):
    raise ImproperlyConfigured(
        "Resume AI requires an approved, hash-pinned candidate consent document."
    )
if LEGAL_WORKFLOW_PREVIEW and (not DEBUG or APP_ENV not in {"local", "test"}):
    raise ImproperlyConfigured("Unpublished legal workflow requires local development/test.")
if LEGAL_WORKFLOW_PREVIEW:
    # Unpublished review must not send messages to real recipients.
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
if APP_ENV == "production" and not LEGAL_CONTENT_APPROVED:
    raise ImproperlyConfigured("Approve published privacy, terms and consent before public launch.")
if APP_ENV == "production" and LEGAL_CONTENT_APPROVED:
    required_legal_release_values = {
        "LEGAL_EFFECTIVE_DATE": LEGAL_EFFECTIVE_DATE,
        "LEGAL_PRIVACY_SHA256": LEGAL_PRIVACY_SHA256,
        "LEGAL_TERMS_SHA256": LEGAL_TERMS_SHA256,
        "LEGAL_AGE_SHA256": LEGAL_AGE_SHA256,
        "LEGAL_SUBMISSION_SHA256": LEGAL_SUBMISSION_SHA256,
    }
    missing_legal_release_values = [
        name for name, value in required_legal_release_values.items() if not value
    ]
    if missing_legal_release_values:
        raise ImproperlyConfigured(
            "Published legal release is missing immutable evidence: "
            + ", ".join(missing_legal_release_values)
        )
    if CANDIDATE_REGISTRATION_COUNTRIES != {"IN"}:
        raise ImproperlyConfigured(
            "The approved candidate launch requires CANDIDATE_REGISTRATION_COUNTRIES=IN."
        )
if APP_ENV == "production" and (
    RETENTION_REMINDER_DELIVERY_ENABLED
    or RETENTION_DELETION_ENABLED
    or ANCILLARY_RETENTION_ENABLED
):
    if not LEGAL_CONTENT_APPROVED:
        raise ImproperlyConfigured("Retention automation requires approved legal content.")
    if not LEGAL_BUSINESS_HOLIDAYS:
        raise ImproperlyConfigured(
            "Retention automation requires the approved LEGAL_BUSINESS_HOLIDAYS calendar."
        )

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["talent.authentication.ExpiringTokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "talent.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "login": os.getenv("LOGIN_RATE_LIMIT", "1000/hour" if DEBUG else "10/min"),
        "signup": os.getenv("SIGNUP_RATE_LIMIT", "1000/hour" if DEBUG else "5/hour"),
        "verification": os.getenv(
            "VERIFICATION_RATE_LIMIT", "1000/hour" if DEBUG else "5/hour"
        ),
        "verification_consume": os.getenv(
            "VERIFICATION_CONSUME_RATE_LIMIT", "1000/hour" if DEBUG else "60/hour"
        ),
        "password_reset": os.getenv(
            "PASSWORD_RESET_RATE_LIMIT", "1000/hour" if DEBUG else "5/hour"
        ),
        "password_reset_confirm": os.getenv(
            "PASSWORD_RESET_CONFIRM_RATE_LIMIT", "1000/hour" if DEBUG else "30/hour"
        ),
        "resume_upload": os.getenv(
            "RESUME_UPLOAD_RATE_LIMIT", "1000/hour" if DEBUG else "10/hour"
        ),
        "recruiter_search": os.getenv(
            "RECRUITER_SEARCH_RATE_LIMIT", "1000/hour" if DEBUG else "120/hour"
        ),
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        }
    },
    "filters": {
        "redact_sensitive": {"()": "talent.logging_filters.SensitiveValueFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["redact_sensitive"],
        }
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.server": {"handlers": ["console"], "propagate": False, "level": "WARNING"}
    },
}

if not DEBUG:
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = AUTH_COOKIE_SAMESITE
    CSRF_COOKIE_HTTPONLY = True
