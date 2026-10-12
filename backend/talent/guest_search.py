"""Anonymous hiring-brief interpretation. Never queries or serializes candidates.

Briefs are short-lived signed capabilities bound to an HttpOnly browser cookie;
they are NOT recruiter credentials and cannot authorize any existing endpoint.
"""

import hashlib
import secrets

from django.conf import settings
from django.core import signing
from django.utils import timezone
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import RateLimitBucket
from .search_understanding import (
    SearchUnderstandingUnavailable,
    continue_search,
    understand_search,
)
from .throttling import DatabaseRateThrottle

COOKIE = "enter_guest_search"
SALT = "enter.guest-search.v1"
TTL = 1800
MAX_ANSWERS = 5


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class GuestIPBurst(DatabaseRateThrottle):
    scope = "guest_ip_burst"

    def get_rate(self):
        return settings.GUEST_SEARCH_RATES[self.scope]


class GuestIPDaily(GuestIPBurst):
    scope = "guest_ip_daily"


class GuestGlobalBurst(GuestIPBurst):
    scope = "guest_global_burst"

    def get_cache_key(self, request, view):
        return digest(self.scope)


class GuestGlobalDaily(GuestGlobalBurst):
    scope = "guest_global_daily"


class GuestBrowserDaily(GuestIPBurst):
    scope = "guest_browser_daily"

    def get_cache_key(self, request, view):
        return digest(f"{self.scope}:{request.guest_browser}")


class BriefInput(serializers.Serializer):
    request_id = serializers.UUIDField()
    query = serializers.CharField(max_length=2000, trim_whitespace=False)

    def validate_query(self, value):
        if not value.strip():
            raise serializers.ValidationError("Describe the role you want to hire for.")
        return value


class AnswerInput(serializers.Serializer):
    token = serializers.CharField(max_length=24000)
    answer = serializers.CharField(max_length=500)


def safe_response(data, status=200, browser=None):
    response = Response(data, status=status)
    response["Cache-Control"] = "private, no-store"
    if browser:
        response.set_cookie(
            COOKIE, browser, max_age=TTL, httponly=True,
            secure=settings.AUTH_COOKIE_SECURE, samesite=settings.AUTH_COOKIE_SAMESITE,
            path="/api/v1/guest/",
        )
    return response


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([GuestIPBurst, GuestIPDaily])
def guest_search(request, answering=False):
    # DRF api_view is csrf_exempt; an outer Django decorator is insufficient.
    # Enforce CSRF explicitly even though no authenticated account is required.
    SessionAuthentication().enforce_csrf(request)
    if not settings.GUEST_SEARCH_ENABLED:
        return safe_response({
            "detail": "Guest search is not available here yet.", "code": "guest_search_disabled",
        }, 503)
    serializer = AnswerInput(data=request.data) if answering else BriefInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    browser = request.COOKIES.get(COOKIE, "")
    if len(browser) != 64:
        browser = secrets.token_hex(32)
    request.guest_browser = browser
    owner = digest(browser)
    state = None
    if answering:
        try:
            state = signing.loads(serializer.validated_data["token"], salt=SALT, max_age=TTL)
            if state["owner"] != owner:
                raise signing.BadSignature()
        except (signing.BadSignature, KeyError, TypeError):
            return safe_response({
                "detail": "This search has expired. Please start a new search.",
                "code": "guest_search_expired",
            }, 410)
        if not state["question"] or len(state["history"]) >= MAX_ANSWERS:
            return safe_response({
                "detail": "Please start a new search with your updated requirements.",
                "code": "guest_search_complete",
            }, 409)

    # All attempts, including upstream failures, consume these shared DB quotas.
    # Cookie rotation does not bypass the IP or application-wide limits.
    for throttle_type in (GuestBrowserDaily, GuestGlobalBurst, GuestGlobalDaily):
        limiter = throttle_type()
        if not limiter.allow_request(request, None):
            response = safe_response({
                "detail": "Guest search has reached its request limit. Please try again later.",
                "code": "guest_search_limited",
            }, 429, browser)
            response["Retry-After"] = str(limiter.wait())
            return response

    # A signed clarification token can be consumed only once. This also stops
    # double-clicks/concurrent replays from making duplicate provider requests.
    operation = (serializer.validated_data["token"] if answering
                 else f"{browser}:{serializer.validated_data['request_id']}")
    key = digest(f"guest-operation:{operation}")
    _, created = RateLimitBucket.objects.get_or_create(
        key=key, defaults={"count": 1, "window_started_at": timezone.now()},
    )
    if not created:
        return safe_response({
            "detail": "This request was already submitted. Continue the current search or "
                      "start a new search with updated wording.",
            "code": "guest_search_duplicate",
        }, 409, browser)
    try:
        if state:
            answer = serializer.validated_data["answer"]
            result = continue_search(
                state["query"], state["criteria"], state["question"], answer,
                history=state["history"],
            )
            history = [*state["history"], {"question": state["question"], "answer": answer}]
            query = state["query"]
        else:
            query = serializer.validated_data["query"]
            result = understand_search(query)
            history = []
        if result.source not in {"openai", "openrouter"}:
            raise SearchUnderstandingUnavailable(
                "Guest search requires an available AI provider.", code="guest_ai_unavailable",
            )
    except SearchUnderstandingUnavailable as error:
        # Explicit user retry is possible; never retry the provider automatically.
        RateLimitBucket.objects.filter(key=key).delete()
        response = safe_response({"detail": str(error), "code": error.code},
                                 error.status_code, browser)
        if error.retry_after:
            response["Retry-After"] = str(error.retry_after)
        return response
    token = signing.dumps({
        "id": state["id"] if state else str(serializer.validated_data["request_id"]),
        "owner": owner, "query": query, "criteria": result.criteria,
        "question": result.follow_up_question, "history": history,
    }, salt=SALT, compress=True)
    return safe_response({
        "id": "guest", "token": token, "query": query, "criteria": result.criteria,
        "state": "needs_clarification" if result.follow_up_question else "complete",
        "follow_up_question": result.follow_up_question,
        "follow_up_options": result.follow_up_options,
        "understanding_source": result.source,
        "understanding_model": result.model,
    }, browser=browser)
