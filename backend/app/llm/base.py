"""Provider-agnostic LLM seam (ADR-0001)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol, TypeGuard, runtime_checkable


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


@dataclass
class LLMStreamChunk:
    text: str = ""
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    done: bool = False


@runtime_checkable
class LLMClient(Protocol):
    model: str

    def generate(self, messages: list[LLMMessage]) -> LLMResponse: ...


@runtime_checkable
class StreamingLLMClient(LLMClient, Protocol):
    def generate_stream(self, messages: list[LLMMessage]) -> Iterator[LLMStreamChunk]: ...


def supports_streaming(llm: object) -> TypeGuard[StreamingLLMClient]:
    return callable(getattr(llm, "generate_stream", None))
