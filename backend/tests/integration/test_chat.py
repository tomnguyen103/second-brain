import os
import pytest
from app.chat.service import chat
from app.config import Settings
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from app.llm.fake import FakeLLMClient
from app.llm.base import LLMMessage, LLMResponse

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB")


def test_chat_persists_and_cites(db_session, fake_embedder):
    ingest_documents(db_session, fake_embedder, source=SourceSpec("manual", "T"),
                     documents=[DocumentInput(title="HNSW",
                                             content="HNSW tuning m ef_construction. " * 20)])
    r = chat(db_session, fake_embedder, FakeLLMClient(), Settings(),
             message="What about HNSW tuning?")
    assert r.message_id and r.conversation_id
    assert r.retrieval["fused_returned"] >= 1
    assert r.answer  # fake driver returns a non-empty cited answer


def test_chat_empty_corpus_refuses(db_session, fake_embedder):
    r = chat(db_session, fake_embedder, FakeLLMClient(), Settings(), message="anything?")
    assert r.citations == [] and r.model is None


class _CountingLLM:
    model = "counting-fake"

    def __init__(self):
        self.calls = 0

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        self.calls += 1
        return LLMResponse(text="should not be called [1]", model=self.model)


def test_chat_refuses_weak_context_without_llm_call(db_session, fake_embedder):
    ingest_documents(db_session, fake_embedder, source=SourceSpec("manual", "Weak"),
                     documents=[DocumentInput(title="Recipe",
                                             content="Sourdough hydration notes. " * 20)])
    llm = _CountingLLM()
    r = chat(db_session, fake_embedder, llm,
             Settings(retrieval_min_vector_score=1.1),
             message="When is my flight tomorrow?")
    assert r.citations == []
    assert r.model is None
    assert r.retrieval["refusal_reason"] == "weak_context"
    assert r.retrieval["fused_returned"] == 0
    assert llm.calls == 0


def test_chat_continues_conversation(db_session, fake_embedder):
    ingest_documents(db_session, fake_embedder, source=SourceSpec("manual", "Conv"),
                     documents=[DocumentInput(title="Doc",
                                             content="Python async patterns. " * 20)])
    r1 = chat(db_session, fake_embedder, FakeLLMClient(), Settings(),
              message="Tell me about Python async.")
    r2 = chat(db_session, fake_embedder, FakeLLMClient(), Settings(),
              message="Any more details?", conversation_id=r1.conversation_id)
    assert r2.conversation_id == r1.conversation_id
    assert r2.message_id != r1.message_id
