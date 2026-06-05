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
