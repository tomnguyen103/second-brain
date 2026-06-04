"""Integration tests for the registered job handlers, driven end-to-end via the worker.

These use the global HANDLERS registry (run_once with handlers=None) — i.e. the real
briefing/research handlers registered on import — to prove the full enqueue -> worker ->
effect path.
"""
from __future__ import annotations

from sqlalchemy import select

from app.config import Settings
from app.db.models import Briefing, Chunk, Document
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from app.jobs import queue, worker
from app.llm.fake import FakeLLMClient
from app.retrieval.hybrid import hybrid_search


def _run(db, embedder):
    return worker.run_once(db, embedder=embedder, llm=FakeLLMClient(), max_attempts=3)


def test_briefing_handler_via_run_once_produces_briefing(db_session, fake_embedder):
    ingest_documents(
        db_session, fake_embedder,
        source=SourceSpec(type="manual", name="Handler Test"),
        documents=[DocumentInput(title="Handler Doc", content="content for the handler test")],
    )
    queue.enqueue(db_session, type="briefing")

    job = _run(db_session, fake_embedder)

    assert job is not None and job.type == "briefing"
    assert job.status == "done"
    result = job.payload["result"]
    b = db_session.get(Briefing, result["briefing_id"])
    assert b is not None
    assert b.document_count >= 1          # at least the doc we just ingested
    assert result["document_count"] == b.document_count


def test_briefing_handler_second_run_advances_since(db_session, fake_embedder):
    queue.enqueue(db_session, type="briefing")
    job1 = _run(db_session, fake_embedder)
    b1 = db_session.get(Briefing, job1.payload["result"]["briefing_id"])

    # No new documents created between the two runs -> the second briefing's window starts
    # exactly where the first ended and finds nothing new.
    queue.enqueue(db_session, type="briefing")
    job2 = _run(db_session, fake_embedder)
    b2 = db_session.get(Briefing, job2.payload["result"]["briefing_id"])

    assert b2.period_start == b1.period_end   # picks up where the first ended
    assert b2.document_count == 0
    assert b2.model is None                    # nothing new -> no LLM call


def test_research_handler_via_run_once_stores_searchable_note(db_session, fake_embedder):
    topic = "Async research via the worker queue"
    queue.enqueue(db_session, type="research", payload={"topic": topic})

    job = _run(db_session, fake_embedder)

    assert job is not None and job.type == "research"
    assert job.status == "done"
    result = job.payload["result"]
    assert result["status"] == "embedded"
    assert result["searchable"] is True
    assert result["source_id"] is not None

    # the stored research note was auto-ingested and is findable via hybrid search
    chunk = db_session.scalar(select(Chunk).where(Chunk.document_id == result["document_id"]))
    hits, _meta = hybrid_search(
        db_session, fake_embedder, Settings(_env_file=None),
        chunk.content, source_ids=[result["source_id"]],
    )
    assert len(hits) >= 1


def test_research_handler_returns_source_provenance(db_session, fake_embedder):
    queue.enqueue(
        db_session,
        type="research",
        payload={
            "topic": "Evidence-backed async research",
            "source_texts": [{
                "title": "Worker evidence",
                "text": "The worker should pass provided evidence into the research service.",
                "uri": "manual://worker-evidence",
            }],
        },
    )

    job = _run(db_session, fake_embedder)

    assert job is not None and job.type == "research"
    result = job.payload["result"]
    assert result["evidence_count"] == 1
    assert result["sources"][0]["title"] == "Worker evidence"
    assert result["sources"][0]["uri"] == "manual://worker-evidence"

    doc = db_session.get(Document, result["document_id"])
    assert doc is not None
    assert doc.metadata_["sources"] == result["sources"]

