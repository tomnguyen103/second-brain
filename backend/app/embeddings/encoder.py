"""Local sentence-transformers encoder (ADR-0002). Lazy singleton: the model loads once."""
from __future__ import annotations

from functools import lru_cache

from app.config import settings

DIM = 384


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer  # heavy import, deferred
    return SentenceTransformer(settings.embedding_model)


class Embedder:
    model_name = settings.embedding_model
    dim = DIM

    def encode(self, texts: list[str]) -> list[list[float]]:
        vecs = _model().encode(list(texts), normalize_embeddings=True)
        return [[float(x) for x in v] for v in vecs]

    def count_tokens(self, text: str) -> int:
        return len(_model().tokenizer.tokenize(text or ""))
