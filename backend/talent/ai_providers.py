import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass

from django.conf import settings


class AIProviderError(Exception):
    kind = "unavailable"

    def __init__(self, message="AI provider unavailable.", retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class AIProviderRateLimited(AIProviderError):
    kind = "rate_limited"


class AIProviderTimeout(AIProviderError):
    kind = "timeout"


class AIProviderMalformedResponse(AIProviderError):
    kind = "malformed_response"


class AIProviderUnavailable(AIProviderError):
    kind = "unavailable"


@dataclass(frozen=True)
class AIProviderResult:
    data: dict
    provider: str
    model: str
    request_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


def _retry_after(headers):
    value = headers.get("Retry-After") if headers else None
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 30


def _post_json(url, body, headers, timeout):
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise AIProviderRateLimited(retry_after=_retry_after(exc.headers)) from exc
        if exc.code in {408, 504}:
            raise AIProviderTimeout() from exc
        raise AIProviderUnavailable() from exc
    except (TimeoutError, socket.timeout) as exc:
        raise AIProviderTimeout() from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise AIProviderTimeout() from exc
        raise AIProviderUnavailable() from exc
    except OSError as exc:
        raise AIProviderUnavailable() from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AIProviderMalformedResponse() from exc
    if not isinstance(payload, dict):
        raise AIProviderMalformedResponse()
    return payload


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


class OpenRouterChatProvider(StructuredAIProvider):
    name = "openrouter"

    def __init__(self, *, model=None, timeout=None, request_options=None):
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = model or settings.OPENROUTER_SEARCH_MODEL
        self.base_url = settings.OPENROUTER_API_BASE_URL.rstrip("/")
        self.timeout = timeout or settings.AI_REQUEST_TIMEOUT_SECONDS
        self.request_options = request_options or {}

    def generate(self, instructions, input_payload, schema, schema_name):
        if not self.api_key:
            raise AIProviderUnavailable("OpenRouter is not configured.")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if settings.OPENROUTER_HTTP_REFERER:
            headers["HTTP-Referer"] = settings.OPENROUTER_HTTP_REFERER
        if settings.OPENROUTER_APP_TITLE:
            headers["X-OpenRouter-Title"] = settings.OPENROUTER_APP_TITLE
        payload = _post_json(
            f"{self.base_url}/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": instructions},
                    {
                        "role": "user",
                        "content": json.dumps(input_payload, ensure_ascii=False),
                    },
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name,
                        "strict": True,
                        "schema": schema,
                    },
                },
                "provider": {"require_parameters": True},
                "stream": False,
                **self.request_options,
            },
            headers,
            self.timeout,
        )
        if payload.get("error"):
            error_payload = payload["error"]
            error_code = (
                str(error_payload.get("code") or "")
                if isinstance(error_payload, dict)
                else ""
            )
            if error_code in {"429", "rate_limit_exceeded"}:
                raise AIProviderRateLimited(retry_after=30)
            raise AIProviderUnavailable()
        try:
            choice = payload["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderMalformedResponse() from exc
        if choice.get("finish_reason") not in {None, "stop"}:
            raise AIProviderMalformedResponse()
        return AIProviderResult(
            data=_json_content(content),
            provider=self.name,
            model=str(payload.get("model") or self.model),
            request_id=str(payload.get("id") or ""),
            input_tokens=int((payload.get("usage") or {}).get("prompt_tokens") or 0),
            output_tokens=int((payload.get("usage") or {}).get("completion_tokens") or 0),
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
                    "responseMimeType": "application/json",
                    "responseJsonSchema": schema,
                    **self.request_options,
                },
            },
            {"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            self.timeout,
        )
        try:
            candidate = payload["candidates"][0]
            parts = candidate["content"]["parts"]
            content = "".join(part.get("text", "") for part in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderMalformedResponse() from exc
        if candidate.get("finishReason") not in {None, "STOP"}:
            raise AIProviderMalformedResponse()
        usage = payload.get("usageMetadata") or {}
        return AIProviderResult(
            data=_json_content(content),
            provider=self.name,
            model=self.model,
            request_id=str(payload.get("responseId") or ""),
            input_tokens=int(usage.get("promptTokenCount") or 0),
            output_tokens=int(
                (usage.get("candidatesTokenCount") or 0)
                + (usage.get("thoughtsTokenCount") or 0)
            ),
        )


def get_ai_provider(name):
    providers = {
        "gemini": GeminiGenerateContentProvider,
        "openai": OpenAIResponsesProvider,
        "openrouter": OpenRouterChatProvider,
    }
    provider_class = providers.get(name)
    if not provider_class:
        raise AIProviderUnavailable("The configured AI provider is invalid.")
    return provider_class()
