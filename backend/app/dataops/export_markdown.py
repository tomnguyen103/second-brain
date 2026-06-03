"""Local-only Markdown keeper export dry-run.

This CLI reads candidate keeper data from the local Second Brain database and writes
Markdown files to a local output directory for human review. It never calls the
admin export/delete endpoints and it runs all database reads inside a read-only
transaction that is rolled back before exit.
"""
from __future__ import annotations

import argparse
import re
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db.models import Briefing, Chunk, Document, Feedback, Message, Source
from app.security import redact_sensitive_text

EXPORT_KINDS = ("research-notes", "briefings", "chat-answers", "source-documents")
LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1"}
SOURCE_DOCUMENT_TYPES = {"notes_folder", "pdf_upload", "bookmark", "manual"}


@dataclass(frozen=True)
class ExportedFile:
    kind: str
    path: Path


def is_local_database_url(database_url: str) -> bool:
    """Return True only for URLs that point at a local database host."""
    url = make_url(database_url)
    if url.drivername.startswith("sqlite"):
        return True
    return (url.host or "") in LOCAL_DB_HOSTS


def safe_database_label(database_url: str) -> str:
    """Render a database URL without exposing a password."""
    return make_url(database_url).render_as_string(hide_password=True)


def parse_kinds(value: str) -> tuple[str, ...]:
    if value.strip() == "all":
        return EXPORT_KINDS
    kinds = tuple(part.strip() for part in value.split(",") if part.strip())
    unknown = sorted(set(kinds) - set(EXPORT_KINDS))
    if unknown:
        allowed = ", ".join(("all", *EXPORT_KINDS))
        raise argparse.ArgumentTypeError(
            f"unknown export kind(s): {', '.join(unknown)}. Allowed: {allowed}"
        )
    return kinds


def slugify(value: str, *, fallback: str = "untitled", max_length: int = 80) -> str:
    ascii_value = value.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", ascii_value)
    cleaned = re.sub(r"\s+", "-", cleaned.strip()).strip(".-_")
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    return (cleaned[:max_length].strip(".-_") or fallback)


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    return _utc(dt).isoformat()


def filename_time(dt: datetime | None, fmt: str) -> str:
    if dt is None:
        return re.sub(r"\d", "0", datetime(2000, 1, 1).strftime(fmt))
    return _utc(dt).strftime(fmt)


def yaml_scalar(value: object) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    text_value = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text_value}"'


