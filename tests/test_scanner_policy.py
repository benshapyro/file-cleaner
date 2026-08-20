import os
from pathlib import Path

import pytest

from file_cleaner.policy import categorize
from file_cleaner.safety import SafetyError, validate_scan_root
from file_cleaner.scanner import scan_folder


def classify(root: Path, *, recursive: bool = False):
    return {item.path.name: item for item in categorize(scan_folder(root, recursive=recursive))}


def test_scan_is_shallow_and_skips_hidden_and_symlinks(tmp_path, aged_file):
    aged_file(tmp_path / "top.zip")
    aged_file(tmp_path / ".hidden.zip")
    aged_file(tmp_path / "nested" / "inside.zip")
    aged_file(tmp_path / "_Organized" / "already.pdf")
    os.symlink(tmp_path / "top.zip", tmp_path / "link.zip")

    shallow = scan_folder(tmp_path)
    recursive = scan_folder(tmp_path, recursive=True)

    assert [item.path.name for item in shallow] == ["top.zip"]
    assert {item.path.name for item in recursive} == {"top.zip", "inside.zip"}


def test_refuses_home_and_files(tmp_path):
    with pytest.raises(SafetyError):
        validate_scan_root(Path.home())
    target = tmp_path / "file.txt"
    target.write_text("x")
    with pytest.raises(SafetyError):
        validate_scan_root(target)


def test_same_name_is_not_duplicate_without_matching_content(tmp_path, aged_file):
    aged_file(tmp_path / "proposal.pdf", b"first", 100)
    aged_file(tmp_path / "proposal (1).pdf", b"different", 100)

    result = classify(tmp_path)

    assert result["proposal.pdf"].category == "document"
    assert result["proposal (1).pdf"].category == "document"
    assert result["proposal.pdf"].similar_names == [result["proposal (1).pdf"].path]
    assert all(item.recommendation != "quarantine" for item in result.values())


def test_sha256_duplicate_keeps_newest_and_quarantines_older(tmp_path, aged_file):
    content = b"same exact contents" * 100
    aged_file(tmp_path / "older.bin", content, 20)
    aged_file(tmp_path / "newer.bin", content, 10)

    result = classify(tmp_path)

    assert result["newer.bin"].recommendation == "keep"
    assert result["older.bin"].recommendation == "quarantine"
    assert result["older.bin"].exact_duplicate_of == result["newer.bin"].path
    assert len(result["older.bin"].sha256) == 64


@pytest.mark.parametrize(
    ("name", "days", "expected"),
    [
        ("installer.dmg", 13, "keep"),
        ("installer.dmg", 14, "quarantine"),
        ("archive.zip", 29, "keep"),
        ("archive.zip", 30, "quarantine"),
        ("partial.crdownload", 6, "keep"),
        ("partial.crdownload", 7, "quarantine"),
        ("movie.mp4", 59, "keep"),
        ("movie.mp4", 60, "review"),
        ("budget.xlsx", 100, "organize"),
        ("mystery.bin", 500, "keep"),
    ],
)
def test_conservative_age_policy(tmp_path, aged_file, name, days, expected):
    aged_file(tmp_path / name, name.encode() * 200, days)
    assert classify(tmp_path)[name].recommendation == expected


def test_protected_name_and_type_never_suggest_removal(tmp_path, aged_file):
    aged_file(tmp_path / "client-contract.zip", b"contract" * 200, 300)
    aged_file(tmp_path / "secret.pem", b"secret" * 200, 300)
    result = classify(tmp_path)
    assert {item.recommendation for item in result.values()} == {"keep"}
    assert {item.category for item in result.values()} == {"protected"}
