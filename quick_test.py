#!/usr/bin/env python3
"""Compatibility setup check. Makes no network requests and reveals no secrets."""

from file_cleaner.cli import main

if __name__ == "__main__":
    main(args=["doctor"])
