"""Disposable browser fixture, never a production authentication endpoint.

The provider exchange is synthetic. Google signature/claims validation is covered
separately by test_google_oauth.py; this fixture exercises the real local UI/API.
"""

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from unittest.mock import patch


def main():
    if os.environ.get("TESTING") != "true" or os.environ.get("APP_ENV") != "test":
        raise SystemExit("Only an explicit disposable test environment is supported.")
    import django

    django.setup()
    from django.conf import settings
    from django.contrib.auth.models import User
    from django.core.management import call_command
    from django.test import override_settings
    from django.utils import timezone
    from talent import google_signup as signup
    from talent import legal
    from talent.models import CandidateProfile, UserRole

    from tests.test_legal_workflow import published_legal_settings

    database = Path(settings.DATABASES["default"]["NAME"]).resolve()
    if database.parent != Path("/private/tmp") or not database.name.startswith(
        "enter-google-signup-browser-"
    ):
        raise SystemExit("Refusing to use an existing application database.")
    with tempfile.TemporaryDirectory(prefix="enter-google-signup-synthetic-") as temp:
        configuration = published_legal_settings(Path(temp))
        auto = os.environ.get("E2E_AUTOSIGNUP") == "1"
        configuration.update(
            GOOGLE_OAUTH_ENABLED=True,
            GOOGLE_OAUTH_CLIENT_ID="synthetic-browser-client",
            GOOGLE_OAUTH_CLIENT_SECRET="synthetic-browser-secret",
            GOOGLE_OAUTH_REDIRECT_URI="http://127.0.0.1:18012/api/v1/auth/google/callback/",
            GOOGLE_SIGNUP_AUTOCREATE_ENABLED=auto,
        )
        if not auto:
            configuration.update(LEGAL_CONTENT_APPROVED=False, LEGAL_WORKFLOW_PREVIEW=False)
        with override_settings(**configuration):
            if auto:
                review = (
                    settings.BASE_DIR.parent / "review/google-single-button/review-manifest.json"
                )
                approval = {
                    "decision": "approved",
                    "mechanism_id": signup.MECHANISM,
                    "reviewer_name": "SYNTHETIC BROWSER TEST ONLY",
                    "reviewer_role": "TEST FIXTURE",
                    "decision_reference": "NOT REAL APPROVAL",
                    "conditions": "none",
                    "approved_at": timezone.now().isoformat(),
                    "notice_sha256": signup.sha(signup.NOTICE),
                    "review_package_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
                    "documents": {
                        p: {"version": d["version"], "sha256": d["sha256"]}
                        for p, d in legal.documents().items()
                    },
                }
                approval_file = Path(temp) / "synthetic-approval.json"
                approval_file.write_text(json.dumps(approval))
                settings.GOOGLE_SIGNUP_APPROVAL_FILE = str(approval_file)
                settings.GOOGLE_SIGNUP_APPROVAL_SHA256 = hashlib.sha256(
                    approval_file.read_bytes()
                ).hexdigest()
            call_command("migrate", verbosity=0)
            if not User.objects.filter(username="navigation-synthetic@example.test").exists():
                user = User.objects.create_user(
                    username="navigation-synthetic@example.test",
                    email="navigation-synthetic@example.test",
                    password="Synthetic-navigation-password-123!",
                )
                UserRole.objects.create(user=user, role="candidate")
                CandidateProfile.objects.create(
                    user=user,
                    email=user.email,
                    full_name="Synthetic Navigation",
                    email_verified_at=timezone.now(),
                )

            def synthetic_exchange(code, payload):
                if not re.fullmatch(r"synthetic-browser-[a-z0-9-]+", code):
                    raise ValueError("Only synthetic test codes are accepted")
                return {
                    "subject": code,
                    "email": code + "@gmail.com",
                    "full_name": "Synthetic Browser Candidate",
                    "authoritative": True,
                }

            with patch("talent.google_oauth.exchange", side_effect=synthetic_exchange):
                call_command("runserver", "127.0.0.1:18012", use_reloader=False)


if __name__ == "__main__":
    main()
