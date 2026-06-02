"""Phase 5 settings: briefing lookback window, job max attempts, worker poll interval."""
from app.config import Settings


def test_phase5_defaults(monkeypatch):
    for key in [
        "SECOND_BRAIN_BRIEFING_LOOKBACK_HOURS",
        "SECOND_BRAIN_JOB_MAX_ATTEMPTS",
        "SECOND_BRAIN_WORKER_POLL_SECONDS",
    ]:
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)
    assert s.briefing_lookback_hours == 24
    assert s.job_max_attempts == 3
    assert s.worker_poll_seconds == 5.0


def test_phase5_env_override(monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_BRIEFING_LOOKBACK_HOURS", "48")
    monkeypatch.setenv("SECOND_BRAIN_JOB_MAX_ATTEMPTS", "5")
    monkeypatch.setenv("SECOND_BRAIN_WORKER_POLL_SECONDS", "1.5")
    s = Settings(_env_file=None)
    assert s.briefing_lookback_hours == 48
    assert s.job_max_attempts == 5
    assert s.worker_poll_seconds == 1.5
