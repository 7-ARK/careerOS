"""Centralized, configuration-driven model routing for autonomy roles."""

from __future__ import annotations

from collections.abc import Mapping
from os import environ

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from app.autonomy.models import (
    AvailabilityStatus,
    CostClass,
    LogicalRole,
    ModelCapabilities,
    ModelSelection,
    ModelSpec,
    ProviderEndpoint,
)


class RegistrySettings(BaseModel):
    """Environment-overridable model names and provider endpoints."""

    model_config = ConfigDict(extra="forbid", validate_default=True)

    sol_model: str = Field(default="gpt-5.6-sol", min_length=1)
    terra_model: str = Field(default="gpt-5.6-terra", min_length=1)
    luna_model: str = Field(default="gpt-5.6-luna", min_length=1)
    kimi_model: str = Field(default="kimi-k3", min_length=1)
    openai_base_url: AnyHttpUrl = "https://api.openai.com/v1"
    moonshot_base_url: AnyHttpUrl = "https://api.moonshot.ai/v1"
    compatibility_fallback_model: str | None = Field(default=None, min_length=1)

    @classmethod
    def from_environment(cls, values: Mapping[str, str] | None = None) -> RegistrySettings:
        """Load model names and endpoints without reading credential values."""
        source = values if values is not None else environ
        overrides: dict[str, str] = {}
        names = {
            "AUTONOMY_SOL_MODEL": "sol_model",
            "AUTONOMY_CEO_MODEL": "sol_model",
            "AUTONOMY_TERRA_MODEL": "terra_model",
            "AUTONOMY_REVIEWER_MODEL": "terra_model",
            "AUTONOMY_LUNA_MODEL": "luna_model",
            "AUTONOMY_WORKER_MODEL": "luna_model",
            "AUTONOMY_KIMI_MODEL": "kimi_model",
            "AUTONOMY_CRITIC_MODEL": "kimi_model",
            "AUTONOMY_OPENAI_BASE_URL": "openai_base_url",
            "AUTONOMY_MOONSHOT_BASE_URL": "moonshot_base_url",
            "OPENAI_MODEL": "compatibility_fallback_model",
        }
        for environment_name, field_name in names.items():
            value = source.get(environment_name)
            if value:
                overrides[field_name] = value
        return cls(**overrides)


