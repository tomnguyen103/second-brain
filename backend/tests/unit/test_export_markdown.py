from __future__ import annotations

import argparse
from datetime import datetime, timezone

import pytest

from app.dataops.export_markdown import (
    build_parser,
    frontmatter,
    export_markdown,
    is_local_database_url,
    parse_kinds,
    slugify,
    truncate_content,
    write_markdown,
)


def test_local_database_guard_accepts_localhost():
    assert is_local_database_url(
        "postgresql+psycopg://second_brain:pw@localhost:5433/second_brain"
    )
    assert is_local_database_url(
        "postgresql+psycopg://second_brain:pw@127.0.0.1:5433/second_brain"
    )


def test_local_database_guard_rejects_remote_host():
    assert not is_local_database_url(
        "postgresql+psycopg://second_brain:pw@example.com:5432/second_brain"
    )


def test_parse_kinds_accepts_all_or_subset():
    assert parse_kinds("all") == (
        "research-notes",
        "briefings",
        "chat-answers",
        "source-documents",
    )
    assert parse_kinds("briefings,chat-answers") == ("briefings", "chat-answers")


def test_parse_kinds_rejects_unknown_kind():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_kinds("briefings,secrets")


def test_slugify_creates_windows_safe_ascii_name():
    assert slugify('A/B: "note" about retrieval?') == "A-B-note-about-retrieval"


def test_frontmatter_quotes_strings_and_lists():
    created = datetime(2026, 6, 3, tzinfo=timezone.utc).isoformat()
    md = frontmatter(
        {
            "title": 'A "quoted" title',
            "created": created,
            "derived": True,
            "tags": ["second-brain-export", "briefing"],
        }
    )
    assert 'title: "A \\"quoted\\" title"' in md
    assert "derived: true" in md
    assert '  - "briefing"' in md


def test_truncate_content_marks_review_exports():
    content, truncated = truncate_content("abcdef", 3)
    assert truncated is True
    assert content.endswith("[TRUNCATED FOR REVIEW EXPORT]\n")


def test_write_markdown_redacts_sensitive_content(tmp_path):
    exported = write_markdown(
        tmp_path,
        "research-notes",
        "note.md",
        "api_key = AIza12345678901234567890123456789012345",
    )
    assert "[REDACTED:credential]" in exported.path.read_text(encoding="utf-8")
    assert "AIza" not in exported.path.read_text(encoding="utf-8")


def test_export_requires_local_confirmation_before_db_access():
    parser = build_parser()
    args = parser.parse_args([])
    with pytest.raises(SystemExit):
        export_markdown(args)
