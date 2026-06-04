from app.config import Settings
from app.llm.base import LLMMessage, LLMResponse
from app.retrieval.query import maybe_rewrite_query


class _RewriteLLM:
    model = "rewrite-fake"

    def __init__(self, text: str):
        self.text = text
        self.calls = 0
        self.messages: list[list[LLMMessage]] = []

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        self.calls += 1
        self.messages.append(messages)
        return LLMResponse(text=self.text, model=self.model)


def test_query_rewrite_disabled_does_not_call_llm():
    llm = _RewriteLLM("HNSW tuning")
    query, meta = maybe_rewrite_query(llm, Settings(_env_file=None), "What about HNSW?")
    assert query == "What about HNSW?"
    assert meta["query_rewritten"] is False
    assert llm.calls == 0


def test_query_rewrite_enabled_uses_fake_llm_response():
    settings = Settings(_env_file=None, retrieval_query_rewrite_enabled=True)
    llm = _RewriteLLM('"HNSW ef_search tuning"')
    query, meta = maybe_rewrite_query(llm, settings, "Which knob affects recall?")
    assert query == "HNSW ef_search tuning"
    assert meta["query_rewritten"] is True
    assert llm.calls == 1
