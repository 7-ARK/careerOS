"""Intentionally semantic vectors for retrieval tests.

These vectors stand in for an embedding model. Tests must not call OpenAI.
"""

from decimal import ROUND_HALF_UP, Decimal

PYTHON_BACKEND_QUERY = "Python backend development"
FASTAPI_EVIDENCE = "Built REST services using FastAPI."
RELATIONAL_QUERY = "relational database experience"
POSTGRES_EVIDENCE = "Designed PostgreSQL schemas and queries."
AWS_QUERY = "AWS experience"
GCP_EVIDENCE = "Deployed applications to Google Cloud."
UNRELATED_EVIDENCE = "Studied art history in college."

PYTHON_QUERY_VECTOR = [1.0, 0.0, 0.0, 0.0]
FASTAPI_VECTOR = [0.96, 0.28, 0.0, 0.0]
RELATIONAL_QUERY_VECTOR = [0.0, 1.0, 0.0, 0.0]
POSTGRES_VECTOR = [0.0, 0.8, 0.6, 0.0]
AWS_QUERY_VECTOR = [0.0, 0.0, 1.0, 0.0]
GCP_VECTOR = [0.0, 0.0, 1.0, 0.0]
UNRELATED_VECTOR = [0.0, 0.0, 0.0, 1.0]


class SemanticMockEmbeddingProvider:
    """Map the Phase 2 examples onto fixed, human-chosen vectors."""

    provider_name = "semantic_mock"
    model_name = "semantic-mock-v1"
    dimensions = 4

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [list(self._vector(text)) for text in texts]

    @staticmethod
    def _vector(text: str) -> list[float]:
        folded = text.casefold()
        if PYTHON_BACKEND_QUERY.casefold() in folded:
            return PYTHON_QUERY_VECTOR
        if "fastapi" in folded:
            return FASTAPI_VECTOR
        if RELATIONAL_QUERY.casefold() in folded:
            return RELATIONAL_QUERY_VECTOR
        if "postgresql" in folded:
            return POSTGRES_VECTOR
        if AWS_QUERY.casefold() in folded:
            return AWS_QUERY_VECTOR
        if "google cloud" in folded:
            return GCP_VECTOR
        if "art history" in folded:
            return UNRELATED_VECTOR
        raise AssertionError(f"semantic mock has no vector for {text!r}")


def expected_hybrid_score(lexical: Decimal, vector: Decimal) -> Decimal:
    """The unchanged 0.7 lexical / 0.3 vector score, quantized like retrieval."""
    combined = min(Decimal("1"), lexical * Decimal("0.7") + vector * Decimal("0.3"))
    return combined.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
