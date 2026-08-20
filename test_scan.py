#!/usr/bin/env python3
"""Compatibility local preview. Use ``file-cleaner scan`` for new workflows."""

from file_cleaner.cli import main

if __name__ == "__main__":
    main(args=["scan"])
