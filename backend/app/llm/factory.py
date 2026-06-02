from app.config import Settings
from app.llm.base import LLMClient
from app.llm.fake import FakeLLMClient


def get_llm_client(settings: Settings, *, private_mode: bool = False) -> LLMClient:
    provider = "ollama" if private_mode else settings.llm_provider
    if provider == "fake":
        return FakeLLMClient()
    if provider == "ollama":
        from app.llm.ollama import OllamaClient
        return OllamaClient(settings.ollama_base_url, settings.ollama_model)
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("SECOND_BRAIN_GEMINI_API_KEY is required for the gemini provider")
        from app.llm.gemini import GeminiClient
        return GeminiClient(settings.gemini_api_key, settings.gemini_model)
    raise ValueError(f"unknown llm_provider: {provider}")
