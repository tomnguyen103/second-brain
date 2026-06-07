"""Seed a public-safe corpus for portfolio demos.

Run from `backend/`:

    python -m app.demo.seed_public
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy.orm import Session

from app.cache.redis_client import get_redis_client
from app.config import Settings, settings
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents


PUBLIC_DEMO_SOURCE_NAME = "Second Brain Public Demo Corpus"
PUBLIC_DEMO_SOURCE_URI = "https://github.com/tomnguyen103/second-brain"
PUBLIC_DEMO_SUGGESTED_PROMPTS = (
    "Compare regular RAG and Agentic RAG in Second Brain. When should I use each?",
    "What does the local-first runtime protect against?",
    "What MCP tools does Second Brain expose, and which actions are guarded?",
    "How does the feedback and eval workflow improve answer quality?",
    "What happens when evidence is weak or citations are missing?",
)

_COMMON_TAGS = ["public-demo", "second-brain"]
_COMMON_METADATA = {
    "demo_visibility": "public-safe",
    "public_upload": False,
    "purpose": "seeded portfolio demo corpus",
}

PUBLIC_DEMO_DOCUMENTS = (
    DocumentInput(
        title="Regular RAG operating model",
        content=(
            "Regular RAG in Second Brain is the fast default path for direct questions. "
            "It runs one bounded hybrid retrieval pass over the selected sources, combining "
            "PostgreSQL full-text search with pgvector semantic search. Candidates are fused, "
            "the strongest chunks are sent to the configured LLM, and the final answer must "
            "include validated citation markers. Use regular RAG when the question can be "
            "answered from a compact set of retrieved notes without extra planning."
        ),
        external_id="public-demo-regular-rag",
        metadata={**_COMMON_METADATA, "demo_topic": "regular-rag"},
        tags=[*_COMMON_TAGS, "rag", "hybrid-search", "pgvector"],
    ),
    DocumentInput(
        title="Agentic RAG operating model",
        content=(
            "Agentic RAG in Second Brain is an opt-in read-only retrieval workflow built with "
            "LangGraph. It plans multiple focused subqueries, searches existing notes for each "
            "subquery, merges the evidence, and can retry weak evidence before returning an "
            "answer through the same citation validator as regular RAG. Use Agentic RAG for "
            "comparison, decomposition, or questions that need evidence gathered from several "
            "angles. The agentic path does not mutate notes, tasks, or source data."
        ),
        external_id="public-demo-agentic-rag",
        metadata={**_COMMON_METADATA, "demo_topic": "agentic-rag"},
        tags=[*_COMMON_TAGS, "rag", "agentic-rag", "langgraph"],
    ),
    DocumentInput(
        title="Local-first runtime posture",
        content=(
            "Second Brain defaults to a local-first Docker Compose runtime. The owner starts "
            "PostgreSQL with pgvector, the FastAPI backend, the worker, and the Next.js frontend "
            "only when needed. This avoids paying for idle cloud uptime and keeps normal use on "
            "the owner's machine. Optional cloud deployment recipes remain for short demos, but "
            "they are not the default production posture. Uploaded private knowledge should not "
            "be stored in a public demo database."
        ),
        external_id="public-demo-local-first",
        metadata={**_COMMON_METADATA, "demo_topic": "local-first"},
        tags=[*_COMMON_TAGS, "local-first", "docker-compose", "runtime"],
    ),
    DocumentInput(
        title="Source management and governance",
        content=(
            "The web workspace includes a Sources management home where source folders and files "
            "can be inspected, renamed, edited, exported, or deleted through guarded workflows. "
            "Destructive actions require the admin token, and raw-text retention can be purged "
            "without removing searchable chunks until source erasure is requested. The public "
            "demo corpus is intentionally small and public-safe so visitors can query the app "
            "without uploading private documents."
        ),
        external_id="public-demo-source-governance",
        metadata={**_COMMON_METADATA, "demo_topic": "source-governance"},
        tags=[*_COMMON_TAGS, "sources", "governance", "admin"],
    ),
    DocumentInput(
        title="MCP tools and action boundaries",
        content=(
            "Second Brain exposes MCP tools over stdio for trusted local clients. Search notes, "
            "list tasks, and send digest are available by default. Mutating actions such as "
            "create task and research topic require explicit local opt-in before they can write "
            "durable data. This boundary keeps the demo and normal runtime inspectable: read-only "
            "retrieval is easy to show, while mutations stay guarded and intentional."
        ),
        external_id="public-demo-mcp-tools",
        metadata={**_COMMON_METADATA, "demo_topic": "mcp-tools"},
        tags=[*_COMMON_TAGS, "mcp", "tools", "actions"],
    ),
    DocumentInput(
        title="Feedback and eval workflow",
        content=(
            "Second Brain turns feedback into reviewable eval coverage instead of promoting "
            "cases automatically. Thumbs-down feedback can be reviewed, labeled, and exported as "
            "YAML fragments for the source-controlled eval dataset. The eval harness records "
            "metrics with MLflow and CI runs a deterministic quality gate. This makes retrieval "
            "quality, refusal behavior, and prompt changes easier to compare over time."
        ),
        external_id="public-demo-feedback-eval",
        metadata={**_COMMON_METADATA, "demo_topic": "feedback-eval"},
        tags=[*_COMMON_TAGS, "feedback", "eval", "mlflow"],
    ),
    DocumentInput(
        title="Citation safety and weak-context behavior",
        content=(
            "Chat answers in Second Brain are expected to be grounded in retrieved evidence. The "
            "backend validates citation markers and can replace unsupported or uncited model "
            "responses with a safer failure message. Retrieval also tracks weak context so the "
            "app can refuse when evidence is too thin. Regular RAG and Agentic RAG both return "
            "through the citation validator, which keeps the visible answer format consistent."
        ),
        external_id="public-demo-citation-safety",
        metadata={**_COMMON_METADATA, "demo_topic": "citation-safety"},
        tags=[*_COMMON_TAGS, "citations", "safety", "rag"],
    ),
)


@dataclass
class PublicDemoSeedResult:
    source_id: int
    document_ids: list[int]
    embedded_count: int
    duplicate_count: int
    suggested_prompts: tuple[str, ...]


def seed_public_demo_corpus(
    db: Session,
    embedder,
    cfg: Settings,
    *,
    redis_client=None,
) -> PublicDemoSeedResult:
    result = ingest_documents(
        db,
        embedder,
        source=SourceSpec(
            type="manual",
            name=PUBLIC_DEMO_SOURCE_NAME,
            uri=PUBLIC_DEMO_SOURCE_URI,
            config={
                "demo": "public",
                "allows_public_uploads": False,
                "description": "Small public-safe corpus for portfolio demos.",
            },
        ),
        documents=list(PUBLIC_DEMO_DOCUMENTS),
        settings=cfg,
        redis_client=redis_client,
    )
    failed = [doc for doc in result.documents if doc.status == "failed"]
    if failed:
        titles = ", ".join(doc.title for doc in failed)
        raise RuntimeError(f"public demo seed failed for: {titles}")

    document_ids = [doc.document_id for doc in result.documents if doc.document_id is not None]
    return PublicDemoSeedResult(
        source_id=result.source_id,
        document_ids=document_ids,
        embedded_count=sum(1 for doc in result.documents if doc.status == "embedded"),
        duplicate_count=sum(1 for doc in result.documents if doc.status == "duplicate"),
        suggested_prompts=PUBLIC_DEMO_SUGGESTED_PROMPTS,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.demo.seed_public",
        description="Seed a small public-safe corpus for local or hosted demos.",
    )
    parser.parse_args(argv)

    from app.db.session import SessionLocal
    from app.deps import get_embedder

    embedder = get_embedder()
    redis_client = get_redis_client(settings)

    with SessionLocal() as db:
        result = seed_public_demo_corpus(
            db,
            embedder,
            settings,
            redis_client=redis_client,
        )

    print("Seeded Second Brain public demo corpus")
    print(f"  source_id: {result.source_id}")
    print(f"  documents: {len(result.document_ids)}")
    print(f"  embedded: {result.embedded_count}")
    print(f"  duplicates: {result.duplicate_count}")
    print("")
    print("Suggested prompts:")
    for prompt in result.suggested_prompts:
        print(f"  - {prompt}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI boundary
    raise SystemExit(main())
