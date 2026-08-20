"""Compatibility helpers for exact and similar-name comparisons."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from file_cleaner.safety import sha256_file


def calculate_file_hash(
    file_path: Path, algorithm: str = "sha256", chunk_size: int = 1024 * 1024
) -> str:
    if algorithm != "sha256":
        raise ValueError("Only SHA-256 is supported by the safety model.")
    return sha256_file(file_path, chunk_size)


def find_duplicates_by_hash(file_paths: list[Path], min_size: int = 1024) -> dict[str, list[Path]]:
    sizes: dict[int, list[Path]] = defaultdict(list)
    for path in file_paths:
        try:
            if path.is_file() and not path.is_symlink() and path.stat().st_size >= min_size:
                sizes[path.stat().st_size].append(path)
        except OSError:
            continue
    hashes: dict[str, list[Path]] = defaultdict(list)
    for paths in sizes.values():
        if len(paths) > 1:
            for path in paths:
                try:
                    hashes[sha256_file(path)].append(path)
                except OSError:
                    continue
    return {digest: paths for digest, paths in hashes.items() if len(paths) > 1}


def find_duplicates_by_name_pattern(file_paths: list[Path]) -> dict[str, list[Path]]:
    """Return similar names for comparison; this does not establish duplication."""
    groups: dict[str, list[Path]] = defaultdict(list)
    for path in file_paths:
        stem = re.sub(r"(?: \(\d+\)| - copy| copy|_\d+)$", "", path.stem, flags=re.I)
        groups[f"{stem}{path.suffix}".casefold()].append(path)
    return {name: paths for name, paths in groups.items() if len(paths) > 1}
