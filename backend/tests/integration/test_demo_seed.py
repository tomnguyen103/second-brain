from __future__ import annotations

from sqlalchemy import select

from app.config import Settings
from app.db.models import Feedback, Source
from app.demo.seed import DEMO_QUESTION, seed_demo_flow
from app.llm.fake import FakeLLMClient


def test_seed_demo_flow_creates_capture_chat_and_feedback(db_session, fake_embedder):
    result = seed_demo_flow(
        db_session,
        fake_embedder,
        FakeLLMClient(),
        Settings(llm_provider="fake"),
    )

    source = db_session.get(Source, result.source_id)
    feedback = db_session.get(Feedback, result.feedback_id)

    assert source is not None
    assert source.type == "bookmark"
    assert result.document_id is not None
    assert result.question == DEMO_QUESTION
    assert feedback is not None
    assert feedback.rating == -1
    assert feedback.message_id == result.assistant_message_id
    assert db_session.scalar(select(Feedback).where(Feedback.id == result.feedback_id)) is not None
