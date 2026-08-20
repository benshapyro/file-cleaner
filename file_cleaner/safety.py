from __future__ import annotations

import hashlib
import os
from pathlib import Path

SKIPPED_DIRECTORY_NAMES = {"_Organized", "_Archive", ".file-cleaner"}


class SafetyError(ValueError):
    """Raised when a requested path crosses a safety boundary."""


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def validate_scan_root(path: Path) -> Path:
    root = path.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise SafetyError(f"Not a folder: {root}")

    home = Path.home().resolve()
    forbidden = {Path("/"), home, Path("/System"), Path("/Library"), Path("/Applications")}
    if root in forbidden:
        raise SafetyError(
            f"Refusing to scan broad or system folder: {root}. Choose a narrower folder."
        )
    return root


def is_hidden_relative(path: Path, root: Path) -> bool:
    return any(part.startswith(".") for part in path.relative_to(root).parts)


def confined_path(base: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise SafetyError(f"Unsafe relative path: {relative}")
    base_resolved = base.resolve()
    candidate = (base_resolved / relative).resolve(strict=False)
    if candidate != base_resolved and base_resolved not in candidate.parents:
        raise SafetyError(f"Path escapes holding folder: {relative}")
    return candidate


def private_directory(path: Path) -> None:
    if path.is_symlink():
        raise SafetyError(f"Private state path may not be a symlink: {path}")
    if path.exists() and not path.is_dir():
        raise SafetyError(f"Private state path is not a directory: {path}")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)


def private_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise SafetyError(f"Private state record is not a regular file: {path}")
    os.chmod(path, 0o600)
