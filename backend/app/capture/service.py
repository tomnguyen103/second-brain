from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
from urllib.parse import urlparse, urlunparse

from sqlalchemy.orm import Session

from app.config import Settings
from app.ingest.service import DocumentInput, IngestResult, SourceSpec, ingest_documents
from app.schemas.capture import CaptureRequest


CAPTURE_SOURCE_TYPE = "bookmark"


@dataclass
class CaptureResult:
    capture_url: str
    ingest: IngestResult


def validate_capture_url(raw_url: str) -> str:
    """Validate and normalize a user-provided capture URL without fetching it."""
    url = (raw_url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("capture URL must use http or https")
    if not parsed.hostname:
        raise ValueError("capture URL must include a hostname")
    if parsed.username or parsed.password:
        raise ValueError("capture URL must not include credentials")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost"):
        raise ValueError("capture URL host must be public")

    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        ip = None
    if ip is not None and (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise ValueError("capture URL host must be public")

    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("capture URL includes an invalid port") from exc

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path or "/",
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def _clean_tags(tags: list[str]) -> list[str]:
    return list(dict.fromkeys(tag.strip() for tag in tags if tag.strip()))


def _capture_title(req: CaptureRequest, url: str) -> str:
    return (req.title or "").strip() or url


def _capture_content(req: CaptureRequest, *, url: str, title: str, tags: list[str]) -> str:
    parts = [f"Title: {title}", f"URL: {url}"]
    if tags:
        parts.append(f"Tags: {', '.join(tags)}")
    selected_text = (req.selected_text or "").strip()
    if selected_text:
        parts.extend(["", "Selected text:", selected_text])
    notes = (req.notes or "").strip()
    if notes:
        parts.extend(["", "Notes:", notes])
    return "\n".join(parts).strip()


def capture_page(
    db: Session,
    embedder,
    settings: Settings,
    req: CaptureRequest,
    *,
    redis_client=None,
) -> CaptureResult:
    url = validate_capture_url(req.url)
    tags = _clean_tags(req.tags)
    title = _capture_title(req, url)
    content = _capture_content(req, url=url, title=title, tags=tags)
    captured_at = datetime.now(timezone.utc).isoformat()
    ingest = ingest_documents(
        db,
        embedder,
        source=SourceSpec(
            type=CAPTURE_SOURCE_TYPE,
            name=url,
            uri=url,
            config={"kind": "capture"},
        ),
        documents=[
            DocumentInput(
                title=title,
                content=content,
                external_id=url,
                content_type="text/markdown",
                metadata={
                    "kind": "capture",
                    "capture_url": url,
                    "capture_title": title,
                    "capture_tags": tags,
                    "captured_at": captured_at,
                    "has_selected_text": bool((req.selected_text or "").strip()),
                    "has_notes": bool((req.notes or "").strip()),
                },
                tags=tags,
            )
        ],
        settings=settings,
        redis_client=redis_client,
    )
    return CaptureResult(capture_url=url, ingest=ingest)
