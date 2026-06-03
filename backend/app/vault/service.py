"""Filesystem-backed Obsidian vault operations."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.ingest.hashing import content_hash
from app.vault.markdown import note_tags, note_title, render_note, slugify_title, split_frontmatter
from app.vault.paths import resolve_vault_path, to_vault_relative, vault_root


@dataclass
class VaultNote:
    path: str
    title: str
    content: str
    metadata: dict
    tags: list[str]
    content_hash: str
    mtime: float


def _folder_prefixes(folders: list[str] | None) -> list[tuple[str, ...]]:
    prefixes: list[tuple[str, ...]] = []
    for folder in folders or []:
        normalized = str(folder).replace("\\", "/").strip("/")
        parts = tuple(part.casefold() for part in normalized.split("/") if part)
        if parts:
            prefixes.append(parts)
    return prefixes


def _relative_parts(relative_path: str) -> tuple[str, ...]:
    normalized = str(relative_path).replace("\\", "/").strip("/")
    return tuple(part.casefold() for part in normalized.split("/") if part)


def _is_under_prefix(path_parts: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    return len(path_parts) > len(prefix) and path_parts[: len(prefix)] == prefix


def is_indexable_vault_path(
    relative_path: str,
    *,
    include_dirs: list[str] | None = None,
    exclude_dirs: list[str] | None = None,
) -> bool:
    """Return whether a vault-relative note path should be included in the derived index."""
    path_parts = _relative_parts(relative_path)
    include_prefixes = _folder_prefixes(include_dirs)
    exclude_prefixes = _folder_prefixes(exclude_dirs)
    if include_prefixes and not any(_is_under_prefix(path_parts, prefix) for prefix in include_prefixes):
        return False
    return not any(_is_under_prefix(path_parts, prefix) for prefix in exclude_prefixes)


def list_markdown_files(
    root_path: str,
    *,
    include_dirs: list[str] | None = None,
    exclude_dirs: list[str] | None = None,
) -> list[Path]:
    root = vault_root(root_path)
    if not root.exists():
        return []
    return sorted(
        p
        for p in root.rglob("*.md")
        if p.is_file()
        and is_indexable_vault_path(
            to_vault_relative(root_path, p),
            include_dirs=include_dirs,
            exclude_dirs=exclude_dirs,
        )
    )


def read_note(root_path: str, relative_path: str) -> VaultNote:
    path = resolve_vault_path(root_path, relative_path)
    if path.suffix.lower() != ".md":
        raise ValueError("only Markdown notes can be read")
    content = path.read_text(encoding="utf-8")
    metadata, body = split_frontmatter(content)
    return VaultNote(
        path=to_vault_relative(root_path, path),
        title=note_title(path, body, metadata),
        content=content,
        metadata=metadata,
        tags=note_tags(content, metadata),
        content_hash=content_hash(content),
        mtime=path.stat().st_mtime,
    )


def write_note(root_path: str, relative_path: str, content: str, *, mode: str = "create") -> VaultNote:
    path = resolve_vault_path(root_path, relative_path)
    if path.suffix.lower() != ".md":
        raise ValueError("only Markdown notes can be written")
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "create" and path.exists():
        raise FileExistsError(f"note already exists: {relative_path}")
    if mode == "append":
        prior = path.read_text(encoding="utf-8") if path.exists() else ""
        path.write_text(prior.rstrip() + "\n\n" + content.strip() + "\n", encoding="utf-8")
    elif mode in {"create", "overwrite"}:
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
    else:
        raise ValueError("mode must be create, append, or overwrite")
    return read_note(root_path, to_vault_relative(root_path, path))


def create_research_note(
    root_path: str,
    *,
    topic: str,
    body: str,
    sources: list[str] | None = None,
) -> VaultNote:
    filename = slugify_title(topic) + ".md"
    path = f"10 Research/{filename}"
    content = render_note(
        title=topic,
        body=f"## Synthesis\n\n{body.strip()}",
        kind="research",
        tags=["research"],
        sources=sources,
    )
    return write_note(root_path, path, content, mode="create")


def capture_notebooklm_session(
    root_path: str,
    *,
    title: str,
    body: str,
    sources: list[str] | None = None,
) -> VaultNote:
    filename = slugify_title(title) + ".md"
    path = f"50 Agent Outputs/{filename}"
    content = render_note(
        title=title,
        body=f"## NotebookLM Capture\n\n{body.strip()}",
        kind="notebooklm-capture",
        tags=["notebooklm", "derived"],
        sources=sources,
    )
    return write_note(root_path, path, content, mode="create")
