from app.chat.service import _PreparedChat, _citation_support_failures
from app.llm.base import LLMMessage
from app.retrieval.fusion import FusedHit
from app.retrieval.hybrid import DisplayChunk


def test_grouped_citation_markers_support_claim_segment():
    prepared = _PreparedChat(
        conversation_id=1,
        messages=[LLMMessage("user", "q")],
        hits=[
            FusedHit(chunk_id=10, score=1.0, method="hybrid", rank=1),
            FusedHit(chunk_id=11, score=0.9, method="hybrid", rank=2),
        ],
        display={
            10: DisplayChunk(
                chunk_id=10,
                content="Hybrid retrieval combines vector search and full-text search.",
                document_id=1,
                document_title="Hybrid Retrieval",
                source_id=1,
                source_name="Docs",
                char_start=0,
                char_end=64,
            ),
            11: DisplayChunk(
                chunk_id=11,
                content="Eval gating and citation validation make generated answers safer.",
                document_id=2,
                document_title="Eval Safety",
                source_id=1,
                source_name="Docs",
                char_start=0,
                char_end=66,
            ),
        },
        meta={},
        item_count=2,
        include_chunks=True,
    )

    failures = _citation_support_failures(
        "Hybrid retrieval, eval gating, and citation validation make answers safer [1, 2].",
        prepared,
    )

    assert failures == []


def test_block_citation_supports_prompt_fragments_in_same_list_item():
    prepared = _PreparedChat(
        conversation_id=1,
        messages=[LLMMessage("user", "q")],
        hits=[FusedHit(chunk_id=10, score=1.0, method="hybrid", rank=1)],
        display={
            10: DisplayChunk(
                chunk_id=10,
                content=(
                    "Create a YouTube search skill. It should filter to the last 6 months "
                    "by default. It should calculate a views-to-subscribers ratio."
                ),
                document_id=1,
                document_title="Workflow Setup",
                source_id=1,
                source_name="Uploaded PDF",
                char_start=0,
                char_end=140,
            ),
        },
        meta={},
        item_count=1,
        include_chunks=True,
    )

    failures = _citation_support_failures(
        (
            "3. **Create YouTube Search Skill:**\n"
            "   * In Claude Code, run a prompt to create a YouTube search skill: "
            "`It should filter to the last 6 months by default. "
            "It should calculate a views-to-subscribers ratio.` [1]"
        ),
        prepared,
    )

    assert failures == []


def test_structural_headings_do_not_require_citations():
    prepared = _PreparedChat(
        conversation_id=1,
        messages=[LLMMessage("user", "q")],
        hits=[FusedHit(chunk_id=10, score=1.0, method="hybrid", rank=1)],
        display={
            10: DisplayChunk(
                chunk_id=10,
                content="Claude Code, NotebookLM, and Obsidian form a research workflow.",
                document_id=1,
                document_title="Workflow Setup",
                source_id=1,
                source_name="Uploaded PDF",
                char_start=0,
                char_end=68,
            ),
        },
        meta={},
        item_count=1,
        include_chunks=True,
    )

    failures = _citation_support_failures(
        (
            "To set up this workflow pipeline, follow these steps:\n\n"
            "1. **Preparation:**\n"
            "   * Claude Code, NotebookLM, and Obsidian form a research workflow [1]."
        ),
        prepared,
    )

    assert failures == []


def test_block_citation_still_rejects_unsupported_claims():
    prepared = _PreparedChat(
        conversation_id=1,
        messages=[LLMMessage("user", "q")],
        hits=[FusedHit(chunk_id=10, score=1.0, method="hybrid", rank=1)],
        display={
            10: DisplayChunk(
                chunk_id=10,
                content="Hybrid retrieval combines vector search and full-text search.",
                document_id=1,
                document_title="Hybrid Retrieval",
                source_id=1,
                source_name="Docs",
                char_start=0,
                char_end=64,
            ),
        },
        meta={},
        item_count=1,
        include_chunks=True,
    )

    failures = _citation_support_failures(
        "The moon is made of cheese. Hybrid retrieval combines vector search and full-text search [1].",
        prepared,
    )

    assert failures
    assert failures[0]["reason"] == "unsupported_segment"


def test_cross_language_cited_context_does_not_require_english_token_overlap():
    prepared = _PreparedChat(
        conversation_id=1,
        messages=[LLMMessage("user", "q")],
        hits=[FusedHit(chunk_id=10, score=1.0, method="hybrid", rank=1)],
        display={
            10: DisplayChunk(
                chunk_id=10,
                content=(
                    "Claude Code chạy lệnh, gọi skill, quản lý file và điều phối "
                    "toàn bộ pipeline."
                ),
                document_id=1,
                document_title="Vietnamese Workflow",
                source_id=1,
                source_name="Uploaded PDF",
                char_start=0,
                char_end=86,
            ),
        },
        meta={},
        item_count=1,
        include_chunks=True,
    )

    failures = _citation_support_failures(
        "It coordinates tools, skills, files, and the whole pipeline [1].",
        prepared,
    )

    assert failures == []
