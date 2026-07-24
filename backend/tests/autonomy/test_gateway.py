"""Tests for validated model-call caching and probe bounds."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.autonomy.gateway import ModelCallError, ModelGateway
from app.autonomy.models import LogicalRole, ProviderErrorCategory
from app.autonomy.registry import ModelRegistry, RegistrySettings
from app.autonomy.store import RunStore


class ExampleOutput(BaseModel):
    status: str


class FakeResponses:
    def __init__(self, output: str) -> None:
        self.output = output
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(
            id=f"resp_{len(self.calls)}",
            output_text=self.output,
            usage=SimpleNamespace(input_tokens=5, output_tokens=3, total_tokens=8),
        )


def test_validated_structured_call_is_cached_by_prompt_hash(tmp_path) -> None:
    responses = FakeResponses('{"status":"ok"}')
    client = SimpleNamespace(responses=responses)
    registry = ModelRegistry(RegistrySettings())
    gateway = ModelGateway(
        registry,
        RunStore(tmp_path),
        {"OPENAI_API_KEY": "test-key"},
        client_factory=lambda **_: client,
    )

    first, first_call, _ = gateway.call_structured(
        run_id="run-1",
        role=LogicalRole.CEO,
        purpose="test",
        instructions="Return structured output.",
        input_text="Check the cache.",
        output_type=ExampleOutput,
    )
    second, second_call, _ = gateway.call_structured(
        run_id="run-1",
        role=LogicalRole.CEO,
        purpose="test",
        instructions="Return structured output.",
        input_text="Check the cache.",
        output_type=ExampleOutput,
    )

    assert first == second == ExampleOutput(status="ok")
    assert first_call.cached is False
    assert second_call.cached is True
    assert len(responses.calls) == 1


def test_invalid_structured_output_is_not_cached(tmp_path) -> None:
    responses = FakeResponses('{"wrong":"shape"}')
    gateway = ModelGateway(
        ModelRegistry(RegistrySettings()),
        RunStore(tmp_path),
        {"OPENAI_API_KEY": "test-key"},
        client_factory=lambda **_: SimpleNamespace(responses=responses),
    )

    with pytest.raises(ModelCallError) as captured:
        gateway.call_structured(
            run_id="run-1",
            role=LogicalRole.CEO,
            purpose="invalid",
            instructions="Return structured output.",
            input_text="Return the wrong shape.",
            output_type=ExampleOutput,
        )

    assert captured.value.call.error is not None
    assert captured.value.call.error.category is ProviderErrorCategory.OUTPUT_VALIDATION
    assert not (tmp_path / "run-1" / "model_call_cache.json").exists()


def test_probe_is_called_at_most_once_per_provider_model_and_run(tmp_path) -> None:
    responses = FakeResponses("available")
    gateway = ModelGateway(
        ModelRegistry(RegistrySettings()),
        RunStore(tmp_path),
        {"OPENAI_API_KEY": "test-key"},
        client_factory=lambda **_: SimpleNamespace(responses=responses),
    )

    first = gateway.probe_role(run_id="run-1", role=LogicalRole.CEO)
    second = gateway.probe_role(run_id="run-1", role=LogicalRole.CEO)

    assert first == second
    assert len(responses.calls) == 1


def test_missing_key_fails_without_constructing_provider_client(tmp_path) -> None:
    factory_calls = 0

    def factory(**_: object) -> object:
        nonlocal factory_calls
        factory_calls += 1
        return SimpleNamespace()

    gateway = ModelGateway(
        ModelRegistry(RegistrySettings()),
        RunStore(tmp_path),
        {},
        client_factory=factory,
    )

    with pytest.raises(ModelCallError) as captured:
        gateway.call_structured(
            run_id="run-1",
            role=LogicalRole.CEO,
            purpose="missing-key",
            instructions="Return structured output.",
            input_text="No provider should be called.",
            output_type=ExampleOutput,
        )

    assert factory_calls == 0
    assert captured.value.call.error is not None
    assert captured.value.call.error.category is ProviderErrorCategory.AUTHENTICATION


def test_ambiguous_probe_checkpoint_is_not_repeated(tmp_path) -> None:
    registry = ModelRegistry(RegistrySettings())
    spec = registry.get(LogicalRole.CEO)
    digest = hashlib.sha256(f"{spec.provider}:{spec.model}".encode()).hexdigest()[:16]
    store = RunStore(tmp_path)
    store.write_json(
        "run-1",
        f"probe-checkpoint-{digest}.json",
        {"status": "running", "provider": spec.provider, "model": spec.model},
    )
    factory_calls = 0

    def factory(**_: object) -> object:
        nonlocal factory_calls
        factory_calls += 1
        return SimpleNamespace()

    gateway = ModelGateway(
        registry,
        store,
        {"OPENAI_API_KEY": "test-key"},
        client_factory=factory,
    )

    probe = gateway.probe_role(run_id="run-1", role=LogicalRole.CEO)

    assert probe.status.value == "unavailable"
    assert probe.error is not None
    assert "ambiguous" in probe.error.detail
    assert factory_calls == 0
