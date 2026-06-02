import httpx
from app.llm.base import LLMMessage, LLMResponse


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.1"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        payload = {"model": self.model, "stream": False,
                   "messages": [{"role": m.role, "content": m.content} for m in messages]}
        r = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=120.0)
        r.raise_for_status()
        data = r.json()
        return LLMResponse(text=data["message"]["content"], model=self.model,
                           prompt_tokens=data.get("prompt_eval_count"),
                           completion_tokens=data.get("eval_count"))
