"""Local browser tests with disposable DB/media, no real mail and no external AI."""
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def wait_for(url, process):
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError("Isolated server exited; inspect test log.")
        try:
            urllib.request.urlopen(url, timeout=1).close()
            return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError("Isolated server did not start.")


if __name__ == "__main__":
    api_port = int(os.environ.get("E2E_API_PORT", "8025"))
    api_origin = f"http://127.0.0.1:{api_port}"
    os.environ.update({
        "DJANGO_SETTINGS_MODULE": "config.settings", "APP_ENV": "test", "DEBUG": "true",
        "TESTING": "true", "AI_PROVIDER": "deterministic", "OPENAI_API_KEY": "",
        "ANTHROPIC_API_KEY": "", "RESUME_AI_ENABLED": "false",
        "RESUME_AI_EXTERNAL_PROCESSING_APPROVED": "false",
        "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
        "EXPOSE_LOCAL_EMAIL_LINKS": "true", "RESUME_QUEUE_BACKEND": "database",
        "RESUME_SCANNER_BACKEND": "development",
        "ALLOWED_HOSTS": "127.0.0.1,localhost,testserver",
        "CORS_ALLOWED_ORIGINS": "http://127.0.0.1:5175",
        "CSRF_TRUSTED_ORIGINS": "http://127.0.0.1:5175",
        "FRONTEND_URL": "http://127.0.0.1:5175", "AUTH_COOKIE_SECURE": "false",
        "PLAYWRIGHT_BASE_URL": "http://127.0.0.1:5175",
        "PLAYWRIGHT_API_URL": f"{api_origin}/api/v1",
        "VITE_API_URL": f"{api_origin}/api/v1",
        "SECURE_SSL_REDIRECT": "false",
    })
    if os.environ.get("E2E_REAL_CLAMAV") == "1":
        port = int(os.environ.get("E2E_CLAMAV_PORT", "33310"))
        if not 1024 <= port <= 65535:
            raise SystemExit("The isolated ClamAV port must be unprivileged and local.")
        os.environ.update({
            "RESUME_SCANNER_BACKEND": "clamav", "CLAMAV_HOST": "127.0.0.1",
            "CLAMAV_PORT": str(port),
        })
    if os.environ.get("E2E_PUBLISHED_LEGAL") == "1":
        # Exercise the published candidate flow with the repository's approved
        # public copy. Keep the hashes pinned so a changed document fails closed.
        allowed = {
            "LEGAL_EFFECTIVE_DATE", "LEGAL_PRIVACY_VERSION", "LEGAL_TERMS_VERSION",
            "LEGAL_AGE_VERSION", "LEGAL_SUBMISSION_VERSION",
            "LEGAL_PRIVACY_SHA256", "LEGAL_TERMS_SHA256", "LEGAL_AGE_SHA256",
            "LEGAL_SUBMISSION_SHA256",
        }
        example = ROOT / "deploy" / "production.env.example"
        public_legal = dict(
            line.split("=", 1) for line in example.read_text().splitlines()
            if line.split("=", 1)[0] in allowed
        )
        # The original production example predates the approved Gemini-aware
        # privacy/terms publication. Use the matching approved overlay for those
        # public hashes and versions; the backend still verifies the actual copy.
        overlay_keys = {
            "LEGAL_PRIVACY_VERSION", "LEGAL_TERMS_VERSION",
            "LEGAL_PRIVACY_SHA256", "LEGAL_TERMS_SHA256",
            "LEGAL_RESUME_AI_VERSION", "LEGAL_RESUME_AI_SHA256",
        }
        overlay = ROOT / "deploy" / "compose.gemini-publication.yaml"
        updated_legal = dict(
            (key.strip(), value.strip().strip('"'))
            for line in overlay.read_text().splitlines()
            if ":" in line
            for key, value in [line.split(":", 1)]
            if key.strip() in overlay_keys
        )
        if set(updated_legal) != overlay_keys or not all(updated_legal.values()):
            raise SystemExit("Approved legal overlay is incomplete.")
        public_legal.update(updated_legal)
        required_legal = allowed | {"LEGAL_RESUME_AI_VERSION", "LEGAL_RESUME_AI_SHA256"}
        if set(public_legal) != required_legal or not all(public_legal.values()):
            raise SystemExit("Published legal test configuration is incomplete.")
        os.environ.update(public_legal)
        os.environ.update({
            "LEGAL_CONTENT_APPROVED": "true", "LEGAL_WORKFLOW_PREVIEW": "false",
            "LEGAL_RESUME_AI_APPROVED": "true", "VITE_LEGAL_CONTENT_APPROVED": "true",
        })
    else:
        os.environ.update({
            "LEGAL_CONTENT_APPROVED": "false", "LEGAL_WORKFLOW_PREVIEW": "false",
            "LEGAL_RESUME_AI_APPROVED": "false", "VITE_LEGAL_CONTENT_APPROVED": "false",
        })
    os.environ.pop("AWS_STORAGE_BUCKET_NAME", None)
    import django

    django.setup()
    from django.conf import settings
    from django.test.utils import setup_databases, teardown_databases

    database = "test_enter_e2e_" + uuid.uuid4().hex[:12]
    settings.DATABASES["default"]["TEST"]["NAME"] = database
    old = setup_databases(verbosity=0, interactive=False)
    url = urlsplit(os.environ["DATABASE_URL"])
    os.environ["DATABASE_URL"] = urlunsplit(url._replace(path="/" + database))
    processes = []
    try:
        with tempfile.TemporaryDirectory(prefix="enter-e2e-private-") as media:
            os.environ["MEDIA_ROOT"] = media
            with tempfile.TemporaryFile(mode="w+") as log:
                api = subprocess.Popen(
                    [sys.executable, "manage.py", "runserver", f"127.0.0.1:{api_port}",
                     "--noreload"],
                    cwd=ROOT / "backend", stdout=log, stderr=log, start_new_session=True,
                )
                processes.append(api)
                ui = subprocess.Popen(
                    ["npm", "run", "dev", "--", "--host", "127.0.0.1",
                     "--port", "5175", "--strictPort"],
                    cwd=ROOT / "frontend", stdout=log, stderr=log, start_new_session=True,
                )
                processes.append(ui)
                wait_for(f"{api_origin}/api/v1/health/", api)
                wait_for("http://127.0.0.1:5175/", ui)
                if os.environ.get("E2E_START_WORKER") == "1":
                    processes.append(subprocess.Popen(
                        [sys.executable, "manage.py", "run_resume_worker"],
                        cwd=ROOT / "backend", stdout=log, stderr=log, start_new_session=True,
                    ))
                result = subprocess.run(
                    ["npx", "playwright", "test", *sys.argv[1:]],
                    cwd=ROOT / "frontend", check=False,
                )
                code = result.returncode
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
        teardown_databases(old, verbosity=0)
    raise SystemExit(code)
