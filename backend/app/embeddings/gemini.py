"""Hosted Gemini embeddings (ADR-0002 swap point).

Using the Gemini embedding API instead of the local sentence-transformers/torch model drops
~1.5-2 GB of RAM from the box, so the always-on stack fits a small (2 GB) VPS. Selected via
`embedding_provider=gemini`.

Output is requested at `embedding_dim` (384) so it drops into the existing `vector(384)` schema
with **no migration**. Vectors are L2-normalized here because Gemini does not return normalized
vectors when the output dimensionality is reduced below the model's native size, and retrieval
uses cosine similarity (matching the local encoder's normalized output).
"""
from __future__ import annotations

import math
from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def _client():
    from google import genai  # deferred; light import (no torch)

    return genai.Client(api_key=settings.gemini_api_key)


def _l2_normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in values))
    return [v / norm for v in values] if norm > 0 else values


class GeminiEmbedder:
    """Drop-in for the local `Embedder`: same `encode` / `count_tokens` / `dim` interface."""

    model_name = settings.gemini_embedding_model
    dim = settings.embedding_dim

    def __init__(self, client=None):
        self._client = client  # injectable for tests

    def _models(self):
        return (self._client or _client()).models

    def encode(self, texts: list[str]) -> list[list[float]]:
        from google.genai import types  # deferred

        items = list(texts)
        if not items:
            return []
        out: list[list[float]] = []
        for start in range(0, len(items), 100):  # batch (the API caps inputs per request)
            batch = items[start : start + 100]
            resp = self._models().embed_content(
                model=self.model_name,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=self.dim,
                ),
            )
            out.extend(_l2_normalize([float(x) for x in e.values]) for e in resp.embeddings)
        return out

    def count_tokens(self, text: str) -> int:
        # No local tokenizer (avoiding torch is the whole point). ~4 chars/token is plenty for
        # chunk sizing, which only needs an approximate count.
        return max(1, round(len(text or "") / 4))
