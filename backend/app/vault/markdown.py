"""Minimal Markdown/frontmatter helpers for Obsidian notes."""
from __future__ import annotations

import re
from pathlib import Path

_TAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_/-]+)")
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_UNSAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._ -]+")


def slugify_title(title: str) -> str:
    title = (title or "Untitled").strip()
    slug = _UNSAFE_FILENAME_RE.sub("", title).strip().replace(" ", "-")
    slug = re.sub(r"-+", "-", slug)[:80].strip(".-")
    return slug or "Untitled"


def split_frontmatter(content: str) -> tuple[dict, str]:
    """Parse a small YAML-like frontmatter subset without adding a dependency."""
    if not content.startswith("---\n"):
        return {}, content
    end = content.find("\n---", 4)
    if end == -1:
        return {}, content
    raw = content[4:end].strip()
    body = content[content.find("\n", end + 1) + 1:]
    meta: dict = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key] = [v.strip().strip("\"'") for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key] = value.strip("\"'")
    return meta, body


def note_title(path: Path, content: str, metadata: dict) -> str:
    title = metadata.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    match = _H1_RE.search(content)
    if match:
        return match.group(1).strip()
    return path.stem


def note_tags(content: str, metadata: dict) -> list[str]:
    tags: list[str] = []
    raw = metadata.get("tags")
    if isinstance(raw, list):
        tags.extend(str(t).strip().lstrip("#") for t in raw)
    elif isinstance(raw, str):
        tags.extend(t.strip().lstrip("#") for t in raw.split(","))
    tags.extend(m.group(1) for m in _TAG_RE.finditer(content))
    return sorted({t for t in tags if t})


def _yaml_string(value: str) -> str:
    cleaned = str(value).replace("\r", " ").replace("\n", " ").strip()
    return '"' + cleaned.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_note(
    *,
    title: str,
    body: str,
    kind: str,
    tags: list[str] | None = None,
    sources: list[str] | None = None,
) -> str:
    tags = tags or []
    sources = sources or []
    lines = [
        "---",
        f"title: {_yaml_string(title)}",
        f"kind: {kind}",
        f"tags: [{', '.join(_yaml_string(tag) for tag in tags)}]",
        "---",
        "",
        f"# {title}",
        "",
        body.strip(),
    ]
    if sources:
        lines.extend(["", "## Sources", ""])
        lines.extend(f"- {source}" for source in sources)
    return "\n".join(lines).rstrip() + "\n"
