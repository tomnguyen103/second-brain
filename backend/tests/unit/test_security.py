import pytest

from app.security import SensitiveContentError, detect_sensitive_markers, ensure_no_sensitive_content, redact_sensitive_text


def test_detects_and_redacts_credentials():
    text = "password=supersecretvalue and token = abcdefghijklmnop"
    assert "credential_assignment" in detect_sensitive_markers(text)
    redacted = redact_sensitive_text(text)
    assert "supersecretvalue" not in redacted
    assert "[REDACTED:credential]" in redacted


def test_sensitive_content_error_names_markers_without_raw_secret():
    with pytest.raises(SensitiveContentError) as exc:
        ensure_no_sensitive_content("api_key=verysecretvalue", context="unit")
    assert "credential_assignment" in str(exc.value)
    assert "verysecretvalue" not in str(exc.value)
