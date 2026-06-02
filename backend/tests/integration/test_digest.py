"""Digest builder vs real DB (ADR-0010)."""
import os

import pytest

from app.digest.service import build_digest
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB")


def test_digest_reflects_recent_ingest(db_session, fake_embedder):
    ingest_documents(db_session, fake_embedder, source=SourceSpec(type="manual", name="Digest Test"),
                     documents=[DocumentInput(title="Zzz Unique Digest Doc",
                                              content="alpha beta gamma delta. " * 20)])
    out = build_digest(db_session, limit=25)
    assert "# Second Brain — daily digest" in out
    assert "documents across" in out
    assert "Zzz Unique Digest Doc" in out      # the just-added doc shows in "recently added"
