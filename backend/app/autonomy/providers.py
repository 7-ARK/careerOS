"""Dependency-injected OpenAI-compatible provider adapters."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.autonomy.models import (
    AvailabilityProbe,
    AvailabilityStatus,
    LogicalRole,
    ModelSpec,
    ProviderCall,
    ProviderCallState,
    ProviderEndpoint,
    ProviderErrorCategory,
    ProviderRequest,
    ProviderUsage,
    RetryPolicy,
    SanitizedProviderError,
)
from app.autonomy.registry import ModelRegistry


class CompletionsResource(Protocol):
    """Subset of the OpenAI SDK chat-completions resource used by the adapter."""

    def create(self, **kwargs: Any) -> Any:
        """Create one provider completion."""


class OpenAICompatibleClient(Protocol):
    """Any injected client exposing OpenAI-compatible API resources."""

    chat: Any
    responses: Any


class ProviderAdapter(Protocol):
    """Provider adapter contract used by orchestration code."""

    def call(self, request: ProviderRequest) -> ProviderCall:
        """Execute a bounded provider call."""

    def probe(self, request: ProviderRequest | None = None) -> AvailabilityProbe:
        """Record provider availability without exposing credentials."""


class OpenAICompatibleProviderAdapter:
    """Use an injected OpenAI-compatible SDK client for any registered spec."""

    def __init__(
        self,
        spec: ModelSpec,
        client: OpenAICompatibleClient,
        *,
        clock: Callable[[], float] = time.perf_counter,
        sleep: Callable[[float], None] = time.sleep,
        id_factory: Callable[[], UUID] | None = None,
    ) -> None:
        self.spec = spec
        self.client = client
        self._clock = clock
        self._sleep = sleep
        self._id_factory = id_factory or uuid4

    def call(self, request: ProviderRequest) -> ProviderCall:
        """Call the provider, retrying transient failures at most once."""
        policy = request.retry_policy
        attempts = 0
        started = self._clock()
        while True:
            attempts += 1
            try:
                response = self._create_completion(request)
                return ProviderCall(
                    call_id=self._new_id(),
                    role=self.spec.role,
                    provider=self.spec.provider,
                    model=self.spec.model,
                    purpose=request.purpose,
                    state=ProviderCallState.SUCCEEDED,
                    attempts=attempts,
                    response_id=_response_id(response),
                    text=_response_text(response),
                    structured_output=_structured_output(response, request),
                    usage=_usage(response),
                    duration_ms=_duration_ms(self._clock() - started),
                )
            except Exception as exc:  # Provider SDK exceptions are intentionally normalized.
                error = classify_provider_error(exc)
                if error.retryable and attempts <= policy.max_transient_retries:
                    if policy.backoff_seconds:
                        self._sleep(policy.backoff_seconds)
                    continue
                return ProviderCall(
                    call_id=self._new_id(),
                    role=self.spec.role,
                    provider=self.spec.provider,
                    model=self.spec.model,
                    purpose=request.purpose,
                    state=ProviderCallState.FAILED,
                    attempts=attempts,
                    duration_ms=_duration_ms(self._clock() - started),
                    error=error,
                )

    def probe(self, request: ProviderRequest | None = None) -> AvailabilityProbe:
        """Run one injectable probe and return only safe availability evidence."""
        probe_request = request or ProviderRequest(
            messages=[
                {
                    "role": "user",
                    "content": "Return a short availability acknowledgment.",
                }
            ],
            retry_policy=RetryPolicy(max_transient_retries=0),
        )
        result = self.call(probe_request)
        error = result.error
        authenticated = True if error is None else _authentication_result(error)
        endpoint_reachable = True if error is None else _endpoint_result(error)
        return AvailabilityProbe(
            provider=self.spec.provider,
            model=self.spec.model,
            status=(
                AvailabilityStatus.AVAILABLE if error is None else AvailabilityStatus.UNAVAILABLE
            ),
            authenticated=authenticated,
            endpoint=self.spec.endpoint,
            endpoint_reachable=endpoint_reachable,
            tool_calling=self.spec.capabilities.tool_calling,
            structured_output=self.spec.capabilities.structured_output,
            response_id=result.response_id,
            usage=result.usage,
            duration_ms=result.duration_ms,
            error=error,
            probed_at=datetime.now(UTC),
        )

    def _create_completion(self, request: ProviderRequest) -> Any:
        messages = [
            {
                "role": "system" if message.role == "developer" else message.role,
                "content": message.content,
            }
            for message in request.messages
        ]
        kwargs: dict[str, Any] = {
            "model": self.spec.model,
            "messages": messages,
        }
        if request.tools:
            kwargs["tools"] = request.tools
        if request.max_output_tokens is not None:
            kwargs["max_tokens"] = request.max_output_tokens
        if request.response_format is not None:
            response_format = request.response_format
            if response_format.get("type") == "json_schema" and "schema" in response_format:
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_format.get("name", "structured_result"),
                        "strict": response_format.get("strict", True),
                        "schema": response_format["schema"],
                    },
                }
            kwargs["response_format"] = response_format
        if self.spec.endpoint is ProviderEndpoint.RESPONSES:
            return self._create_response(request)
        return self.client.chat.completions.create(**kwargs)

    def _create_response(self, request: ProviderRequest) -> Any:
        instructions = "\n\n".join(
            message.content
            for message in request.messages
            if message.role in {"system", "developer"}
        )
        inputs = [
            {
                "role": message.role,
                "content": [{"type": "input_text", "text": message.content}],
            }
            for message in request.messages
            if message.role in {"user", "assistant"}
        ]
        kwargs: dict[str, Any] = {
            "model": self.spec.model,
            "input": inputs or request.messages[-1].content,
            "store": False,
        }
        if instructions:
            kwargs["instructions"] = instructions
        reasoning_effort = request.reasoning_effort or self.spec.default_reasoning_effort
        if reasoning_effort:
            kwargs["reasoning"] = {"effort": reasoning_effort}
        max_output_tokens = request.max_output_tokens
        if max_output_tokens:
            kwargs["max_output_tokens"] = max_output_tokens
        if request.tools:
            kwargs["tools"] = request.tools
        if request.response_format is not None:
            kwargs["text"] = {"format": request.response_format}
        return self.client.responses.create(**kwargs)

    def _new_id(self) -> UUID:
        return self._id_factory()


class OpenAIProviderAdapter(OpenAICompatibleProviderAdapter):
    """Named adapter for the OpenAI registry provider."""


class MoonshotProviderAdapter(OpenAICompatibleProviderAdapter):
    """Named adapter for the official Moonshot-compatible endpoint."""


def create_provider_adapter(
    registry: ModelRegistry,
    role: LogicalRole,
    client: OpenAICompatibleClient,
    *,
    use_compatibility_fallback: bool = False,
) -> OpenAICompatibleProviderAdapter:
    """Route an injected client using the centralized registry."""
    selection = registry.resolve(
        role,
        use_compatibility_fallback=use_compatibility_fallback,
    )
    adapter_type = (
        MoonshotProviderAdapter if selection.spec.provider == "moonshot" else OpenAIProviderAdapter
    )
    return adapter_type(selection.spec, client)


def build_openai_compatible_client(
    spec: ModelSpec,
    api_key: str,
    *,
    client_factory: Callable[..., OpenAICompatibleClient] | None = None,
) -> OpenAICompatibleClient:
    """Build an SDK client through injection, without reading environment secrets."""
    factory = client_factory
    if factory is None:
        from openai import OpenAI

        factory = OpenAI
    return factory(
        api_key=api_key,
        base_url=str(spec.base_url),
        timeout=float(spec.timeout_seconds),
        max_retries=0,
    )


def classify_provider_error(exc: Exception) -> SanitizedProviderError:
    """Classify an SDK error and retain only a bounded, redacted detail."""
    status_code = _status_code(exc)
    raw_type = type(exc).__name__.casefold()
    raw_detail = str(exc).strip() or raw_type
    searchable = f"{raw_type} {raw_detail}".casefold()
    if status_code == 401 or any(
        marker in searchable for marker in ("authentication", "invalid api key", "unauthorized")
    ):
        category = ProviderErrorCategory.AUTHENTICATION
    elif status_code in {403, 404} or any(
        marker in searchable
        for marker in (
            "model not found",
            "model_not_found",
            "model access",
            "does not exist",
            "permission denied",
            "access denied",
        )
    ):
        category = ProviderErrorCategory.MODEL_ACCESS
    elif status_code in {400, 422} or any(
        marker in searchable
        for marker in ("invalid request", "unprocessable", "unsupported parameter")
    ):
        category = ProviderErrorCategory.INVALID_REQUEST
    elif status_code == 429:
        category = ProviderErrorCategory.RATE_LIMIT
    elif status_code == 408 or "timeout" in searchable or "timed out" in searchable:
        category = ProviderErrorCategory.TIMEOUT
    elif status_code in {500, 502, 503, 504, 520}:
        category = ProviderErrorCategory.SERVER
    elif (
        any(marker in searchable for marker in ("connection", "connecterror", "temporarily"))
        or status_code == 409
    ):
        category = ProviderErrorCategory.TRANSIENT
    elif any(marker in searchable for marker in ("endpoint", "base url", "dns", "not reachable")):
        category = ProviderErrorCategory.ENDPOINT_ACCESS
    else:
        category = ProviderErrorCategory.UNKNOWN
    detail = _safe_detail(raw_detail, category)
    return SanitizedProviderError(
        category=category,
        detail=detail,
        retryable=category
        in {
            ProviderErrorCategory.RATE_LIMIT,
            ProviderErrorCategory.SERVER,
            ProviderErrorCategory.TIMEOUT,
            ProviderErrorCategory.TRANSIENT,
        },
        status_code=status_code,
    )


def _status_code(exc: Exception) -> int | None:
    candidate = getattr(exc, "status_code", None)
    if candidate is None:
        response = getattr(exc, "response", None)
        candidate = getattr(response, "status_code", None)
    return candidate if isinstance(candidate, int) else None


def _safe_detail(detail: str, category: ProviderErrorCategory) -> str:
    if category is ProviderErrorCategory.AUTHENTICATION:
        return "provider authentication was rejected; credential detail [REDACTED]"
    redacted = re.sub(r"(?i)\bsk-[^\s,;'\"}]+", "[REDACTED]", detail)
    redacted = re.sub(r"Bearer\s+\S+", "Bearer [REDACTED]", redacted, flags=re.IGNORECASE)
    redacted = re.sub(
        r"(?i)(api[_ -]?key\s*[:=]\s*)\S+",
        r"\1[REDACTED]",
        redacted,
    )
    return redacted[:300] or "provider request failed"


def _duration_ms(seconds: float) -> int:
    return max(0, round(seconds * 1000))


def _response_id(response: Any) -> str | None:
    value = getattr(response, "id", None)
    return str(value) if value is not None else None


def _response_text(response: Any) -> str | None:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text
    choices = getattr(response, "choices", None) or []
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
    return None


def _structured_output(
    response: Any, request: ProviderRequest
) -> dict[str, Any] | list[Any] | None:
    content = _response_text(response)
    if isinstance(content, str) and request.response_format is not None:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, (dict, list)) else None
    choices = getattr(response, "choices", None) or []
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, (dict, list)):
            return content
    return None


def _usage(response: Any) -> ProviderUsage | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    input_tokens = getattr(usage, "prompt_tokens", None)
    if input_tokens is None:
        input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "completion_tokens", None)
    if output_tokens is None:
        output_tokens = getattr(usage, "output_tokens", None)
    total_tokens = getattr(usage, "total_tokens", None)
    return ProviderUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def _authentication_result(error: SanitizedProviderError) -> bool | None:
    if error.category is ProviderErrorCategory.AUTHENTICATION:
        return False
    return None


def _endpoint_result(error: SanitizedProviderError) -> bool | None:
    if error.category in {
        ProviderErrorCategory.ENDPOINT_ACCESS,
        ProviderErrorCategory.RATE_LIMIT,
        ProviderErrorCategory.SERVER,
        ProviderErrorCategory.TIMEOUT,
        ProviderErrorCategory.TRANSIENT,
    }:
        return False
    if error.category in {
        ProviderErrorCategory.AUTHENTICATION,
        ProviderErrorCategory.MODEL_ACCESS,
        ProviderErrorCategory.INVALID_REQUEST,
    }:
        return True
    return None


__all__ = [
    "MoonshotProviderAdapter",
    "OpenAICompatibleClient",
    "OpenAICompatibleProviderAdapter",
    "OpenAIProviderAdapter",
    "ProviderAdapter",
    "build_openai_compatible_client",
    "classify_provider_error",
    "create_provider_adapter",
]
