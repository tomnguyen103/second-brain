import re
from app.llm.base import LLMClient, LLMMessage, LLMResponse


class FakeLLMClient:
    model = "fake"

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        markers = "".join(sorted(set(re.findall(r"\[\d+\]", user)),
                                 key=lambda m: int(m.strip("[]"))))[:6]
        text = f"(fake) answer grounded in context {markers}".strip()
        return LLMResponse(text=text, model=self.model,
                           prompt_tokens=0, completion_tokens=0, total_tokens=0)


_: LLMClient = FakeLLMClient()  # structural conformance check
