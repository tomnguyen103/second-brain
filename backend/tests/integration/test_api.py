import json
import os
import pytest

from app.chat.service import CITATION_FAILURE_TEXT
from app.llm.base import LLMMessage, LLMResponse, LLMStreamChunk

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB")


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


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_ingest_then_chat(client):
    ing = client.post("/ingest", json={
        "source": {"type": "manual", "name": "My Notes"},
        "documents": [{"title": "HNSW", "content": "HNSW tuning m ef_construction. " * 20,
                       "tags": ["ml"]}],
    })
    assert ing.status_code == 200, ing.text
    body = ing.json()
    assert body["summary"]["embedded"] == 1
    assert body["summary"]["chunks_created"] >= 1

    chat_r = client.post("/chat", json={"message": "How do I tune HNSW?", "top_k": 5})
    assert chat_r.status_code == 200, chat_r.text
    cb = chat_r.json()
    assert cb["conversation_id"] and cb["message_id"]
    assert cb["retrieval"]["fused_returned"] >= 1


def test_chat_empty_corpus(client):
    r = client.post("/chat", json={"message": "anything about nothing?"})
    assert r.status_code == 200
    body = r.json()
    assert body["citations"] == []
    assert body["model"] is None


def test_agentic_chat_disabled_by_default(client):
    r = client.post("/chat", json={
        "message": "anything?",
        "options": {"agentic": True},
    })
    assert r.status_code == 409
    assert r.json()["detail"] == "agentic RAG is disabled"


def test_agentic_chat_endpoint_returns_trace_when_enabled(client, test_settings):
    test_settings.agentic_rag_enabled = True
    ing = client.post("/ingest", json={
        "source": {"type": "manual", "name": "Agentic API Notes"},
        "documents": [{"title": "Agentic HNSW",
                       "content": "HNSW tuning m ef_construction. " * 20}],
    })
    assert ing.status_code == 200, ing.text

    r = client.post("/chat", json={
        "message": "How do I tune HNSW?",
        "options": {"agentic": True},
    })

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["citations"]
    assert body["retrieval"]["method"] == "agentic_hybrid"
    assert body["retrieval"]["agentic"]["enabled"] is True
    assert body["retrieval"]["agentic"]["subqueries"]


def test_agentic_chat_stream_returns_unavailable(client):
    r = client.post("/chat/stream", json={
        "message": "anything?",
        "options": {"agentic": True},
    })
    assert r.status_code == 409
    assert r.json()["detail"] == "streaming is unavailable for agentic RAG"


def test_chat_stream_sends_sse_deltas_and_completion(client):
    ing = client.post("/ingest", json={
        "source": {"type": "manual", "name": "Streaming Notes"},
        "documents": [{"title": "SSE", "content": "SSE streaming keeps citations. " * 20}],
    })
    assert ing.status_code == 200, ing.text

    with client.stream("POST", "/chat/stream", json={"message": "What does SSE keep?"}) as r:
        body = "".join(r.iter_text())

    assert r.status_code == 200, body
    assert r.headers["content-type"].startswith("text/event-stream")
    blocks = [b for b in body.strip().split("\n\n") if b]
    assert any(b.startswith("event: delta") for b in blocks)
    complete_block = next(b for b in blocks if b.startswith("event: complete"))
    complete_data = json.loads(next(
        line.removeprefix("data:").strip()
        for line in complete_block.splitlines()
        if line.startswith("data:")
    ))
    delta_text = "".join(
        json.loads(next(
            line.removeprefix("data:").strip()
            for line in block.splitlines()
            if line.startswith("data:")
        ))["text"]
        for block in blocks
        if block.startswith("event: delta")
    )
    assert complete_data["answer"] == delta_text
    assert complete_data["citations"]


def test_chat_stream_never_sends_uncited_model_text(client, monkeypatch):
    from app.api import chat as chat_api

    monkeypatch.setattr(
        chat_api.deps,
        "get_llm_client",
        lambda settings, private_mode=False: _LeakyStreamingLLM(),
    )
    ing = client.post("/ingest", json={
        "source": {"type": "manual", "name": "Streaming Security Notes"},
        "documents": [{"title": "Private", "content": "Private SSE security context. " * 20}],
    })
    assert ing.status_code == 200, ing.text

    with client.stream("POST", "/chat/stream", json={"message": "What is private?"}) as r:
        body = "".join(r.iter_text())

    assert r.status_code == 200, body
    assert "SECRET_STREAM_LEAK" not in body
    blocks = [b for b in body.strip().split("\n\n") if b]
    assert not any(b.startswith("event: delta") for b in blocks)
    complete_block = next(b for b in blocks if b.startswith("event: complete"))
    complete_data = json.loads(next(
        line.removeprefix("data:").strip()
        for line in complete_block.splitlines()
        if line.startswith("data:")
    ))
    assert complete_data["answer"] == CITATION_FAILURE_TEXT
    assert complete_data["citations"] == []
    assert complete_data["retrieval"]["citation_validation_failed"] is True


def test_ingest_duplicate(client):
    payload = {
        "source": {"type": "manual", "name": "Dedup Test"},
        "documents": [{"title": "Doc", "content": "unique content for dedup test " * 5}],
    }
    r1 = client.post("/ingest", json=payload)
    r2 = client.post("/ingest", json=payload)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["summary"]["embedded"] == 1
    assert r2.json()["summary"]["duplicates"] == 1
