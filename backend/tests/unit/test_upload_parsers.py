from __future__ import annotations

import pytest

from app.ingest.parsers import UploadParseError, parse_upload_bytes, safe_upload_filename


def _sample_pdf_bytes() -> bytes:
    content = b"BT /F1 24 Tf 72 720 Td (Hello PDF upload) Tj ET\n"
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
        ),
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        (
            f"5 0 obj\n<< /Length {len(content)} >>\nstream\n".encode("ascii")
            + content
            + b"endstream\nendobj\n"
        ),
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


def _encrypted_pdf_bytes(password: str) -> bytes:
    from io import BytesIO

    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(BytesIO(_sample_pdf_bytes()))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def test_parse_pdf_extracts_text_and_metadata():
    parsed = parse_upload_bytes(
        filename="reports/hello.pdf",
        content_type="application/pdf",
        data=_sample_pdf_bytes(),
        allowed_extensions=[".pdf", ".txt", ".md"],
    )

    assert parsed.title == "hello"
    assert "Hello PDF upload" in parsed.content
    assert parsed.content_type == "application/pdf"
    assert parsed.metadata["original_filename"] == "hello.pdf"
    assert parsed.metadata["page_count"] == 1
    assert parsed.metadata["stored_original_file"] is False
    assert parsed.metadata["pdf_encrypted"] is False


def test_parse_passwordless_encrypted_pdf_extracts_text():
    parsed = parse_upload_bytes(
        filename="permissioned.pdf",
        content_type="application/pdf",
        data=_encrypted_pdf_bytes(""),
        allowed_extensions=[".pdf", ".txt", ".md"],
    )

    assert "Hello PDF upload" in parsed.content
    assert parsed.metadata["pdf_encrypted"] is True


def test_parse_password_protected_pdf_is_rejected():
    with pytest.raises(UploadParseError, match="password-protected PDFs"):
        parse_upload_bytes(
            filename="locked.pdf",
            content_type="application/pdf",
            data=_encrypted_pdf_bytes("secret"),
            allowed_extensions=[".pdf", ".txt", ".md"],
        )


def test_parse_markdown_upload_as_text_document():
    parsed = parse_upload_bytes(
        filename="notes.md",
        content_type="text/markdown",
        data=b"# Upload Notes\n\nMultipart upload text.",
        allowed_extensions=[".pdf", ".txt", ".md"],
    )

    assert parsed.title == "notes"
    assert parsed.content_type == "text/markdown"
    assert "Multipart upload text" in parsed.content
    assert parsed.metadata["upload_parser"] == "utf-8"


def test_rejects_unsupported_extension():
    with pytest.raises(UploadParseError, match="unsupported file type"):
        parse_upload_bytes(
            filename="archive.zip",
            content_type="application/zip",
            data=b"PK\x03\x04",
            allowed_extensions=[".pdf", ".txt", ".md"],
        )


def test_rejects_binary_data_in_text_upload():
    with pytest.raises(UploadParseError, match="binary data"):
        parse_upload_bytes(
            filename="notes.txt",
            content_type="text/plain",
            data=b"hello\x00world",
            allowed_extensions=[".pdf", ".txt", ".md"],
        )


def test_safe_upload_filename_drops_path_segments():
    assert safe_upload_filename("../../secret.pdf") == "secret.pdf"
