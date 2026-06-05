from collections.abc import Iterator

from app.llm.base import LLMMessage, LLMResponse, LLMStreamChunk


class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        from google import genai
        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self.model = model

    def _payload(self, messages: list[LLMMessage]):
        from google.genai import types
        system = "\n\n".join(m.content for m in messages if m.role == "system") or None
        contents = [
            types.Content(role="user" if m.role == "user" else "model",
                          parts=[types.Part(text=m.content)])
            for m in messages if m.role != "system"
        ]
        return contents, types.GenerateContentConfig(system_instruction=system)

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        contents, config = self._payload(messages)
        resp = self._client.models.generate_content(
            model=self.model, contents=contents, config=config,
        )
        u = getattr(resp, "usage_metadata", None)
        return LLMResponse(
            text=resp.text or "", model=self.model,
            prompt_tokens=getattr(u, "prompt_token_count", None),
            completion_tokens=getattr(u, "candidates_token_count", None),
            total_tokens=getattr(u, "total_token_count", None),
        )

    def generate_stream(self, messages: list[LLMMessage]) -> Iterator[LLMStreamChunk]:
        contents, config = self._payload(messages)
        usage = None
        for chunk in self._client.models.generate_content_stream(
            model=self.model, contents=contents, config=config,
        ):
            usage = getattr(chunk, "usage_metadata", None) or usage
            try:
                text = chunk.text or ""
            except ValueError:
                text = ""
            if text:
                yield LLMStreamChunk(text=text, model=self.model)
        yield LLMStreamChunk(
            model=self.model,
            prompt_tokens=getattr(usage, "prompt_token_count", None),
            completion_tokens=getattr(usage, "candidates_token_count", None),
            total_tokens=getattr(usage, "total_token_count", None),
            done=True,
        )
