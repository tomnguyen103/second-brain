"""Seed a compact capture -> chat -> feedback demo flow.

Run from `backend/`:

    python -m app.demo.seed
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy.orm import Session

from app.cache.redis_client import get_redis_client
from app.capture.service import capture_page
from app.chat.service import chat
from app.config import Settings, settings
from app.db.models import Feedback
from app.schemas.capture import CaptureRequest


DEMO_URL = "https://example.com/second-brain-demo"
DEMO_TITLE = "Second Brain Demo: Feedback Eval Loop"
DEMO_SELECTED_TEXT = (
    "Second Brain captures browser-provided passages, retrieves them with hybrid Postgres search, "
    "answers with citations, collects thumbs-down feedback, and stages reviewed eval cases before "
    "they become source-controlled release gates."
)
DEMO_NOTES = (
    "Use this seeded note to demo the loop: capture, cited chat, feedback review, eval export, "
    "and the deterministic eval gate."
)
DEMO_QUESTION = "How does Second Brain turn feedback into eval coverage?"
DEMO_FEEDBACK = "Demo negative feedback: promote this into a reviewed eval case after checking labels."


@dataclass
class DemoSeedResult:
    source_id: int
    document_id: int | None
    conversation_id: int
    assistant_message_id: int
    feedback_id: int
    question: str


def seed_demo_flow(
    db: Session,
    embedder,
    llm,
    cfg: Settings,
    *,
    redis_client=None,
) -> DemoSeedResult:
    capture = capture_page(
        db,
        embedder,
        cfg,
        CaptureRequest(
            url=DEMO_URL,
            title=DEMO_TITLE,
            selected_text=DEMO_SELECTED_TEXT,
            notes=DEMO_NOTES,
            tags=["demo", "eval", "feedback"],
        ),
        redis_client=redis_client,
    )
    document = capture.ingest.documents[0]

    result = chat(
        db,
        embedder,
        llm,
        cfg,
        message=DEMO_QUESTION,
        top_k=5,
        redis_client=redis_client,
    )

    feedback = Feedback(message_id=result.message_id, rating=-1, comment=DEMO_FEEDBACK)
    db.add(feedback)
    db.commit()

    return DemoSeedResult(
        source_id=capture.ingest.source_id,
        document_id=document.document_id,
        conversation_id=result.conversation_id,
        assistant_message_id=result.message_id,
        feedback_id=feedback.id,
        question=DEMO_QUESTION,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.demo.seed",
        description="Seed a small capture/chat/feedback demo flow.",
    )
    parser.add_argument(
        "--real-llm",
        action="store_true",
        help="use the configured LLM instead of the deterministic fake LLM",
    )
    args = parser.parse_args(argv)

    from app.db.session import SessionLocal
    from app.deps import get_embedder
    from app.llm.factory import get_llm_client
    from app.llm.fake import FakeLLMClient

    embedder = get_embedder()
    llm = get_llm_client(settings) if args.real_llm else FakeLLMClient()
    redis_client = get_redis_client(settings)

    with SessionLocal() as db:
        result = seed_demo_flow(db, embedder, llm, settings, redis_client=redis_client)

    print("Seeded Second Brain demo flow")
    print(f"  source_id: {result.source_id}")
    print(f"  document_id: {result.document_id}")
    print(f"  conversation_id: {result.conversation_id}")
    print(f"  assistant_message_id: {result.assistant_message_id}")
    print(f"  feedback_id: {result.feedback_id}")
    print(f"  question: {result.question}")
    print("")
    print("Next: open /feedback, review the negative case, promote it, then export staged evals:")
    print("  python -m app.eval.export_cases --output eval/promoted-cases.yaml")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI boundary
    raise SystemExit(main())
