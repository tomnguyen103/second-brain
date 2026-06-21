import pytest
from pydantic import ValidationError

from app.schemas.capture import CaptureRequest, MAX_CAPTURE_TEXT_CHARS
from app.schemas.chat import ChatRequest, MAX_CHAT_MESSAGE_CHARS, MAX_CHAT_TOP_K
from app.schemas.ingest import (
    IngestRequest,
    MAX_DOCUMENT_CONTENT_CHARS,
    MAX_DOCUMENT_METADATA_JSON_CHARS,
    MAX_INGEST_DOCUMENTS,
    MAX_SOURCE_CONFIG_JSON_CHARS,
)
from app.schemas.research import (
    MAX_RESEARCH_SOURCE_TEXT_CHARS,
    MAX_RESEARCH_SOURCES,
    ResearchJobCreateRequest,
)


def test_ingest_request_bounds_document_count_and_content_size():
    too_many_docs = [
        {"title": f"Doc {i}", "content": "body"}
        for i in range(MAX_INGEST_DOCUMENTS + 1)
    ]

    with pytest.raises(ValidationError):
        IngestRequest.model_validate(
            {"source": {"type": "manual", "name": "Bulk"}, "documents": too_many_docs}
        )

    with pytest.raises(ValidationError):
        IngestRequest.model_validate(
            {
                "source": {"type": "manual", "name": "Huge"},
                "documents": [
                    {"title": "Huge", "content": "x" * (MAX_DOCUMENT_CONTENT_CHARS + 1)}
                ],
            }
        )


def test_ingest_request_bounds_nested_json_payloads():
    with pytest.raises(ValidationError):
        IngestRequest.model_validate(
            {
                "source": {
                    "type": "manual",
                    "name": "Huge config",
                    "config": {"blob": "x" * MAX_SOURCE_CONFIG_JSON_CHARS},
                },
                "documents": [{"title": "Doc", "content": "body"}],
            }
        )

    with pytest.raises(ValidationError):
        IngestRequest.model_validate(
            {
                "source": {"type": "manual", "name": "Huge metadata"},
                "documents": [
                    {
                        "title": "Doc",
                        "content": "body",
                        "metadata": {"blob": "x" * MAX_DOCUMENT_METADATA_JSON_CHARS},
                    }
                ],
            }
        )


def test_chat_request_bounds_message_and_retrieval_fanout():
    with pytest.raises(ValidationError):
        ChatRequest.model_validate({"message": "x" * (MAX_CHAT_MESSAGE_CHARS + 1)})

    with pytest.raises(ValidationError):
        ChatRequest.model_validate({"message": "hello", "top_k": MAX_CHAT_TOP_K + 1})

    with pytest.raises(ValidationError):
        ChatRequest.model_validate({"message": "   "})


def test_capture_request_bounds_user_supplied_text():
    with pytest.raises(ValidationError):
        CaptureRequest.model_validate(
            {
                "url": "https://example.com",
                "selected_text": "x" * (MAX_CAPTURE_TEXT_CHARS + 1),
            }
        )


def test_research_request_bounds_source_count_and_text_size():
    with pytest.raises(ValidationError):
        ResearchJobCreateRequest.model_validate(
            {
                "topic": "RRF",
                "source_urls": [f"https://example.com/{i}" for i in range(MAX_RESEARCH_SOURCES)],
                "source_texts": [{"text": "extra"}],
            }
        )

    with pytest.raises(ValidationError):
        ResearchJobCreateRequest.model_validate(
            {
                "topic": "RRF",
                "source_texts": [{"text": "x" * (MAX_RESEARCH_SOURCE_TEXT_CHARS + 1)}],
            }
        )
