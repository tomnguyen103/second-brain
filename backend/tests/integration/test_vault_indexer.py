import pytest

from app.config import Settings
from app.db.models import Document, Source
from app.retrieval.hybrid import hybrid_search
from app.vault.indexer import VAULT_SOURCE_NAME, index_vault
from sqlalchemy import select


def _vault_documents(db_session, source_id: int) -> list[Document]:
    return db_session.scalars(
        select(Document).where(Document.source_id == source_id).order_by(Document.external_id)
    ).all()


def test_index_vault_indexes_markdown_and_is_idempotent(db_session, fake_embedder, tmp_path):
    note_dir = tmp_path / "10 Research"
    note_dir.mkdir()
    (note_dir / "agent-security.md").write_text(
        """---
title: "Agent Security"
tags: [security, agents]
---
# Agent Security

Prompt injection defenses protect local MCP vault tools.
""",
        encoding="utf-8",
    )
    settings = Settings(_env_file=None, llm_provider="fake", vault_path=str(tmp_path))

    first = index_vault(db_session, fake_embedder, settings)
    second = index_vault(db_session, fake_embedder, settings)

    assert first.indexed == 1
    assert second.indexed == 0
    assert second.skipped == 1
    docs = _vault_documents(db_session, first.source_id)
    assert len(docs) == 1
    doc = docs[0]
    assert doc.external_id == "10 Research/agent-security.md"
    assert doc.title == "Agent Security"
    assert doc.metadata_["vault_path"] == "10 Research/agent-security.md"
    assert doc.metadata_["content_hash"] == doc.content_hash
    assert doc.metadata_["title"] == "Agent Security"
    assert doc.metadata_["tags"] == ["agents", "security"]
    assert doc.metadata_["frontmatter"] == {"title": "Agent Security", "tags": ["security", "agents"]}
    assert isinstance(doc.metadata_["mtime"], float)
    assert sorted(t.name for t in doc.tags) == ["agents", "security"]

    hits, _ = hybrid_search(db_session, fake_embedder, settings, "prompt injection MCP", top_k=3)
    assert hits


def test_index_vault_excludes_noisy_default_folders(db_session, fake_embedder, tmp_path):
    for folder in ["10 Research", "Templates", ".obsidian", "90 Archive"]:
        (tmp_path / folder).mkdir()
    (tmp_path / "10 Research" / "keeper.md").write_text(
        "# Keeper\n\nDaily-use local memory should be indexed.",
        encoding="utf-8",
    )
    (tmp_path / "Templates" / "research-template.md").write_text(
        "# Template\n\nTemplate placeholder text should stay out.",
        encoding="utf-8",
    )
    (tmp_path / ".obsidian" / "workspace.md").write_text(
        "# Workspace\n\nObsidian config text should stay out.",
        encoding="utf-8",
    )
    (tmp_path / "90 Archive" / "old.md").write_text(
        "# Old\n\nArchived daily clutter should stay out by default.",
        encoding="utf-8",
    )
    settings = Settings(_env_file=None, llm_provider="fake", vault_path=str(tmp_path))

    result = index_vault(db_session, fake_embedder, settings)

    assert result.requested == 1
    assert result.indexed == 1
    assert result.excluded == 3
    docs = _vault_documents(db_session, result.source_id)
    assert [doc.external_id for doc in docs] == ["10 Research/keeper.md"]


def test_index_vault_missing_root_aborts_before_creating_source(
    db_session, fake_embedder, tmp_path
):
    existing_sources = db_session.scalars(
        select(Source).where(Source.name == VAULT_SOURCE_NAME)
    ).all()
    existing_ids = {source.id for source in existing_sources}
    missing_path = str(tmp_path / "missing")
    settings = Settings(
        _env_file=None,
        llm_provider="fake",
        vault_path=missing_path,
    )

    with pytest.raises(FileNotFoundError, match="vault root does not exist"):
        index_vault(db_session, fake_embedder, settings)

    sources = db_session.scalars(select(Source).where(Source.name == VAULT_SOURCE_NAME)).all()
    assert {source.id for source in sources} == existing_ids
    assert all(source.uri != missing_path for source in sources)


