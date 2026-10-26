import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass

from django.conf import settings


class AIProviderError(Exception):
    kind = "unavailable"

    def __init__(
        self,
        message="AI provider unavailable.",
        retry_after=None,
        *,
        stage="provider_request",
        request_id="",
        provider="",
        model="",
        input_tokens=0,
        output_tokens=0,
        stop_reason="",
        usage_confirmed=False,
        http_status=None,
        provider_error_code="",
        provider_error_status="",
        latency_ms=0,
    ):
        super().__init__(message)
        self.retry_after = retry_after
        # Safe diagnostics only. Provider messages and response content are deliberately
        # excluded because they can contain document data.
        self.stage = stage
        self.request_id = request_id
        self.provider = provider
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.stop_reason = stop_reason
        self.usage_confirmed = usage_confirmed
        self.http_status = http_status
        self.provider_error_code = provider_error_code
        self.provider_error_status = provider_error_status
        self.latency_ms = latency_ms


class AIProviderRateLimited(AIProviderError):
    kind = "rate_limited"


class AIProviderTimeout(AIProviderError):
    kind = "timeout"


class AIProviderMalformedResponse(AIProviderError):
    kind = "malformed_response"


class AIProviderUnavailable(AIProviderError):
    kind = "unavailable"


class AIProviderInvalidRequest(AIProviderUnavailable):
    kind = "invalid_request"


class AIProviderAuthenticationError(AIProviderUnavailable):
    kind = "authentication_error"


class AIProviderPermissionDenied(AIProviderUnavailable):
    kind = "permission_denied"


class AIProviderNotFound(AIProviderUnavailable):
    kind = "not_found"


@dataclass(frozen=True)
class AIProviderResult:
    data: dict
    provider: str
    model: str
    request_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str = ""
    http_status: int | None = None
    latency_ms: int = 0


class _HTTPPayload(dict):
    """JSON object plus non-sensitive transport metadata."""

    def __init__(self, value, request_id="", http_status=200, latency_ms=0):
        super().__init__(value)
        self.request_id = request_id
        self.http_status = http_status
        self.latency_ms = latency_ms


def _retry_after(headers):
    value = headers.get("Retry-After") if headers else None
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 30


def _request_id(payload, headers):
    if isinstance(payload, dict) and payload.get("request_id"):
        return str(payload["request_id"])
    if headers:
        for name in ("request-id", "x-request-id", "x-goog-request-id"):
            value = headers.get(name)
            if value:
                return str(value)
    return ""


def _safe_provider_error(payload):
    """Return only non-sensitive machine-readable provider error identifiers."""
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return "", ""
    code = error.get("code")
    status = error.get("status")
    safe_code = str(code) if isinstance(code, (str, int)) else ""
    safe_status = str(status) if isinstance(status, str) else ""
    return safe_code[:80], safe_status[:80]


