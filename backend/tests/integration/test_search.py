"""Integration tests for GET /search, GET /conversations, POST /feedback."""
import os
import pytest
from sqlalchemy import select

from app import deps
from app.api import conversations
from app.config import Settings
from app.db.models import AuditLog
from app.eval.dataset import load_dataset
from app.main import app

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB"
)

ADMIN_TOKEN = "test-admin-token"
ADMIN = {"X-Second-Brain-Admin-Token": ADMIN_TOKEN}


def _enable_admin():
    app.dependency_overrides[deps.get_settings] = lambda: Settings(
        llm_provider="fake", api_token="test-api-token", admin_token=ADMIN_TOKEN
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


def test_conversation_detail_reconstructs_citations(client):
    """Replayed conversation detail must expose the SAME citations the live /chat
    returned (marker → document/source/snippet), so the UI renders clickable [n]."""
    client.post("/ingest", json={
        "source": {"type": "manual", "name": "Cite Reconstruct"},
        "documents": [{"title": "pgvector basics", "content": "pgvector stores vector embeddings in Postgres for similarity search. " * 20}],
    })
    chat_r = client.post("/chat", json={"message": "what does pgvector store?"})
    body = chat_r.json()
    conv_id = body["conversation_id"]
    live_markers = sorted(c["marker"] for c in body["citations"])
    assert live_markers, "fake LLM should cite at least one context marker"

    r = client.get(f"/conversations/{conv_id}")
    assert r.status_code == 200, r.text
    msgs = r.json()["messages"]

    assistant = next(m for m in msgs if m["role"] == "assistant")
    assert "citations" in assistant, "detail must expose reconstructed citations"
    hist_markers = sorted(c["marker"] for c in assistant["citations"])
    assert hist_markers == live_markers, (hist_markers, live_markers)
    c0 = assistant["citations"][0]
    assert c0["document_title"] and c0["source_name"] and c0["chunk_id"]
    assert c0["snippet"]

    # user messages carry no citations
    user = next(m for m in msgs if m["role"] == "user")
    assert user["citations"] == []


def _seed_feedback_with_cited_answer(client):
    client.post("/ingest", json={
        "source": {"type": "manual", "name": "Feedback Quality"},
        "documents": [{
            "title": "Feedback analytics doc",
            "content": (
                "pgvector stores vector embeddings in Postgres for similarity search, "
                "which helps feedback quality review connect thumbs down answers to sources. "
            ) * 20,
        }],
    })
    chat_r = client.post("/chat", json={"message": "what does pgvector store for feedback quality?"})
    assert chat_r.status_code == 200, chat_r.text
    chat = chat_r.json()
    assert chat["citations"], "fake LLM should cite the retrieved feedback doc"
    return chat


def test_feedback_analytics_summarizes_trends(client):
    before = client.get("/feedback/analytics", params={"days": 7}).json()
    negative_chat = _seed_feedback_with_cited_answer(client)
    negative = client.post(
        "/feedback",
        json={
            "message_id": negative_chat["message_id"],
            "rating": -1,
            "comment": "missed the action item",
        },
    )
    assert negative.status_code == 201, negative.text

    positive_chat = client.post(
        "/chat", json={"message": "What does feedback analytics track?"}
    ).json()
    positive = client.post(
        "/feedback",
        json={"message_id": positive_chat["message_id"], "rating": 1},
    )
    assert positive.status_code == 201, positive.text

    r = client.get("/feedback/analytics", params={"days": 7})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == before["total"] + 2
    assert body["positive"] == before["positive"] + 1
    assert body["negative"] == before["negative"] + 1
    assert len(body["trend"]) == 7
    assert any(bucket["total"] >= 2 for bucket in body["trend"])
    assert any(model["model"] == "fake" for model in body["by_model"])
    assert any(
        doc["document_title"] == "Feedback analytics doc"
        for doc in body["top_negative_documents"]
    )


def test_negative_feedback_lists_conversation_message_and_citations(client):
    chat = _seed_feedback_with_cited_answer(client)
    fb = client.post(
        "/feedback",
        json={"message_id": chat["message_id"], "rating": -1, "comment": "wrong source"},
    ).json()

    r = client.get("/feedback/negative", params={"limit": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["feedback_id"] == fb["id"]
    assert item["message_id"] == chat["message_id"]
    assert item["conversation_id"] == chat["conversation_id"]
    assert item["question"] == "what does pgvector store for feedback quality?"
    assert item["answer"] == chat["answer"]
    assert item["comment"] == "wrong source"
    assert item["retrievals"]
    assert item["citations"][0]["document_title"] == "Feedback analytics doc"


def test_negative_feedback_exports_eval_candidates(client):
    chat = _seed_feedback_with_cited_answer(client)
    fb = client.post(
        "/feedback",
        json={"message_id": chat["message_id"], "rating": -1, "comment": "needs eval"},
    ).json()

    r = client.get("/feedback/eval-candidates")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "feedback"
    assert body["total"] == 1
    case = body["cases"][0]
    assert case["id"] == f"feedback-{fb['id']}"
    assert case["question"] == "what does pgvector store for feedback quality?"
    assert case["expected_docs"] == ["Feedback analytics doc"]
    assert case["metadata"]["feedback_id"] == fb["id"]
    assert case["metadata"]["needs_review"] is True
    assert case["metadata"]["citations"][0]["document_title"] == "Feedback analytics doc"


def _patch_review_dataset(monkeypatch, tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "feedback.md").write_text("# Feedback analytics doc\nbody\n", encoding="utf-8")
    dataset = tmp_path / "dataset.yaml"
    dataset.write_text("cases: []\n", encoding="utf-8")
    monkeypatch.setattr(conversations, "EVAL_DATASET_PATH", dataset)
    monkeypatch.setattr(conversations, "EVAL_CORPUS_DIR", corpus)
    return dataset, corpus


def test_eval_candidate_export_does_not_promote_automatically(client, monkeypatch, tmp_path):
    chat = _seed_feedback_with_cited_answer(client)
    client.post(
        "/feedback",
        json={"message_id": chat["message_id"], "rating": -1, "comment": "review later"},
    )
    dataset, _corpus = _patch_review_dataset(monkeypatch, tmp_path)

    r = client.get("/feedback/eval-candidates")

    assert r.status_code == 200, r.text
    assert r.json()["cases"]
    assert dataset.read_text(encoding="utf-8") == "cases: []\n"


def test_promote_feedback_eval_candidate_requires_confirmations(client, monkeypatch, tmp_path):
    _enable_admin()
    chat = _seed_feedback_with_cited_answer(client)
    fb = client.post(
        "/feedback",
        json={"message_id": chat["message_id"], "rating": -1, "comment": "needs eval"},
    ).json()
    dataset, _corpus = _patch_review_dataset(monkeypatch, tmp_path)

    r = client.post(
        f"/feedback/eval-candidates/{fb['id']}/promote",
        json={
            "id": f"feedback-{fb['id']}",
            "question": "what does pgvector store for feedback quality?",
            "expected_docs": ["Feedback analytics doc"],
            "expected_keywords": ["pgvector"],
            "expect_refusal": False,
            "confirmations": {
                "expected_docs": True,
                "expected_keywords": False,
                "expect_refusal": True,
            },
        },
        headers=ADMIN,
    )

    assert r.status_code == 422
    assert dataset.read_text(encoding="utf-8") == "cases: []\n"


def test_promote_feedback_eval_candidate_requires_admin_token(client, monkeypatch, tmp_path):
    chat = _seed_feedback_with_cited_answer(client)
    fb = client.post(
        "/feedback",
        json={"message_id": chat["message_id"], "rating": -1, "comment": "needs eval"},
    ).json()
    dataset, _corpus = _patch_review_dataset(monkeypatch, tmp_path)

    r = client.post(
        f"/feedback/eval-candidates/{fb['id']}/promote",
        json={
            "id": f"feedback-{fb['id']}-reviewed",
            "question": "What should feedback review connect thumbs down answers to?",
            "expected_docs": ["Feedback analytics doc"],
            "expected_keywords": ["sources"],
            "expect_refusal": False,
            "confirmations": {
                "expected_docs": True,
                "expected_keywords": True,
                "expect_refusal": True,
            },
        },
    )

    assert r.status_code == 503
    assert dataset.read_text(encoding="utf-8") == "cases: []\n"


def test_promote_feedback_eval_candidate_appends_reviewed_case(
    client, db_session, monkeypatch, tmp_path
):
    _enable_admin()
    chat = _seed_feedback_with_cited_answer(client)
    fb = client.post(
        "/feedback",
        json={"message_id": chat["message_id"], "rating": -1, "comment": "needs eval"},
    ).json()
    dataset, corpus = _patch_review_dataset(monkeypatch, tmp_path)

    r = client.post(
        f"/feedback/eval-candidates/{fb['id']}/promote",
        json={
            "id": f"feedback-{fb['id']}-reviewed",
            "question": "What should feedback review connect thumbs down answers to?",
            "expected_docs": ["Feedback analytics doc"],
            "expected_keywords": ["sources"],
            "expect_refusal": False,
            "confirmations": {
                "expected_docs": True,
                "expected_keywords": True,
                "expect_refusal": True,
            },
        },
        headers=ADMIN,
    )

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["dataset_path"] == "backend/eval/dataset.yaml"
    assert body["case"]["id"] == f"feedback-{fb['id']}-reviewed"
    assert body["case"]["metadata"]["needs_review"] is False
    cases = load_dataset(dataset, corpus_dir=corpus)
    assert cases[0].id == body["case"]["id"]
    assert cases[0].expected_docs == ["Feedback analytics doc"]
    assert cases[0].expected_keywords == ["sources"]
    assert cases[0].review["source"] == "feedback"
    assert cases[0].review["feedback_id"] == fb["id"]
    assert cases[0].review["confirmations"] == {
        "expect_refusal": True,
        "expected_docs": True,
        "expected_keywords": True,
    }
    assert body["case"]["metadata"]["review"] == cases[0].review
    audit_row = db_session.scalars(
        select(AuditLog).where(AuditLog.entity_type == "eval_case")
    ).one()
    assert audit_row.action == "create"
    assert audit_row.entity_id == fb["id"]
    assert audit_row.detail["op"] == "promote_eval_case"
    assert audit_row.detail["case_id"] == body["case"]["id"]
    assert audit_row.detail["review"] == cases[0].review


def test_promote_feedback_eval_candidate_rejects_unknown_expected_doc(
    client, monkeypatch, tmp_path
):
    _enable_admin()
    chat = _seed_feedback_with_cited_answer(client)
    fb = client.post(
        "/feedback",
        json={"message_id": chat["message_id"], "rating": -1, "comment": "needs eval"},
    ).json()
    dataset, _corpus = _patch_review_dataset(monkeypatch, tmp_path)

    r = client.post(
        f"/feedback/eval-candidates/{fb['id']}/promote",
        json={
            "id": f"feedback-{fb['id']}-bad",
            "question": "What did it cite?",
            "expected_docs": ["Missing document"],
            "expected_keywords": ["anything"],
            "expect_refusal": False,
            "confirmations": {
                "expected_docs": True,
                "expected_keywords": True,
                "expect_refusal": True,
            },
        },
        headers=ADMIN,
    )

    assert r.status_code == 422
    assert "not in the eval corpus" in r.text
    assert dataset.read_text(encoding="utf-8") == "cases: []\n"
