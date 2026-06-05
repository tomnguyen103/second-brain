import json
import logging
from collections.abc import Iterator

import httpx
from app.llm.base import LLMMessage, LLMResponse, LLMStreamChunk

logger = logging.getLogger(__name__)


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

    def generate_stream(self, messages: list[LLMMessage]) -> Iterator[LLMStreamChunk]:
        payload = {"model": self.model, "stream": True,
                   "messages": [{"role": m.role, "content": m.content} for m in messages]}
        with httpx.stream("POST", f"{self.base_url}/api/chat", json=payload,
                          timeout=120.0) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning("ollama streaming response contained malformed JSON", exc_info=True)
                    raise RuntimeError("Ollama returned malformed streaming JSON") from exc
                if data.get("done"):
                    prompt_tokens = data.get("prompt_eval_count")
                    completion_tokens = data.get("eval_count")
                    total_tokens = (
                        prompt_tokens + completion_tokens
                        if prompt_tokens is not None and completion_tokens is not None
                        else None
                    )
                    yield LLMStreamChunk(
                        model=self.model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        done=True,
                    )
                    continue
                text = (data.get("message") or {}).get("content") or ""
                if text:
                    yield LLMStreamChunk(text=text, model=self.model)
