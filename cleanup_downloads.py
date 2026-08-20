#!/usr/bin/env python3
"""Compatibility entry point for the former single-file cleaner."""

from __future__ import annotations

import argparse
import sys

from file_cleaner.cli import main


def legacy_arguments(argv: list[str]) -> list[str]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--path")
    parser.add_argument(
        "--mode", choices=["clean", "organize", "both", "review-archive"], default="both"
    )
    known, extra = parser.parse_known_args(argv)
    if extra or "--help" in argv or "-h" in argv:
        return argv
    path = [known.path] if known.path else []
    if known.dry_run:
        return ["scan", *path, "--details"]
    if known.mode == "review-archive":
        return ["archive-review", *path]
    only = "quarantine" if known.mode == "clean" else known.mode
    return ["clean", *path, "--only", only]


if __name__ == "__main__":
    print(
        "Note: cleanup_downloads.py is deprecated; use the file-cleaner command.", file=sys.stderr
    )
    main(args=legacy_arguments(sys.argv[1:]))
