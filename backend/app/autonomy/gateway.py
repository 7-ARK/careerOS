"""Validated, cached model calls routed through logical roles."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.autonomy.models import (
    AvailabilityProbe,
    AvailabilityStatus,
    ChatMessage,
    LogicalRole,
    ModelSelection,
    ProviderCall,
    ProviderCallState,
    ProviderErrorCategory,
    ProviderRequest,
    RetryPolicy,
    SanitizedProviderError,
)
from app.autonomy.providers import (
    OpenAICompatibleClient,
    build_openai_compatible_client,
    create_provider_adapter,
)
from app.autonomy.registry import ModelRegistry
from app.autonomy.store import RunStore

OutputT = TypeVar("OutputT", bound=BaseModel)


class ModelCallError(RuntimeError):
    """Raised when a provider call or structured validation fails."""

    def __init__(self, call: ProviderCall) -> None:
        self.call = call
        reason = call.error.detail if call.error else "provider call failed"
        super().__init__(reason)


class ModelGateway:
    """Resolve roles, call providers, validate output, and cache valid responses."""

    def __init__(
        self,
        registry: ModelRegistry,
        store: RunStore,
        environment: Mapping[str, str],
        *,
        client_factory: Callable[..., OpenAICompatibleClient] | None = None,
    ) -> None:
        self.registry = registry
        self.store = store
        self.environment = environment
        self.client_factory = client_factory
        self.availability: dict[tuple[str, str], AvailabilityStatus] = {}

    def call_structured(
        self,
        *,
        run_id: str,
        role: LogicalRole,
        purpose: str,
        instructions: str,
        input_text: str,
        output_type: type[OutputT],
        allow_model_fallback: bool = True,
        allow_compatibility_fallback: bool = False,
        max_output_tokens: int = 8_000,
    ) -> tuple[OutputT, ProviderCall, ModelSelection]:
        """Return one validated structured response, reusing valid cached calls."""
        selection = self.registry.resolve(
            role,
            availability=self.availability or None,
            allow_model_fallback=allow_model_fallback,
            use_compatibility_fallback=allow_compatibility_fallback,
        )
        response_format = {
            "type": "json_schema",
            "name": output_type.__name__.casefold(),
            "strict": True,
            "schema": output_type.model_json_schema(),
        }
        messages = [
            ChatMessage(role="developer", content=instructions),
            ChatMessage(role="user", content=input_text),
        ]
        prompt_hash = _prompt_hash(
            selection=selection,
            purpose=purpose,
            messages=messages,
            response_format=response_format,
        )
        cached = self._load_cached(run_id, prompt_hash, output_type)
        if cached is not None:
            output, call = cached
            return output, call, selection

        self.store.append_event(
            run_id,
            {
                "event": "model_selected",
                "role": role.value,
                "purpose": purpose,
                "provider": selection.spec.provider,
                "model": selection.spec.model,
                "fallback_from": selection.fallback_from,
                "compatibility_fallback": selection.used_compatibility_fallback,
                "warning": selection.warning,
            },
        )
        self.store.write_json(
            run_id,
            "provider_call_checkpoint.json",
            {
                "status": "running",
                "prompt_hash": prompt_hash,
                "purpose": purpose,
                "provider": selection.spec.provider,
                "model": selection.spec.model,
                "started_at": datetime.now(UTC).isoformat(),
            },
        )
        self.store.append_event(
            run_id,
            {
                "event": "provider_call_started",
                "prompt_hash": prompt_hash,
                "purpose": purpose,
                "provider": selection.spec.provider,
                "model": selection.spec.model,
            },
        )
        api_key = self.environment.get(selection.spec.api_key_env, "").strip()
        if not api_key:
            call = ProviderCall(
                role=role,
                provider=selection.spec.provider,
                model=selection.spec.model,
                purpose=purpose,
                state=ProviderCallState.FAILED,
                attempts=1,
                prompt_hash=prompt_hash,
                duration_ms=0,
                error=SanitizedProviderError(
                    category=ProviderErrorCategory.AUTHENTICATION,
                    detail=f"{selection.spec.api_key_env} is not configured",
                    retryable=False,
                ),
            )
            self._record_call(run_id, call)
            self._complete_checkpoint(run_id, call)
            raise ModelCallError(call)

        client = build_openai_compatible_client(
            selection.spec,
            api_key,
            client_factory=self.client_factory,
        )
        adapter = create_provider_adapter(
            self.registry,
            role,
            client,
            use_compatibility_fallback=selection.used_compatibility_fallback,
        )
        # Preserve the exact fallback candidate selected from availability.
        adapter.spec = selection.spec
        call = adapter.call(
            ProviderRequest(
                purpose=purpose,
                messages=messages,
                response_format=response_format,
                reasoning_effort=selection.spec.default_reasoning_effort,
                max_output_tokens=min(
                    max_output_tokens,
                    selection.spec.maximum_output or max_output_tokens,
                ),
                retry_policy=selection.spec.retry_policy,
            )
        ).model_copy(update={"prompt_hash": prompt_hash})
        if call.state is ProviderCallState.FAILED:
            self._record_call(run_id, call)
            self._complete_checkpoint(run_id, call)
            raise ModelCallError(call)
        try:
            payload = call.structured_output
            if payload is None and call.text:
                payload = json.loads(call.text)
            output = output_type.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            invalid_call = call.model_copy(
                update={
                    "state": ProviderCallState.FAILED,
                    "structured_output": None,
                    "text": None,
                    "error": SanitizedProviderError(
                        category=ProviderErrorCategory.OUTPUT_VALIDATION,
                        detail=(
                            "provider returned output that did not satisfy "
                            f"{output_type.__name__}: {type(exc).__name__}"
                        ),
                        retryable=False,
                    ),
                }
            )
            self._record_call(run_id, invalid_call)
            self._complete_checkpoint(run_id, invalid_call)
            raise ModelCallError(invalid_call) from exc

        validated_call = call.model_copy(
            update={"structured_output": output.model_dump(mode="json")}
        )
        self._record_call(run_id, validated_call)
        self._save_cached(run_id, prompt_hash, output, validated_call)
        self._complete_checkpoint(run_id, validated_call)
        return output, validated_call, selection

    def probe_role(self, *, run_id: str, role: LogicalRole) -> AvailabilityProbe:
        """Probe a role's primary model at most once per run."""
        spec = self.registry.get(role)
        existing = self._load_probe(run_id, spec.provider, spec.model)
        if existing is not None:
            self.availability[(spec.provider, spec.model)] = existing.status
            return existing
        checkpoint_name = _probe_checkpoint_name(spec.provider, spec.model)
        if self.store.exists(run_id, checkpoint_name):
            checkpoint = self.store.read_json(run_id, checkpoint_name)
            if checkpoint.get("status") == "running":
                probe = AvailabilityProbe(
                    provider=spec.provider,
                    model=spec.model,
                    status=AvailabilityStatus.UNAVAILABLE,
                    authenticated=None,
                    endpoint=spec.endpoint,
                    endpoint_reachable=None,
                    tool_calling=spec.capabilities.tool_calling,
                    structured_output=spec.capabilities.structured_output,
                    duration_ms=0,
                    error=SanitizedProviderError(
                        category=ProviderErrorCategory.UNKNOWN,
                        detail=(
                            "prior availability probe outcome is ambiguous; probe was not repeated"
                        ),
                        retryable=False,
                    ),
                    probed_at=datetime.now(UTC),
                )
                self.availability[(spec.provider, spec.model)] = probe.status
                self._save_probe(run_id, probe)
                return probe
        self.store.write_json(
            run_id,
            checkpoint_name,
            {
                "status": "running",
                "provider": spec.provider,
                "model": spec.model,
                "started_at": datetime.now(UTC).isoformat(),
            },
        )

        api_key = self.environment.get(spec.api_key_env, "").strip()
        if not api_key:
            probe = AvailabilityProbe(
                provider=spec.provider,
                model=spec.model,
                status=AvailabilityStatus.UNAVAILABLE,
                authenticated=False,
                endpoint=spec.endpoint,
                endpoint_reachable=None,
                tool_calling=spec.capabilities.tool_calling,
                structured_output=spec.capabilities.structured_output,
                duration_ms=0,
                error=SanitizedProviderError(
                    category=ProviderErrorCategory.AUTHENTICATION,
                    detail=f"{spec.api_key_env} is not configured",
                    retryable=False,
                ),
                probed_at=datetime.now(UTC),
            )
        else:
            client = build_openai_compatible_client(
                spec,
                api_key,
                client_factory=self.client_factory,
            )
            adapter = create_provider_adapter(self.registry, role, client)
            probe = adapter.probe(
                ProviderRequest(
                    purpose="availability_probe",
                    messages=[
                        ChatMessage(
                            role="user",
                            content='Return exactly {"status":"available"}.',
                        )
                    ],
                    max_output_tokens=32,
                    retry_policy=RetryPolicy(max_transient_retries=0),
                )
            )
        self.availability[(spec.provider, spec.model)] = probe.status
        self._save_probe(run_id, probe)
        self.store.write_json(
            run_id,
            checkpoint_name,
            {
                "status": "completed",
                "provider": spec.provider,
                "model": spec.model,
                "result": probe.status.value,
                "response_id": probe.response_id,
            },
        )
        return probe

    def _record_call(self, run_id: str, call: ProviderCall) -> None:
        self.store.append_records(
            run_id,
            "provider_calls.jsonl",
            [call.model_dump(mode="json", exclude={"text"})],
        )

    def _complete_checkpoint(self, run_id: str, call: ProviderCall) -> None:
        self.store.write_json(
            run_id,
            "provider_call_checkpoint.json",
            {
                "status": "completed",
                "prompt_hash": call.prompt_hash,
                "purpose": call.purpose,
                "provider": call.provider,
                "model": call.model,
                "call_id": str(call.call_id),
                "result": call.state.value,
            },
        )
        self.store.append_event(
            run_id,
            {
                "event": "provider_call_completed",
                "prompt_hash": call.prompt_hash,
                "purpose": call.purpose,
                "provider": call.provider,
                "model": call.model,
                "call_id": str(call.call_id),
                "result": call.state.value,
            },
        )

    def _cache_path_payload(self, run_id: str) -> dict[str, Any]:
        if not self.store.exists(run_id, "model_call_cache.json"):
            return {"schema_version": 1, "entries": {}}
        return self.store.read_json(run_id, "model_call_cache.json")

    def _load_cached(
        self,
        run_id: str,
        prompt_hash: str,
        output_type: type[OutputT],
    ) -> tuple[OutputT, ProviderCall] | None:
        entry = self._cache_path_payload(run_id).get("entries", {}).get(prompt_hash)
        if not isinstance(entry, dict) or not entry.get("validated"):
            return None
        try:
            output = output_type.model_validate(entry["output"])
            call = ProviderCall.model_validate(entry["call"]).model_copy(update={"cached": True})
        except (KeyError, ValidationError, TypeError):
            return None
        return output, call

    def _save_cached(
        self,
        run_id: str,
        prompt_hash: str,
        output: BaseModel,
        call: ProviderCall,
    ) -> None:
        payload = self._cache_path_payload(run_id)
        entries = payload.setdefault("entries", {})
        entries[prompt_hash] = {
            "validated": True,
            "output": output.model_dump(mode="json"),
            "call": call.model_dump(mode="json", exclude={"text"}),
        }
        self.store.write_json(run_id, "model_call_cache.json", payload)

    def _load_probe(self, run_id: str, provider: str, model: str) -> AvailabilityProbe | None:
        if not self.store.exists(run_id, "model_availability_report.json"):
            return None
        payload = self.store.read_json(run_id, "model_availability_report.json")
        for item in payload.get("probes", []):
            if item.get("provider") == provider and item.get("model") == model:
                return AvailabilityProbe.model_validate(item)
        return None

    def _save_probe(self, run_id: str, probe: AvailabilityProbe) -> None:
        probes: list[dict[str, Any]] = []
        if self.store.exists(run_id, "model_availability_report.json"):
            payload = self.store.read_json(run_id, "model_availability_report.json")
            probes = list(payload.get("probes", []))
        probes = [
            item
            for item in probes
            if not (item.get("provider") == probe.provider and item.get("model") == probe.model)
        ]
        probes.append(probe.model_dump(mode="json"))
        self.store.write_json(
            run_id,
            "model_availability_report.json",
            {"probes": probes},
        )


def _prompt_hash(
    *,
    selection: ModelSelection,
    purpose: str,
    messages: list[ChatMessage],
    response_format: dict[str, Any],
) -> str:
    payload = {
        "provider": selection.spec.provider,
        "model": selection.spec.model,
        "endpoint": selection.spec.endpoint,
        "purpose": purpose,
        "messages": [message.model_dump(mode="json") for message in messages],
        "response_format": response_format,
        "reasoning_effort": selection.spec.default_reasoning_effort,
        "tool_policy": "structured-no-shell-v1",
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _probe_checkpoint_name(provider: str, model: str) -> str:
    digest = hashlib.sha256(f"{provider}:{model}".encode()).hexdigest()[:16]
    return f"probe-checkpoint-{digest}.json"


__all__ = ["ModelCallError", "ModelGateway"]
