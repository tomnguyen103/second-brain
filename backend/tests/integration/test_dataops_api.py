"""Admin-guarded data-ops endpoints (Phase 6, ADR-0012): export, delete, retention purge."""
import os

import pytest

from app import deps
from app.config import Settings
from app.db.models import Source
from app.main import app

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB"
)

TOKEN = "test-admin-token"
ADMIN = {"X-Second-Brain-Admin-Token": TOKEN}


def _enable_admin():
    """Override settings so the admin token is configured (the `client` fixture clears it)."""
    app.dependency_overrides[deps.get_settings] = lambda: Settings(
        llm_provider="fake", api_token="test-api-token", admin_token=TOKEN
    )


def _ingest(client, name: str) -> int:
    r = client.post(
        "/ingest",
        json={
            "source": {"type": "manual", "name": name},
            "documents": [{"title": "D", "content": "api dataops content. " * 30}],
        },
    )
    assert r.status_code == 200
    return r.json()["source_id"]


def test_admin_disabled_without_token(client):
    # Default test settings have no admin token → endpoints report disabled.
    r = client.get("/data/export", params={"source_id": 1})
    assert r.status_code == 503


def test_wrong_token_rejected(client):
    _enable_admin()
    assert client.get("/data/export", params={"source_id": 1}).status_code == 401
    assert (
        client.get(
            "/data/export", params={"source_id": 1}, headers={"X-Second-Brain-Admin-Token": "nope"}
        ).status_code
        == 401
    )


def test_admin_token_alone_is_not_api_access(client):
    _enable_admin()
    r = client.get(
        "/data/export",
        params={"source_id": 1},
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "X-Second-Brain-Admin-Token": TOKEN,
        },
    )
    assert r.status_code == 401


def test_export_authorized(client):
    _enable_admin()
    source_id = _ingest(client, "ApiExport")
    r = client.get("/data/export", params={"source_id": source_id}, headers=ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert body["source"]["id"] == source_id
    assert body["document_count"] == 1


def test_delete_authorized_removes_source(client, db_session):
    _enable_admin()
    source_id = _ingest(client, "ApiDelete")
    r = client.delete(f"/data/sources/{source_id}", headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["documents_deleted"] == 1
    assert db_session.query(Source).filter(Source.id == source_id).count() == 0


def test_delete_missing_returns_404(client):
    _enable_admin()
    assert client.delete("/data/sources/99999999", headers=ADMIN).status_code == 404


def test_retention_purge_authorized(client):
    _enable_admin()
    r = client.post("/admin/retention/purge", params={"older_than_days": 365}, headers=ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert body["older_than_days"] == 365
    assert body["purged"] >= 0
