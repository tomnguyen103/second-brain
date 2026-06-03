"""Index approved Markdown notes from the Obsidian vault."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import Document, Source
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from app.vault.paths import resolve_vault_path, vault_root
from app.vault.service import is_indexable_vault_path, list_markdown_files, read_note, require_approved_note

VAULT_SOURCE_NAME = "SecondBrainVault"


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
        "format": "markdown",
        "include_dirs": list(settings.vault_index_include_dirs),
        "exclude_dirs": list(settings.vault_index_exclude_dirs),
    }


def _require_vault_root(settings: Settings) -> Path:
    root = vault_root(settings.obsidian_vault_path)
    if not root.exists():
        raise FileNotFoundError(f"vault root does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"vault root is not a directory: {root}")
    return root


def _selected_markdown_files(
    settings: Settings, paths: list[str] | None, listed_files: list[Path] | None = None
) -> tuple[list[Path], int]:
    root = _require_vault_root(settings)
    if not paths:
        return sorted(listed_files or []), 0

    files: list[Path] = []
    excluded = 0
    seen: set[str] = set()
    for raw_path in paths:
        path = resolve_vault_path(root, raw_path)
        rel = path.relative_to(root).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        if path.suffix.lower() != ".md":
            raise ValueError(f"only Markdown notes can be indexed: {rel}")
        if not path.is_file():
            raise FileNotFoundError(f"vault note not found: {rel}")
        if not is_indexable_vault_path(
            rel, settings.vault_index_include_dirs, settings.vault_index_exclude_dirs
        ):
            excluded += 1
            continue
        files.append(path)
    return sorted(files), excluded


def _get_or_create_vault_source(db: Session, settings: Settings) -> Source:
    config = _vault_source_config(settings)
    source = db.scalar(
        select(Source).where(Source.type == "notes_folder", Source.name == VAULT_SOURCE_NAME)
    )
    if source:
        source.uri = settings.obsidian_vault_path
        source.config = config
        db.flush()
        return source
    source = Source(
        type="notes_folder", name=VAULT_SOURCE_NAME, uri=settings.obsidian_vault_path, config=config
    )
    db.add(source)
    db.flush()
    return source


def index_vault(
    db: Session, embedder, settings: Settings, *, paths: list[str] | None = None
) -> VaultIndexResult:
    root = _require_vault_root(settings)
    source = _get_or_create_vault_source(db, settings)
    listed_files = list_markdown_files(
        root, settings.vault_index_include_dirs, settings.vault_index_exclude_dirs
    )
    total_markdown = len(listed_files)
    files, excluded = _selected_markdown_files(settings, paths, listed_files)

    documents: list[DocumentInput] = []
    seen_paths: set[str] = set()
    skipped = 0
    for path in files:
        rel = path.relative_to(root).as_posix()
        seen_paths.add(rel)
        note = read_note(root, rel)
        try:
            require_approved_note(note)
        except ValueError:
            skipped += 1
            continue
        documents.append(
            DocumentInput(
                title=note.title,
                content=note.content,
                external_id=rel,
                content_type="text/markdown",
                metadata={
                    "kind": "obsidian_note",
                    "path": rel,
                    "content_hash": note.content_hash,
                    "mtime": note.mtime,
                    "title": note.title,
                    "tags": note.tags,
                },
                tags=note.tags,
            )
        )

    result = ingest_documents(
        db,
        embedder,
        source=SourceSpec(
            type="notes_folder",
            name=VAULT_SOURCE_NAME,
            uri=settings.obsidian_vault_path,
            config=_vault_source_config(settings),
        ),
        documents=documents,
    )

    removed_stale = 0
    if paths is None and seen_paths:
        stale_ids = db.scalars(
            select(Document.id).where(
                Document.source_id == source.id,
                Document.external_id.is_not(None),
                Document.external_id.not_in(seen_paths),
            )
        ).all()
        if stale_ids:
            db.execute(
                delete(Document).where(Document.id.in_(stale_ids)),
                execution_options={"synchronize_session": False},
            )
            removed_stale = len(stale_ids)
            db.commit()

    indexed = sum(1 for doc in result.documents if doc.status in ("embedded", "duplicate"))
    requested = len(files) if paths else total_markdown
    return VaultIndexResult(
        source_id=source.id,
        indexed=indexed,
        skipped=skipped,
        removed_stale=removed_stale,
        requested=requested,
        excluded=excluded,
    )
