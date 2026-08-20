from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

KEYCHAIN_SERVICE = "file-cleaner-openai"
KEYCHAIN_ACCOUNT = "OPENAI_API_KEY"


class CredentialError(RuntimeError):
    pass


def _legacy_env_key(path: Path) -> str | None:
    if not path.exists():
        return None
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise CredentialError(
            f"Legacy credential file {path} is too broadly readable. Run: chmod 600 {path}"
        )
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == "OPENAI_API_KEY":
            return value.strip().strip("\"'") or None
    return None


def get_api_key(*, legacy_env: Path | None = None) -> tuple[str | None, str | None]:
    if value := os.getenv("OPENAI_API_KEY"):
        return value, "environment"
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                KEYCHAIN_SERVICE,
                "-a",
                KEYCHAIN_ACCOUNT,
                "-w",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip(), "macOS Keychain"
    except OSError:
        pass
    path = legacy_env or (Path.cwd() / ".env")
    if value := _legacy_env_key(path):
        return value, f"legacy file {path}"
    return None, None


def store_api_key(value: str) -> None:
    if not value.strip():
        raise CredentialError("API key cannot be empty.")
    try:
        result = subprocess.run(
            [
                "security",
                "add-generic-password",
                "-U",
                "-s",
                KEYCHAIN_SERVICE,
                "-a",
                KEYCHAIN_ACCOUNT,
                "-w",
                value.strip(),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise CredentialError(f"macOS Keychain is unavailable: {error}") from error
    if result.returncode != 0:
        raise CredentialError("macOS Keychain refused the credential update.")
