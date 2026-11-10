"""Thin HTTP endpoints for candidate-only Google authentication."""

import logging
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.utils import timezone
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import google_oauth as google
from . import google_signup, legal
from .account_security import local_email_shortcuts_enabled, send_verification_email
from .authentication import CsrfProtectedPublicAuthentication
from .models import CandidateProfile, ExternalIdentity, PublishedSignupDocument, UserRole
from .permissions import IsCandidate
from .throttling import LoginRateThrottle, SignupRateThrottle


def redirect(result, next_path="/"):
    return google.private(
        HttpResponseRedirect(
            settings.FRONTEND_URL.rstrip("/")
            + "/auth/google?"
            + urlencode({"result": result, "next": google.destination(next_path)})
        )
    )


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def configuration(request):
    body = {"enabled": settings.GOOGLE_OAUTH_ENABLED}
    browser = None
    if settings.GOOGLE_OAUTH_ENABLED:
        try:
            body["signup_notice"], browser = google_signup.offer(request)
        except google_signup.SignupUnavailable:
            pass
    response = google.private(Response(body))
    if browser:
        google.cookie(response, google.BROWSER_COOKIE, browser)
    return response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def signup_document(request, purpose):
    if purpose not in {"terms", "privacy"}:
        return Response(status=404)
    document = PublishedSignupDocument.objects.filter(
        purpose=purpose,
        version=request.query_params.get("version", ""),
        sha256=request.query_params.get("sha256", ""),
    ).first()
    if not document or google_signup.sha(document.text) != document.sha256:
        return Response(status=404)
    response = HttpResponse(document.text, content_type="text/plain; charset=utf-8")
    response["X-Content-Type-Options"] = "nosniff"
    return google.private(response)


@api_view(["POST"])
@authentication_classes([CsrfProtectedPublicAuthentication])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def start(request):
    try:
        action = google_signup.capture(request)
    except google_signup.SignupUnavailable:
        return google.private(
            Response({"detail": "Signup requirements are unavailable."}, status=503)
        )
    url, browser = google.begin(request, signup_action=action)
    response = google.private(Response({"url": url}))
    google.cookie(response, google.BROWSER_COOKIE, browser)
    return response


@api_view(["POST"])
@authentication_classes([CsrfProtectedPublicAuthentication])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def link_start(request):
    google.enabled()
    email = str(request.data.get("email", "")).strip().lower()
    user = authenticate(request, username=email, password=request.data.get("password", ""))
    if not user or not google.eligible(user):
        raise ValidationError("Sign in to your verified candidate account to connect Google.")
    url, browser = google.begin(request, intent="link", user=user)
    response = google.private(Response({"url": url}))
    google.cookie(response, google.BROWSER_COOKIE, browser)
    return response


@api_view(["POST"])
@permission_classes([IsCandidate])
@throttle_classes([LoginRateThrottle])
def reauth_start(request):
    if not google.eligible(request.user):
        raise ValidationError("Candidate account required.")
    action = request.data.get("action")
    if action not in {"delete_account", "confirm_resume"}:
        raise ValidationError("Choose the account action to confirm.")
    url, browser = google.begin(request, intent="reauth", user=request.user, action=action)
    response = google.private(Response({"url": url}))
    google.cookie(response, google.BROWSER_COOKIE, browser)
    return response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def callback(request):
    phase = "response_validation"
    try:
        google.enabled()
        if any(len(request.query_params.getlist(key)) != 1 for key in ["state"]):
            raise ValueError("Invalid response")
        obj = google.take(request, request.query_params.get("state"), "authorize")
        payload = obj.payload
        if request.query_params.get("error"):
            return redirect("cancelled")
        if len(request.query_params.getlist("code")) != 1:
            raise ValueError("Invalid response")
        phase = "identity_verification"
        identity = google.exchange(request.query_params["code"], payload)
        phase = "account_resolution"
        existing = google.identity_user(identity)
        intent = payload["intent"]
        if intent == "reauth":
            user = obj.user
            from rest_framework.authtoken.models import Token

            token = Token.objects.filter(user=user).first()
            if (
                not user
                or not google.eligible(user)
                or not existing
                or existing.pk != user.pk
                or not token
                or token.created
                <= timezone.now() - timedelta(seconds=settings.AUTH_TOKEN_TTL_SECONDS)
                or payload["session_hash"] != google.digest(token.key)
                or payload["session_hash"]
                != google.digest(request.COOKIES.get(settings.AUTH_COOKIE_NAME))
            ):
                raise ValueError("Invalid reauthentication")
            obj.stage = "proof"
            obj.payload = {"session_hash": payload["session_hash"], "action": payload["action"]}
            obj.expires_at = timezone.now() + timedelta(minutes=5)
            obj.save(update_fields=["stage", "payload", "expires_at"])
            response = redirect("reauthenticated", payload["next"])
            google.cookie(response, google.PROOF_COOKIE, request.query_params["state"], 300)
            return response
        if intent == "link":
            user = obj.user
            if (
                not user
                or not google.eligible(user)
                or payload["password_hash"] != google.digest(user.password)
                or identity["email"].casefold() != user.email.casefold()
                or (existing and existing.pk != user.pk)
            ):
                raise ValueError("Account linking failed")
            obj.stage = "confirm_link"
            obj.payload = {
                **identity,
                "password_hash": payload["password_hash"],
                "next": payload["next"],
            }
        elif existing:
            authenticated = google.authenticated(existing)
            response = redirect("success", payload["next"])
            response.cookies = authenticated.cookies
            return response
        else:
            collision = google.matching_accounts(identity["email"]).exists()
            if not collision and settings.GOOGLE_SIGNUP_AUTOCREATE_ENABLED:
                phase = "automatic_registration"
                try:
                    user = google_signup.register(identity, payload.get("signup_action"), request)
                except google_signup.SignupUnavailable:
                    return redirect("signup_unavailable", payload["next"])
                if user:
                    if user.is_active:
                        authenticated = google.authenticated(user)
                        response = redirect("success", payload["next"])
                        response.cookies = authenticated.cookies
                        return response
                    # Google is not authoritative for third-party mailboxes. Preserve
                    # ENTER's existing email-ownership verification requirement.
                    try:
                        send_verification_email(user)
                    except Exception:
                        pass
                    return redirect("verification_required", payload["next"])
                collision = google.matching_accounts(identity["email"]).exists()
                if not collision:
                    return redirect("failed", payload["next"])
            obj.stage = "link" if collision else "signup"
            obj.payload = {**identity, "next": payload["next"]}
        obj.save(update_fields=["stage", "payload"])
        response = redirect(obj.stage, payload["next"])
        google.cookie(response, google.PENDING_COOKIE, request.query_params["state"])
        return response
    except Exception as exc:
        # Local diagnostics contain only fixed phase labels and exception class names.
        # Never include the exception text, traceback, request, claims or provider response.
        if settings.DEBUG and settings.APP_ENV == "local":
            logging.getLogger(__name__).warning(
                "Google Login failed: phase=%s exception_type=%s", phase, type(exc).__name__
            )
        return redirect("failed")


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def pending(request):
    google.enabled()
    obj = google.pending(request)
    return google.private(
        Response(
            {
                "stage": obj.stage,
                "email": obj.payload["email"],
                "full_name": obj.payload["full_name"],
                "signup_available": legal.enabled(),
            }
        )
    )


