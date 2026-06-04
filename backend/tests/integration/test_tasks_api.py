"""REST API coverage for user tasks."""
from __future__ import annotations


def test_task_api_create_list_and_update(client):
    create = client.post("/tasks", json={"title": "Review briefing", "detail": "Check citations"})
    assert create.status_code == 201
    created = create.json()
    assert created["title"] == "Review briefing"
    assert created["status"] == "open"

    listed = client.get("/tasks", params={"status": "open"})
    assert listed.status_code == 200
    assert any(t["id"] == created["id"] for t in listed.json()["tasks"])

    updated = client.patch(f"/tasks/{created['id']}", json={"status": "done"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "done"

    open_only = client.get("/tasks", params={"status": "open"}).json()["tasks"]
    assert created["id"] not in {t["id"] for t in open_only}


def test_task_api_rejects_empty_title_and_missing_task(client):
    assert client.post("/tasks", json={"title": "   "}).status_code == 422
    assert client.patch("/tasks/99999999", json={"status": "done"}).status_code == 404
