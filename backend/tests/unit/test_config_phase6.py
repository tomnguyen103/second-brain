"""Phase 6 settings: admin token, retention TTL, metrics/audit toggles, pgbouncer URL."""
from app.config import Settings


def test_phase6_defaults(monkeypatch):
    for key in [
        "SECOND_BRAIN_ADMIN_TOKEN",
        "SECOND_BRAIN_RETENTION_RAW_TEXT_DAYS",
        "SECOND_BRAIN_METRICS_ENABLED",
        "SECOND_BRAIN_AUDIT_ENABLED",
        "SECOND_BRAIN_PGBOUNCER_URL",
    ]:
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)
    assert s.admin_token is None
    assert s.retention_raw_text_days == 180
    assert s.metrics_enabled is True
    assert s.audit_enabled is True
    assert s.pgbouncer_url is None


def test_phase6_env_override(monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_ADMIN_TOKEN", "s3cret")
    monkeypatch.setenv("SECOND_BRAIN_RETENTION_RAW_TEXT_DAYS", "30")
    monkeypatch.setenv("SECOND_BRAIN_METRICS_ENABLED", "false")
    s = Settings(_env_file=None)
    assert s.admin_token == "s3cret"
    assert s.retention_raw_text_days == 30
    assert s.metrics_enabled is False
