# Repository guidance

File Cleaner is a guided, reversible macOS cleanup tool. Read `README.md` and `implementation.md` before changing behavior.

## Development commands

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest
uv run file-cleaner doctor
uv run file-cleaner scan /path/to/test-folder --details
```

Use temporary fixtures for actions. Do not run `clean`, `undo`, or `quarantine purge` against a real personal folder during development.

## Architecture

- `file_cleaner/scanner.py`: bounded file discovery; shallow by default, no symlink following.
- `file_cleaner/policy.py`: deterministic protections, age rules, similar-name comparison, and SHA-256 duplicate evidence.
- `file_cleaner/ai.py`: optional advisory notes; never changes an action recommendation.
- `file_cleaner/quarantine.py`: action revalidation, private records, quarantine, organization, restore, and confirmed purge.
- `file_cleaner/cli.py`: guided commands and confirmation boundaries.
- `cleanup_downloads.py`: one-release compatibility wrapper; do not add new behavior here.

## Safety invariants

1. A default scan performs no writes and no network requests.
2. AI requires `--ai` and a per-run consent prompt. Never send file contents.
3. Similar filenames are not duplicates. Only matching SHA-256 content establishes duplication.
4. Deterministic policy authorizes actions; callers and AI cannot bypass it.
5. Revalidate every selected file immediately before moving it.
6. Removal means quarantine. Only an eligible, explicitly confirmed purge permanently deletes.
7. Restore never overwrites an occupied original path.
8. Manifest paths must remain confined to their declared root, and private state must not use symlinks.
9. Run records report actual success, skip, failure, restore, and purge outcomes.
10. Tests must use temporary folders and mocked AI; a failing dependency, network request, or safety check must return a nonzero exit code.

When changing a safety boundary, first demonstrate that its targeted test fails when the boundary is removed, then restore the boundary and run the full suite.
