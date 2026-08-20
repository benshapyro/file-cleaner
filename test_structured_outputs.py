#!/usr/bin/env python3
"""Compatibility test entry point; all AI behavior is mocked in the real suite."""

import subprocess
import sys

if __name__ == "__main__":
    raise SystemExit(
        subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_cli_ai.py"], check=False
        ).returncode
    )
