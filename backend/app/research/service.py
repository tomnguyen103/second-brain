"""Research service - source-backed MCP research_topic action (ADR-0010).

The flagship agentic action stores a generated research note as a `research_note` document and
feeds it through normal ingest (chunk + embed), so the result is permanently searchable. Research
can be grounded in user-provided snippets and safe public URLs without adding a paid search API.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
import http.client
import ipaddress
import socket
import ssl
from urllib.error import URLError
from urllib.parse import urljoin, urlparse, urlunparse

from sqlalchemy.orm import Session

from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from app.llm.base import LLMMessage

# All automated research notes live under one source so they're easy to find and filter.
RESEARCH_SOURCE = "Automated Research"

MAX_RESEARCH_SOURCES = 8
MAX_SOURCE_BYTES = 1_000_000
MAX_SOURCE_CHARS = 12_000
METADATA_EXCERPT_CHARS = 700
URL_FETCH_TIMEOUT_SECONDS = 10
MAX_URL_REDIRECTS = 3
_TEXT_CONTENT_TYPES = {
    "application/json",
    "application/ld+json",
    "application/xhtml+xml",
    "application/xml",
}

RESEARCH_SYSTEM = (
    "You are a research assistant. Write concise source-backed research notes. Use only provided "
    "source excerpts for factual claims, cite them inline with markers like [S1], and include "
    "uncertainty when the evidence is thin. If no source excerpts are provided, state that no "
    "source evidence was provided and avoid inventing citations, statistics, or sources."
)

SourceTextLike = str | Mapping[str, object]


@dataclass
class ResearchEvidence:
    id: str
    type: str
    title: str
    text: str = ""
    uri: str | None = None
    content_type: str | None = None
    status: str = "included"
    error: str | None = None
    retrieved_at: str | None = None
    char_count: int = 0
    truncated: bool = False

    def to_metadata(self) -> dict:
        data = {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "status": self.status,
        }
        if self.uri:
            data["uri"] = self.uri
        if self.content_type:
            data["content_type"] = self.content_type
        if self.retrieved_at:
            data["retrieved_at"] = self.retrieved_at
        if self.error:
            data["error"] = self.error
        if self.status == "included":
            data["char_count"] = self.char_count or len(self.text)
            data["excerpt"] = _truncate(self.text, METADATA_EXCERPT_CHARS)
            data["truncated"] = self.truncated
        return data


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _collapse_ws(text: str) -> str:
    return " ".join((text or "").split())


def _truncate(text: str, limit: int) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self._in_title = False
        self._parts: list[str] = []
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001 - HTMLParser signature
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag in {"br", "div", "p", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1
            return
        if tag == "title":
            self._in_title = False
        if tag in {"div", "p", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._in_title:
            self._title_parts.append(data)
        else:
            self._parts.append(data)

    @property
    def title(self) -> str:
        return _collapse_ws(" ".join(self._title_parts))

    @property
    def text(self) -> str:
        return _collapse_ws(" ".join(self._parts))


def _decode_source_bytes(data: bytes, charset: str | None) -> str:
    encoding = charset or "utf-8"
    try:
        return data.decode(encoding, errors="replace")
    except LookupError:
        return data.decode("utf-8", errors="replace")


def _is_private_or_special_address(raw_address: str) -> bool:
    ip = ipaddress.ip_address(raw_address)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _resolve_public_addresses(hostname: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"could not resolve source URL host: {hostname}") from exc

    addresses: list[str] = []
    for info in infos:
        address = info[4][0]
        if _is_private_or_special_address(address):
            raise ValueError("source URL host must resolve to a public address")
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise ValueError(f"could not resolve source URL host: {hostname}")
    return addresses


def _url_port(parsed) -> int:  # noqa: ANN001 - urllib ParseResult is version-stable but verbose
    default_port = 443 if parsed.scheme == "https" else 80
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("source URL includes an invalid port") from exc
    if port is not None and port != default_port:
        raise ValueError("source URLs may only use default http/https ports")
    return default_port


def _validate_public_http_url(url: str) -> str:
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("source URLs must use http or https")
    if not parsed.hostname:
        raise ValueError("source URL must include a hostname")
    if parsed.username or parsed.password:
        raise ValueError("source URLs must not include credentials")

    hostname = parsed.hostname
    port = _url_port(parsed)
    if hostname.lower() in {"localhost", "localhost.localdomain"}:
        raise ValueError("source URL host must be public")

    _resolve_public_addresses(hostname, port)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.params, parsed.query, ""))


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, hostname: str, port: int, connect_address: str) -> None:
        super().__init__(hostname, port=port, timeout=URL_FETCH_TIMEOUT_SECONDS)
        self._connect_address = connect_address

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self._connect_address, self.port),
            self.timeout,
            self.source_address,
        )


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, hostname: str, port: int, connect_address: str) -> None:
        context = ssl.create_default_context()
        super().__init__(hostname, port=port, timeout=URL_FETCH_TIMEOUT_SECONDS, context=context)
        self._connect_address = connect_address
        self._ssl_context = context

    def connect(self) -> None:
        sock = socket.create_connection(
            (self._connect_address, self.port),
            self.timeout,
            self.source_address,
        )
        self.sock = self._ssl_context.wrap_socket(sock, server_hostname=self.host)


def _request_target(parsed) -> str:  # noqa: ANN001 - urllib ParseResult is version-stable but verbose
    return urlunparse(("", "", parsed.path or "/", parsed.params, parsed.query, ""))


def _fetch_public_url_bytes(url: str, redirects: int = 0) -> tuple[str, str, str | None, bytes]:
    safe_url = _validate_public_http_url(url)
    parsed = urlparse(safe_url)
    hostname = parsed.hostname
    if hostname is None:
        raise ValueError("source URL must include a hostname")
    port = _url_port(parsed)
    connect_address = _resolve_public_addresses(hostname, port)[0]

    connection_cls = _PinnedHTTPSConnection if parsed.scheme == "https" else _PinnedHTTPConnection
    connection = connection_cls(hostname, port, connect_address)
    try:
        connection.request(
            "GET",
            _request_target(parsed),
            headers={
                "Host": parsed.netloc,
                "User-Agent": "SecondBrainResearch/1.0 (+https://second-brain.local)",
                "Accept": "text/*, application/json, application/xml;q=0.9, */*;q=0.1",
            },
        )
        response = connection.getresponse()
        if 300 <= response.status < 400:
            location = response.getheader("Location")
            if not location:
                raise URLError(f"HTTP {response.status} redirect missing Location")
            if redirects >= MAX_URL_REDIRECTS:
                raise URLError("too many redirects while fetching research source")
            return _fetch_public_url_bytes(urljoin(safe_url, location), redirects + 1)
        if response.status >= 400:
            raise URLError(f"HTTP {response.status}")
        content_type = response.headers.get_content_type()
        charset = response.headers.get_content_charset()
        data = response.read(MAX_SOURCE_BYTES + 1)
        return safe_url, content_type, charset, data
    finally:
        connection.close()


def _included_evidence(
    *,
    source_id: str,
    type: str,
    title: str,
    text: str,
    uri: str | None = None,
    content_type: str | None = None,
    retrieved_at: str | None = None,
    already_truncated: bool = False,
) -> ResearchEvidence | None:
    text = _collapse_ws(text)
    if not text:
        return None
    char_count = len(text)
    truncated_text = _truncate(text, MAX_SOURCE_CHARS)
    return ResearchEvidence(
        id=source_id,
        type=type,
        title=(title or source_id).strip() or source_id,
        text=truncated_text,
        uri=uri,
        content_type=content_type,
        status="included",
        retrieved_at=retrieved_at,
        char_count=char_count,
        truncated=already_truncated or char_count > len(truncated_text),
    )


def _failed_url_evidence(source_id: str, url: str, error: str) -> ResearchEvidence:
    return ResearchEvidence(
        id=source_id,
        type="url",
        title=url,
        uri=url,
        status="failed",
        error=error,
        retrieved_at=_now_iso(),
    )


def _fetch_url_evidence(url: str, source_id: str) -> ResearchEvidence:
    safe_url = _validate_public_http_url(url)
    try:
        final_url, content_type, charset, data = _fetch_public_url_bytes(safe_url)
    except (http.client.HTTPException, URLError, TimeoutError, OSError, ValueError) as exc:
        return _failed_url_evidence(source_id, safe_url, str(exc))

    byte_truncated = len(data) > MAX_SOURCE_BYTES
    data = data[:MAX_SOURCE_BYTES]

    if not (content_type.startswith("text/") or content_type in _TEXT_CONTENT_TYPES):
        return _failed_url_evidence(source_id, safe_url, f"unsupported content type: {content_type}")

    decoded = _decode_source_bytes(data, charset)
    if content_type in {"text/html", "application/xhtml+xml"}:
        parser = _HTMLTextExtractor()
        parser.feed(decoded)
        text = parser.text
        title = parser.title or final_url
    else:
        text = _collapse_ws(decoded)
        title = final_url

    evidence = _included_evidence(
        source_id=source_id,
        type="url",
        title=title,
        text=text,
        uri=final_url,
        content_type=content_type,
        retrieved_at=_now_iso(),
        already_truncated=byte_truncated,
    )
    if evidence is None:
        return _failed_url_evidence(source_id, final_url, "no readable text found")
    return evidence


def _source_text_field(source: Mapping[str, object], *keys: str) -> str | None:
    for key in keys:
        value = source.get(key)
        if value is not None:
            return str(value)
    return None


def _provided_text_evidence(source: SourceTextLike, source_id: str, index: int) -> ResearchEvidence | None:
    if isinstance(source, str):
        title = f"Provided source {index}"
        text = source
        uri = None
    elif isinstance(source, Mapping):
        title = _source_text_field(source, "title", "name") or f"Provided source {index}"
        text = _source_text_field(source, "text", "content", "snippet") or ""
        uri = _source_text_field(source, "uri", "url")
    else:
        raise ValueError("source_texts entries must be strings or objects")

    return _included_evidence(
        source_id=source_id,
        type="provided_text",
        title=title,
        text=text,
        uri=uri,
        content_type="text/plain",
    )


def collect_research_sources(
    *,
    source_urls: Sequence[str] | None = None,
    source_texts: Sequence[SourceTextLike] | None = None,
) -> list[ResearchEvidence]:
    urls = [url.strip() for url in (source_urls or []) if (url or "").strip()]
    texts = list(source_texts or [])
    if len(urls) + len(texts) > MAX_RESEARCH_SOURCES:
        raise ValueError(f"at most {MAX_RESEARCH_SOURCES} research sources are supported")

    evidence: list[ResearchEvidence] = []
    for url in urls:
        evidence.append(_fetch_url_evidence(url, f"S{len(evidence) + 1}"))
    for source in texts:
        item = _provided_text_evidence(source, f"S{len(evidence) + 1}", len(evidence) + 1)
        if item is not None:
            evidence.append(item)
    return evidence


def _included_sources(sources: Sequence[ResearchEvidence] | None) -> list[ResearchEvidence]:
    return [s for s in (sources or []) if s.status == "included" and s.text.strip()]


def _format_source_context(sources: Sequence[ResearchEvidence]) -> str:
    blocks = []
    for source in sources:
        uri_line = f"\nURI: {source.uri}" if source.uri else ""
        blocks.append(f"[{source.id}] {source.title}{uri_line}\nExcerpt:\n{source.text}")
    return "\n\n".join(blocks)


def build_research_messages(
    topic: str,
    sources: Sequence[ResearchEvidence] | None = None,
) -> list[LLMMessage]:
    topic = (topic or "").strip()
    included = _included_sources(sources)
    if included:
        user_content = (
            "Research this topic using only the source excerpts below. Write a concise, factual "
            "research note: a one or two sentence overview followed by 3-6 key points. Cite "
            "claims with the source markers shown (for example [S1]).\n\n"
            f"Topic:\n{topic}\n\nSource excerpts:\n{_format_source_context(included)}"
        )
    else:
        user_content = f"Research this topic and write a research note:\n\n{topic}"
    return [
        LLMMessage("system", RESEARCH_SYSTEM),
        LLMMessage("user", user_content),
    ]


def _append_sources_section(note: str, sources: Sequence[ResearchEvidence]) -> str:
    included = _included_sources(sources)
    note = (note or "").strip()
    if not included:
        return note

    lines = [note, "", "## Sources"]
    for source in included:
        label = f"[{source.id}] {source.title}"
        if source.uri:
            label = f"{label} - {source.uri}"
        lines.append(f"- {label}")
    return "\n".join(lines).strip()


@dataclass
class ResearchResult:
    topic: str
    document_id: int | None
    source_id: int
    status: str
    duplicate_of: int | None
    chunk_count: int
    model: str | None
    summary: str
    searchable: bool
    evidence_count: int
    sources: list[dict]


def research_topic(
    db: Session,
    embedder,
    llm,
    topic: str,
    *,
    source_urls: Sequence[str] | None = None,
    source_texts: Sequence[SourceTextLike] | None = None,
) -> ResearchResult:
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("research topic is required")

    evidence = collect_research_sources(source_urls=source_urls, source_texts=source_texts)
    resp = llm.generate(build_research_messages(topic, evidence))
    summary = _append_sources_section(resp.text or "", evidence)
    source_metadata = [source.to_metadata() for source in evidence]
    evidence_count = len(_included_sources(evidence))

    result = ingest_documents(
        db, embedder,
        source=SourceSpec(type="research_note", name=RESEARCH_SOURCE),
        documents=[DocumentInput(
            title=topic, content=summary, content_type="text/markdown",
            metadata={
                "kind": "research",
                "topic": topic,
                "model": resp.model,
                "grounding": "source_backed" if evidence_count else "no_source_evidence",
                "source_count": evidence_count,
                "sources": source_metadata,
            },
        )],
    )
    doc = result.documents[0]
    return ResearchResult(
        topic=topic, document_id=doc.document_id, source_id=result.source_id,
        status=doc.status, duplicate_of=doc.duplicate_of, chunk_count=doc.chunk_count,
        model=resp.model, summary=summary,
        searchable=doc.status in ("embedded", "duplicate"),
        evidence_count=evidence_count, sources=source_metadata,
    )
