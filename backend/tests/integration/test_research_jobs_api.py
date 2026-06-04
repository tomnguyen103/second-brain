"""REST API coverage for queued research jobs."""
from __future__ import annotations

from app.jobs import queue
from app.db.models import Job


def test_research_job_api_enqueue_list_and_get(client):
    created = client.post("/research/jobs", json={"topic": "Reciprocal rank fusion"})
    assert created.status_code == 201
    job = created.json()
    assert job["type"] == "research"
    assert job["topic"] == "Reciprocal rank fusion"
    assert job["status"] == "queued"

    listed = client.get("/research/jobs")
    assert listed.status_code == 200
    assert any(item["id"] == job["id"] for item in listed.json()["jobs"])

    fetched = client.get(f"/research/jobs/{job['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == job["id"]


def test_research_job_api_accepts_source_inputs(client, db_session):
    created = client.post("/research/jobs", json={
        "topic": "Source-backed research",
        "source_urls": ["https://example.com/research"],
        "source_texts": [{
            "title": "Manual evidence",
            "text": "A manually provided source snippet for the research job.",
            "uri": "manual://evidence",
        }],
    })

    assert created.status_code == 201
    job = db_session.get(Job, created.json()["id"])
    assert job is not None
    assert job.payload["source_urls"] == ["https://example.com/research"]
    assert job.payload["source_texts"] == [{
        "title": "Manual evidence",
        "text": "A manually provided source snippet for the research job.",
        "uri": "manual://evidence",
    }]


def test_research_job_api_rejects_empty_topic_and_non_research_job(client, db_session):
    assert client.post("/research/jobs", json={"topic": "   "}).status_code == 422
    briefing = queue.enqueue(db_session, type="briefing")
    db_session.commit()
    assert client.get(f"/research/jobs/{briefing.id}").status_code == 404
