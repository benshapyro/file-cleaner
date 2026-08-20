from __future__ import annotations

import os
import time
from collections import defaultdict
from pathlib import Path

from .models import FileSnapshot
from .safety import SKIPPED_DIRECTORY_NAMES, is_hidden_relative, validate_scan_root


def scan_folder(
    path: Path, *, recursive: bool = False, now: float | None = None
) -> list[FileSnapshot]:
    root = validate_scan_root(path)
    observed_at = time.time() if now is None else now
    paths: list[Path] = []

    if recursive:
        for current, directories, filenames in os.walk(root, followlinks=False):
            current_path = Path(current)
            directories[:] = [
                name
                for name in directories
                if not name.startswith(".")
                and name not in SKIPPED_DIRECTORY_NAMES
                and not (current_path / name).is_symlink()
            ]
            for name in filenames:
                candidate = current_path / name
                if not name.startswith("."):
                    paths.append(candidate)
    else:
        paths = [candidate for candidate in root.iterdir() if not candidate.name.startswith(".")]

    snapshots: list[FileSnapshot] = []
    for candidate in sorted(paths, key=lambda item: str(item).casefold()):
        try:
            if (
                candidate.is_symlink()
                or not candidate.is_file()
                or is_hidden_relative(candidate, root)
            ):
                continue
            stat = candidate.stat()
        except OSError:
            continue
        snapshots.append(
            FileSnapshot(
                path=candidate.resolve(),
                root=root,
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
                mode=stat.st_mode,
                age_days=max(0, int((observed_at - stat.st_mtime) // 86400)),
                extension=candidate.suffix.casefold(),
            )
        )
    return snapshots


def same_size_groups(files: list[FileSnapshot], min_size: int = 1024) -> list[list[FileSnapshot]]:
    groups: dict[int, list[FileSnapshot]] = defaultdict(list)
    for item in files:
        if item.size >= min_size:
            groups[item.size].append(item)
    return [group for group in groups.values() if len(group) > 1]
