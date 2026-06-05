"""Pure research prompt/source handling (ADR-0010). DB-free."""
import pytest

from app.research import service as research_service
from app.research.service import build_research_messages, collect_research_sources


def test_messages_shape():
    msgs = build_research_messages("  pgvector HNSW indexes  ")
    assert msgs[0].role == "system" and "research assistant" in msgs[0].content.lower()
    assert msgs[1].role == "user"
    assert "pgvector HNSW indexes" in msgs[1].content     # trimmed topic included
    assert msgs[1].content.strip().endswith("pgvector HNSW indexes")


def test_messages_include_provided_source_context():
    sources = collect_research_sources(
        source_texts=[{
            "title": "RRF note",
            "uri": "manual://rrf",
            "text": "Reciprocal rank fusion combines independently ranked retrieval results.",
        }]
    )

    msgs = build_research_messages("reciprocal rank fusion", sources)

    assert "[S1] RRF note" in msgs[1].content
    assert "manual://rrf" in msgs[1].content
    assert "using only the source excerpts" in msgs[1].content
    assert "Reciprocal rank fusion combines" in msgs[1].content


def test_collect_research_sources_rejects_non_public_urls():
    with pytest.raises(ValueError, match="public|http"):
        collect_research_sources(source_urls=["http://127.0.0.1/internal"])


def test_collect_research_sources_rejects_non_default_public_ports():
    with pytest.raises(ValueError, match="default http/https ports"):
        collect_research_sources(source_urls=["https://example.com:8443/research"])


def test_url_evidence_rejects_redirect_to_private_host(monkeypatch):
    def fake_resolve(hostname: str, port: int) -> list[str]:
        if hostname == "example.com":
            return ["93.184.216.34"]
        raise ValueError("source URL host must resolve to a public address")

    class _RedirectResponse:
        status = 302

        def getheader(self, name: str):
            if name.lower() == "location":
                return "http://127.0.0.1/admin"
            return None

    class _RedirectConnection:
        def __init__(self, hostname: str, port: int, connect_address: str) -> None:
            self.hostname = hostname
            self.port = port
            self.connect_address = connect_address

        def request(self, *args, **kwargs):  # noqa: ANN002, ANN003
            return None

        def getresponse(self):
            return _RedirectResponse()

        def close(self):
            return None

    monkeypatch.setattr(research_service, "_resolve_public_addresses", fake_resolve)
    monkeypatch.setattr(research_service, "_PinnedHTTPConnection", _RedirectConnection)

    evidence = research_service._fetch_url_evidence("http://example.com/start", "S1")

    assert evidence.status == "failed"
    assert "public address" in (evidence.error or "")
