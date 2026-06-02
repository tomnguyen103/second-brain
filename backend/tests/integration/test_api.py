import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB")


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
