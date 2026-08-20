from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from .models import FileSnapshot
from .safety import sha256_file
from .scanner import same_size_groups

CRITICAL_EXTENSIONS = {
    ".key",
    ".pem",
    ".p12",
    ".pfx",
    ".env",
    ".gpg",
    ".license",
    ".lic",
    ".keychain",
    ".keystore",
    ".sqlite",
    ".db",
    ".wallet",
    ".dat",
}
PROTECTED_PATTERNS = {
    "important",
    "backup",
    "credentials",
    "password",
    "license",
    "certificate",
    "work",
    "project",
    "invoice",
    "receipt",
    "tax",
    "contract",
}
DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".pages",
    ".numbers",
    ".keynote",
    ".txt",
    ".md",
    ".rtf",
    ".csv",
    ".json",
    ".xml",
    ".sql",
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".go",
    ".rs",
    ".c",
    ".cpp",
}
INSTALLER_EXTENSIONS = {".dmg", ".pkg", ".exe", ".msi", ".deb", ".rpm"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"}
TEMP_EXTENSIONS = {".tmp", ".temp", ".part", ".download", ".crdownload"}
MEDIA_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".bmp",
    ".webp",
    ".heic",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".wmv",
    ".flv",
    ".mp3",
    ".wav",
    ".flac",
    ".aac",
    ".m4a",
}

ORGANIZATION_GROUPS = {
    "Documents": DOCUMENT_EXTENSIONS,
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".svg", ".bmp", ".webp", ".heic"},
    "Videos": {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv"},
    "Audio": {".mp3", ".wav", ".flac", ".aac", ".m4a"},
    "Archives": ARCHIVE_EXTENSIONS,
    "Installers": INSTALLER_EXTENSIONS,
}


def _similar_name_key(path: Path) -> str:
    stem = re.sub(r"(?: \(\d+\)| - copy| copy|_\d+)$", "", path.stem, flags=re.I)
    return f"{stem}{path.suffix}".casefold()


def _mark_similar_names(files: list[FileSnapshot]) -> None:
    groups: dict[str, list[FileSnapshot]] = defaultdict(list)
    for item in files:
        groups[_similar_name_key(item.path)].append(item)
    for group in groups.values():
        if len(group) > 1:
            for item in group:
                item.similar_names = [other.path for other in group if other is not item]


def _mark_exact_duplicates(files: list[FileSnapshot]) -> None:
    for size_group in same_size_groups(files):
        hash_groups: dict[str, list[FileSnapshot]] = defaultdict(list)
        for item in size_group:
            try:
                item.sha256 = sha256_file(item.path)
            except OSError:
                continue
            hash_groups[item.sha256].append(item)

        for group in hash_groups.values():
            if len(group) < 2:
                continue
            keep = max(group, key=lambda item: (item.mtime_ns, -len(item.path.name)))
            for item in group:
                if item is keep:
                    item.category = "exact_duplicate_original"
                    item.recommendation = "keep"
                    item.reason = "Newest copy in an exact SHA-256 content match."
                elif item.age_days >= 7:
                    item.category = "exact_duplicate"
                    item.recommendation = "quarantine"
                    item.reason = f"Exact SHA-256 match; keep {keep.path.name}."
                    item.exact_duplicate_of = keep.path
                else:
                    item.category = "exact_duplicate_too_new"
                    item.recommendation = "keep"
                    item.reason = "Exact match, but this copy is less than seven days old."
                    item.exact_duplicate_of = keep.path


def organization_group(extension: str) -> str:
    for group, extensions in ORGANIZATION_GROUPS.items():
        if extension in extensions:
            return group
    return "Other"


def categorize(files: list[FileSnapshot]) -> list[FileSnapshot]:
    _mark_similar_names(files)
    _mark_exact_duplicates(files)

    for item in files:
        if item.category.startswith("exact_duplicate"):
            continue
        lower_name = item.path.name.casefold()
        if item.extension in CRITICAL_EXTENSIONS or any(
            word in lower_name for word in PROTECTED_PATTERNS
        ):
            item.category = "protected"
            item.recommendation = "keep"
            item.reason = "Protected type or filename; never suggested for removal."
        elif item.extension in DOCUMENT_EXTENSIONS:
            item.category = "document"
            item.recommendation = "organize" if item.age_days >= 60 else "keep"
            item.reason = (
                "Document is at least 60 days old; organize or archive only."
                if item.age_days >= 60
                else "Document is kept; age alone never permits removal."
            )
        elif item.extension in INSTALLER_EXTENSIONS:
            item.category = "installer"
            item.recommendation = "quarantine" if item.age_days >= 14 else "keep"
            item.reason = f"Installer is {item.age_days} days old; threshold is 14 days."
        elif item.extension in ARCHIVE_EXTENSIONS:
            item.category = "archive"
            item.recommendation = "quarantine" if item.age_days >= 30 else "keep"
            item.reason = f"Archive is {item.age_days} days old; threshold is 30 days."
        elif item.extension in TEMP_EXTENSIONS:
            item.category = "temporary"
            item.recommendation = "quarantine" if item.age_days >= 7 else "keep"
            item.reason = f"Temporary download is {item.age_days} days old; threshold is 7 days."
        elif item.extension in MEDIA_EXTENSIONS:
            item.category = "media"
            item.recommendation = "review" if item.age_days >= 60 else "keep"
            item.reason = (
                "Media is at least 60 days old; review manually."
                if item.age_days >= 60
                else "Recent media is kept."
            )
        else:
            item.category = "unknown"
            item.recommendation = "keep"
            item.reason = "Unknown files are kept by default."
        if item.similar_names and item.category != "exact_duplicate":
            item.reason += " A similar filename exists, but content has not been assumed identical."
    return files