def _post_json(url, body, headers, timeout):
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            response_headers = getattr(response, "headers", None)
            request_id = _request_id(payload, response_headers)
            http_status = int(getattr(response, "status", 200) or 200)
    except urllib.error.HTTPError as exc:
        error_payload = {}
        try:
            error_payload = json.loads(exc.read().decode("utf-8"))
        except (AttributeError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass
        provider_error_code, provider_error_status = _safe_provider_error(error_payload)
        metadata = {
            "stage": "http_error",
            "request_id": _request_id(error_payload, exc.headers),
            "http_status": int(exc.code),
            "provider_error_code": provider_error_code,
            "provider_error_status": provider_error_status,
            "latency_ms": round((time.monotonic() - started) * 1000),
        }
        if exc.code == 429:
            raise AIProviderRateLimited(
                retry_after=_retry_after(exc.headers), **metadata
            ) from exc
        if exc.code in {408, 504}:
            raise AIProviderTimeout(**metadata) from exc
        error_class = {
            400: AIProviderInvalidRequest,
            401: AIProviderAuthenticationError,
            403: AIProviderPermissionDenied,
            404: AIProviderNotFound,
        }.get(exc.code, AIProviderUnavailable)
        raise error_class(**metadata) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise AIProviderTimeout(
            latency_ms=round((time.monotonic() - started) * 1000)
        ) from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise AIProviderTimeout(
                latency_ms=round((time.monotonic() - started) * 1000)
            ) from exc
        raise AIProviderUnavailable(
            latency_ms=round((time.monotonic() - started) * 1000)
        ) from exc
    except OSError as exc:
        raise AIProviderUnavailable(
            latency_ms=round((time.monotonic() - started) * 1000)
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        response_headers = getattr(locals().get("response"), "headers", None)
        raise AIProviderMalformedResponse(
            stage="http_response_json",
            request_id=_request_id({}, response_headers),
            http_status=int(getattr(locals().get("response"), "status", 200) or 200),
            latency_ms=round((time.monotonic() - started) * 1000),
        ) from exc
    if not isinstance(payload, dict):
        raise AIProviderMalformedResponse(
            stage="http_response_json",
            request_id=request_id,
            http_status=http_status,
            latency_ms=round((time.monotonic() - started) * 1000),
        )
    return _HTTPPayload(
        payload,
        request_id=request_id,
        http_status=http_status,
        latency_ms=round((time.monotonic() - started) * 1000),
    )


def _json_content(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        raise AIProviderMalformedResponse()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise AIProviderMalformedResponse() from exc
    if not isinstance(payload, dict):
        raise AIProviderMalformedResponse()
    return payload


def _anthropic_schema(schema):
    """Remove constraints Anthropic structured outputs do not compile.

    The original schema is still enforced by the application after the response,
    including its string and array length bounds.
    """
    if isinstance(schema, dict):
        return {
            key: _anthropic_schema(value)
            for key, value in schema.items()
            if key not in {"maxLength", "maxItems"}
        }
    if isinstance(schema, list):
        return [_anthropic_schema(value) for value in schema]
    return schema


def _gemini_schema(schema):
    """Build a low-complexity Gemini JSON response schema.

    Gemini ignores string/property length bounds during constrained decoding and can
    reject schemas whose grammar has too many states. Keep closed-object constraints,
    however: without them Gemini is allowed to emit keys that ENTER's strict application
    schema must reject. ENTER still validates the complete original schema after decoding.
    """
    omitted_constraints = {
        "contains",
        "default",
        "example",
        "examples",
        "maxContains",
        "maxItems",
        "maxLength",
        "maxProperties",
        "minContains",
        "minItems",
        "minLength",
        "minProperties",
        "pattern",
        "uniqueItems",
    }
    if isinstance(schema, dict):
        return {
            key: _gemini_schema(value)
            for key, value in schema.items()
            if key not in omitted_constraints
        }
    if isinstance(schema, list):
        return [_gemini_schema(value) for value in schema]
    return schema


class StructuredAIProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def generate(self, instructions, input_payload, schema, schema_name):
        raise NotImplementedError


class OpenAIResponsesProvider(StructuredAIProvider):
    name = "openai"

    def __init__(self, *, model=None, timeout=None, request_options=None):
        self.api_key = settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_SEARCH_MODEL
        self.base_url = settings.OPENAI_API_BASE_URL.rstrip("/")
        self.timeout = timeout or settings.AI_REQUEST_TIMEOUT_SECONDS
        self.request_options = request_options or {}

    def generate(self, instructions, input_payload, schema, schema_name):
        if not self.api_key:
            raise AIProviderUnavailable("OpenAI is not configured.")
        payload = _post_json(
            f"{self.base_url}/responses",
            {
                "model": self.model,
                "instructions": instructions,
                "input": json.dumps(input_payload, ensure_ascii=False),
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "strict": True,
                        "schema": schema,
                    }
                },
                **self.request_options,
            },
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            self.timeout,
        )
        if payload.get("error"):
            raise AIProviderUnavailable()
        if payload.get("status") in {"incomplete", "failed", "cancelled"}:
            raise AIProviderMalformedResponse()
        output_text = payload.get("output_text")
        if not isinstance(output_text, str):
            output = payload.get("output", [])
            if not isinstance(output, list):
                raise AIProviderMalformedResponse()
            for item in output:
                if not isinstance(item, dict) or not isinstance(item.get("content", []), list):
                    raise AIProviderMalformedResponse()
                for content in item.get("content", []):
                    if not isinstance(content, dict):
                        raise AIProviderMalformedResponse()
                    if content.get("type") == "output_text":
                        output_text = content.get("text")
                        break
                if isinstance(output_text, str):
                    break
        return AIProviderResult(
            data=_json_content(output_text),
            provider=self.name,
            model=str(payload.get("model") or self.model),
            request_id=str(payload.get("id") or ""),
            input_tokens=int((payload.get("usage") or {}).get("input_tokens") or 0),
            output_tokens=int((payload.get("usage") or {}).get("output_tokens") or 0),
        )


class AnthropicMessagesProvider(StructuredAIProvider):
    name = "anthropic"

    def __init__(self, *, model=None, timeout=None, request_options=None):
        self.api_key = settings.ANTHROPIC_API_KEY
        self.model = model or settings.ANTHROPIC_SEARCH_MODEL
        self.base_url = settings.ANTHROPIC_API_BASE_URL.rstrip("/")
        self.timeout = timeout or settings.AI_REQUEST_TIMEOUT_SECONDS
        self.request_options = request_options or {}

    def generate(self, instructions, input_payload, schema, schema_name):
        del schema_name
        if not self.api_key:
            raise AIProviderUnavailable("Anthropic is not configured.")
        payload = _post_json(
            f"{self.base_url}/messages",
            {
                "model": self.model,
                "max_tokens": settings.ANTHROPIC_SEARCH_MAX_OUTPUT_TOKENS,
                "system": instructions,
                "messages": [
                    {
                        "role": "user",
                        "content": json.dumps(input_payload, ensure_ascii=False),
                    },
                ],
                "output_config": {
                    "effort": "low",
                    "format": {
                        "type": "json_schema",
                        "schema": _anthropic_schema(schema),
                    }
                },
                **self.request_options,
            },
            {
                "Authorization": f"Bearer {self.api_key}",
                "anthropic-version": settings.ANTHROPIC_API_VERSION,
                "Content-Type": "application/json",
            },
            self.timeout,
        )
        usage = payload.get("usage") or {}
        try:
            input_tokens = int(usage.get("input_tokens") or 0)
            output_tokens = int(usage.get("output_tokens") or 0)
        except (AttributeError, TypeError, ValueError) as exc:
            raise AIProviderMalformedResponse(
                stage="provider_response",
                request_id=str(getattr(payload, "request_id", "") or payload.get("id") or ""),
                provider=self.name,
                model=str(payload.get("model") or self.model),
            ) from exc
        metadata = {
            "request_id": str(
                getattr(payload, "request_id", "") or payload.get("id") or ""
            ),
            "provider": self.name,
            "model": str(payload.get("model") or self.model),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "stop_reason": str(payload.get("stop_reason") or ""),
            "usage_confirmed": bool(payload.get("usage")),
        }
        if payload.get("error"):
            error_payload = payload["error"]
            error_type = (
                str(error_payload.get("type") or "")
                if isinstance(error_payload, dict)
                else ""
            )
            if error_type == "rate_limit_error":
                raise AIProviderRateLimited(
                    retry_after=30, stage="api_error", **metadata
                )
            raise AIProviderUnavailable(stage="api_error", **metadata)
        if payload.get("type") not in {None, "message"}:
            raise AIProviderMalformedResponse(stage="provider_response", **metadata)
        if metadata["stop_reason"] in {"max_tokens", "model_context_window_exceeded"}:
            raise AIProviderMalformedResponse(stage="truncated_output", **metadata)
        if metadata["stop_reason"] != "end_turn":
            raise AIProviderMalformedResponse(stage="finish_reason", **metadata)
        try:
            blocks = payload["content"]
            if not isinstance(blocks, list) or not blocks or not all(
                isinstance(block, dict) for block in blocks
            ):
                raise AIProviderMalformedResponse(stage="provider_response", **metadata)
            text_blocks = [block for block in blocks if block.get("type") == "text"]
            if not text_blocks or not all(
                isinstance(block.get("text"), str) for block in text_blocks
            ):
                raise AIProviderMalformedResponse(stage="provider_response", **metadata)
            content = "".join(block["text"] for block in text_blocks)
        except (KeyError, TypeError) as exc:
            raise AIProviderMalformedResponse(
                stage="provider_response", **metadata
            ) from exc
        try:
            data = _json_content(content)
        except AIProviderMalformedResponse as exc:
            raise AIProviderMalformedResponse(stage="json_decode", **metadata) from exc
        return AIProviderResult(
            data=data,
            provider=self.name,
            model=metadata["model"],
            request_id=metadata["request_id"],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason=metadata["stop_reason"],
        )


class GeminiGenerateContentProvider(StructuredAIProvider):
    name = "gemini"

    def __init__(self, *, model=None, timeout=None, request_options=None):
        self.api_key = settings.RESUME_AI_API_KEY or settings.GEMINI_API_KEY
        self.model = model or settings.RESUME_AI_MODEL
        self.base_url = settings.GEMINI_API_BASE_URL.rstrip("/")
        self.timeout = timeout or settings.AI_REQUEST_TIMEOUT_SECONDS
        self.request_options = request_options or {}

    def generate(self, instructions, input_payload, schema, schema_name):
        del schema_name
        if not self.api_key:
            raise AIProviderUnavailable("Gemini is not configured.")
        model = urllib.parse.quote(self.model, safe="-._")
        payload = _post_json(
            f"{self.base_url}/models/{model}:generateContent",
            {
                "systemInstruction": {"parts": [{"text": instructions}]},
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": json.dumps(input_payload, ensure_ascii=False)}
                        ],
                    }
                ],
                "generationConfig": {
                    "responseFormat": {
                        "text": {
                            "mimeType": "APPLICATION_JSON",
                            "schema": _gemini_schema(schema),
                        }
                    },
                    **self.request_options,
                },
            },
            {"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            self.timeout,
        )
        usage = payload.get("usageMetadata") or {}
        try:
            input_tokens = int(usage.get("promptTokenCount") or 0)
            output_tokens = int(
                (usage.get("candidatesTokenCount") or 0)
                + (usage.get("thoughtsTokenCount") or 0)
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise AIProviderMalformedResponse(
                stage="provider_response",
                request_id=str(
                    payload.get("responseId") or getattr(payload, "request_id", "") or ""
                ),
                provider=self.name,
                model=self.model,
                http_status=getattr(payload, "http_status", 200),
                latency_ms=getattr(payload, "latency_ms", 0),
            ) from exc
        metadata = {
            "request_id": str(
                payload.get("responseId") or getattr(payload, "request_id", "") or ""
            ),
            "provider": self.name,
            "model": self.model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "usage_confirmed": bool(payload.get("usageMetadata")),
            "http_status": getattr(payload, "http_status", 200),
            "latency_ms": getattr(payload, "latency_ms", 0),
        }
        if payload.get("error"):
            provider_error_code, provider_error_status = _safe_provider_error(payload)
            error_class = {
                "INVALID_ARGUMENT": AIProviderInvalidRequest,
                "UNAUTHENTICATED": AIProviderAuthenticationError,
                "PERMISSION_DENIED": AIProviderPermissionDenied,
                "NOT_FOUND": AIProviderNotFound,
                "RESOURCE_EXHAUSTED": AIProviderRateLimited,
            }.get(provider_error_status, AIProviderUnavailable)
            raise error_class(
                stage="api_error",
                provider_error_code=provider_error_code,
                provider_error_status=provider_error_status,
                **metadata,
            )
        try:
            candidate = payload["candidates"][0]
            if not isinstance(candidate, dict):
                raise AIProviderMalformedResponse(
                    stage="provider_response", **metadata
                )
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderMalformedResponse(
                stage="provider_response", **metadata
            ) from exc
        stop_reason = str(candidate.get("finishReason") or "")
        metadata["stop_reason"] = stop_reason
        if stop_reason not in {"", "STOP"}:
            stage = "truncated_output" if stop_reason == "MAX_TOKENS" else "finish_reason"
            raise AIProviderMalformedResponse(stage=stage, **metadata)
        try:
            parts = candidate["content"]["parts"]
            if not isinstance(parts, list) or not parts or not all(
                isinstance(part, dict) for part in parts
            ):
                raise AIProviderMalformedResponse(
                    stage="provider_response", **metadata
                )
            output_parts = [part for part in parts if not part.get("thought")]
            if not output_parts or not all(
                isinstance(part.get("text"), str) and part["text"]
                for part in output_parts
            ):
                raise AIProviderMalformedResponse(
                    stage="provider_response", **metadata
                )
            content = "".join(part["text"] for part in output_parts)
        except (KeyError, TypeError) as exc:
            raise AIProviderMalformedResponse(
                stage="provider_response", **metadata
            ) from exc
        try:
            data = _json_content(content)
        except AIProviderMalformedResponse as exc:
            raise AIProviderMalformedResponse(stage="json_decode", **metadata) from exc
        return AIProviderResult(
            data=data,
            provider=self.name,
            model=self.model,
            request_id=metadata["request_id"],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason=stop_reason,
            http_status=metadata["http_status"],
            latency_ms=metadata["latency_ms"],
        )


def get_ai_provider(name):
    providers = {
        "anthropic": AnthropicMessagesProvider,
        "gemini": GeminiGenerateContentProvider,
        "openai": OpenAIResponsesProvider,
    }
    provider_class = providers.get(name)
    if not provider_class:
        raise AIProviderUnavailable("The configured AI provider is invalid.")
    return provider_class()
