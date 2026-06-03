"""Index Obsidian Markdown notes into the existing derived Postgres/RAG store."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import Document, Source
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from app.vault.paths import resolve_vault_path, vault_root
from app.vault.service import is_indexable_vault_path, list_markdown_files, read_note

VAULT_SOURCE_NAME = "Obsidian Vault"


@dataclass
class VaultIndexResult:
    source_id: int
    indexed: int
    skipped: int
    removed_stale: int
    requested: int
    excluded: int = 0


def _vault_source_config(settings: Settings) -> dict:
    return {
        "kind": "obsidian_vault",
        "canonical": "markdown",
        "index_include_dirs": list(settings.vault_index_include_dirs),
        "index_exclude_dirs": list(settings.vault_index_exclude_dirs),
    }


def _selected_markdown_files(settings: Settings, paths: list[str] | None) -> list:
    root = vault_root(settings.vault_path)
    if paths is None:
        return list_markdown_files(
            settings.vault_path,
            include_dirs=settings.vault_index_include_dirs,
            exclude_dirs=settings.vault_index_exclude_dirs,
        )

    files = []
    seen: set[str] = set()
    for raw_path in paths:
        path = resolve_vault_path(settings.vault_path, raw_path)
        rel = path.relative_to(root).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        if path.suffix.lower() != ".md":
            raise ValueError(f"only Markdown notes can be indexed: {raw_path}")
        if not path.is_file():
            raise FileNotFoundError(f"vault note not found: {raw_path}")
        if not is_indexable_vault_path(
            rel,
            include_dirs=settings.vault_index_include_dirs,
            exclude_dirs=settings.vault_index_exclude_dirs,
        ):
            raise ValueError(f"vault note is excluded from indexing by configuration: {raw_path}")
        files.append(path)
    return sorted(files)


def _get_or_create_vault_source(db: Session, settings: Settings) -> Source:
    config = _vault_source_config(settings)
    source = db.scalar(
        select(Source).where(Source.type == "notes_folder", Source.name == VAULT_SOURCE_NAME)
    )
    if source:
        source.uri = settings.vault_path
        source.config = config
        db.flush()
        return source
    source = Source(
        type="notes_folder",
        name=VAULT_SOURCE_NAME,
        uri=settings.vault_path,
        config=config,
    )
    db.add(source)
    db.flush()
    return source


def _vault_document_metadata(note, rel: str) -> dict:
    return {
        "vault_path": rel,
        "content_hash": note.content_hash,
        "mtime": note.mtime,
        "title": note.title,
        "tags": note.tags,
        "frontmatter": note.metadata,
        "kind": note.metadata.get("kind", "obsidian_note"),
        "canonical": "markdown",
    }


def index_vault(
    db: Session,
    embedder,
    settings: Settings,
    *,
    paths: list[str] | None = None,
) -> VaultIndexResult:
    """Index all or selected vault Markdown notes.

    The DB is a derived index. A changed vault file replaces prior indexed rows for the same
    vault-relative path; unchanged files are skipped.
    """
    source = _get_or_create_vault_source(db, settings)
    root = vault_root(settings.vault_path)
    total_markdown = len(list_markdown_files(settings.vault_path)) if paths is None else None
    files = _selected_markdown_files(settings, paths)
    excluded = max(0, total_markdown - len(files)) if total_markdown is not None else 0

    seen_paths: set[str] = set()
    indexed = 0
    skipped = 0

    for path in files:
        rel = path.relative_to(root).as_posix()
        seen_paths.add(rel)
        note = read_note(settings.vault_path, rel)
        existing = db.scalars(
            select(Document).where(Document.source_id == source.id, Document.external_id == rel)
        ).all()
        matching = next((doc for doc in existing if doc.content_hash == note.content_hash), None)
        if matching is not None:
            matching.title = note.title
            matching.metadata_ = _vault_document_metadata(note, rel)
            db.flush()
            skipped += 1
            continue
        if existing:
            db.execute(delete(Document).where(Document.source_id == source.id, Document.external_id == rel))
            db.flush()
        result = ingest_documents(
            db,
            embedder,
            source=SourceSpec(
                type="notes_folder",
                name=VAULT_SOURCE_NAME,
                uri=settings.vault_path,
                config=_vault_source_config(settings),
            ),
            documents=[
                DocumentInput(
                    title=note.title,
                    content=note.content,
                    external_id=rel,
                    content_type="text/markdown",
                    metadata=_vault_document_metadata(note, rel),
                    tags=note.tags,
                )
            ],
        )
        indexed += sum(1 for doc in result.documents if doc.status in {"embedded", "duplicate"})

    removed_stale = 0
    if paths is None:
        stale = db.scalars(
            select(Document).where(Document.source_id == source.id, Document.external_id.is_not(None))
        ).all()
        stale_ids = [doc.id for doc in stale if doc.external_id not in seen_paths]
        if stale_ids:
            db.execute(delete(Document).where(Document.id.in_(stale_ids)))
            db.commit()
            removed_stale = len(stale_ids)

    db.commit()
    return VaultIndexResult(source_id=source.id, indexed=indexed, skipped=skipped,
                            removed_stale=removed_stale, requested=len(files),
                            excluded=excluded)
