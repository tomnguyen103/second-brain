"""research_topic vs real DB: stores a research_note, embeds it, makes it searchable (ADR-0010)."""
import os

import pytest

from app.config import Settings
from app.llm.fake import FakeLLMClient
from app.research.service import RESEARCH_SOURCE, research_topic
from app.retrieval.hybrid import hybrid_search

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB")


def test_research_stores_embeds_and_is_searchable(db_session, fake_embedder):
    res = research_topic(db_session, fake_embedder, FakeLLMClient(), "Reciprocal rank fusion basics")
    assert res.document_id is not None
    assert res.status == "embedded"
    assert res.chunk_count >= 1
    assert res.searchable is True
    assert res.summary                                  # the (fake) note text

    # auto-ingested → retrievable: search the stored note text, scoped to the research source
    hits, _meta = hybrid_search(db_session, fake_embedder, Settings(_env_file=None),
                                res.summary, source_ids=[res.source_id])
    assert len(hits) >= 1


def test_research_empty_topic_rejected(db_session, fake_embedder):
    with pytest.raises(ValueError):
        research_topic(db_session, fake_embedder, FakeLLMClient(), "   ")


def test_research_source_is_research_note(db_session, fake_embedder):
    res = research_topic(db_session, fake_embedder, FakeLLMClient(), "Some distinct topic xyz")
    from sqlalchemy import select
    from app.db.models import Source
    src = db_session.scalar(select(Source).where(Source.id == res.source_id))
    assert src.type == "research_note" and src.name == RESEARCH_SOURCE
