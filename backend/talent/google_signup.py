"""Approved notice-bound Google signup. All release gates default to closed."""

import hashlib
import json
import secrets
import uuid
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from . import google_oauth as google
from . import legal
from .models import (
    CandidateProfile,
    ExternalIdentity,
    GoogleOAuthTransaction,
    GoogleSignupEvidence,
    LegalAcceptance,
    PublishedSignupDocument,
    UserRole,
)

NOTICE_VERSION = "enter-google-signup-notice-draft-02"
MECHANISM = "enter-google-signup-button-draft-02"
METHOD = "notice_bound_google_button_v1"
NOTICE = (
    "For new accounts, selecting “Continue with Google” means you agree to ENTER’s Terms, "
    "declare that you are at least 18, and select India as your registration country. "
    "These are your declarations; Google sign-in does not verify your age or registration "
    "country for ENTER. Read our Privacy Policy."
)


class SignupUnavailable(Exception):
    """Configuration and audit details are never included in public error bodies."""


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def release():
    if not settings.GOOGLE_SIGNUP_AUTOCREATE_ENABLED:
        raise SignupUnavailable()
    try:
        if not legal.published() or not settings.GOOGLE_SIGNUP_APPROVAL_SHA256:
            raise SignupUnavailable()
        raw = Path(settings.GOOGLE_SIGNUP_APPROVAL_FILE).read_bytes()
        if hashlib.sha256(raw).hexdigest() != settings.GOOGLE_SIGNUP_APPROVAL_SHA256:
            raise SignupUnavailable()
        approval = json.loads(raw)
        required = [
            "reviewer_name",
            "reviewer_role",
            "decision_reference",
            "approved_at",
            "review_package_sha256",
        ]
        if any(not isinstance(approval.get(k), str) or not approval[k].strip() for k in required):
            raise SignupUnavailable()
        scope = approval.get("release_scope")
        if scope not in {None, "local_testing_and_staging_validation"}:
            raise SignupUnavailable()
        if scope and settings.APP_ENV not in {"local", "test", "staging"}:
            raise SignupUnavailable()
        if approval.get("effective_date") and (
            approval["effective_date"] != settings.LEGAL_EFFECTIVE_DATE
        ):
            raise SignupUnavailable()
        approved_at = parse_datetime(approval["approved_at"])
        if (
            approval.get("decision") != "approved"
            or approval.get("mechanism_id") != MECHANISM
            or approval.get("notice_sha256") != sha(NOTICE)
            or not approved_at
            or timezone.is_naive(approved_at)
            or approved_at > timezone.now()
            or approval.get("conditions") != "none"
        ):
            raise SignupUnavailable()
        # Pin the exact review package; an unrelated approval cannot authorize this action.
        review = settings.BASE_DIR.parent / "review/google-single-button/review-manifest.json"
        if hashlib.sha256(review.read_bytes()).hexdigest() != approval["review_package_sha256"]:
            raise SignupUnavailable()
        manifest = json.loads(review.read_bytes())
        for filename, digest in manifest["draft_files"].items():
            if hashlib.sha256((review.parent / filename).read_bytes()).hexdigest() != digest:
                raise SignupUnavailable()
        docs = legal.documents()
        if any(
            approval.get("documents", {}).get(p)
            != {
                "version": docs[p]["version"],
                "sha256": docs[p]["sha256"],
            }
            for p in ["terms", "privacy", "age", "submission"]
        ):
            raise SignupUnavailable()
        return {
            "approval_sha256": settings.GOOGLE_SIGNUP_APPROVAL_SHA256,
            "notice_sha256": sha(NOTICE),
            "documents": docs,
        }
    except SignupUnavailable:
        raise
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OverflowError,
        ValidationError,
    ):
        raise SignupUnavailable() from None


def public_document(doc, purpose):
    snapshot, _ = PublishedSignupDocument.objects.get_or_create(
        purpose=purpose,
        version=doc["version"],
        sha256=doc["sha256"],
        defaults={"text": doc["text"]},
    )
    if snapshot.text != doc["text"]:
        raise SignupUnavailable()
    return (
        "/api/v1/auth/google/documents/"
        + purpose
        + "/?"
        + urlencode(
            {
                "version": snapshot.version,
                "sha256": snapshot.sha256,
            }
        )
    )


