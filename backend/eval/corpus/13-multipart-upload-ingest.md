# Multipart upload ingest

`POST /ingest/upload` accepts local multipart files with a small allow-list: `.pdf`, `.txt`, and
`.md`. PDF text extraction uses `pypdf`; text and markdown files must be UTF-8. The ingest service
still owns dedupe, chunking, embedding, tagging, and source persistence. Mixed text batches use the
generic `file_upload` source type, while PDF-only batches may use `pdf_upload`. Uploaded binaries
are not retained by default; the app stores extracted text plus parser and original-filename
metadata. Password-protected PDFs are rejected with a clear validation error.