class ModelRegistry:
    """Resolve logical roles through ordered, explicit model candidates."""

    def __init__(self, settings: RegistrySettings | None = None) -> None:
        self.settings = settings or RegistrySettings.from_environment()
        self._routes = self._build_routes(self.settings)

    @classmethod
    def from_environment(cls, values: Mapping[str, str] | None = None) -> ModelRegistry:
        """Create a registry using explicit environment overrides."""
        return cls(RegistrySettings.from_environment(values))

    def get(self, role: LogicalRole) -> ModelSpec:
        """Return a role's enabled primary model."""
        return self.candidates(role)[0]

    def candidates(self, role: LogicalRole) -> tuple[ModelSpec, ...]:
        """Return enabled candidates in deterministic priority order."""
        candidates = tuple(
            sorted(
                (spec for spec in self._routes[role] if spec.enabled),
                key=lambda spec: spec.priority,
            )
        )
        if not candidates:
            raise ValueError(f"no enabled model candidates for role {role.value}")
        return candidates

    def resolve(
        self,
        role: LogicalRole,
        *,
        availability: Mapping[tuple[str, str], AvailabilityStatus] | None = None,
        allow_model_fallback: bool = True,
        use_compatibility_fallback: bool = False,
    ) -> ModelSelection:
        """Resolve a role without silently hiding fallback provenance."""
        candidates = self.candidates(role)
        primary = candidates[0]
        if availability:
            for index, candidate in enumerate(candidates):
                status = availability.get(
                    (candidate.provider, candidate.model),
                    candidate.availability_status,
                )
                if status is AvailabilityStatus.AVAILABLE:
                    return ModelSelection(
                        spec=candidate.model_copy(update={"availability_status": status}),
                        fallback_from=primary.model if index else None,
                        warning=(
                            f"Primary model {primary.model} unavailable; selected "
                            f"{candidate.model}."
                            if index
                            else None
                        ),
                    )
                if index == 0 and not allow_model_fallback:
                    break
        elif not use_compatibility_fallback:
            return ModelSelection(spec=primary)

        if use_compatibility_fallback:
            return self._compatibility_selection(role, primary)
        unavailable = ", ".join(spec.model for spec in candidates)
        raise ValueError(f"no available model for role {role.value}: {unavailable}")

    def all(self) -> dict[LogicalRole, ModelSpec]:
        """Return primary routing for compatibility with simple callers."""
        return {role: self.get(role) for role in self._routes}

    def snapshot(self) -> dict[str, list[dict[str, object]]]:
        """Return a non-secret machine-readable registry snapshot."""
        return {
            role.value: [
                spec.model_dump(mode="json", exclude={"api_key_env"})
                | {"api_key_env": spec.api_key_env}
                for spec in self.candidates(role)
            ]
            for role in self._routes
        }

    def _compatibility_selection(
        self,
        role: LogicalRole,
        primary: ModelSpec,
    ) -> ModelSelection:
        fallback = self.settings.compatibility_fallback_model
        allowed_roles = {
            LogicalRole.IMPLEMENTATION_WORKER,
            LogicalRole.RESEARCH_WORKER,
            LogicalRole.TEST_WORKER,
            LogicalRole.REVIEWER,
            LogicalRole.SUMMARIZER,
        }
        if role not in allowed_roles:
            raise ValueError(f"the compatibility fallback is not available for {role.value}")
        if not fallback:
            raise ValueError("OPENAI_MODEL compatibility fallback was not configured")
        fallback_spec = primary.model_copy(
            update={
                "model": fallback,
                "provider": "openai",
                "base_url": self.settings.openai_base_url,
                "api_key_env": "OPENAI_API_KEY",
                "endpoint": ProviderEndpoint.CHAT_COMPLETIONS,
                "priority": 99,
                "compatibility_fallback": True,
                "availability_status": AvailabilityStatus.UNKNOWN,
            }
        )
        return ModelSelection(
            spec=fallback_spec,
            fallback_from=primary.model,
            used_compatibility_fallback=True,
            warning=(
                f"Explicit compatibility fallback {fallback} selected for {role.value}; "
                f"primary {primary.model} was not used."
            ),
        )

    @staticmethod
    def _build_routes(settings: RegistrySettings) -> dict[LogicalRole, tuple[ModelSpec, ...]]:
        openai_capabilities = ModelCapabilities(
            structured_output=True,
            tool_calling=True,
            reasoning=True,
            vision=True,
            multimodal=True,
        )
        kimi_capabilities = ModelCapabilities(
            structured_output=True,
            tool_calling=True,
            reasoning=True,
            vision=True,
            multimodal=True,
        )

        def openai(
            role: LogicalRole,
            model: str,
            *,
            priority: int,
            cost: CostClass,
            reasoning: str,
        ) -> ModelSpec:
            return ModelSpec(
                provider="openai",
                model=model,
                role=role,
                base_url=settings.openai_base_url,
                api_key_env="OPENAI_API_KEY",
                endpoint=ProviderEndpoint.RESPONSES,
                priority=priority,
                supported_reasoning_efforts=("none", "low", "medium", "high", "xhigh", "max"),
                default_reasoning_effort=reasoning,
                context_window=1_050_000,
                maximum_output=128_000,
                capabilities=openai_capabilities,
                cost_class=cost,
                timeout_seconds=300 if cost is CostClass.HIGH else 180,
            )

        def kimi(role: LogicalRole, *, priority: int) -> ModelSpec:
            return ModelSpec(
                provider="moonshot",
                model=settings.kimi_model,
                role=role,
                base_url=settings.moonshot_base_url,
                api_key_env="KIMI_API_KEY",
                endpoint=ProviderEndpoint.CHAT_COMPLETIONS,
                priority=priority,
                supported_reasoning_efforts=("high", "max"),
                default_reasoning_effort="max",
                context_window=1_000_000,
                maximum_output=32_000,
                capabilities=kimi_capabilities,
                cost_class=CostClass.HIGH,
                timeout_seconds=300,
            )

        return {
            LogicalRole.CEO: (
                openai(
                    LogicalRole.CEO,
                    settings.sol_model,
                    priority=1,
                    cost=CostClass.HIGH,
                    reasoning="high",
                ),
                openai(
                    LogicalRole.CEO,
                    settings.terra_model,
                    priority=2,
                    cost=CostClass.MEDIUM,
                    reasoning="high",
                ),
            ),
            LogicalRole.PLANNER: (
                openai(
                    LogicalRole.PLANNER,
                    settings.sol_model,
                    priority=1,
                    cost=CostClass.HIGH,
                    reasoning="high",
                ),
                openai(
                    LogicalRole.PLANNER,
                    settings.terra_model,
                    priority=2,
                    cost=CostClass.MEDIUM,
                    reasoning="medium",
                ),
            ),
            LogicalRole.IMPLEMENTATION_WORKER: (
                openai(
                    LogicalRole.IMPLEMENTATION_WORKER,
                    settings.luna_model,
                    priority=1,
                    cost=CostClass.LOW,
                    reasoning="medium",
                ),
                openai(
                    LogicalRole.IMPLEMENTATION_WORKER,
                    settings.terra_model,
                    priority=2,
                    cost=CostClass.MEDIUM,
                    reasoning="medium",
                ),
            ),
            LogicalRole.RESEARCH_WORKER: (
                openai(
                    LogicalRole.RESEARCH_WORKER,
                    settings.luna_model,
                    priority=1,
                    cost=CostClass.LOW,
                    reasoning="medium",
                ),
                kimi(LogicalRole.RESEARCH_WORKER, priority=2),
            ),
            LogicalRole.TEST_WORKER: (
                openai(
                    LogicalRole.TEST_WORKER,
                    settings.luna_model,
                    priority=1,
                    cost=CostClass.LOW,
                    reasoning="medium",
                ),
            ),
            LogicalRole.REVIEWER: (
                openai(
                    LogicalRole.REVIEWER,
                    settings.terra_model,
                    priority=1,
                    cost=CostClass.MEDIUM,
                    reasoning="high",
                ),
                openai(
                    LogicalRole.REVIEWER,
                    settings.sol_model,
                    priority=2,
                    cost=CostClass.HIGH,
                    reasoning="high",
                ),
            ),
            LogicalRole.INDEPENDENT_CRITIC: (
                kimi(LogicalRole.INDEPENDENT_CRITIC, priority=1),
                openai(
                    LogicalRole.INDEPENDENT_CRITIC,
                    settings.terra_model,
                    priority=2,
                    cost=CostClass.MEDIUM,
                    reasoning="high",
                ),
            ),
            LogicalRole.SUMMARIZER: (
                openai(
                    LogicalRole.SUMMARIZER,
                    settings.luna_model,
                    priority=1,
                    cost=CostClass.LOW,
                    reasoning="low",
                ),
            ),
        }


__all__ = ["ModelRegistry", "RegistrySettings"]
