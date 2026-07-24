"""Offline tests for centralized model routing."""

import pytest

from app.autonomy import AvailabilityStatus, LogicalRole, ModelRegistry, RegistrySettings


def test_default_registry_routes_each_logical_role() -> None:
    registry = ModelRegistry(RegistrySettings())

    assert registry.get(LogicalRole.CEO).model == "gpt-5.6-sol"
    assert registry.get(LogicalRole.REVIEWER).model == "gpt-5.6-terra"
    assert registry.get(LogicalRole.WORKER).model == "gpt-5.6-luna"
    critic = registry.get(LogicalRole.CRITIC)
    assert critic.model == "kimi-k3"
    assert str(critic.base_url) == "https://api.moonshot.ai/v1"
    assert critic.api_key_env == "KIMI_API_KEY"


def test_registry_accepts_explicit_environment_overrides() -> None:
    registry = ModelRegistry.from_environment(
        {
            "AUTONOMY_CEO_MODEL": "ceo-test",
            "AUTONOMY_MOONSHOT_BASE_URL": "https://moonshot.example/v1",
        }
    )

    assert registry.get(LogicalRole.CEO).model == "ceo-test"
    assert str(registry.get(LogicalRole.CRITIC).base_url) == "https://moonshot.example/v1"


def test_compatibility_fallback_is_explicit_and_worker_safe() -> None:
    registry = ModelRegistry.from_environment({"OPENAI_MODEL": "low-cost-test"})

    primary = registry.resolve(LogicalRole.REVIEWER)
    fallback = registry.resolve(LogicalRole.REVIEWER, use_compatibility_fallback=True)

    assert primary.used_compatibility_fallback is False
    assert primary.spec.model == "gpt-5.6-terra"
    assert fallback.used_compatibility_fallback is True
    assert fallback.spec.model == "low-cost-test"
    assert fallback.spec.compatibility_fallback is True
    assert fallback.warning
    worker = registry.resolve(LogicalRole.WORKER, use_compatibility_fallback=True)
    assert worker.used_compatibility_fallback is True
    assert worker.spec.model == "low-cost-test"
    with pytest.raises(ValueError, match="not available for ceo"):
        registry.resolve(LogicalRole.CEO, use_compatibility_fallback=True)


def test_registry_exposes_all_required_logical_roles() -> None:
    registry = ModelRegistry(RegistrySettings())

    assert set(registry.all()) == {
        LogicalRole.CEO,
        LogicalRole.PLANNER,
        LogicalRole.IMPLEMENTATION_WORKER,
        LogicalRole.RESEARCH_WORKER,
        LogicalRole.TEST_WORKER,
        LogicalRole.REVIEWER,
        LogicalRole.INDEPENDENT_CRITIC,
        LogicalRole.SUMMARIZER,
    }


def test_registry_fallback_records_provenance() -> None:
    registry = ModelRegistry(RegistrySettings())
    primary = registry.get(LogicalRole.IMPLEMENTATION_WORKER)
    fallback = registry.candidates(LogicalRole.IMPLEMENTATION_WORKER)[1]

    selection = registry.resolve(
        LogicalRole.IMPLEMENTATION_WORKER,
        availability={
            (primary.provider, primary.model): AvailabilityStatus.UNAVAILABLE,
            (fallback.provider, fallback.model): AvailabilityStatus.AVAILABLE,
        },
    )

    assert selection.spec.model == "gpt-5.6-terra"
    assert selection.fallback_from == "gpt-5.6-luna"
    assert selection.warning


def test_missing_compatibility_fallback_fails_loudly() -> None:
    registry = ModelRegistry(RegistrySettings())

    with pytest.raises(ValueError, match="was not configured"):
        registry.resolve(LogicalRole.REVIEWER, use_compatibility_fallback=True)
