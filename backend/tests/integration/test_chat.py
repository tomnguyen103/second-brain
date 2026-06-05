import os
import pytest
from app.chat.service import CITATION_FAILURE_TEXT, chat, stream_chat
from app.config import Settings
from app.db.models import Message
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from app.llm.fake import FakeLLMClient
from app.llm.base import LLMMessage, LLMResponse, LLMStreamChunk

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
    r = chat(
        db_session,
        fake_embedder,
        FakeLLMClient(),
        Settings(),
        message="anything?",
        filters={"source_ids": [-1]},
    )
    assert r.citations == [] and r.model is None


class _CountingLLM:
    model = "counting-fake"

    def __init__(self):
        self.calls = 0

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        self.calls += 1
        return LLMResponse(text="should not be called [1]", model=self.model)


class _UncitedLLM:
    model = "uncited-fake"

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        return LLMResponse(text="This answer has no citation marker.", model=self.model)


class _UnsupportedCitedLLM:
    model = "unsupported-cited-fake"

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        return LLMResponse(text="The moon is made of cheese [1].", model=self.model)


class _RepairingCitationLLM:
    model = "repairing-citation-fake"

    def __init__(self):
        self.calls = 0

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                text=(
                    "Here is what the notes say. "
                    "Hybrid retrieval combines vector search and full-text search [1]."
                ),
                model=self.model,
            )
        return LLMResponse(
            text="Hybrid retrieval combines vector search and full-text search [1].",
            model=self.model,
        )


class _LeakyStreamingLLM:
    model = "leaky-stream-fake"

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        return LLMResponse(text="SECRET_STREAM_LEAK with no citation marker.", model=self.model)

    def generate_stream(self, messages: list[LLMMessage]):
        yield LLMStreamChunk(text="SECRET_STREAM_LEAK ", model=self.model)
        yield LLMStreamChunk(text="with no citation marker.", model=self.model)
        yield LLMStreamChunk(
            model=self.model,
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
            done=True,
        )


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


def test_chat_replaces_uncited_answer_with_citation_failure(db_session, fake_embedder):
    ingest_documents(db_session, fake_embedder, source=SourceSpec("manual", "Citations"),
                     documents=[DocumentInput(title="Citation policy",
                                             content="Every sourced claim needs markers. " * 20)])
    r = chat(db_session, fake_embedder, _UncitedLLM(), Settings(),
             message="What does the policy require?")

    assert r.answer == CITATION_FAILURE_TEXT
    assert r.citations == []
    assert r.retrieval["citation_validation_failed"] is True
    stored = db_session.get(Message, r.message_id)
    assert stored is not None
    assert stored.content == CITATION_FAILURE_TEXT


def test_chat_replaces_unsupported_cited_answer_with_citation_failure(db_session, fake_embedder):
    ingest_documents(db_session, fake_embedder, source=SourceSpec("manual", "Support"),
                     documents=[DocumentInput(title="Citation support",
                                             content="Every sourced claim needs markers. " * 20)])
    r = chat(db_session, fake_embedder, _UnsupportedCitedLLM(), Settings(),
             message="What does the policy require?")

    assert r.answer == CITATION_FAILURE_TEXT
    assert r.citations == []
    assert r.retrieval["citation_validation_failed"] is True
    assert r.retrieval["citation_failure_reason"] == "unsupported_claims"
    assert r.retrieval["unsupported_citation_segments"]


def test_chat_repairs_uncited_framing_before_persisting(db_session, fake_embedder):
    ingest_documents(db_session, fake_embedder, source=SourceSpec("manual", "Repair"),
                     documents=[DocumentInput(title="Hybrid retrieval",
                                             content=(
                                                 "Hybrid retrieval combines vector search "
                                                 "and full-text search. "
                                             ) * 20)])
    llm = _RepairingCitationLLM()
    r = chat(db_session, fake_embedder, llm, Settings(),
             message="What does hybrid retrieval combine?")

    assert llm.calls == 2
    assert r.answer == "Hybrid retrieval combines vector search and full-text search [1]."
    assert r.citations
    assert r.retrieval["citation_repair_attempted"] is True
    assert r.retrieval["citation_repair_succeeded"] is True
    stored = db_session.get(Message, r.message_id)
    assert stored is not None
    assert stored.content == r.answer


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


def test_agentic_chat_persists_cited_answer_with_trace(db_session, fake_embedder):
    from app.agentic_rag.service import agentic_chat

    ingest_documents(db_session, fake_embedder, source=SourceSpec("manual", "Agentic"),
                     documents=[DocumentInput(title="Agentic HNSW",
                                             content="HNSW tuning m ef_construction. " * 20)])

    r = agentic_chat(
        db_session,
        fake_embedder,
        FakeLLMClient(),
        Settings(agentic_rag_enabled=True),
        message="What about HNSW tuning?",
    )

    assert r.message_id and r.conversation_id
    assert r.citations
    assert r.retrieval["method"] == "agentic_hybrid"
    assert r.retrieval["agentic"]["enabled"] is True
    assert r.retrieval["agentic"]["subqueries"]
    assert r.retrieval["agentic"]["selected_chunks"] >= 1
    stored = db_session.get(Message, r.message_id)
    assert stored is not None
    assert stored.content == r.answer


def test_agentic_chat_empty_corpus_refuses_with_trace(db_session, fake_embedder):
    from app.agentic_rag.service import agentic_chat

    r = agentic_chat(
        db_session,
        fake_embedder,
        FakeLLMClient(),
        Settings(agentic_rag_enabled=True),
        message="anything?",
        filters={"source_ids": [-1]},
    )

    assert r.citations == []
    assert r.model is None
    assert r.retrieval["refusal_reason"] == "weak_context"
    assert r.retrieval["agentic"]["enabled"] is True
    assert r.retrieval["agentic"]["weak_evidence"] is True


def test_stream_chat_emits_deltas_and_persists_cited_completion(db_session, fake_embedder):
    ingest_documents(db_session, fake_embedder, source=SourceSpec("manual", "Stream"),
                     documents=[DocumentInput(title="Streaming",
                                             content="SSE token streaming citations. " * 20)])
    events = list(stream_chat(db_session, fake_embedder, FakeLLMClient(), Settings(),
                              message="What does streaming preserve?"))

    deltas = [e.text for e in events if e.type == "delta"]
    complete = next(e.result for e in events if e.type == "complete")

    assert "".join(deltas) == complete.answer
    assert complete.citations
    assert complete.model == "fake"
    stored = db_session.get(Message, complete.message_id)
    assert stored is not None
    assert stored.content == complete.answer


def test_stream_chat_does_not_emit_uncited_model_deltas(db_session, fake_embedder):
    ingest_documents(db_session, fake_embedder, source=SourceSpec("manual", "Stream Security"),
                     documents=[DocumentInput(title="Private",
                                             content="Private stream security context. " * 20)])

    events = list(stream_chat(db_session, fake_embedder, _LeakyStreamingLLM(), Settings(),
                              message="What does private stream security say?"))

    leaked_delta_text = "".join(e.text or "" for e in events if e.type == "delta")
    complete = next(e.result for e in events if e.type == "complete")

    assert "SECRET_STREAM_LEAK" not in leaked_delta_text
    assert leaked_delta_text == ""
    assert complete.answer == CITATION_FAILURE_TEXT
    assert complete.citations == []
    assert complete.retrieval["citation_validation_failed"] is True
    stored = db_session.get(Message, complete.message_id)
    assert stored is not None
    assert stored.content == CITATION_FAILURE_TEXT
