"""Unit tests for the hosted Gemini embedder + the provider factory (ADR-0002 swap point)."""
import pytest

from app.config import Settings
from app.embeddings.factory import build_embedder
from app.embeddings.gemini import GeminiEmbedder, _l2_normalize


class _StubEmbedding:
    def __init__(self, values):
        self.values = values


class _StubResp:
    def __init__(self, embeddings):
        self.embeddings = embeddings


class _StubModels:
    def __init__(self):
        self.calls = []

    def embed_content(self, *, model, contents, config):
        self.calls.append({"model": model, "n": len(contents)})
        # Unnormalized 384-dim vectors (3,4,0...) -> should come back as 0.6,0.8,0...
        return _StubResp([_StubEmbedding([3.0, 4.0] + [0.0] * 382) for _ in contents])


class _StubClient:
    def __init__(self):
        self.models = _StubModels()


def test_l2_normalize():
    assert _l2_normalize([3.0, 4.0]) == [0.6, 0.8]
    assert _l2_normalize([0.0, 0.0]) == [0.0, 0.0]  # no div-by-zero


def test_encode_shape_and_normalized():
    emb = GeminiEmbedder(client=_StubClient())
    out = emb.encode(["a", "b", "c"])
    assert len(out) == 3 and all(len(v) == 384 for v in out)
    assert abs(out[0][0] - 0.6) < 1e-9 and abs(out[0][1] - 0.8) < 1e-9
    assert abs(sum(x * x for x in out[0]) - 1.0) < 1e-9  # unit length


def test_encode_empty_makes_no_call():
    client = _StubClient()
    emb = GeminiEmbedder(client=client)
    assert emb.encode([]) == []
    assert client.models.calls == []


def test_encode_batches_over_100():
    client = _StubClient()
    emb = GeminiEmbedder(client=client)
    out = emb.encode([f"t{i}" for i in range(250)])
    assert len(out) == 250
    assert [c["n"] for c in client.models.calls] == [100, 100, 50]


def test_count_tokens_heuristic_no_tokenizer():
    emb = GeminiEmbedder(client=_StubClient())
    assert emb.count_tokens("") == 1
    assert emb.count_tokens("a" * 40) == 10


def test_factory_local_returns_local_embedder():
    from app.embeddings.encoder import Embedder

    assert isinstance(build_embedder(Settings(embedding_provider="local")), Embedder)


def test_factory_gemini_returns_gemini_embedder():
    emb = build_embedder(Settings(embedding_provider="gemini", gemini_api_key="test-key"))
    assert isinstance(emb, GeminiEmbedder)


def test_factory_gemini_requires_key():
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        build_embedder(Settings(embedding_provider="gemini", gemini_api_key=None))


def test_factory_unknown_provider():
    with pytest.raises(ValueError, match="unknown embedding_provider"):
        build_embedder(Settings(embedding_provider="bogus"))
