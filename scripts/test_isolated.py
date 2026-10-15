"""Run backend tests in a unique disposable PostgreSQL DB, never the development DB."""
import os
import sys
import tempfile
import uuid
from pathlib import Path

os.environ.update({
    "DJANGO_SETTINGS_MODULE": "config.settings", "APP_ENV": "test", "DEBUG": "true",
    "TESTING": "true", "AI_PROVIDER": "deterministic", "OPENAI_API_KEY": "",
    "OPENROUTER_API_KEY": "", "RESUME_AI_ENABLED": "false",
    "RESUME_AI_EXTERNAL_PROCESSING_APPROVED": "false",
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "RESUME_QUEUE_BACKEND": "database", "RESUME_SCANNER_BACKEND": "development",
    "SECURE_SSL_REDIRECT": "false", "AUTH_COOKIE_SECURE": "false",
    "ALLOWED_HOSTS": "127.0.0.1,localhost,testserver",
    "FRONTEND_URL": "http://127.0.0.1:5173",
    "CORS_ALLOWED_ORIGINS": "http://127.0.0.1:5173,http://localhost:5173",
    "CSRF_TRUSTED_ORIGINS": "http://127.0.0.1:5173,http://localhost:5173",
})
os.environ.pop("AWS_STORAGE_BUCKET_NAME", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

if __name__ == "__main__":
    if not os.environ.get("DATABASE_URL", "").startswith(("postgresql://", "postgres://")):
        raise SystemExit(
            "Set DATABASE_URL to the local PostgreSQL server; SQLite is not supported."
        )
    import django
    import pytest

    django.setup()
    from django.conf import settings

    settings.DATABASES["default"]["TEST"]["NAME"] = "test_enter_launch_" + uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix="enter-launch-tests-") as media:
        settings.MEDIA_ROOT = media
        raise SystemExit(pytest.main(["-q", "-o", f"cache_dir={media}/pytest", *sys.argv[1:]]))
