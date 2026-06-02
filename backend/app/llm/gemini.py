from app.llm.base import LLMMessage, LLMResponse


class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        from google import genai
        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self.model = model

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        from google.genai import types
        system = "\n\n".join(m.content for m in messages if m.role == "system") or None
        contents = [
            types.Content(role="user" if m.role == "user" else "model",
                          parts=[types.Part(text=m.content)])
            for m in messages if m.role != "system"
        ]
        resp = self._client.models.generate_content(
            model=self.model, contents=contents,
            config=types.GenerateContentConfig(system_instruction=system),
        )
        u = getattr(resp, "usage_metadata", None)
        return LLMResponse(
            text=resp.text or "", model=self.model,
            prompt_tokens=getattr(u, "prompt_token_count", None),
            completion_tokens=getattr(u, "candidates_token_count", None),
            total_tokens=getattr(u, "total_token_count", None),
        )
