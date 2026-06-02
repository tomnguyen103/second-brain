"""Inline ingest: find-or-create source → dedupe → chunk → embed → store (ADR-0007)."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Chunk, Document, DocumentTag, Embedding, Source, Tag
from app.ingest.chunking import chunk_text
from app.ingest.hashing import content_hash


@dataclass
class SourceSpec:
    type: str
    name: str
    uri: str | None = None
    config: dict = field(default_factory=dict)


@dataclass
class DocumentInput:
    title: str
    content: str
    external_id: str | None = None
    content_type: str | None = "text/plain"
    metadata: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class DocumentResult:
    document_id: int | None
    title: str
    status: str                 # embedded | duplicate | failed
    content_hash: str
    chunk_count: int = 0
    embedded_count: int = 0
    duplicate_of: int | None = None
    error: str | None = None


@dataclass
class IngestResult:
    source_id: int
    documents: list[DocumentResult]


def _get_or_create_source(db: Session, spec: SourceSpec) -> Source:
    src = db.scalar(select(Source).where(Source.type == spec.type, Source.name == spec.name))
    if src:
        return src
    src = Source(type=spec.type, name=spec.name, uri=spec.uri, config=spec.config)
    db.add(src)
    db.flush()
    return src


def _get_or_create_tags(db: Session, names: list[str]) -> list[Tag]:
    tags: list[Tag] = []
    for name in dict.fromkeys(n.strip() for n in names if n.strip()):
        tag = db.scalar(select(Tag).where(Tag.name == name))
        if not tag:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
        tags.append(tag)
    return tags


def ingest_documents(db: Session, embedder, *, source: SourceSpec,
                     documents: list[DocumentInput]) -> IngestResult:
    src = _get_or_create_source(db, source)
    results: list[DocumentResult] = []

    for doc_in in documents:
        chash = content_hash(doc_in.content)
        existing = db.scalar(
            select(Document).where(Document.source_id == src.id,
                                   Document.content_hash == chash))
        if existing:
            results.append(DocumentResult(existing.id, doc_in.title, "duplicate",
                                          chash, duplicate_of=existing.id))
            continue
        # Per-document SAVEPOINT: a failure rolls back only this doc, not earlier successes.
        try:
            with db.begin_nested():
                doc = Document(
                    source_id=src.id, title=doc_in.title, external_id=doc_in.external_id,
                    content_type=doc_in.content_type, content_hash=chash,
                    raw_text=doc_in.content, metadata_=doc_in.metadata, status="pending",
                )
                db.add(doc)
                db.flush()
                for tag in _get_or_create_tags(db, doc_in.tags):
                    db.add(DocumentTag(document_id=doc.id, tag_id=tag.id))

                pieces = chunk_text(doc_in.content, embedder.count_tokens,
                                    settings.chunk_target_tokens, settings.chunk_overlap_ratio)
                vectors = embedder.encode([p.content for p in pieces]) if pieces else []
                for piece, vec in zip(pieces, vectors):
                    chunk = Chunk(document_id=doc.id, chunk_index=piece.index,
                                  content=piece.content, token_count=piece.token_count,
                                  char_start=piece.char_start, char_end=piece.char_end)
                    db.add(chunk)
                    db.flush()
                    db.add(Embedding(chunk_id=chunk.id, model=embedder.model_name,
                                     dim=embedder.dim, embedding=vec))

                from datetime import datetime, timezone
                doc.status = "embedded"
                doc.ingested_at = datetime.now(timezone.utc)
                db.flush()

            results.append(DocumentResult(doc.id, doc_in.title, "embedded", chash,
                                          chunk_count=len(pieces), embedded_count=len(vectors)))
        except Exception as exc:
            results.append(DocumentResult(None, doc_in.title, "failed", chash, error=str(exc)))

    db.commit()
    return IngestResult(source_id=src.id, documents=results)
