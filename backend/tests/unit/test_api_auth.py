from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import deps
from app.api import dataops
from app.config import Settings
from app.main import app


def test_require_api_access_disabled_for_keyless_local_dev():
    assert deps.require_api_access(None, Settings(_env_file=None)) is True


def test_require_api_access_rejects_missing_or_wrong_token():
    settings = Settings(_env_file=None, api_token="api-secret")

    with pytest.raises(HTTPException) as missing:
        deps.require_api_access(None, settings)
    with pytest.raises(HTTPException) as wrong:
        deps.require_api_access("Bearer wrong", settings)

    assert missing.value.status_code == 401
    assert wrong.value.status_code == 401


def test_require_api_access_accepts_only_api_token():
    settings = Settings(_env_file=None, api_token="api-secret", admin_token="admin-secret")

    assert deps.require_api_access("Bearer api-secret", settings) is True
    with pytest.raises(HTTPException) as admin_only:
        deps.require_api_access("Bearer admin-secret", settings)
    assert admin_only.value.status_code == 401


def test_require_admin_rejects_api_token_and_accepts_admin_token():
    settings = Settings(_env_file=None, api_token="api-secret", admin_token="admin-secret")

    with pytest.raises(HTTPException) as api_only:
        deps.require_admin("api-secret", settings)

    assert api_only.value.status_code == 401
    assert deps.require_admin("admin-secret", settings) is True


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("post", "/chat", {"json": {}}),
        ("post", "/chat/stream", {"json": {}}),
        ("post", "/capture", {"json": {}}),
        ("get", "/conversations", {}),
        ("post", "/ingest", {"json": {}}),
        ("post", "/ingest/upload", {"data": {"source_name": "Upload"}}),
        ("get", "/search", {"params": {"q": "notes"}}),
        ("get", "/briefing", {}),
        ("post", "/feedback", {"json": {}}),
        ("get", "/feedback/analytics", {}),
        ("post", "/feedback/eval-candidates/1/promote", {"json": {}}),
        ("get", "/tasks", {}),
        ("get", "/research/jobs", {}),
        ("get", "/sources", {}),
        ("get", "/data/export", {"params": {"source_id": 1}}),
        ("post", "/admin/retention/purge", {}),
    ],
)
def test_personal_data_routes_require_api_token(method: str, path: str, kwargs: dict):
    app.dependency_overrides[deps.get_settings] = lambda: Settings(
        _env_file=None,
        api_token="api-secret",
        admin_token="admin-secret",
        metrics_enabled=False,
    )
    try:
        with TestClient(app) as client:
            request = getattr(client, method)
            assert request(path, **kwargs).status_code == 401
            assert (
                request(path, headers={"Authorization": "Bearer wrong"}, **kwargs).status_code
                == 401
            )
    finally:
        app.dependency_overrides.clear()


def test_authenticated_request_passes_api_gate_but_still_validates_request_body():
    app.dependency_overrides[deps.get_settings] = lambda: Settings(
        _env_file=None,
        api_token="api-secret",
        metrics_enabled=False,
    )
    try:
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            response = client.post(
                "/chat",
                json={},
                headers={"Authorization": "Bearer api-secret"},
            )
            assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_cors_preflight_allows_admin_token_header():
    app.dependency_overrides[deps.get_settings] = lambda: Settings(
        _env_file=None,
        cors_origins=["http://localhost:3000"],
        metrics_enabled=False,
    )
    try:
        with TestClient(app) as client:
            response = client.options(
                "/data/export?source_id=1",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": (
                        "Authorization, X-Second-Brain-Admin-Token"
                    ),
                },
            )

        assert response.status_code == 200
        allowed = response.headers["access-control-allow-headers"].lower()
        assert "authorization" in allowed
        assert "x-second-brain-admin-token" in allowed
    finally:
        app.dependency_overrides.clear()


def test_destructive_dataops_requires_admin_after_api_gate(monkeypatch):
    class DummyDb:
        committed = False

        def commit(self):
            self.committed = True

    db = DummyDb()

    app.dependency_overrides[deps.get_settings] = lambda: Settings(
        _env_file=None,
        api_token="api-secret",
        admin_token="admin-secret",
        metrics_enabled=False,
    )
    app.dependency_overrides[deps.get_db] = lambda: db
    monkeypatch.setattr(
        dataops.erasure,
        "export_source",
        lambda db, source_id, audit_enabled: {
            "source": {"id": source_id, "name": "Stub"},
            "documents": [],
            "document_count": 0,
        },
    )
    try:
        with TestClient(app) as client:
            assert (
                client.get(
                    "/data/export",
                    params={"source_id": 1},
                    headers={"Authorization": "Bearer api-secret"},
                ).status_code
                == 401
            )

            assert (
                client.get(
                    "/data/export",
                    params={"source_id": 1},
                    headers={"Authorization": "Bearer admin-secret"},
                ).status_code
                == 401
            )

            response = client.get(
                "/data/export",
                params={"source_id": 1},
                headers={
                    "Authorization": "Bearer api-secret",
                    "X-Second-Brain-Admin-Token": "admin-secret",
                },
            )

            assert response.status_code == 200
            assert response.json()["source"]["id"] == 1
            assert db.committed is True
    finally:
        app.dependency_overrides.clear()
