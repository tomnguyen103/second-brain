"""Shared fixtures for all tests: fake embedder + test settings."""
from __future__ import annotations

import hashlib
import os

import pytest

from app.config import Settings


class _FakeEmbedder:
    """Deterministic 384-d embedder for tests — no model load, no network."""
    model_name = "fake-embedder"
    dim = 384

    def encode(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            # Hash-derived unit vector so cosine similarity is stable & keyword-sensitive
            digest = hashlib.sha256(text.encode()).digest()
            vec = [0.0] * 384
            for i, b in enumerate(digest[:48]):
                vec[i * 8] = (b - 128) / 128.0
            norm = sum(v * v for v in vec) ** 0.5 or 1.0
            results.append([v / norm for v in vec])
        return results

    def count_tokens(self, text: str) -> int:
        return len((text or "").split())


@pytest.fixture
def fake_embedder():
    return _FakeEmbedder()


@pytest.fixture
def test_settings():
    return Settings(_env_file=None, llm_provider="fake", api_token="test-api-token")