def test_index_vault_selects_paths_and_removes_stale(db_session, fake_embedder, tmp_path):
    note_dir = tmp_path / "10 Research"
    note_dir.mkdir()
    alpha = note_dir / "alpha.md"
    beta = note_dir / "beta.md"
    alpha.write_text("# Alpha\n\nLocal-first vault search uses pgvector.", encoding="utf-8")
    beta.write_text("# Beta\n\nStale derived rows should be removed.", encoding="utf-8")
    settings = Settings(_env_file=None, llm_provider="fake", vault_path=str(tmp_path))

    selected = index_vault(db_session, fake_embedder, settings, paths=["10 Research/alpha.md"])

    assert selected.requested == 1
    assert selected.indexed == 1
    hits, _ = hybrid_search(
        db_session,
        fake_embedder,
        settings,
        "local-first pgvector",
        top_k=3,
        source_ids=[selected.source_id],
    )
    assert hits

    full = index_vault(db_session, fake_embedder, settings)
    assert full.requested == 2
    assert full.indexed == 1
    assert full.skipped == 1

    beta.unlink()
    cleaned = index_vault(db_session, fake_embedder, settings)
    assert cleaned.removed_stale == 1


def test_index_vault_empty_eligible_set_does_not_remove_existing_docs(
    db_session, fake_embedder, tmp_path
):
    note_dir = tmp_path / "10 Research"
    note_dir.mkdir()
    note = note_dir / "keeper.md"
    note.write_text("# Keeper\n\nSearchable note.", encoding="utf-8")
    settings = Settings(_env_file=None, llm_provider="fake", vault_path=str(tmp_path))
    first = index_vault(db_session, fake_embedder, settings)
    note.unlink()

    with pytest.raises(RuntimeError, match="zero eligible Markdown notes"):
        index_vault(db_session, fake_embedder, settings)

    docs = _vault_documents(db_session, first.source_id)
    assert [doc.external_id for doc in docs] == ["10 Research/keeper.md"]


def test_index_vault_replaces_changed_note_and_removes_deleted_note(
    db_session, fake_embedder, tmp_path
):
    note_dir = tmp_path / "10 Research"
    note_dir.mkdir()
    changing = note_dir / "changing.md"
    deleted = note_dir / "deleted.md"
    changing.write_text(
        """---
title: "Original Title"
tags: [old]
kind: research
---
# Original Title

Original retrieval phrase.
""",
        encoding="utf-8",
    )
    deleted.write_text("# Deleted\n\nTemporary stale content.", encoding="utf-8")
    settings = Settings(_env_file=None, llm_provider="fake", vault_path=str(tmp_path))

    first = index_vault(db_session, fake_embedder, settings)
    original_docs = _vault_documents(db_session, first.source_id)
    assert len(original_docs) == 2
    original_changed = next(d for d in original_docs if d.external_id == "10 Research/changing.md")
    original_id = original_changed.id
    original_hash = original_changed.content_hash

    changing.write_text(
        """---
title: "Updated Title"
tags: [new, research]
kind: decision
---
# Updated Title

Updated vault retrieval phrase.
""",
        encoding="utf-8",
    )
    deleted.unlink()

    second = index_vault(db_session, fake_embedder, settings)

    assert second.indexed == 1
    assert second.removed_stale == 1
    docs = _vault_documents(db_session, first.source_id)
    assert len(docs) == 1
    updated = docs[0]
    assert updated.id != original_id
    assert updated.external_id == "10 Research/changing.md"
    assert updated.title == "Updated Title"
    assert updated.content_hash != original_hash
    assert updated.metadata_["content_hash"] == updated.content_hash
    assert updated.metadata_["vault_path"] == "10 Research/changing.md"
    assert updated.metadata_["title"] == "Updated Title"
    assert updated.metadata_["tags"] == ["new", "research"]
    assert updated.metadata_["frontmatter"] == {
        "title": "Updated Title",
        "tags": ["new", "research"],
        "kind": "decision",
    }
    assert updated.metadata_["kind"] == "decision"
    assert sorted(t.name for t in updated.tags) == ["new", "research"]

    hits, _ = hybrid_search(
        db_session,
        fake_embedder,
        settings,
        "updated vault retrieval phrase",
        top_k=3,
        source_ids=[first.source_id],
    )
    assert hits