def frontmatter(items: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in items.items():
        if isinstance(value, list | tuple):
            if value:
                lines.append(f"{key}:")
                lines.extend(f"  - {yaml_scalar(item)}" for item in value)
            else:
                lines.append(f"{key}: []")
        else:
            lines.append(f"{key}: {yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def truncate_content(content: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0 or len(content) <= max_chars:
        return content, False
    return content[:max_chars].rstrip() + "\n\n[TRUNCATED FOR REVIEW EXPORT]\n", True


def write_markdown(base_dir: Path, kind: str, filename: str, body: str) -> ExportedFile:
    kind_dir = base_dir / kind
    kind_dir.mkdir(parents=True, exist_ok=True)
    path = kind_dir / filename
    path.write_text(redact_sensitive_text(body), encoding="utf-8")
    return ExportedFile(kind=kind, path=path)


def document_tags(doc: Document) -> list[str]:
    return sorted({tag.name for tag in doc.tags})


def document_text(db: Session, doc: Document) -> tuple[str, str]:
    if doc.raw_text:
        return doc.raw_text, "raw_text"
    chunks = db.scalars(
        select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.chunk_index.asc())
    ).all()
    return "\n\n".join(chunk.content for chunk in chunks), "chunks"


def render_review_checklist(target_folder: str) -> str:
    return "\n".join(
        [
            "## Keeper Review",
            "- [ ] Worth keeping",
            f"- [ ] Move approved note into Obsidian `{target_folder}`",
            "- [ ] Reindex through `/ingest`",
            "- [ ] Search-verify by title and one important term",
            "- [ ] Mark `status: approved` after verification",
        ]
    )


def render_research_note(db: Session, doc: Document, max_chars: int) -> str:
    content, content_source = document_text(db, doc)
    content, truncated = truncate_content(content, max_chars)
    tags = ["second-brain-export", "research", *document_tags(doc)]
    metadata = dict(doc.metadata_ or {})
    topic = metadata.get("topic") or doc.title
    return "\n\n".join(
        [
            frontmatter(
                {
                    "title": doc.title,
                    "kind": "research-note",
                    "status": "review",
                    "created": iso(doc.created_at),
                    "derived": True,
                    "source_tool": "second-brain",
                    "second_brain_source_id": doc.source_id,
                    "second_brain_document_id": doc.id,
                    "content_source": content_source,
                    "truncated": truncated,
                    "tags": tags,
                }
            ),
            f"# {doc.title}",
            render_review_checklist("10 Research"),
            "## Provenance",
            f"- Topic: {topic}",
            f"- Source: {doc.source.name} (`{doc.source.type}`)",
            f"- Document ID: {doc.id}",
            f"- Content source: `{content_source}`",
            "## Research Note",
            content.strip() or "_No text available in raw_text or chunks._",
        ]
    )


def export_research_notes(db: Session, base_dir: Path, limit: int, max_chars: int) -> list[ExportedFile]:
    docs = db.scalars(
        select(Document)
        .join(Source, Source.id == Document.source_id)
        .options(selectinload(Document.tags), selectinload(Document.source))
        .where(Source.type == "research_note")
        .order_by(Document.created_at.desc(), Document.id.desc())
        .limit(limit)
    ).all()
    files: list[ExportedFile] = []
    for doc in docs:
        filename = (
            f"{filename_time(doc.created_at, '%Y%m%d')}-{doc.id}-"
            f"{slugify(redact_sensitive_text(doc.title))}.md"
        )
        files.append(
            write_markdown(
                base_dir,
                "research-notes",
                filename,
                render_research_note(db, doc, max_chars),
            )
        )
    return files


def render_briefing(briefing: Briefing) -> str:
    return "\n\n".join(
        [
            frontmatter(
                {
                    "title": f"Second Brain briefing {briefing.generated_at:%Y-%m-%d %H:%M UTC}",
                    "kind": "briefing",
                    "status": "review",
                    "created": iso(briefing.generated_at),
                    "derived": True,
                    "source_tool": "second-brain",
                    "second_brain_briefing_id": briefing.id,
                    "period_start": iso(briefing.period_start),
                    "period_end": iso(briefing.period_end),
                    "document_count": briefing.document_count,
                    "model": briefing.model,
                    "tags": ["second-brain-export", "briefing"],
                }
            ),
            f"# Briefing {briefing.generated_at:%Y-%m-%d}",
            render_review_checklist("50 Agent Outputs"),
            "## Summary",
            briefing.summary.strip(),
            "## Stored Briefing",
            briefing.body_markdown.strip(),
        ]
    )


def export_briefings(db: Session, base_dir: Path, limit: int) -> list[ExportedFile]:
    briefings = db.scalars(
        select(Briefing)
        .order_by(Briefing.generated_at.desc(), Briefing.id.desc())
        .limit(limit)
    ).all()
    files: list[ExportedFile] = []
    for briefing in briefings:
        filename = f"{briefing.generated_at:%Y%m%d-%H%M}-{briefing.id}-briefing.md"
        files.append(write_markdown(base_dir, "briefings", filename, render_briefing(briefing)))
    return files


def nearest_user_question(db: Session, answer: Message) -> str:
    msg = db.scalar(
        select(Message)
        .where(
            Message.conversation_id == answer.conversation_id,
            Message.role == "user",
            Message.created_at <= answer.created_at,
            Message.id < answer.id,
        )
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
    )
    return msg.content if msg else ""


def citation_blocks(db: Session, answer: Message) -> list[str]:
    blocks: list[str] = []
    for retrieval in sorted(answer.retrievals, key=lambda item: item.rank):
        chunk = db.get(Chunk, retrieval.chunk_id)
        if chunk is None:
            continue
        doc = db.get(Document, chunk.document_id)
        source = db.get(Source, doc.source_id) if doc else None
        title = doc.title if doc else "Unknown document"
        source_name = source.name if source else "Unknown source"
        score = "" if retrieval.score is None else f"{retrieval.score:.4f}"
        blocks.append(
            "\n".join(
                [
                    f"### [{retrieval.rank}] {title}",
                    f"- Source: {source_name}",
                    f"- Method: {retrieval.method}",
                    f"- Score: {score}",
                    "",
                    chunk.content.strip(),
                ]
            )
        )
    return blocks


def feedback_lines(answer: Message) -> list[str]:
    if not answer.feedback:
        return ["- _No feedback recorded._"]
    lines = []
    for fb in sorted(answer.feedback, key=lambda item: item.created_at):
        label = "positive" if fb.rating == 1 else "negative"
        comment = f" - {fb.comment}" if fb.comment else ""
        lines.append(f"- {label} at {iso(fb.created_at)}{comment}")
    return lines


def render_chat_answer(db: Session, answer: Message, mode: str) -> str:
    question = nearest_user_question(db, answer)
    citations = citation_blocks(db, answer)
    return "\n\n".join(
        [
            frontmatter(
                {
                    "title": f"Chat answer {answer.id}",
                    "kind": "chat-answer",
                    "status": "review",
                    "created": iso(answer.created_at),
                    "derived": True,
                    "source_tool": "second-brain",
                    "second_brain_conversation_id": answer.conversation_id,
                    "second_brain_message_id": answer.id,
                    "important_signal": mode,
                    "model": answer.model,
                    "latency_ms": answer.latency_ms,
                    "tags": ["second-brain-export", "chat-answer"],
                }
            ),
            f"# Chat Answer {answer.id}",
            render_review_checklist("50 Agent Outputs"),
            "## Question",
            question.strip() or "_No preceding user question found._",
            "## Answer",
            answer.content.strip(),
            "## Citations",
            "\n\n".join(citations) if citations else "_No retrieval citations recorded._",
            "## Feedback",
            "\n".join(feedback_lines(answer)),
        ]
    )


def export_chat_answers(
    db: Session, base_dir: Path, limit: int, mode: str
) -> list[ExportedFile]:
    query = (
        select(Message)
        .options(selectinload(Message.retrievals), selectinload(Message.feedback))
        .where(Message.role == "assistant")
    )
    if mode == "positive-feedback":
        query = query.where(Message.feedback.any(Feedback.rating == 1))
    elif mode == "recent-cited":
        query = query.where(Message.retrievals.any())
    elif mode != "all":
        raise ValueError(f"unknown chat export mode: {mode}")

    answers = db.scalars(
        query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit)
    ).all()
    files: list[ExportedFile] = []
    for answer in answers:
        filename = f"{filename_time(answer.created_at, '%Y%m%d-%H%M')}-{answer.id}-chat-answer.md"
        files.append(
            write_markdown(base_dir, "chat-answers", filename, render_chat_answer(db, answer, mode))
        )
    return files


