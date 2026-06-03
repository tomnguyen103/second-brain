"""Phase 6 settings: admin token, retention TTL, metrics/audit toggles, pgbouncer URL."""
from app.config import Settings


def test_phase6_defaults(monkeypatch):
    for key in [
        "SECOND_BRAIN_ADMIN_TOKEN",
        "SECOND_BRAIN_RETENTION_RAW_TEXT_DAYS",
        "SECOND_BRAIN_METRICS_ENABLED",
        "SECOND_BRAIN_AUDIT_ENABLED",
        "SECOND_BRAIN_PGBOUNCER_URL",
        "SECOND_BRAIN_MIN_RETENTION_PURGE_DAYS",
        "SECOND_BRAIN_DATA_ENVIRONMENT",
        "SECOND_BRAIN_MCP_WRITE_REQUIRES_APPROVAL",
        "SECOND_BRAIN_MCP_WRITE_APPROVAL_TOKEN",
    ]:
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)
    assert s.admin_token is None
    assert s.retention_raw_text_days == 180
    assert s.min_retention_purge_days == 1
    assert s.metrics_enabled is True
    assert s.audit_enabled is True
    assert s.pgbouncer_url is None
    assert s.data_environment == "local"
    assert s.mcp_write_requires_approval is True
    assert s.mcp_write_approval_token is None


def test_phase6_env_override(monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_ADMIN_TOKEN", "s3cret")
    monkeypatch.setenv("SECOND_BRAIN_RETENTION_RAW_TEXT_DAYS", "30")
    monkeypatch.setenv("SECOND_BRAIN_METRICS_ENABLED", "false")
    monkeypatch.setenv("SECOND_BRAIN_MCP_WRITE_APPROVAL_TOKEN", "approve-me")
    monkeypatch.setenv("SECOND_BRAIN_MCP_WRITE_REQUIRES_APPROVAL", "false")
    s = Settings(_env_file=None)
    assert s.admin_token == "s3cret"
    assert s.retention_raw_text_days == 30
    assert s.metrics_enabled is False
    assert s.mcp_write_approval_token == "approve-me"
    assert s.mcp_write_requires_approval is False
