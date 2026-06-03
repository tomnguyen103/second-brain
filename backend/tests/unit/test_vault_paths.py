from pathlib import Path

import pytest

from app.config import Settings
from app.vault.indexer import _selected_markdown_files
from app.vault.paths import VaultPathError, resolve_vault_path


def test_resolve_vault_path_rejects_absolute(tmp_path):
    with pytest.raises(VaultPathError):
        resolve_vault_path(str(tmp_path), str(Path("C:/outside.md")))


def test_resolve_vault_path_rejects_traversal(tmp_path):
    with pytest.raises(VaultPathError):
        resolve_vault_path(str(tmp_path), "../outside.md")


def test_resolve_vault_path_allows_nested_note(tmp_path):
    path = resolve_vault_path(str(tmp_path), "10 Research/note.md")
    assert path == (tmp_path / "10 Research" / "note.md").resolve()


def test_selected_markdown_files_rejects_invalid_requests(tmp_path):
    settings = Settings(_env_file=None, vault_path=str(tmp_path))
    (tmp_path / "10 Research").mkdir()
    (tmp_path / "10 Research" / "note.txt").write_text("not markdown", encoding="utf-8")

    with pytest.raises(VaultPathError):
        _selected_markdown_files(settings, ["../outside.md"])
    with pytest.raises(ValueError):
        _selected_markdown_files(settings, ["10 Research/note.txt"])
    with pytest.raises(FileNotFoundError):
        _selected_markdown_files(settings, ["10 Research/missing.md"])


def test_selected_markdown_files_uses_default_excluded_folders(tmp_path):
    for folder in ["10 Research", "Templates", ".obsidian", "90 Archive"]:
        (tmp_path / folder).mkdir()
    (tmp_path / "10 Research" / "keep.md").write_text("# Keep", encoding="utf-8")
    (tmp_path / "Templates" / "template.md").write_text("# Template", encoding="utf-8")
    (tmp_path / ".obsidian" / "config.md").write_text("# Config", encoding="utf-8")
    (tmp_path / "90 Archive" / "old.md").write_text("# Old", encoding="utf-8")
    settings = Settings(_env_file=None, vault_path=str(tmp_path))

    selected = _selected_markdown_files(settings, None)
    relative = [path.relative_to(tmp_path).as_posix() for path in selected]

    assert relative == ["10 Research/keep.md"]
    with pytest.raises(ValueError, match="excluded from indexing"):
        _selected_markdown_files(settings, ["Templates/template.md"])


def test_selected_markdown_files_respects_include_dirs(tmp_path):
    for folder in ["00 Inbox", "10 Research"]:
        (tmp_path / folder).mkdir()
    (tmp_path / "00 Inbox" / "quick.md").write_text("# Quick", encoding="utf-8")
    (tmp_path / "10 Research" / "deep.md").write_text("# Deep", encoding="utf-8")
    settings = Settings(
        _env_file=None,
        vault_path=str(tmp_path),
        vault_index_include_dirs=["10 Research"],
        vault_index_exclude_dirs=[],
    )

    selected = _selected_markdown_files(settings, None)

    assert [path.relative_to(tmp_path).as_posix() for path in selected] == [
        "10 Research/deep.md"
    ]
    with pytest.raises(ValueError, match="excluded from indexing"):
        _selected_markdown_files(settings, ["00 Inbox/quick.md"])
