"""Validation that generated resume claims cite verified candidate evidence."""

from decimal import ROUND_HALF_UP, Decimal

from app.features.resume_intelligence.retrieval import CandidateEvidenceRetriever
from app.models import CandidateProfile, ResumeDraft
from app.schemas import GroundingValidationResult

_MISSING_CITATION = "no evidence citation"


def unsupported_claims_are_recoverable(result: GroundingValidationResult) -> bool:
    """Return whether every failure is an uncited claim rather than corrupt evidence.

    A claim with no citation is an unsupported requirement and can finish as
    ``not_evidenced``. A claim that cites an unknown evidence ID violates the
    grounding invariant and must still fail hard.
    """
    if result.valid or not result.unsupported_claims:
        return False
    missing_citation = f": {_MISSING_CITATION}"
    return all(claim.endswith(missing_citation) for claim in result.unsupported_claims)


def validate_resume_grounding(
    candidate: CandidateProfile,
    draft: ResumeDraft,
    *,
    retriever: CandidateEvidenceRetriever | None = None,
) -> GroundingValidationResult:
    """Reject uncited or unknown evidence references without coercing the draft."""
    retriever = retriever or CandidateEvidenceRetriever()
    valid_ids = {item.evidence_id for item in retriever.collect(candidate)}
    unsupported: list[str] = []
    cited = 0
    for claim in draft.grounding_manifest:
        evidence_ids = [str(value) for value in claim.get("evidence_ids", []) if value]
        unknown = [value for value in evidence_ids if value not in valid_ids]
        if evidence_ids and not unknown:
            cited += 1
            continue
        text = str(claim.get("text", "Unnamed resume claim"))
        reason = (
            _MISSING_CITATION
            if not evidence_ids
            else f"unknown evidence: {', '.join(unknown)}"
        )
        unsupported.append(f"{text}: {reason}")
    checked = len(draft.grounding_manifest)
    coverage = (
        (Decimal(cited) / Decimal(checked) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if checked
        else Decimal("0.00")
    )
    return GroundingValidationResult(
        valid=checked > 0 and not unsupported,
        checked_claims=checked,
        cited_claims=cited,
        citation_coverage=coverage,
        unsupported_claims=unsupported,
    )
