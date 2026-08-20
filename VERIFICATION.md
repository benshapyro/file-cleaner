# Verification record

Date: 2026-08-20  
Implementation commit: `2f8fd45`  
Base commit: `061bc82`  
Branch: `feat/safe-guided-cleaner`

## Automated checks

- `uv lock --check`: passed.
- `ruff check .`: passed with no findings.
- Python 3.14.6: 37 tests passed.
- Python 3.11.15 in an isolated environment: 37 tests passed.
- Python bytecode compilation: passed.
- Both `.command` scripts passed `zsh -n` syntax checks.
- Source distribution and wheel built successfully.
- The wheel installed into a disposable Python 3.11 environment; `file-cleaner --version` returned `1.0.0` with exit code 0.
- `file-cleaner doctor` passed and deliberately skipped network access.

The tests use temporary folders and mocked AI responses. They cover local scans, conservative policy, SHA-256 duplicates, similar-name files, changed-file revalidation, deterministic-policy bypass attempts, state and manifest path confinement, symlink rejection, actual failure records, quarantine, organize, restore, purge eligibility, CLI confirmation, AI consent, credential permissions, legacy dry-run mapping, and a complete guided cleanup plus undo.

## Mutation sensitivity

A disposable copy was changed to disable both checks in `confined_path()`. The manifest traversal test then failed with raw exit code 1 because the expected `SafetyError` was absent. The unmodified targeted test passed, followed by the full passing suite.

This demonstrates that the traversal test observes the operative path-confinement mechanism rather than merely passing beside it.

## Live Downloads read-only check

The final scan used the current `/Users/bshap/Downloads` folder with socket connection methods replaced by a function that raises if called. Only aggregate results were printed.

- Files scanned: 4,228.
- Bytes represented: 17,559,387,433.
- Recommendations: 1,179 keep; 2,083 organize; 431 review; 535 quarantine.
- Exact-duplicate members found by the product policy: 717.
- Exact-duplicate members found by a separate SHA-256 implementation: 717.
- The two duplicate member sets matched exactly.
- Top-level names, modes, sizes, modification times, and symlink states were unchanged before versus after.
- Observed network calls: zero.

No real Downloads file was organized, quarantined, restored, purged, or otherwise changed.

## Local security change

The existing ignored project `.env` file was not read or displayed. Its permissions were tightened from `644` to owner-only `600` and verified as `-rw-------`.

## Deliberate limits

- Real AI inference was not called; the boundary is tested with mocks, and live use remains an explicit, potentially spend-bearing action.
- Recommendation groups are selected as groups. Individual-file selection is documented as future work.
- The installer and launcher were built and syntax-checked but not installed into the user account, because that location choice remains an explicit installer prompt.
- No scheduled or unattended cleanup exists.
