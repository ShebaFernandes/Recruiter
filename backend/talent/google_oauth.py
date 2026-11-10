"""Candidate OIDC services. No OAuth tokens survive the exchange."""

import hashlib
import logging
import secrets
from datetime import timedelta
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
from authlib.integrations.httpx_client import OAuth2Client
from authlib.oidc.core import CodeIDToken
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from joserfc import jwt
from joserfc.errors import BadSignatureError, InvalidKeyIdError, MissingKeyError
from joserfc.jwk import KeySet
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError

from .models import ExternalIdentity, GoogleOAuthTransaction, UserRole
from .permissions import is_verified_candidate

ISSUER = "https://accounts.google.com"
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
KEYS_URL = "https://www.googleapis.com/oauth2/v3/certs"
BROWSER_COOKIE = "enter_google_browser"
PENDING_COOKIE = "enter_google_pending"
PROOF_COOKIE = "enter_google_proof"


def digest(value):
    return hashlib.sha256(str(value or "").encode()).hexdigest()


def enabled():
    if not settings.GOOGLE_OAUTH_ENABLED:
        raise ValidationError("Google Login is not available. Continue with email and password.")


def eligible(user):
    return bool(
        is_verified_candidate(user)
        and UserRole.objects.filter(user=user, role="candidate").exists()
        and not hasattr(user, "recruiter_profile")
    )


def cookie_name(name):
    return "__Host-" + name if settings.AUTH_COOKIE_SECURE else name


def read_cookie(request, name):
    return request.COOKIES.get(cookie_name(name), "")


def cookie(response, name, value, ttl=600):
    response.set_cookie(
        cookie_name(name),
        value,
        max_age=ttl,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="Lax",
        path="/",
    )


def private(response):
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response


def destination(value):
    from .opportunity_views import OPPORTUNITY_IDS

    if not isinstance(value, str) or not value.startswith("/") or value.startswith("//"):
        return "/"
    url = urlsplit(value)
    if url.scheme or url.netloc or url.fragment or url.path != "/opportunities":
        return "/"
    query = parse_qs(url.query, keep_blank_values=True)
    if set(query) - {"role", "apply"} or any(len(v) != 1 for v in query.values()):
        return "/"
    role = query.get("role", [None])[0]
    apply = query.get("apply", [None])[0]
    if (role is not None and role not in OPPORTUNITY_IDS) or (
        apply is not None and (apply != "1" or not role)
    ):
        return "/"
    canonical = {}
    if role:
        canonical["role"] = role
    if apply:
        canonical["apply"] = apply
    return "/opportunities" + ("?" + urlencode(canonical) if canonical else "")


def client():
    return OAuth2Client(
        settings.GOOGLE_OAUTH_CLIENT_ID,
        settings.GOOGLE_OAUTH_CLIENT_SECRET,
        scope="openid email profile",
        redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI,
        code_challenge_method="S256",
        token_endpoint_auth_method="client_secret_post",
        timeout=10,
        follow_redirects=False,
    )


def begin(request, intent="login", user=None, action="", signup_action=None):
    enabled()
    state, nonce, verifier = (secrets.token_urlsafe(48) for _ in range(3))
    browser = read_cookie(request, BROWSER_COOKIE)
    if len(browser) < 40 or len(browser) > 128:
        browser = secrets.token_urlsafe(48)
    payload = {
        "nonce": nonce,
        "verifier": verifier,
        "intent": intent,
        "action": action,
        "next": destination(request.data.get("next")),
    }
    if signup_action:
        payload["signup_action"] = signup_action
    if user:
        payload["password_hash"] = digest(user.password)
    if intent == "reauth":
        payload["session_hash"] = digest(request.auth.key)
    GoogleOAuthTransaction.objects.create(
        state_hash=digest(state),
        browser_hash=digest(browser),
        payload=payload,
        user=user,
        expires_at=timezone.now()
        + timedelta(seconds=settings.GOOGLE_OAUTH_TRANSACTION_TTL_SECONDS),
    )
    with client() as oauth:
        url, _ = oauth.create_authorization_url(
            AUTHORIZE_URL,
            state=state,
            nonce=nonce,
            code_verifier=verifier,
            prompt="select_account",
            **({"max_age": 0} if intent == "reauth" else {}),
        )
    return url, browser


def jwks(refresh=False):
    keys = None if refresh else cache.get("enter_google_jwks")
    if keys is None:
        response = httpx.get(KEYS_URL, timeout=10, follow_redirects=False)
        response.raise_for_status()
        keys = response.json()
        cache.set("enter_google_jwks", keys, 3600)
    return keys


