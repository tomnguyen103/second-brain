import pytest
from app.config import Settings
from app.llm.base import LLMMessage
from app.llm.factory import get_llm_client
from app.llm.fake import FakeLLMClient


def test_factory_selects_fake():
    assert isinstance(get_llm_client(Settings(llm_provider="fake")), FakeLLMClient)


def test_private_mode_forces_ollama():
    c = get_llm_client(Settings(llm_provider="gemini"), private_mode=True)
    assert c.model  # OllamaClient, not Gemini
    assert c.__class__.__name__ == "OllamaClient"


def test_gemini_requires_key():
    with pytest.raises(RuntimeError):
        get_llm_client(Settings(llm_provider="gemini", gemini_api_key=None))


def test_fake_cites_context_markers():
    out = FakeLLMClient().generate([LLMMessage("user", "ctx [1] and [2] then question")])
    assert "[1]" in out.text and "[2]" in out.text
