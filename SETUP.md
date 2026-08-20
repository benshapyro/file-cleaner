# Setup

## Recommended: double-click installation

1. Open the `scripts` folder.
2. Double-click `install.command`.
3. The installer uses `uv` to create an isolated tool environment.
4. Choose whether to place `File Cleaner.command` in your personal Applications folder.
5. Start with the read-only command printed by the installer.

The installer does not edit `.zshrc`, change your PATH, or inspect Downloads.

## Developer setup

```bash
uv sync --extra dev
uv run pytest
uv run file-cleaner doctor
```

Dependencies are locked in `uv.lock`. Python 3.11–3.14 is supported.

## Optional AI setup

Run `file-cleaner configure-ai`. The key is stored in macOS Keychain and is only used after `--ai` plus a per-run confirmation.

Do not paste credentials into source code. Legacy `.env` support is temporary and requires permissions of `600`.