def verify_token(token, nonce, require_fresh_auth=False):
    # Only Google's fixed JWKS URL is trusted; JWT jku/x5u headers are never followed.
    try:
        decoded = jwt.decode(token["id_token"], KeySet.import_key_set(jwks()), algorithms=["RS256"])
    except (BadSignatureError, InvalidKeyIdError, MissingKeyError):
        decoded = jwt.decode(
            token["id_token"], KeySet.import_key_set(jwks(True)), algorithms=["RS256"]
        )
    claims = CodeIDToken(
        decoded.claims,
        decoded.header,
        options={
            "iss": {"values": [ISSUER, "accounts.google.com"]},
            "aud": {"essential": True, "value": settings.GOOGLE_OAUTH_CLIENT_ID},
        },
        params={
            "nonce": nonce,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "access_token": token.get("access_token"),
        },
    )
    claims.validate(leeway=30)
    if require_fresh_auth:
        auth_time = claims.get("auth_time")
        now = timezone.now().timestamp()
        if not isinstance(auth_time, (int, float)) or not now - 300 <= auth_time <= now + 30:
            raise ValueError("Fresh Google authentication required")
    # Enforce nonce independently even if a provider/library supports optional nonce behavior.
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise ValueError("Invalid nonce")
    if claims.get("email_verified") is not True:
        raise ValueError("Unverified Google email")
    email = str(claims.get("email", "")).strip().lower()
    validate_email(email)
    if (
        len(email) > 150
        or not isinstance(claims.get("sub"), str)
        or not claims["sub"]
        or len(claims["sub"]) > 255
    ):
        raise ValueError("Unsupported identity")
    return {
        "subject": claims["sub"],
        "email": email,
        "full_name": str(claims.get("name") or email.split("@")[0])[:180],
        "authoritative": email.endswith("@gmail.com") or bool(claims.get("hd")),
    }


def exchange(code, payload):
    with client() as oauth:
        token = oauth.fetch_token(TOKEN_URL, code=code, code_verifier=payload["verifier"])
    return verify_token(token, payload["nonce"], require_fresh_auth=payload["intent"] == "reauth")


def take(request, raw_state, stage):
    """Atomic compare-and-swap also prevents duplicate callbacks on SQLite."""
    obj = GoogleOAuthTransaction.objects.filter(
        state_hash=digest(raw_state),
        browser_hash=digest(read_cookie(request, BROWSER_COOKIE)),
        stage=stage,
        expires_at__gt=timezone.now(),
    ).first()
    if not raw_state or not read_cookie(request, BROWSER_COOKIE) or not obj:
        if settings.DEBUG and settings.APP_ENV == "local":
            candidate = GoogleOAuthTransaction.objects.filter(state_hash=digest(raw_state)).first()
            if not raw_state:
                reason = "missing_transaction"
            elif not read_cookie(request, BROWSER_COOKIE):
                reason = "missing_browser_binding"
            elif not candidate:
                reason = "unknown_transaction"
            elif candidate.stage != stage:
                reason = "already_used_or_wrong_stage"
            elif candidate.expires_at <= timezone.now():
                reason = "expired_transaction"
            else:
                reason = "browser_binding_mismatch"
            logging.getLogger(__name__).warning(
                "Google transaction validation rejected: reason=%s", reason
            )
        raise ValidationError("This Google sign-in expired. Please start again.")
    if (
        GoogleOAuthTransaction.objects.filter(pk=obj.pk, stage=stage).update(
            stage="used", payload={}
        )
        != 1
    ):
        raise ValidationError("This Google sign-in was already used.")
    return obj


def pending(request, stage=None):
    obj = GoogleOAuthTransaction.objects.filter(
        state_hash=digest(read_cookie(request, PENDING_COOKIE)),
        browser_hash=digest(read_cookie(request, BROWSER_COOKIE)),
        expires_at__gt=timezone.now(),
        stage__in=["signup", "link", "confirm_link"],
    ).first()
    if not read_cookie(request, PENDING_COOKIE) or not obj or (stage and obj.stage != stage):
        raise ValidationError("This Google sign-in expired. Please start again.")
    return obj


def matching_accounts(email):
    return User.objects.filter(Q(username__iexact=email) | Q(email__iexact=email))


def identity_user(identity):
    row = (
        ExternalIdentity.objects.select_related("user")
        .filter(
            provider="google",
            issuer=ISSUER,
            subject=identity["subject"],
        )
        .first()
    )
    return row.user if row else None


def authenticated(user):
    from .views import _authenticated_response

    if not eligible(user):
        raise ValidationError(
            "This candidate account cannot sign in. Use account verification or support."
        )
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)
    return private(_authenticated_response(user, token))


def reauthentication(request, action):
    """Password fallback or a single-use, session-bound Google proof for this action."""
    if request.user.has_usable_password():
        return request.user.check_password(str(request.data.get("password", "")))
    if not settings.GOOGLE_OAUTH_ENABLED:
        return False
    try:
        obj = take(request, read_cookie(request, PROOF_COOKIE), "proof")
    except ValidationError:
        return False
    return bool(
        obj.user_id == request.user.pk
        and obj.payload.get("action") == action
        and obj.payload.get("session_hash") == digest(request.auth.key)
    )
