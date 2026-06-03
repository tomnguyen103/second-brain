import os

import pytest

from app.config import Settings
from app.db.models import Document
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from app.vault.indexer import VAULT_SOURCE_NAME, index_vault

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB"
)


def test_empty_full_scan_does_not_delete_existing_vault_documents(
    db_session, fake_embedder, tmp_path
):
    result = ingest_documents(
        db_session,
        fake_embedder,
        source=SourceSpec(type="notes_folder", name=VAULT_SOURCE_NAME, uri=str(tmp_path)),
        documents=[
            DocumentInput(
                title="Old Approved",
                content="---\nstatus: approved\n---\n# Old Approved\n" + ("Safe content. " * 30),
                external_id="10 Research/old-approved.md",
                content_type="text/markdown",
            )
        ],
    )
    doc_id = result.documents[0].document_id
    assert doc_id is not None

    settings = Settings(
        _env_file=None,
        llm_provider="fake",
        obsidian_vault_path=str(tmp_path),
        vault_index_include_dirs=[],
        vault_index_exclude_dirs=[],
    )
    indexed = index_vault(db_session, fake_embedder, settings)

    assert indexed.requested == 0
    assert indexed.removed_stale == 0
    assert db_session.get(Document, doc_id) is not None
