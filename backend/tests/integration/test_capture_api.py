import os

import pytest


pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB"
)


def _capture_payload(url: str = "https://example.com/second-brain-capture"):
    return {
        "url": url,
        "title": "Capture comet note",
        "selected_text": (
            "Capture comet annotations preserve selected text for searchable cited answers. "
            "The bookmark pipeline stores the quoted passage."
        ),
        "notes": "Remember to connect this to the source review workflow.",
        "tags": ["capture", "inbox"],
    }


def test_capture_stores_searchable_and_citeable_bookmark(client):
    capture = client.post("/capture", json=_capture_payload())

    assert capture.status_code == 200, capture.text
    body = capture.json()
    assert body["capture_url"] == "https://example.com/second-brain-capture"
    assert body["document"]["status"] == "embedded"
    assert body["document"]["title"] == "Capture comet note"
    assert body["summary"]["embedded"] == 1

    search = client.get("/search", params={"q": "capture comet annotations", "top_k": 3})
    assert search.status_code == 200, search.text
    hits = search.json()["hits"]
    assert any(hit["document_title"] == "Capture comet note" for hit in hits)
    assert any("Capture comet annotations" in hit["snippet"] for hit in hits)

    chat = client.post("/chat", json={"message": "What do capture comet annotations preserve?"})
    assert chat.status_code == 200, chat.text
    answer = chat.json()
    assert answer["citations"], answer
    assert any(c["document_title"] == "Capture comet note" for c in answer["citations"])


def test_capture_duplicate_returns_duplicate_document(client):
    first = client.post("/capture", json=_capture_payload("https://example.com/duplicate-capture"))
    second = client.post("/capture", json=_capture_payload("https://example.com/duplicate-capture"))

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    first_doc = first.json()["document"]
    second_doc = second.json()["document"]
    assert first_doc["status"] == "embedded"
    assert second_doc["status"] == "duplicate"
    assert second_doc["duplicate_of"] == first_doc["document_id"]
    assert second.json()["summary"]["duplicates"] == 1


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://localhost/admin",
        "http://127.0.0.1/admin",
        "http://10.0.0.5/admin",
        "http://[::1]/admin",
        "https://user:pass@example.com/private",
    ],
)
def test_capture_rejects_unsafe_urls(client, url: str):
    response = client.post("/capture", json=_capture_payload(url))

    assert response.status_code == 400
    assert "URL" in response.json()["detail"] or "host must be public" in response.json()["detail"]
