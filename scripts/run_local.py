"""Start the offline local API, durable worker and frontend together (no deployment)."""
import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def local_environment():
    # These override dotenv: this launcher cannot make paid provider calls.
    os.environ.update({
        "APP_ENV": "local", "DEBUG": "true", "DJANGO_SETTINGS_MODULE": "config.settings",
        "RESUME_AI_ENABLED": "false", "RESUME_AI_EXTERNAL_PROCESSING_APPROVED": "false",
        "AI_PROVIDER": "deterministic", "RESUME_QUEUE_BACKEND": "database",
    })
    sys.path.insert(0, str(ROOT / "backend"))
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    if settings.DATABASES["default"].get("HOST") not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("This launcher requires a local PostgreSQL database.")
    if getattr(settings, "AWS_STORAGE_BUCKET_NAME", ""):
        raise RuntimeError("This launcher requires local private file storage.")
    executor = MigrationExecutor(connection)
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        raise RuntimeError("Apply pending local migrations before starting the platform.")
    connection.close()
    env = dict(os.environ)
    env["MEDIA_ROOT"] = str(settings.MEDIA_ROOT)
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-only", action="store_true",
                        help="Start the missing worker alongside an already-running local UI/API.")
    args = parser.parse_args()
    env = local_environment()
    children = []
    interrupted = False

    def stop(_signum, _frame):
        nonlocal interrupted
        interrupted = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        if not args.worker_only:
            for port in (8010, 5173):
                with socket.socket() as probe:
                    if probe.connect_ex(("127.0.0.1", port)) == 0:
                        raise RuntimeError(f"Port {port} is in use; stop that local server first.")
            children.append(subprocess.Popen(
                [sys.executable, "backend/manage.py", "runserver", "127.0.0.1:8010",
                 "--noreload"], cwd=ROOT, env=env,
            ))
            ui_env = {**env, "VITE_API_URL": "http://127.0.0.1:8010/api/v1"}
            children.append(subprocess.Popen(
                ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173",
                 "--strictPort"], cwd=ROOT / "frontend", env=ui_env,
            ))
        worker_command = [sys.executable, "backend/manage.py", "run_resume_worker"]
        worker = subprocess.Popen(worker_command, cwd=ROOT, env=env)
        print("Local resume worker started; external AI disabled. Ctrl+C stops this session.",
              flush=True)
        failures = 0
        started = time.monotonic()
        while not interrupted:
            if any(child.poll() is not None for child in children):
                raise RuntimeError("A local server stopped. Restart the local stack.")
            if worker.poll() is not None:
                failures = 1 if time.monotonic() - started > 60 else failures + 1
                if failures > 5:
                    raise RuntimeError("Worker repeatedly stopped; inspect local service health.")
                print("Local worker stopped; restarting with backoff.", flush=True)
                time.sleep(min(30, 2 ** failures))
                if interrupted:
                    break
                worker = subprocess.Popen(worker_command, cwd=ROOT, env=env)
                started = time.monotonic()
            time.sleep(0.5)
    finally:
        if 'worker' in locals():
            children.append(worker)
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Do not print connection strings or parser/provider exception contents.
        print(f"Local startup stopped ({type(error).__name__}). "
              "Check local DB, migrations and ports.", file=sys.stderr)
        raise SystemExit(1) from None
