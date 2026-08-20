# File Cleaner

File Cleaner is a guided macOS tool for reviewing clutter without giving a script unattended control of personal files.

Its default scan is local and read-only. Removal recommendations go into a recoverable quarantine, organization moves can be undone, and permanent deletion always requires a separate confirmation after at least 30 days.

## Install

Double-click [`scripts/install.command`](scripts/install.command). It installs an isolated `file-cleaner` command and asks before adding a launcher to `~/Applications`.

The installer does not edit your shell settings. Developers can instead run:

```bash
uv sync --extra dev
uv run file-cleaner --help
```

Python 3.11–3.14 and macOS are supported.

## Four everyday workflows

### 1. Preview Downloads without changing anything

```bash
file-cleaner scan ~/Downloads --details
```

This makes no network requests, creates no logs, and changes no files. Scans are shallow by default: nested folders are not entered.

### 2. Run guided cleanup

```bash
file-cleaner clean ~/Downloads
```

The tool shows every proposed action, asks which recommendation groups to select, asks again before applying them, and rechecks each file immediately before moving it. The default answer to every action prompt is **No**.

Use `--recursive` only when you deliberately want nested folders included. Symlinks, hidden folders, `_Organized`, and `_Archive` are not followed.

### 3. Undo a cleanup run

The completion message provides a run identifier:

```bash
file-cleaner undo 20260820T120000Z-example
```

File Cleaner restores organization and quarantine moves to their original paths. It never overwrites a file that now occupies an original path.

### 4. Review the quarantine

```bash
file-cleaner quarantine list
file-cleaner quarantine restore RUN_ID
file-cleaner quarantine purge --older-than 30
```

Purge shows the eligible count and size, then requires typing `PURGE`. Nothing is deleted automatically.

## What the recommendations mean

- **Quarantine:** A recoverable removal candidate, such as an old installer, old archive, stale partial download, or independently verified SHA-256 duplicate.
- **Organize:** A document that may be moved into `_Organized`; age alone never makes a document removable.
- **Review:** Old media worth looking at manually. The tool does not select it automatically.
- **Keep:** Protected, recent, ambiguous, or otherwise unauthorized for action.

Similar filenames are only flagged for comparison. `proposal.pdf` and `proposal (1).pdf` are not duplicates unless their SHA-256 content hashes match.

## Optional AI notes

AI is off by default. To configure it:

```bash
file-cleaner configure-ai
file-cleaner scan ~/Downloads --ai
```

The key is stored in macOS Keychain. Before each AI run, the tool states how many filenames and requests are involved and asks permission. It sends filenames, sizes, ages, and local categories—not file contents. AI can add organization notes but cannot change deterministic protections or authorize removal.

An existing `.env` credential is temporarily supported only when its permissions are `600`. The key is never printed or logged.

## Safety and records

- Quarantine: `~/.local/share/file-cleaner/quarantine/`
- Run records: `~/.local/share/file-cleaner/runs/`
- Private directory permissions: `700`
- Private record permissions: `600`

Run `file-cleaner doctor` for a local configuration check. It never tests an API connection or lists personal filenames.

The old `cleanup_downloads.py` flags remain available for one transition release. `--dry-run` now routes to the strictly local scan, and the old archive review is inventory-only.

## Development and verification

```bash
uv sync --extra dev
uv run pytest
```

The automated suite uses temporary folders and mocked AI responses. It never scans or changes the real Downloads folder.
