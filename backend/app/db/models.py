"""ORM models — the Phase 0 schema. The hand-written baseline migration
(migrations/versions/0001_baseline.py) is the source of truth for DDL (pgvector extension,
generated tsvector column, HNSW/GIN indexes); these models mirror it for app use and future
autogenerate. Keep the two in sync.
"""
from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

EMBED_DIM = 384  # all-MiniLM-L6-v2; see ADR-0002


def _pk() -> Mapped[int]:
    return mapped_column(BigInteger, primary_key=True, autoincrement=True)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint(
            "type IN ('notes_folder','github','rss','pdf_upload','bookmark','research_note','manual')",
            name="ck_sources_type",
        ),
    )
    id: Mapped[int] = _pk()
    type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    uri: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    documents: Mapped[list["Document"]] = relationship(back_populates="source")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("source_id", "content_hash", name="uq_documents_source_hash"),
        CheckConstraint(
            "status IN ('pending','chunked','embedded','failed')", name="ck_documents_status"
        ),
        Index("ix_documents_source_id", "source_id"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_metadata", "metadata", postgresql_using="gin"),
    )
    id: Mapped[int] = _pk()
    source_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)  # purged after embedding — ADR/D5
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    source: Mapped["Source"] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document")
    tags: Mapped[list["Tag"]] = relationship(secondary="document_tags", back_populates="documents")


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_doc_index"),
        Index("ix_chunks_document_id", "document_id"),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
    )
    id: Mapped[int] = _pk()
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    # GENERATED ALWAYS AS (to_tsvector('english', content)) STORED — read-only.
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', content)", persisted=True)
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = _created()
    document: Mapped["Document"] = relationship(back_populates="chunks")
    embeddings: Mapped[list["Embedding"]] = relationship(back_populates="chunk")


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint("chunk_id", "model", name="uq_embeddings_chunk_model"),
        Index(
            "ix_embeddings_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    id: Mapped[int] = _pk()
    chunk_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False
    )
    model: Mapped[str] = mapped_column(Text, nullable=False)
    dim: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM), nullable=False)
    created_at: Mapped[datetime] = _created()
    chunk: Mapped["Chunk"] = relationship(back_populates="embeddings")


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[int] = _pk()
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = _created()
    documents: Mapped[list["Document"]] = relationship(
        secondary="document_tags", back_populates="tags"
    )


class DocumentTag(Base):
    __tablename__ = "document_tags"
    __table_args__ = (Index("ix_document_tags_tag_id", "tag_id"),)
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = _pk()
    title: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant','system')", name="ck_messages_role"),
        Index("ix_messages_conversation", "conversation_id", "created_at"),
    )
    id: Mapped[int] = _pk()
    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(Text)
    token_usage: Mapped[dict | None] = mapped_column(JSONB)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _created()
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    retrievals: Mapped[list["Retrieval"]] = relationship(back_populates="message")
    feedback: Mapped[list["Feedback"]] = relationship(back_populates="message")


class Retrieval(Base):
    __tablename__ = "retrievals"
    __table_args__ = (
        CheckConstraint("method IN ('vector','fulltext','hybrid')", name="ck_retrievals_method"),
        Index("ix_retrievals_message", "message_id"),
        Index("ix_retrievals_chunk", "chunk_id"),
    )
    id: Mapped[int] = _pk()
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float | None] = mapped_column(Double)
    vector_score: Mapped[float | None] = mapped_column(Double)
    fulltext_score: Mapped[float | None] = mapped_column(Double)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created()
    message: Mapped["Message"] = relationship(back_populates="retrievals")


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("rating IN (-1, 1)", name="ck_feedback_rating"),
        Index("ix_feedback_message", "message_id"),
    )
    id: Mapped[int] = _pk()
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    message: Mapped["Message"] = relationship(back_populates="feedback")


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(
            "action IN ('read','create','update','delete','export')", name="ck_audit_action"
        ),
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
    )
    id: Mapped[int] = _pk()
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = _created()


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "type IN ('ingest','embed','briefing','research')", name="ck_jobs_type"
        ),
        CheckConstraint(
            "status IN ('queued','running','done','failed')", name="ck_jobs_status"
        ),
        Index("ix_jobs_status_scheduled", "status", "scheduled_at"),
    )
    id: Mapped[int] = _pk()
    type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()
