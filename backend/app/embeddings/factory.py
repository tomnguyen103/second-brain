"""Embedding-provider factory (ADR-0002).

Selects the local sentence-transformers/torch model or the hosted Gemini API by
`settings.embedding_provider`, so the always-on box can drop the torch RAM footprint and run on
a small VPS. Imports are deferred so choosing `gemini` never imports torch (and vice versa).
"""
from __future__ import annotations

from app.config import Settings


def build_embedder(settings: Settings):
    """Return the embedder for the configured provider (`local` | `gemini`)."""
    provider = settings.embedding_provider
    if provider == "local":
        from app.embeddings.encoder import Embedder

        return Embedder()
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError(
                "SECOND_BRAIN_GEMINI_API_KEY is required for the gemini embedding provider"
            )
        from app.embeddings.gemini import GeminiEmbedder

        return GeminiEmbedder()
    raise ValueError(f"unknown embedding_provider: {provider!r}")
