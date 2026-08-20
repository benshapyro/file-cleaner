# Current architecture

The former single-file prototype is retained only as a compatibility wrapper. Current behavior lives in the `file_cleaner` package:

- `scanner.py` enumerates a bounded folder without following symlinks.
- `policy.py` creates deterministic recommendations and SHA-256 duplicate evidence.
- `ai.py` adds optional advisory notes without changing local authority.
- `quarantine.py` revalidates actions, moves files, writes private run records, restores runs, and performs confirmed expiry purges.
- `cli.py` provides the guided interface.

The public command is installed from `pyproject.toml`; exact dependency resolution is recorded in `uv.lock`.

## Trust boundaries

1. A scan may observe but not change files.
2. AI is a per-run network permission and may only add text notes.
3. Deterministic policy decides which actions are permitted.
4. The executor revalidates the policy recommendation, path, type, size, time, and available hash evidence.
5. Removal means quarantine, not deletion.
6. Restoration refuses collisions.
7. Permanent purge requires age eligibility and explicit confirmation.

Tests construct failures at these boundaries before checking normal behavior.
