"""The live embedding smoke command stays out of CI and never prints a key."""

from decimal import Decimal
from pathlib import Path

import pytest

from scripts.semantic_embedding_smoke import (
    SmokeHit,
    SmokeReport,
    estimate_embedding_cost_usd,
    format_smoke_report,
    main,
    redact_sensitive,
)


def test_cost_estimate_uses_published_list_prices() -> None:
    assert estimate_embedding_cost_usd("text-embedding-3-small", 1_000_000) == Decimal("0.02000000")
    assert estimate_embedding_cost_usd("text-embedding-3-small", 0) == Decimal("0.00000000")
    assert estimate_embedding_cost_usd("text-embedding-3-large", 1_000_000) == Decimal("0.13000000")
    assert estimate_embedding_cost_usd("custom-embed", 10) is None


def test_report_includes_query_evidence_and_score_components() -> None:
    report = format_smoke_report(
        SmokeReport(
            model_name="text-embedding-3-small",
            dimensions=1536,
            persisted="yes",
            embedded=1,
            reused=1,
            api_requests=2,
            prompt_tokens=42,
            estimated_cost_usd="0.00000084",
            hits=(
                SmokeHit(
                    query="Python backend development",
                    evidence="Built REST services using FastAPI.",
                    lexical_score="0.0000",
                    vector_score="0.8200",
                    retrieval_score="0.2460",
                ),
            ),
        )
    )

    assert "query: Python backend development" in report
    assert "retrieved_evidence: Built REST services using FastAPI." in report
    assert "lexical_score: 0.0000" in report
    assert "vector_score: 0.8200" in report
    assert "retrieval_score: 0.2460" in report
    assert "dimensions: 1536" in report
    assert "persisted: yes" in report
    assert "api_requests: 2" in report


def test_redaction_removes_the_key_and_database_url() -> None:
    message = redact_sensitive(
        "failed for sk-test-secret-value at postgresql://user:secret@localhost/careeros",
        ("sk-test-secret-value", "postgresql://user:secret@localhost/careeros"),
    )

    assert "sk-test-secret-value" not in message
    assert "secret@localhost" not in message
    assert "[redacted]" in message


def test_source_does_not_contain_an_api_key() -> None:
    source = Path(__file__).resolve().parents[2].joinpath(
        "scripts",
        "semantic_embedding_smoke.py",
    )
    text = source.read_text(encoding="utf-8")
    assert "sk-" not in text


def test_missing_key_exits_before_openai(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("scripts.semantic_embedding_smoke.load_dotenv", lambda: False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("OpenAI client constructed")

    monkeypatch.setattr("openai.OpenAI", boom)

    assert main() == 2
    error = capsys.readouterr().err
    assert "OPENAI_API_KEY" in error


def test_missing_database_exits_before_openai(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("scripts.semantic_embedding_smoke.load_dotenv", lambda: False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret-value")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CAREEROS_PREVIEW_MODE", raising=False)

    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("OpenAI client constructed")

    monkeypatch.setattr("openai.OpenAI", boom)

    assert main() == 2
    captured = capsys.readouterr()
    assert "DATABASE_URL" in captured.err
    assert "sk-test-secret-value" not in captured.err
    assert "sk-test-secret-value" not in captured.out


def test_non_postgres_database_exits_before_openai(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("scripts.semantic_embedding_smoke.load_dotenv", lambda: False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret-value")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.delenv("CAREEROS_PREVIEW_MODE", raising=False)

    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("OpenAI client constructed")

    monkeypatch.setattr("openai.OpenAI", boom)

    assert main() == 2
    captured = capsys.readouterr()
    assert "PostgreSQL" in captured.err
    assert "sk-test-secret-value" not in captured.err


def test_preview_mode_exits_before_openai(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("scripts.semantic_embedding_smoke.load_dotenv", lambda: False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret-value")
    monkeypatch.setenv("CAREEROS_PREVIEW_MODE", "true")

    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("OpenAI client constructed")

    monkeypatch.setattr("openai.OpenAI", boom)

    assert main() == 2
    captured = capsys.readouterr()
    assert "PREVIEW_MODE" in captured.err
    assert "sk-test-secret-value" not in captured.err
