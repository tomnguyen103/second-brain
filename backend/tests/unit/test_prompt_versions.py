"""Prompt-version registry + versioned build_messages (ADR-0009)."""
import pytest

from app.chat.prompt import (
    DEFAULT_PROMPT_VERSION,
    PROMPTS,
    SYSTEM_PROMPT,
    ContextItem,
    build_messages,
    get_prompt,
)


def test_registry_has_both_versions():
    assert set(PROMPTS) >= {"rag-v1", "rag-v2"}
    for version, spec in PROMPTS.items():
        assert spec.version == version
        assert spec.system_prompt and spec.refusal_text


def test_default_is_v1_and_aliases_match():
    assert DEFAULT_PROMPT_VERSION == "rag-v1"
    assert get_prompt("rag-v1").system_prompt == SYSTEM_PROMPT


def test_get_prompt_unknown_raises():
    with pytest.raises(ValueError):
        get_prompt("rag-v999")


def test_build_messages_default_uses_v1():
    items = [ContextItem(1, "Notes", "Doc A", "alpha")]
    msgs = build_messages("q?", items)
    assert msgs[0].role == "system"
    assert msgs[0].content == get_prompt("rag-v1").system_prompt


def test_build_messages_selects_version():
    items = [ContextItem(1, "Notes", "Doc A", "alpha")]
    v1 = build_messages("q?", items, prompt_version="rag-v1")
    v2 = build_messages("q?", items, prompt_version="rag-v2")
    assert v1[0].content == get_prompt("rag-v1").system_prompt
    assert v2[0].content == get_prompt("rag-v2").system_prompt
    assert v1[0].content != v2[0].content
    # context + question rendering is version-independent
    assert "[1]" in v1[-1].content and "Question: q?" in v1[-1].content
    assert "[1]" in v2[-1].content and "Question: q?" in v2[-1].content
