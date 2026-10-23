"""One read-only launch check. Run only against the paused production stack."""

import json
import os
import stat
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

PUBLIC_ORIGIN = "https://enter.careers"
MAX_BACKUP_AGES = {"hourly": 2 * 3600, "daily": 26 * 3600, "recovery": 35 * 86400}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


HTTP = urllib.request.build_opener(NoRedirect)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def backup_marker_path(base, kind):
    return base.with_name(f"{base.stem}-{kind}{base.suffix}")


def verify_backup_marker(path, kind, now=None):
    now = time.time() if now is None else now
    require(path.is_absolute(), "Backup evidence path must be absolute")
    require(path.is_file() and not path.is_symlink(), f"Verified {kind} backup evidence is missing")
    require(stat.S_IMODE(path.stat().st_mode) & 0o077 == 0, "Backup evidence must be private")
    data = json.loads(path.read_text())
    require(data.get("class") == kind, f"Verified {kind} backup class is invalid")
    require(
        0 <= now - float(data["verified_at"]) <= MAX_BACKUP_AGES[kind],
        f"Verified {kind} backup is stale",
    )
    require(
        isinstance(data.get("key"), str) and data["key"],
        f"Verified {kind} backup key is missing",
    )
    require(
        isinstance(data.get("sha256"), str)
        and len(data["sha256"]) == 64
        and all(character in "0123456789abcdef" for character in data["sha256"].lower()),
        f"Verified {kind} backup checksum is invalid",
    )
    require(int(data.get("bytes", 0)) > 0, f"Verified {kind} backup is empty")


def fetch(path, method="GET"):
    request = urllib.request.Request(
        PUBLIC_ORIGIN + path,
        method=method,
        headers={"User-Agent": "ENTER-Candidate-Launch-Check/1.0"},
    )
    try:
        with HTTP.open(request, timeout=15) as response:
            return response.status, response.headers, response.read(65537)
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read(65537)


def verify_https():
    status, headers, body = fetch("/")
    require(status == 200 and len(body) <= 65536, "Public HTTPS frontend is unavailable")
    require(b'<div id="root"' in body, "Public HTTPS frontend response is unexpected")
    require("text/html" in headers.get("Content-Type", "").lower(), "Frontend is not HTML")

    status, headers, body = fetch("/api/v1/health/ready/")
    require(status == 200 and len(body) <= 65536, "Public HTTPS readiness is unavailable")
    require("application/json" in headers.get("Content-Type", "").lower(), "Readiness is not JSON")
    readiness = json.loads(body)
    require(
        readiness.get("status") == "ready" and readiness.get("database") == "ok",
        "Public application is not ready",
    )

    status, _, _ = fetch("/recruiter")
    require(status == 404, "Recruiter surface is not disabled")
    status, _, _ = fetch("/api/v1/auth/signup/", method="POST")
    require(status == 503, "Registration is not paused")
    status, _, _ = fetch("/api/v1/candidate/resumes/", method="POST")
    require(status == 503, "Resume intake is not paused")

    status, headers, body = fetch("/api/v1/legal/documents/")
    require(status == 200 and len(body) <= 65536, "Published legal documents are unavailable")
    require(headers.get("X-Robots-Tag") == "index, follow", "Legal documents are not published")
    documents = json.loads(body).get("documents", {})
    require(
        set(documents) == {"age", "terms", "privacy", "submission"}
        and all(not item.get("unpublished") for item in documents.values()),
        "Published legal document set is invalid",
    )


def verify_runtime():
    env_file = os.environ.get("ENTER_ENV_FILE", ".env.production")
    command = [
        "docker",
        "compose",
        "--project-name",
        "recruiter",
        "--env-file",
        env_file,
        "-f",
        "compose.production.yaml",
        "exec",
        "-T",
        "backend",
        "python",
        "manage.py",
        "candidate_launch_runtime_check",
    ]
    subprocess.run(command, check=True, timeout=60)


def main():
    require(Path("compose.production.yaml").is_file(), "Run from the ENTER repository root")
    base_value = os.environ.get("ENTER_BACKUP_STATE_FILE", "")
    require(base_value, "ENTER_BACKUP_STATE_FILE is required")
    base = Path(base_value)
    now = time.time()
    for kind in MAX_BACKUP_AGES:
        verify_backup_marker(backup_marker_path(base, kind), kind, now)
    verify_runtime()
    verify_https()
    print(
        json.dumps(
            {
                "candidate_launch_check": "PASS",
                "registration": "paused",
                "recruiter_access": "disabled",
                "https": "verified",
                "backup_recovery": "verified",
            }
        )
    )


if __name__ == "__main__":
    main()
