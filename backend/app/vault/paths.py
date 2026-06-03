"""Safe path handling for the local Obsidian vault."""
from __future__ import annotations

from pathlib import Path, PureWindowsPath


class VaultPathError(ValueError):
    """Raised when a requested vault path is unsafe or outside the vault root."""


def vault_root(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def resolve_vault_path(root_path: str | Path, relative_path: str | Path) -> Path:
    """Resolve a vault-relative path and ensure it stays inside the vault root."""
    root = vault_root(root_path)
    normalized = str(relative_path).replace("\\", "/")
    requested = Path(normalized)
    windows_requested = PureWindowsPath(normalized)
    if (
        requested.is_absolute()
        or windows_requested.is_absolute()
        or windows_requested.drive
        or normalized.startswith("//")
        or normalized.startswith("../")
        or "/../" in normalized
        or normalized == ".."
    ):
        raise VaultPathError("vault paths must be relative")

    target = (root / normalized).resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise VaultPathError("path escapes the configured vault root") from exc
    return target


def to_vault_relative(root_path: str | Path, path: str | Path) -> str:
    root = vault_root(root_path)
    target = Path(path).resolve(strict=False)
    try:
        return target.relative_to(root).as_posix()
    except ValueError as exc:
        raise VaultPathError("path escapes the configured vault root") from exc
