import re
from collections.abc import Iterator

from app.llm.base import LLMClient, LLMMessage, LLMResponse, LLMStreamChunk


class FakeLLMClient:
    model = "fake"

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        markers = "".join(sorted(set(re.findall(r"\[\d+\]", user)),
                                 key=lambda m: int(m.strip("[]"))))[:6]
        excerpt = "context"
        match = re.search(r"\[1\][^\n]*\n(.+?)(?:\n\n|\n</context>|\Z)", user, flags=re.S)
        if match:
            excerpt = " ".join(match.group(1).split()[:8])
            excerpt = re.sub(r"[.!?]+", "", excerpt).strip()
        text = f"(fake) {excerpt} {markers}".strip()
        return LLMResponse(text=text, model=self.model,
                           prompt_tokens=0, completion_tokens=0, total_tokens=0)

    def generate_stream(self, messages: list[LLMMessage]) -> Iterator[LLMStreamChunk]:
        resp = self.generate(messages)
        midpoint = max(1, len(resp.text) // 2)
        yield LLMStreamChunk(text=resp.text[:midpoint], model=resp.model)
        yield LLMStreamChunk(text=resp.text[midpoint:], model=resp.model)
        yield LLMStreamChunk(
            model=resp.model,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            total_tokens=resp.total_tokens,
            done=True,
        )


_: LLMClient = FakeLLMClient()  # structural conformance check
