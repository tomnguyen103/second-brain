"""Read/write helpers for the local-first Obsidian vault."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.ingest.hashing import content_hash
from app.security import ensure_no_sensitive_content
from app.vault.markdown import note_tags, note_title, render_note, slugify_title, split_frontmatter
from app.vault.paths import resolve_vault_path, to_vault_relative, vault_root


@dataclass
class VaultNote:
    path: str
    title: str
    content: str
    metadata: dict[str, object]
    tags: list[str]
    content_hash: str
    mtime: float


def _folder_prefixes(folders: list[str]) -> list[tuple[str, ...]]:
    prefixes: list[tuple[str, ...]] = []
    for folder in folders:
        normalized = str(folder).replace("\\", "/").strip("/")
        if normalized:
            prefixes.append(tuple(part.casefold() for part in normalized.split("/") if part))
    return prefixes


def _relative_parts(relative_path: str) -> tuple[str, ...]:
    normalized = str(relative_path).replace("\\", "/").strip("/")
    return tuple(part.casefold() for part in normalized.split("/") if part)


def _is_under_prefix(path_parts: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    return len(path_parts) >= len(prefix) and path_parts[: len(prefix)] == prefix


def is_indexable_vault_path(
    relative_path: str, include_dirs: list[str], exclude_dirs: list[str]
) -> bool:
    """Return whether a vault-relative note path should be included in the derived index."""
    parts = _relative_parts(relative_path)
    include_prefixes = _folder_prefixes(include_dirs)
    exclude_prefixes = _folder_prefixes(exclude_dirs)
    if include_prefixes and not any(_is_under_prefix(parts, prefix) for prefix in include_prefixes):
        return False
    if exclude_prefixes and any(_is_under_prefix(parts, prefix) for prefix in exclude_prefixes):
        return False
    return True


def list_markdown_files(
    root_path: str | Path, include_dirs: list[str], exclude_dirs: list[str]
) -> list[Path]:
    root = vault_root(root_path)
    if not root.exists():
        return []
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file()
        and p.suffix.lower() == ".md"
        and is_indexable_vault_path(to_vault_relative(root, p), include_dirs, exclude_dirs)
    )


def read_note(root_path: str | Path, relative_path: str | Path) -> VaultNote:
    path = resolve_vault_path(root_path, relative_path)
    if path.suffix.lower() != ".md":
        raise ValueError("only Markdown notes can be read")
    content = path.read_text(encoding="utf-8")
    metadata, _body = split_frontmatter(content)
    return VaultNote(
        path=to_vault_relative(root_path, path),
        title=note_title(path, content, metadata),
        content=content,
        metadata=metadata,
        tags=note_tags(content, metadata),
        content_hash=content_hash(content),
        mtime=path.stat().st_mtime,
    )


def require_approved_note(note: VaultNote) -> None:
    status = str(note.metadata.get("status", "")).strip().casefold()
    if status != "approved":
        raise ValueError("vault note must have frontmatter status: approved before ingest")
    ensure_no_sensitive_content(note.title, note.content, note.metadata, context="vault note")


def write_note(
    root_path: str | Path, relative_path: str | Path, content: str, *, mode: str = "create"
) -> VaultNote:
    ensure_no_sensitive_content(content, context="vault note")
    path = resolve_vault_path(root_path, relative_path)
    if path.suffix.lower() != ".md":
        raise ValueError("only Markdown notes can be written")
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "create":
        if path.exists():
            raise FileExistsError(f"note already exists: {to_vault_relative(root_path, path)}")
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
    elif mode == "append":
        prior = path.read_text(encoding="utf-8") if path.exists() else ""
        separator = "" if not prior else "\n\n"
        path.write_text(prior.rstrip("\n") + separator + content.rstrip("\n") + "\n", encoding="utf-8")
    elif mode == "overwrite":
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
    else:
        raise ValueError("mode must be create, append, or overwrite")
    return read_note(root_path, to_vault_relative(root_path, path))


def create_research_note(
    root_path: str | Path, topic: str, body: str, sources: list[str] | None = None
) -> VaultNote:
    ensure_no_sensitive_content(topic, body, sources or [], context="research note")
    filename = slugify_title(topic) + ".md"
    path = "10 Research/" + filename
    content = render_note(
        topic,
        "## Synthesis\n\n" + (body or "").strip(),
        kind="research",
        status="draft",
        tags=["research"],
        sources=sources,
    )
    return write_note(root_path, path, content, mode="create")


def capture_notebooklm_session(
    root_path: str | Path, title: str, body: str, sources: list[str] | None = None
) -> VaultNote:
    ensure_no_sensitive_content(title, body, sources or [], context="NotebookLM capture")
    filename = slugify_title(title) + ".md"
    path = "50 Agent Outputs/" + filename
    content = render_note(
        title,
        "## NotebookLM Capture\n\n" + (body or "").strip(),
        kind="notebooklm-capture",
        status="draft",
        tags=["notebooklm", "derived"],
        sources=sources,
    )
    return write_note(root_path, path, content, mode="create")
