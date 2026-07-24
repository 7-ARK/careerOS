"""Offline tests for injected provider adapters and safe failure handling."""

from types import SimpleNamespace

from app.autonomy import (
    ChatMessage,
    LogicalRole,
    ModelCapabilities,
    ModelSpec,
    OpenAICompatibleProviderAdapter,
    ProviderCallState,
    ProviderEndpoint,
    ProviderErrorCategory,
    ProviderRequest,
    RetryPolicy,
    build_openai_compatible_client,
    classify_provider_error,
)


class FakeProviderError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class FakeCompletions:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _adapter(responses: list[object]) -> tuple[OpenAICompatibleProviderAdapter, FakeCompletions]:
    completions = FakeCompletions(responses)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    spec = ModelSpec(
        provider="openai",
        model="provider-test-model",
        role=LogicalRole.WORKER,
        base_url="https://api.example/v1",
        api_key_env="OPENAI_API_KEY",
        endpoint=ProviderEndpoint.CHAT_COMPLETIONS,
        capabilities=ModelCapabilities(structured_output=True, tool_calling=True),
    )
    return OpenAICompatibleProviderAdapter(spec, client), completions


def _response(text: str = "ok") -> object:
    return SimpleNamespace(
        id="resp_test_123",
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2, total_tokens=5),
    )


def test_injected_client_receives_model_messages_and_structured_output() -> None:
    adapter, completions = _adapter([_response('{"ok": true}')])

    result = adapter.call(
        ProviderRequest(
            messages=[ChatMessage(role="user", content="hello")],
            response_format={"type": "json_object"},
        )
    )

    assert result.state.value == "succeeded"
    assert result.structured_output == {"ok": True}
    assert result.response_id == "resp_test_123"
    assert result.usage is not None and result.usage.total_tokens == 5
    assert completions.calls[0]["model"] == "provider-test-model"
    assert completions.calls[0]["response_format"] == {"type": "json_object"}


def test_chat_endpoint_bounds_output_and_normalizes_developer_role() -> None:
    adapter, completions = _adapter([_response('{"ok": true}')])

    adapter.call(
        ProviderRequest(
            messages=[
                ChatMessage(role="developer", content="Return JSON."),
                ChatMessage(role="user", content="Check the contract."),
            ],
            response_format={"type": "json_object"},
            max_output_tokens=321,
        )
    )

    assert completions.calls[0]["max_tokens"] == 321
    assert completions.calls[0]["messages"][0] == {
        "role": "system",
        "content": "Return JSON.",
    }


def test_sdk_client_disables_hidden_retries_and_uses_registered_timeout() -> None:
    captured: dict[str, object] = {}

    def factory(**kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace()

    spec = ModelSpec(
        provider="openai",
        model="bounded-client",
        role=LogicalRole.CEO,
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        timeout_seconds=47,
    )

    build_openai_compatible_client(spec, "test-key", client_factory=factory)

    assert captured["timeout"] == 47.0
    assert captured["max_retries"] == 0


def test_transient_failure_is_retried_exactly_once() -> None:
    adapter, completions = _adapter(
        [FakeProviderError("temporarily unavailable", 503), _response()]
    )

    result = adapter.call(
        ProviderRequest(
            messages=[ChatMessage(role="user", content="hello")],
            retry_policy=RetryPolicy(max_transient_retries=1),
        )
    )

    assert result.state.value == "succeeded"
    assert result.attempts == 2
    assert len(completions.calls) == 2


def test_authentication_failure_is_not_retried_and_secret_is_redacted() -> None:
    secret = "sk-test-secret-value"
    adapter, completions = _adapter([FakeProviderError(f"Incorrect API key: {secret}", 401)])

    result = adapter.call(ProviderRequest(messages=[ChatMessage(role="user", content="hello")]))

    assert result.state.value == "failed"
    assert result.attempts == 1
    assert len(completions.calls) == 1
    assert result.error is not None
    assert result.error.category is ProviderErrorCategory.AUTHENTICATION
    assert secret not in result.error.detail
    assert "[REDACTED]" in result.error.detail
    assert result.error.retryable is False


def test_authentication_error_never_preserves_a_masked_key_suffix() -> None:
    error = classify_provider_error(
        FakeProviderError(
            "Incorrect API key provided: sk-proj-****************qDYA",
            401,
        )
    )

    assert error.category is ProviderErrorCategory.AUTHENTICATION
    assert "qDYA" not in error.detail
    assert "Incorrect API key" not in error.detail
    assert error.detail == ("provider authentication was rejected; credential detail [REDACTED]")


def test_probe_records_safe_provider_and_capability_evidence() -> None:
    adapter, _ = _adapter([_response()])

    probe = adapter.probe()

    assert probe.provider == "openai"
    assert probe.model == "provider-test-model"
    assert probe.authenticated is True
    assert probe.endpoint_reachable is True
    assert probe.tool_calling is True
    assert probe.structured_output is True
    assert probe.response_id == "resp_test_123"
    assert probe.duration_ms >= 0


def test_error_categories_disable_retry_for_access_and_invalid_request() -> None:
    model_error = classify_provider_error(FakeProviderError("model not found", 404))
    endpoint_error = classify_provider_error(FakeProviderError("endpoint not reachable"))
    invalid_error = classify_provider_error(FakeProviderError("invalid request", 400))

    assert model_error.category is ProviderErrorCategory.MODEL_ACCESS
    assert endpoint_error.category is ProviderErrorCategory.ENDPOINT_ACCESS
    assert invalid_error.category is ProviderErrorCategory.INVALID_REQUEST
    assert not model_error.retryable
    assert not endpoint_error.retryable
    assert not invalid_error.retryable


def test_openai_responses_endpoint_uses_reasoning_and_structured_format() -> None:
    responses = FakeCompletions([SimpleNamespace(id="resp_1", output_text='{"ok":true}')])
    client = SimpleNamespace(responses=responses)
    spec = ModelSpec(
        provider="openai",
        model="responses-test-model",
        role=LogicalRole.CEO,
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        endpoint=ProviderEndpoint.RESPONSES,
        supported_reasoning_efforts=("high",),
        default_reasoning_effort="high",
        capabilities=ModelCapabilities(structured_output=True, reasoning=True),
    )
    adapter = OpenAICompatibleProviderAdapter(spec, client)

    result = adapter.call(
        ProviderRequest(
            messages=[
                ChatMessage(role="developer", content="Return JSON."),
                ChatMessage(role="user", content="Check availability."),
            ],
            response_format={
                "type": "json_schema",
                "name": "result",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"],
                    "additionalProperties": False,
                },
            },
            max_output_tokens=100,
        )
    )

    assert result.state is ProviderCallState.SUCCEEDED
    assert result.structured_output == {"ok": True}
    assert responses.calls[0]["reasoning"] == {"effort": "high"}
    assert responses.calls[0]["text"]["format"]["type"] == "json_schema"
