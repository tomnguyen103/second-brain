"""Provider-agnostic LLM seam (ADR-0001)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class LLMMessage:
    role: str          # system | user | assistant
    content: str


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@runtime_checkable
class LLMClient(Protocol):
    model: str

    def generate(self, messages: list[LLMMessage]) -> LLMResponse: ...
