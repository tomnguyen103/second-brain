"""Upload parsers that turn allowed local files into text ingest documents."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath


class UploadParseError(ValueError):
    """Raised when an uploaded file cannot be safely converted into text."""


@dataclass(frozen=True)
class ParsedUpload:
    title: str
    content: str
    content_type: str
    metadata: dict


_TEXT_CONTENT_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
}


def safe_upload_filename(filename: str | None) -> str:
    name = PurePath(filename or "uploaded-file").name.replace("\x00", "").strip()
    if not name or name in {".", ".."}:
        return "uploaded-file"
    return name[:180]


def upload_extension(filename: str | None) -> str:
    return PurePath(safe_upload_filename(filename)).suffix.lower()


def parse_upload_bytes(
    *,
    filename: str | None,
    content_type: str | None,
    data: bytes,
    allowed_extensions: list[str],
) -> ParsedUpload:
    if not data:
        raise UploadParseError("empty files cannot be ingested")

    original_filename = safe_upload_filename(filename)
    extension = upload_extension(original_filename)
    allowed = {ext.lower() for ext in allowed_extensions}
    if extension not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise UploadParseError(f"unsupported file type {extension or '(none)'}; allowed: {allowed_list}")

    if extension == ".pdf":
        return _parse_pdf(original_filename, content_type, data)
    if extension in _TEXT_CONTENT_TYPES:
        return _parse_text(original_filename, content_type, data, extension)
    raise UploadParseError(f"no parser is configured for {extension}")


def _base_metadata(
    original_filename: str,
    content_type: str | None,
    data: bytes,
    extension: str,
    parser: str,
) -> dict:
    return {
        "original_filename": original_filename,
        "upload_content_type": content_type,
        "upload_extension": extension,
        "upload_size_bytes": len(data),
        "upload_parser": parser,
        "stored_original_file": False,
    }


def _parse_pdf(original_filename: str, content_type: str | None, data: bytes) -> ParsedUpload:
    if not data[:1024].lstrip().startswith(b"%PDF-"):
        raise UploadParseError("PDF upload does not look like a PDF file")

    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(data))
        was_encrypted = bool(reader.is_encrypted)
        if was_encrypted and not reader.decrypt(""):
            raise UploadParseError("password-protected PDFs are not supported")
        page_text = [(page.extract_text() or "").strip() for page in reader.pages]
    except UploadParseError:
        raise
    except Exception as exc:
        raise UploadParseError(f"could not read PDF: {exc}") from exc

    content = "\n\n".join(text for text in page_text if text).strip()
    if not content:
        raise UploadParseError("PDF has no extractable text")

    metadata = _base_metadata(original_filename, content_type, data, ".pdf", "pypdf")
    metadata["page_count"] = len(page_text)
    metadata["pdf_encrypted"] = was_encrypted
    return ParsedUpload(
        title=PurePath(original_filename).stem or original_filename,
        content=content,
        content_type="application/pdf",
        metadata=metadata,
    )


def _parse_text(
    original_filename: str,
    content_type: str | None,
    data: bytes,
    extension: str,
) -> ParsedUpload:
    if b"\x00" in data[:2048]:
        raise UploadParseError("text upload appears to contain binary data")
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UploadParseError("text uploads must be UTF-8 encoded") from exc
    content = content.strip()
    if not content:
        raise UploadParseError("text upload has no content")
    return ParsedUpload(
        title=PurePath(original_filename).stem or original_filename,
        content=content,
        content_type=_TEXT_CONTENT_TYPES[extension],
        metadata=_base_metadata(original_filename, content_type, data, extension, "utf-8"),
    )
