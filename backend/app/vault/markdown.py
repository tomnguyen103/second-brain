"""Small Markdown/frontmatter helpers for Obsidian notes."""
from __future__ import annotations

import re
from pathlib import Path

_TAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_/-]+)")
_H1_RE = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)
_UNSAFE_FILENAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def slugify_title(title: str) -> str:
    slug = _UNSAFE_FILENAME_RE.sub("-", (title or "").strip() or "Untitled")
    slug = slug.replace(" ", "-")
    slug = re.sub(r"-+", "-", slug).strip(".-")
    return slug or "Untitled"


def split_frontmatter(content: str) -> tuple[dict[str, object], str]:
    """Parse a small YAML-like frontmatter subset without adding a dependency."""
    normalized = (content or "").replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized
    end = normalized.find("\n---", 4)
    if end < 0:
        return {}, normalized
    raw = normalized[4:end]
    close_end = normalized.find("\n", end + 1)
    body = normalized[close_end + 1 :] if close_end >= 0 else ""
    meta: dict[str, object] = {}
    for line in raw.splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            items = [item.strip().strip("\"'") for item in value[1:-1].split(",")]
            meta[key] = [item for item in items if item]
        else:
            meta[key] = value.strip("\"'")
    return meta, body


def note_title(path: Path, content: str, metadata: dict[str, object]) -> str:
    title = metadata.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    match = _H1_RE.search(content or "")
    if match:
        return match.group(1).strip()
    return path.stem


def note_tags(content: str, metadata: dict[str, object]) -> list[str]:
    tags: list[str] = []
    raw = metadata.get("tags")
    if isinstance(raw, list):
        tags.extend(str(t).strip().lstrip("#") for t in raw)
    elif isinstance(raw, str):
        tags.extend(t.strip().lstrip("#") for t in raw.split(","))
    tags.extend(m.group(1) for m in _TAG_RE.finditer(content or ""))
    return sorted({tag for tag in tags if tag})


def _yaml_string(value: object) -> str:
    cleaned = str(value).replace("\r", " ").replace("\n", " ").replace("\\", "\\\\")
    return '"' + cleaned.replace('"', '\\"').strip() + '"'


def render_note(
    title: str,
    body: str,
    *,
    kind: str,
    status: str = "draft",
    tags: list[str] | None = None,
    sources: list[str] | None = None,
) -> str:
    lines = [
        "---",
        f"title: {_yaml_string(title)}",
        f"kind: {_yaml_string(kind)}",
        f"status: {_yaml_string(status)}",
    ]
    if tags:
        lines.append("tags: [" + ", ".join(_yaml_string(tag) for tag in tags) + "]")
    lines.extend(["---", "", f"# {title}", ""])
    if sources:
        lines.extend(["## Sources", *[f"- {source}" for source in sources], ""])
    lines.append((body or "").strip())
    return "\n".join(lines).rstrip() + "\n"
