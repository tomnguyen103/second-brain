"""Security helpers for local-first data handling.

The app stores personal notes and may call hosted LLM/embedding APIs. Keep the
checks conservative and dependency-free so they can run before ingest, export,
and MCP approval summaries.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


class SensitiveContentError(ValueError):
    """Raised when user-supplied content appears to contain secrets or private data."""

    def __init__(self, markers: Sequence[str], *, context: str = "content") -> None:
        self.markers = tuple(dict.fromkeys(markers))
        self.context = context
        joined = ", ".join(self.markers) or "sensitive content"
        super().__init__(f"{context} contains blocked sensitive data: {joined}")


@dataclass(frozen=True)
class _Pattern:
    name: str
    regex: re.Pattern[str]
    replacement: str


_CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|secret|client[_-]?secret|"
    r"password|passwd|pwd|private[_-]?key)\b\s*[:=]\s*['\"]?([^\s'\"`]{8,})"
)

_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern(
        "google_api_key",
        re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
        "[REDACTED:google_api_key]",
    ),
    _Pattern(
        "aws_access_key",
        re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
        "[REDACTED:aws_access_key]",
    ),
    _Pattern(
        "bearer_token",
        re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}\b"),
        "Bearer [REDACTED:token]",
    ),
    _Pattern(
        "private_key",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
        "[REDACTED:private_key]",
    ),
    _Pattern(
        "database_url_password",
        re.compile(r"(?i)\b(postgresql|postgres|mysql|redis)://([^:\s/@]+):([^@\s]+)@"),
        r"\1://\2:[REDACTED:password]@",
    ),
    _Pattern(
        "email_address",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[REDACTED:email]",
    ),
    _Pattern(
        "phone_number",
        re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\d)"),
        "[REDACTED:phone]",
    ),
)

_PAYMENT_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


def _luhn_ok(value: str) -> bool:
    digits = [int(ch) for ch in re.sub(r"\D", "", value)]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for idx, digit in enumerate(digits):
        if idx % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _text_from(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        return str(value)


def detect_sensitive_markers(*values: Any) -> list[str]:
    """Return marker names for secret/private-data patterns found in values."""
    markers: list[str] = []
    for value in values:
        text = _text_from(value)
        if not text:
            continue
        if _CREDENTIAL_ASSIGNMENT.search(text):
            markers.append("credential_assignment")
        for pattern in _PATTERNS:
            if pattern.regex.search(text):
                markers.append(pattern.name)
        if any(_luhn_ok(match.group(0)) for match in _PAYMENT_CARD.finditer(text)):
            markers.append("payment_card")
    return list(dict.fromkeys(markers))


def ensure_no_sensitive_content(*values: Any, context: str = "content") -> None:
    """Raise if values contain credentials, private contact data, or payment data."""
    markers = detect_sensitive_markers(*values)
    if markers:
        raise SensitiveContentError(markers, context=context)


def redact_sensitive_text(value: Any) -> str:
    """Return a string with known sensitive patterns removed."""
    text = _text_from(value)
    text = _CREDENTIAL_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}=[REDACTED:credential]", text
    )
    for pattern in _PATTERNS:
        text = pattern.regex.sub(pattern.replacement, text)

    def _redact_card(match: re.Match[str]) -> str:
        raw = match.group(0)
        return "[REDACTED:payment_card]" if _luhn_ok(raw) else raw

    return _PAYMENT_CARD.sub(_redact_card, text)


def redact_sensitive_value(value: Any) -> Any:
    """Recursively redact strings in JSON-like values."""
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, Mapping):
        return {str(k): redact_sensitive_value(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [redact_sensitive_value(v) for v in value]
    return value
