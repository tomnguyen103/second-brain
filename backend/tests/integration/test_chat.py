import os
import pytest
from app.chat.service import chat
from app.config import Settings
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from app.llm.fake import FakeLLMClient

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
