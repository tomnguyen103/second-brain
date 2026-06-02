"""Integration tests for GET /search, GET /conversations, POST /feedback."""
import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB"
)


def test_search_returns_hits(client):
    client.post("/ingest", json={
        "source": {"type": "manual", "name": "Search Test"},
        "documents": [{"title": "HNSW paper", "content": "HNSW is an algorithm for approximate nearest neighbour search. " * 15}],
    })
    r = client.get("/search", params={"q": "nearest neighbour search", "top_k": 3})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["query"] == "nearest neighbour search"
    assert len(body["hits"]) >= 1
    hit = body["hits"][0]
    assert hit["chunk_id"] and hit["document_title"]
    assert hit["score"] > 0


def test_search_empty_returns_empty(client):
    r = client.get("/search", params={"q": "zzzzz xyzzy completely absent"})
    assert r.status_code == 200
    assert isinstance(r.json()["hits"], list)


def test_conversations_list(client):
    client.post("/chat", json={"message": "hello"})
    r = client.get("/conversations")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "conversations" in body and "total" in body
    assert body["total"] >= 1


def test_conversations_detail(client):
    chat_r = client.post("/chat", json={"message": "tell me about HNSW"})
    conv_id = chat_r.json()["conversation_id"]

    r = client.get(f"/conversations/{conv_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == conv_id
    assert len(body["messages"]) >= 1
    assert body["messages"][0]["role"] == "user"


def test_conversations_not_found(client):
    r = client.get("/conversations/999999")
    assert r.status_code == 404


def test_feedback_thumbs_up(client):
    chat_r = client.post("/chat", json={"message": "what is HNSW?"})
    msg_id = chat_r.json()["message_id"]

    r = client.post("/feedback", json={"message_id": msg_id, "rating": 1, "comment": "great"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["message_id"] == msg_id and body["rating"] == 1


def test_feedback_invalid_rating(client):
    r = client.post("/feedback", json={"message_id": 1, "rating": 5})
    assert r.status_code == 422


def test_feedback_unknown_message(client):
    r = client.post("/feedback", json={"message_id": 999999, "rating": 1})
    assert r.status_code == 404