def render_source_document(db: Session, doc: Document, max_chars: int) -> str:
    content, content_source = document_text(db, doc)
    content, truncated = truncate_content(content, max_chars)
    return "\n\n".join(
        [
            frontmatter(
                {
                    "title": doc.title,
                    "kind": "source-document",
                    "status": "review",
                    "created": iso(doc.created_at),
                    "derived": False,
                    "source_tool": "second-brain",
                    "second_brain_source_id": doc.source_id,
                    "second_brain_document_id": doc.id,
                    "original_source_type": doc.source.type,
                    "content_source": content_source,
                    "truncated": truncated,
                    "tags": ["second-brain-export", "source-document", *document_tags(doc)],
                }
            ),
            f"# {doc.title}",
            render_review_checklist("40 Sources"),
            "## Provenance",
            f"- Source: {doc.source.name} (`{doc.source.type}`)",
            f"- URI: {doc.source.uri or ''}",
            f"- Content type: {doc.content_type or ''}",
            f"- Document ID: {doc.id}",
            f"- Content source: `{content_source}`",
            "## Content",
            content.strip() or "_No text available in raw_text or chunks._",
        ]
    )


def export_source_documents(
    db: Session, base_dir: Path, limit: int, max_chars: int
) -> list[ExportedFile]:
    docs = db.scalars(
        select(Document)
        .join(Source, Source.id == Document.source_id)
        .options(selectinload(Document.tags), selectinload(Document.source))
        .where(Source.type.in_(SOURCE_DOCUMENT_TYPES))
        .order_by(Document.created_at.desc(), Document.id.desc())
        .limit(limit)
    ).all()
    files: list[ExportedFile] = []
    for doc in docs:
        filename = (
            f"{filename_time(doc.created_at, '%Y%m%d')}-{doc.id}-"
            f"{slugify(redact_sensitive_text(doc.title))}.md"
        )
        files.append(
            write_markdown(
                base_dir,
                "source-documents",
                filename,
                render_source_document(db, doc, max_chars),
            )
        )
    return files


def write_manifest(
    output_dir: Path,
    database_label: str,
    selected_kinds: Iterable[str],
    files: list[ExportedFile],
) -> Path:
    counts = {kind: 0 for kind in EXPORT_KINDS}
    for file in files:
        counts[file.kind] += 1
    lines = [
        "# Second Brain keeper export manifest",
        "",
        "This export was produced by the local-only Markdown dry-run CLI.",
        "",
        f"- Database: `{database_label}`",
        f"- Output directory: `{output_dir}`",
        f"- Selected kinds: {', '.join(selected_kinds)}",
        "- Database transaction: read-only, rolled back",
        "",
        "## Counts",
    ]
    lines.extend(f"- {kind}: {counts[kind]}" for kind in EXPORT_KINDS)
    lines.extend(
        [
            "",
            "## Review Steps",
            "1. Count files under each keeper folder.",
            "2. Spot-check content and provenance.",
            "3. Move only approved Markdown into Obsidian.",
            "4. Reindex approved notes through `/ingest`.",
            "5. Search-verify the title and one important term.",
            "6. Back up the database before any future purge.",
            "",
            "No purge was run by this exporter.",
        ]
    )
    path = output_dir / "EXPORT_MANIFEST.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def ensure_empty_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise SystemExit(f"output directory is not empty: {output_dir}")


