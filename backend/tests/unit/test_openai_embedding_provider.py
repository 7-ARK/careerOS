"""OpenAI embedding provider behavior with a fake client. No network calls."""

from __future__ import annotations

import pytest

from app.features.resume_intelligence.retrieval import (
    DeterministicHashEmbeddingProvider,
    EmbeddingProviderError,
    OpenAIEmbeddingProvider,
    build_embedding_provider,
)


class _Item:
    def __init__(self, index: int, embedding: list[float]) -> None:
        self.index = index
        self.embedding = embedding


class _Usage:
    def __init__(self, prompt_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens


class _Response:
    def __init__(self, data: list[_Item], prompt_tokens: int) -> None:
        self.data = data
        self.usage = _Usage(prompt_tokens)


class FakeClient:
    """Stand-in for openai.OpenAI that records requests and returns canned vectors."""

    def __init__(self, *, api_key: str, timeout: float, max_retries: int) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.calls: list[dict[str, object]] = []
        self.width = 1536
        self.error: Exception | None = None
        self.reverse = False
        self.drop_last = False
        self.bad_width = False
        self.non_finite = False
        self.non_numeric = False
        self.skip_index = False
        self.embeddings = self._Embeddings(self)

    class _Embeddings:
        def __init__(self, client: FakeClient) -> None:
            self.client = client

        def create(self, **kwargs: object) -> _Response:
            client = self.client
            client.calls.append(kwargs)
            if client.error is not None:
                raise client.error
            texts = list(kwargs["input"])  # type: ignore[arg-type]
            width = int(kwargs["dimensions"]) if "dimensions" in kwargs else client.width
            vectors = [[float(index + 1), *([0.0] * (width - 1))] for index in range(len(texts))]
            if client.bad_width:
                vectors = [vector[:-1] or [1.0] for vector in vectors]
            if client.non_finite:
                vectors = [[float("nan"), *vector[1:]] for vector in vectors]
            if client.non_numeric:
                vectors = [["nope", *vector[1:]] for vector in vectors]  # type: ignore[list-item]
            data = [_Item(index, vector) for index, vector in enumerate(vectors)]
            if client.skip_index and data:
                data[-1].index = len(data) + 5
            if client.reverse:
                data = list(reversed(data))
            if client.drop_last:
                data = data[:-1]
            return _Response(data, prompt_tokens=len(texts))


@pytest.fixture
def fake_openai(monkeypatch: pytest.MonkeyPatch) -> dict[str, FakeClient]:
    """Return one client for every SDK construction so later tests can set flags."""
    client = FakeClient(api_key="", timeout=0, max_retries=0)
    holder = {"client": client}

    def factory(*, api_key: str, timeout: float, max_retries: int) -> FakeClient:
        client.api_key = api_key
        client.timeout = timeout
        client.max_retries = max_retries
        return client

    monkeypatch.setattr("openai.OpenAI", factory)
    return holder


def test_construction_does_not_call_openai(fake_openai: dict[str, FakeClient]) -> None:
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test-secret-value",
        model_name="text-embedding-3-small",
        timeout_seconds=12,
    )

    assert provider.model_name == "text-embedding-3-small"
    assert provider.dimensions == 1536
    assert "sk-test-secret-value" not in repr(provider)
    assert fake_openai["client"].calls == []
    assert fake_openai["client"].api_key == ""


def test_deterministic_embed_does_not_construct_an_openai_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("OpenAI client constructed")

    monkeypatch.setattr("openai.OpenAI", boom)
    vectors = DeterministicHashEmbeddingProvider().embed(["FastAPI"])

    assert len(vectors) == 1
    assert len(vectors[0]) == 256


def test_batches_validate_order_and_record_usage(fake_openai: dict[str, FakeClient]) -> None:
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test-secret-value",
        model_name="text-embedding-3-small",
        timeout_seconds=12,
        dimensions=4,
        batch_size=2,
    )
    fake_holder = fake_openai

    vectors = provider.embed(["one", "two", "three", "four", "five"])
    client = fake_holder["client"]

    assert [len(call["input"]) for call in client.calls] == [2, 2, 1]  # type: ignore[arg-type]
    assert all(call["model"] == "text-embedding-3-small" for call in client.calls)
    assert all(call["dimensions"] == 4 for call in client.calls)
    assert all(call["timeout"] == 12.0 for call in client.calls)
    assert client.timeout == 12.0
    assert client.max_retries == 1
    assert [vector[0] for vector in vectors] == [1.0, 2.0, 1.0, 2.0, 1.0]
    assert all(len(vector) == 4 for vector in vectors)
    assert provider.usage.requests == 3
    assert provider.usage.prompt_tokens == 5
    assert "sk-test-secret-value" not in repr(provider)


def test_response_order_follows_input_index(fake_openai: dict[str, FakeClient]) -> None:
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test-secret-value",
        model_name="text-embedding-3-small",
        timeout_seconds=5,
        dimensions=4,
    )
    vectors = provider.embed(["alpha", "beta"])
    fake_openai["client"].reverse = True
    ordered = provider.embed(["alpha", "beta"])

    assert [vector[0] for vector in vectors] == [1.0, 2.0]
    assert [vector[0] for vector in ordered] == [1.0, 2.0]


