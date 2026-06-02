"""Named eval configs for A/B (ADR-0009).

A config is the unit we compare in MLflow: an LLM driver + a prompt version + a top_k. The
default A/B (`baseline` vs `variant`) is deterministic (`fake` driver) for CI/repro; `gemini`
is the opt-in real run that produces the shareable comparison.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings


@dataclass(frozen=True)
class EvalConfig:
    name: str
    llm_provider: str       # gemini | ollama | fake
    prompt_version: str     # rag-v1 | rag-v2
    top_k: int


CONFIGS: dict[str, EvalConfig] = {
    "baseline": EvalConfig("baseline", "fake", "rag-v1", 5),
    "variant": EvalConfig("variant", "fake", "rag-v2", 8),
    "gemini": EvalConfig("gemini", "gemini", "rag-v1", 5),
}


def settings_for(config: EvalConfig, base: Settings | None = None) -> Settings:
    """A Settings copy with this config's overrides applied (does not re-read env)."""
    base = base or Settings()
    return base.model_copy(update={
        "llm_provider": config.llm_provider,
        "prompt_version": config.prompt_version,
        "retrieval_top_k": config.top_k,
    })