@api_view(["POST"])
@authentication_classes([CsrfProtectedPublicAuthentication])
@permission_classes([AllowAny])
@throttle_classes([SignupRateThrottle])
def complete(request):
    google.enabled()
    if settings.GOOGLE_SIGNUP_AUTOCREATE_ENABLED:
        return google.private(
            Response({"detail": "Restart Google signup from the notice."}, status=410)
        )
    if not legal.enabled():
        return google.private(
            Response(
                {
                    "detail": "New candidate signup is unavailable until approved signup "
                    "requirements are configured.",
                    "code": "signup_requirements_unavailable",
                },
                status=503,
            )
        )
    if settings.CANDIDATE_REGISTRATION_PAUSED:
        return google.private(
            Response({"detail": "Candidate registration is temporarily paused."}, status=503)
        )
    # Validate current documents at completion, never trust callback query parameters.
    accepted = {p: legal.validate_acceptance(request.data, p) for p in ["age", "terms"]}
    country = str(request.data.get("country_code", "")).strip().upper()
    if settings.CANDIDATE_REGISTRATION_COUNTRIES and country not in (
        settings.CANDIDATE_REGISTRATION_COUNTRIES
    ):
        raise ValidationError("Candidate registration is currently available only in India.")
    try:
        with transaction.atomic():
            obj = google.take(request, google.read_cookie(request, google.PENDING_COOKIE), "signup")
            identity = obj.payload
            if google.matching_accounts(identity["email"]).exists():
                raise ValidationError(
                    "Use your existing ENTER account, then explicitly connect Google."
                )
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
                registration_country_code=country,
                email_verified_at=timezone.now() if identity["authoritative"] else None,
            )
            ExternalIdentity.objects.create(user=user, subject=identity["subject"])
            for purpose, doc in accepted.items():
                legal.record(user, purpose, doc)
    except IntegrityError:
        raise ValidationError("An account already exists. Sign in and connect Google.") from None
    if user.is_active:
        return google.authenticated(user)
    result = {
        "detail": "Check your email to verify your candidate account.",
        "requires_email_verification": True,
    }
    try:
        url = send_verification_email(user)
        if local_email_shortcuts_enabled():
            result["local_verification_url"] = url
    except Exception:
        result["detail"] = "Account created. Use resend verification to receive a new link."
    return google.private(Response(result, status=201))


@api_view(["POST"])
@authentication_classes([CsrfProtectedPublicAuthentication])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def link_confirm(request):
    google.enabled()
    if request.data.get("confirm") is not True:
        raise ValidationError("Explicitly confirm connecting this Google account.")
    try:
        with transaction.atomic():
            obj = google.take(
                request, google.read_cookie(request, google.PENDING_COOKIE), "confirm_link"
            )
            user = User.objects.select_for_update().get(pk=obj.user_id)
            if not google.eligible(user) or obj.payload["password_hash"] != google.digest(
                user.password
            ):
                raise ValidationError("Account linking expired. Sign in again.")
            ExternalIdentity.objects.create(user=user, subject=obj.payload["subject"])
    except IntegrityError:
        raise ValidationError(
            "This Google account or ENTER account is already connected."
        ) from None
    return google.authenticated(user)