def test_default_model_dimensions_are_validated_and_not_sent(
    fake_openai: dict[str, FakeClient],
) -> None:
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test-secret-value",
        model_name="text-embedding-3-small",
        timeout_seconds=5,
    )

    vectors = provider.embed(["hello"])

    assert "dimensions" not in fake_openai["client"].calls[0]
    assert len(vectors[0]) == 1536
    assert provider.dimensions == 1536


def test_known_model_defaults() -> None:
    large = OpenAIEmbeddingProvider(
        api_key="sk-test-secret-value",
        model_name="text-embedding-3-large",
        timeout_seconds=5,
    )
    ada = OpenAIEmbeddingProvider(
        api_key="sk-test-secret-value",
        model_name="text-embedding-ada-002",
        timeout_seconds=5,
    )

    assert large.dimensions == 3072
    assert ada.dimensions == 1536


def test_unknown_model_locks_dimensions_from_the_first_response(
    fake_openai: dict[str, FakeClient],
) -> None:
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test-secret-value",
        model_name="custom-embed",
        timeout_seconds=5,
    )
    fake_openai["client"].width = 8
    assert provider.dimensions is None

    provider.embed(["hello"])
    assert provider.dimensions == 8

    fake_openai["client"].width = 4
    with pytest.raises(EmbeddingProviderError, match="expected 8"):
        provider.embed(["again"])


def test_vector_count_mismatch_fails(fake_openai: dict[str, FakeClient]) -> None:
    provider = _provider()
    provider.embed(["warmup"])
    fake_openai["client"].drop_last = True

    with pytest.raises(EmbeddingProviderError, match="returned 1 vectors for 2 inputs"):
        provider.embed(["one", "two"])


def test_dimension_mismatch_fails(fake_openai: dict[str, FakeClient]) -> None:
    provider = _provider()
    provider.embed(["warmup"])
    fake_openai["client"].bad_width = True

    with pytest.raises(EmbeddingProviderError, match="expected 4"):
        provider.embed(["one"])


def test_non_finite_and_non_numeric_values_fail(fake_openai: dict[str, FakeClient]) -> None:
    provider = _provider()
    provider.embed(["warmup"])
    fake_openai["client"].non_finite = True
    with pytest.raises(EmbeddingProviderError, match="non-finite"):
        provider.embed(["one"])

    fake_openai["client"].non_finite = False
    fake_openai["client"].non_numeric = True
    with pytest.raises(EmbeddingProviderError, match="non-numeric"):
        provider.embed(["one"])


def test_missing_index_fails(fake_openai: dict[str, FakeClient]) -> None:
    provider = _provider()
    provider.embed(["warmup"])
    fake_openai["client"].skip_index = True

    with pytest.raises(EmbeddingProviderError, match="every input index"):
        provider.embed(["one", "two"])


def test_api_errors_fail_clearly_without_the_key(fake_openai: dict[str, FakeClient]) -> None:
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test-secret-value",
        model_name="text-embedding-3-small",
        timeout_seconds=5,
        dimensions=4,
    )

    provider.embed(["warmup"])
    fake_openai["client"].error = RuntimeError(
        "Incorrect API key provided: sk-test-secret-value"
    )
    with pytest.raises(EmbeddingProviderError, match="request failed") as caught:
        provider.embed(["hello"])

    message = str(caught.value)
    assert "text-embedding-3-small" in message
    assert "RuntimeError" in message
    assert "sk-test-secret-value" not in message
    assert caught.value.__cause__ is None


def test_empty_input_does_not_call_the_client(fake_openai: dict[str, FakeClient]) -> None:
    provider = _provider()

    assert provider.embed([]) == []
    assert fake_openai["client"].calls == []
    assert provider.usage.requests == 0


def test_provider_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "deterministic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret-value")
    assert isinstance(build_embedding_provider(), DeterministicHashEmbeddingProvider)

    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("RAG_EMBEDDING_DIMENSIONS", raising=False)
    assert isinstance(build_embedding_provider(), DeterministicHashEmbeddingProvider)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret-value")
    monkeypatch.setenv("RAG_EMBEDDING_MODEL", "text-embedding-3-large")
    monkeypatch.setenv("RAG_EMBEDDING_DIMENSIONS", "256")
    monkeypatch.setenv("PROVIDER_TIMEOUT_SECONDS", "9")
    selected = build_embedding_provider()
    assert isinstance(selected, OpenAIEmbeddingProvider)
    assert selected.model_name == "text-embedding-3-large"
    assert selected.dimensions == 256
    assert selected.timeout_seconds == 9
    assert "sk-test-secret-value" not in repr(selected)


def _provider() -> OpenAIEmbeddingProvider:
    return OpenAIEmbeddingProvider(
        api_key="sk-test-secret-value",
        model_name="text-embedding-3-small",
        timeout_seconds=5,
        dimensions=4,
    )
