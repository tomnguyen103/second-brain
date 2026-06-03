"""Vault path safety helpers."""
from __future__ import annotations

from pathlib import Path, PureWindowsPath


class VaultPathError(ValueError):
    """Raised when a requested vault path is unsafe or outside the vault root."""


def vault_root(path: str) -> Path:
    root = Path(path).expanduser().resolve()
    return root


def resolve_vault_path(root_path: str, relative_path: str) -> Path:
    """Resolve a vault-relative path and ensure it stays inside the vault root."""
    root = vault_root(root_path)
    normalized = str(relative_path).replace("\\", "/")
    requested = Path(normalized)
    windows_requested = PureWindowsPath(relative_path)
    if requested.is_absolute() or windows_requested.is_absolute() or windows_requested.drive:
        raise VaultPathError("vault paths must be relative")
    target = (root / requested).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise VaultPathError("path escapes the configured vault root") from exc
    return target


def to_vault_relative(root_path: str, path: Path) -> str:
    root = vault_root(root_path)
    return path.resolve().relative_to(root).as_posix()
