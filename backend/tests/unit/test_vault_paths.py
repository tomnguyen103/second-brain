from pathlib import Path

import pytest

from app.vault.paths import VaultPathError, resolve_vault_path, to_vault_relative


def test_resolve_vault_path_keeps_paths_inside_root(tmp_path):
    target = resolve_vault_path(tmp_path, "10 Research/note.md")
    assert target == (tmp_path / "10 Research" / "note.md").resolve(strict=False)
    assert to_vault_relative(tmp_path, target) == "10 Research/note.md"


@pytest.mark.parametrize("raw", ["../secret.md", "10 Research/../../secret.md", "/tmp/secret.md", "C:/secret.md"])
def test_resolve_vault_path_rejects_escape_attempts(tmp_path, raw):
    with pytest.raises(VaultPathError):
        resolve_vault_path(tmp_path, raw)


def test_resolve_vault_path_rejects_symlink_escape(tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable on this platform")
    with pytest.raises(VaultPathError):
        resolve_vault_path(tmp_path, "link/secret.md")