def export_markdown(args: argparse.Namespace) -> tuple[Path, list[ExportedFile]]:
    database_url = settings.database_url
    if not getattr(args, "allow_nonlocal_data", False):
        if settings.data_environment != "local":
            raise SystemExit(
                "Refusing export because SECOND_BRAIN_DATA_ENVIRONMENT is not local: "
                f"{settings.data_environment}"
            )
        if getattr(args, "confirm_local_export", "") != "local-only":
            raise SystemExit(
                'Refusing export without explicit confirmation: pass --confirm-local-export local-only'
            )
    if not is_local_database_url(database_url):
        if getattr(args, "allow_nonlocal_data", False):
            pass
        else:
            raise SystemExit(
                "Refusing to read from a non-local database URL: "
                f"{safe_database_label(database_url)}"
            )
    output_dir = Path(args.output_dir) if args.output_dir else Path(
        tempfile.mkdtemp(prefix="second-brain-keeper-export-")
    )
    ensure_empty_output_dir(output_dir)

    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    files: list[ExportedFile] = []
    conn = engine.connect()
    tx = conn.begin()
    try:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        with Session(bind=conn, expire_on_commit=False) as db:
            if "research-notes" in args.kinds:
                files.extend(
                    export_research_notes(
                        db, output_dir, args.research_notes_limit, args.max_content_chars
                    )
                )
            if "briefings" in args.kinds:
                files.extend(export_briefings(db, output_dir, args.briefings_limit))
            if "chat-answers" in args.kinds:
                files.extend(
                    export_chat_answers(
                        db, output_dir, args.chat_answers_limit, args.chat_mode
                    )
                )
            if "source-documents" in args.kinds:
                files.extend(
                    export_source_documents(
                        db, output_dir, args.source_documents_limit, args.max_content_chars
                    )
                )
    finally:
        tx.rollback()
        conn.close()
        engine.dispose()

    manifest = write_manifest(output_dir, safe_database_label(database_url), args.kinds, files)
    files.append(ExportedFile("manifest", manifest))
    return output_dir, files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.dataops.export_markdown",
        description="Export local Second Brain keeper candidates to Markdown without DB writes.",
    )
    parser.add_argument(
        "--output-dir",
        help="Empty local directory to write into. Defaults to a new temp directory.",
    )
    parser.add_argument(
        "--kinds",
        type=parse_kinds,
        default=EXPORT_KINDS,
        help="Comma-separated kinds or 'all'. Default: all.",
    )
    parser.add_argument("--research-notes-limit", type=int, default=100)
    parser.add_argument("--briefings-limit", type=int, default=100)
    parser.add_argument("--chat-answers-limit", type=int, default=100)
    parser.add_argument("--source-documents-limit", type=int, default=100)
    parser.add_argument(
        "--chat-mode",
        choices=("positive-feedback", "recent-cited", "all"),
        default="positive-feedback",
        help="Which assistant answers to export as chat keepers.",
    )
    parser.add_argument(
        "--max-content-chars",
        type=int,
        default=50000,
        help="Max characters per research/source document body; 0 means no limit.",
    )
    parser.add_argument(
        "--confirm-local-export",
        default="",
        help='Required safety acknowledgement for local exports: "local-only".',
    )
    parser.add_argument(
        "--allow-nonlocal-data",
        action="store_true",
        help="Override local-only checks after explicit owner approval.",
    )
    return parser


def print_summary(output_dir: Path, files: Sequence[ExportedFile]) -> None:
    counts: dict[str, int] = {}
    for file in files:
        counts[file.kind] = counts.get(file.kind, 0) + 1
    print(f"Output directory: {output_dir}")
    for kind in (*EXPORT_KINDS, "manifest"):
        print(f"{kind}: {counts.get(kind, 0)}")
    print("Database transaction: read-only, rolled back")
    print("No purge was run.")


def main(argv: Sequence[str] | None = None) -> None:  # pragma: no cover - CLI wiring
    parser = build_parser()
    args = parser.parse_args(argv)
    output_dir, files = export_markdown(args)
    print_summary(output_dir, files)


if __name__ == "__main__":  # pragma: no cover
    main()
