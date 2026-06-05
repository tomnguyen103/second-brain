from app.chat.prompt import ContextItem, build_messages, parse_citations, SYSTEM_PROMPT


def test_build_messages_numbers_context_and_includes_history():
    from app.llm.base import LLMMessage
    items = [ContextItem(1, "Notes", "Doc A", "alpha"), ContextItem(2, "Notes", "Doc B", "beta")]
    msgs = build_messages("q?", items, history=[LLMMessage("user", "earlier")])
    assert msgs[0].role == "system" and msgs[0].content == SYSTEM_PROMPT
    assert msgs[1].content == "earlier"
    assert "[1]" in msgs[-1].content and "[2]" in msgs[-1].content and "Question: q?" in msgs[-1].content
    assert "untrusted quoted data" in msgs[-1].content
    assert "<context>" in msgs[-1].content and "</context>" in msgs[-1].content


def test_parse_citations_dedup_and_range():
    assert parse_citations("uses [2] and [1] and [2] and [9]", n_items=3) == [2, 1]
    assert parse_citations("uses grouped markers [2, 1, 2] and bad [9]", n_items=3) == [2, 1]
