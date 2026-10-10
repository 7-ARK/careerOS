"""Grounding failures that are unsupported claims versus corrupted citations."""

from decimal import Decimal

from app.features.resume_intelligence.grounding import unsupported_claims_are_recoverable
from app.schemas import GroundingValidationResult


def _result(*, valid: bool, unsupported: list[str], checked: int = 1) -> GroundingValidationResult:
    return GroundingValidationResult(
        valid=valid,
        checked_claims=checked,
        cited_claims=0 if unsupported else checked,
        citation_coverage=Decimal("0.00") if unsupported else Decimal("100.00"),
        unsupported_claims=unsupported,
    )


def test_missing_citation_for_any_vendor_token_is_recoverable() -> None:
    result = _result(
        valid=False,
        unsupported=[
            "OpenAI: no evidence citation",
            "Anthropic: no evidence citation",
        ],
        checked=2,
    )
    assert unsupported_claims_are_recoverable(result)


def test_unknown_evidence_is_not_recoverable() -> None:
    result = _result(
        valid=False,
        unsupported=["Kubernetes: unknown evidence: project-missing"],
    )
    assert not unsupported_claims_are_recoverable(result)


def test_mixed_missing_citation_and_unknown_evidence_is_not_recoverable() -> None:
    result = _result(
        valid=False,
        unsupported=[
            "OpenAI: no evidence citation",
            "Kubernetes: unknown evidence: project-missing",
        ],
        checked=2,
    )
    assert not unsupported_claims_are_recoverable(result)


def test_empty_manifest_is_not_a_recoverable_unsupported_claim() -> None:
    result = _result(valid=False, unsupported=[], checked=0)
    assert not unsupported_claims_are_recoverable(result)