def offer(request):
    current = release()
    browser = google.read_cookie(request, google.BROWSER_COOKIE)
    if not 40 <= len(browser) <= 128:
        browser = secrets.token_urlsafe(48)
    challenge = secrets.token_urlsafe(48)
    docs = current["documents"]
    # Only approved public text is archived. Candidate records and audit-person
    # information are never exposed by the document endpoint.
    links = {p: public_document(docs[p], p) for p in ["terms", "privacy"]}
    GoogleOAuthTransaction.objects.create(
        state_hash=google.digest(challenge),
        browser_hash=google.digest(browser),
        stage="notice",
        payload=current,
        expires_at=timezone.now() + timedelta(seconds=600),
    )
    return {
        "text": NOTICE,
        "version": NOTICE_VERSION,
        "challenge": challenge,
        "terms_url": links["terms"],
        "privacy_url": links["privacy"],
    }, browser


def capture(request):
    raw = request.data.get("notice_challenge")
    if not raw:
        return None  # Existing linked candidates may still sign in without signup evidence.
    obj = google.take(request, raw, "notice")
    current = release()
    if obj.payload != current or request.data.get("notice_version") != NOTICE_VERSION:
        raise ValidationError("Signup wording changed. Review the notice and start again.")
    received = timezone.now()
    return {
        **current,
        "action_id": str(uuid.uuid4()),
        "received_at": received.isoformat(),
        "notice_version": NOTICE_VERSION,
        "notice_text": NOTICE,
        "method": METHOD,
        "age_self_declared": True,
        "country_code": "IN",
    }


def register(identity, action, request):
    current = release()
    if not action or any(action.get(k) != current[k] for k in current):
        raise SignupUnavailable()
    received = parse_datetime(action.get("received_at", ""))
    if (
        not received
        or timezone.is_naive(received)
        or not timezone.now() - timedelta(minutes=10) <= received <= timezone.now()
        or action.get("notice_text") != NOTICE
        or action.get("notice_version") != NOTICE_VERSION
        or action.get("method") != METHOD
        or action.get("age_self_declared") is not True
        or action.get("country_code") != "IN"
    ):
        raise SignupUnavailable()
    if settings.CANDIDATE_REGISTRATION_PAUSED:
        raise SignupUnavailable()
    countries = settings.CANDIDATE_REGISTRATION_COUNTRIES
    if countries and "IN" not in countries:
        raise SignupUnavailable()
    # Apply the normal shared signup quota on the callback too.
    from .throttling import SignupRateThrottle

    throttle = SignupRateThrottle()
    if not throttle.allow_request(request, None):
        raise SignupUnavailable()
    docs = action["documents"]
    try:
        with transaction.atomic():
            if google.matching_accounts(identity["email"]).exists():
                return None  # A password signup won a race: require explicit linking.
            user = User.objects.create_user(
                username=identity["email"],
                email=identity["email"],
                password=None,
                is_active=identity["authoritative"],
            )
            UserRole.objects.create(user=user, role="candidate")
            CandidateProfile.objects.create(
                user=user,
                email=identity["email"],
                full_name=identity["full_name"],
                registration_country_code="IN",
                email_verified_at=timezone.now() if identity["authoritative"] else None,
            )
            ExternalIdentity.objects.create(user=user, subject=identity["subject"])
            accepted = {}
            for purpose in ["terms", "age"]:
                doc = docs[purpose]
                accepted[purpose] = LegalAcceptance.objects.create(
                    user=user,
                    subject_user_id=user.pk,
                    subject_joined_at=user.date_joined,
                    purpose=purpose,
                    version=doc["version"],
                    document_text=doc["text"],
                    document_sha256=doc["sha256"],
                    unpublished=False,
                    accepted_at=received,
                )
            GoogleSignupEvidence.objects.create(
                action_id=action["action_id"],
                terms_acceptance=accepted["terms"],
                age_acceptance=accepted["age"],
                method=METHOD,
                received_at=received,
                account_created_at=user.date_joined,
                notice_version=NOTICE_VERSION,
                notice_text=NOTICE,
                notice_sha256=sha(NOTICE),
                privacy_version=docs["privacy"]["version"],
                privacy_text=docs["privacy"]["text"],
                privacy_sha256=docs["privacy"]["sha256"],
                country_code="IN",
                age_self_declared=True,
                approval_sha256=current["approval_sha256"],
            )
            return user
    except IntegrityError:
        # Never merge users or replace an existing identity after a concurrency conflict.
        return None
