import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from file_cleaner.models import PlannedAction
from file_cleaner.policy import categorize, organization_group
from file_cleaner.quarantine import FileExecutor, RunStore
from file_cleaner.safety import SafetyError
from file_cleaner.scanner import scan_folder


def item_for(root: Path, name: str):
    return next(item for item in categorize(scan_folder(root)) if item.path.name == name)


def test_quarantine_records_actual_move_and_restores(tmp_path, aged_file):
    source_root = tmp_path / "source"
    state_root = tmp_path / "state"
    aged_file(source_root / "old.zip", b"archive" * 200, 40)
    item = item_for(source_root, "old.zip")
    executor = FileExecutor(RunStore(state_root))

    run_id, results = executor.execute([PlannedAction(item, "quarantine")])

    assert results[0].status == "succeeded"
    assert not item.path.exists()
    manifest = executor.store.load(run_id)
    entry = manifest["entries"][0]
    held = executor.store.resolve_entry(manifest, entry)[1]
    assert held.read_bytes() == b"archive" * 200
    assert entry["status"] == "succeeded"
    assert entry["recorded_at"]
    assert entry["completed_at"]
    assert stat.S_IMODE(executor.store.manifest_path(run_id).stat().st_mode) == 0o600
    assert stat.S_IMODE(state_root.stat().st_mode) == 0o700

    restored = executor.restore(run_id)
    assert restored[0].status == "restored"
    assert item.path.read_bytes() == b"archive" * 200
    restored_entry = executor.store.load(run_id)["entries"][0]
    assert restored_entry["last_restore_status"] == "restored"
    assert restored_entry["last_restore_at"]


def test_changed_file_is_skipped_immediately_before_action(tmp_path, aged_file):
    source_root = tmp_path / "source"
    aged_file(source_root / "old.zip", b"before" * 200, 40)
    item = item_for(source_root, "old.zip")
    item.path.write_bytes(b"changed")

    executor = FileExecutor(RunStore(tmp_path / "state"))
    run_id, results = executor.execute([PlannedAction(item, "quarantine")])

    assert results[0].status == "skipped"
    assert "changed after preview" in results[0].reason
    assert item.path.exists()
    assert executor.store.load(run_id)["entries"][0]["status"] == "skipped"


def test_executor_refuses_policy_bypass_for_protected_file(tmp_path, aged_file):
    source_root = tmp_path / "source"
    aged_file(source_root / "client-contract.zip", b"protected" * 200, 400)
    item = item_for(source_root, "client-contract.zip")

    _, results = FileExecutor(RunStore(tmp_path / "state")).execute(
        [PlannedAction(item, "quarantine")]
    )

    assert results[0].status == "skipped"
    assert "does not authorize" in results[0].reason
    assert item.path.exists()


def test_duplicate_is_rehashed_against_kept_copy(tmp_path, aged_file):
    source_root = tmp_path / "source"
    content = b"same" * 400
    aged_file(source_root / "old.bin", content, 20)
    aged_file(source_root / "new.bin", content, 10)
    item = item_for(source_root, "old.bin")
    item.exact_duplicate_of.write_bytes(b"no longer the same")

    _, results = FileExecutor(RunStore(tmp_path / "state")).execute(
        [PlannedAction(item, "quarantine")]
    )

    assert results[0].status == "skipped"
    assert "selected to keep" in results[0].reason
    assert item.path.exists()


def test_organize_is_undoable_and_never_overwrites(tmp_path, aged_file):
    source_root = tmp_path / "source"
    aged_file(source_root / "report.pdf", b"report" * 200, 100)
    item = item_for(source_root, "report.pdf")
    executor = FileExecutor(RunStore(tmp_path / "state"))
    run_id, results = executor.execute(
        [PlannedAction(item, "organize", organization_group(item.extension))]
    )
    assert results[0].status == "succeeded"
    destination = Path(results[0].destination)
    assert destination.exists()
    item.path.write_text("new occupant")

    restored = executor.restore(run_id)

    assert restored[0].status == "skipped"
    assert item.path.read_text() == "new occupant"
    assert destination.exists()


def test_manifest_path_traversal_is_rejected(tmp_path, aged_file):
    source_root = tmp_path / "source"
    source_root.mkdir()
    store = RunStore(tmp_path / "state")
    manifest = store.create(source_root)
    manifest["entries"].append(
        {
            "action": "quarantine",
            "source_relative": "../outside.txt",
            "destination_base": "quarantine",
            "destination_relative": "files/item.txt",
            "size": 1,
            "status": "succeeded",
        }
    )
    store.save(manifest)

    with pytest.raises(SafetyError):
        store.load(manifest["run_id"])


def test_state_directory_symlink_is_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    state = tmp_path / "state"
    state.symlink_to(outside, target_is_directory=True)

    with pytest.raises(SafetyError):
        RunStore(state).initialize()


def test_restore_rejects_symlink_in_holding_area(tmp_path, aged_file):
    source_root = tmp_path / "source"
    aged_file(source_root / "old.zip", b"archive" * 200, 40)
    item = item_for(source_root, "old.zip")
    executor = FileExecutor(RunStore(tmp_path / "state"))
    run_id, _ = executor.execute([PlannedAction(item, "quarantine")])
    manifest = executor.store.load(run_id)
    _, held = executor.store.resolve_entry(manifest, manifest["entries"][0])
    held.unlink()
    held.symlink_to(tmp_path / "outside")

    with pytest.raises(SafetyError):
        executor.restore(run_id)
    assert not item.path.exists()


def test_purge_requires_confirmation_and_minimum_age(tmp_path, aged_file):
    source_root = tmp_path / "source"
    aged_file(source_root / "old.zip", b"archive" * 200, 40)
    item = item_for(source_root, "old.zip")
    executor = FileExecutor(RunStore(tmp_path / "state"))
    run_id, _ = executor.execute([PlannedAction(item, "quarantine")])

    with pytest.raises(SafetyError):
        executor.purge_expired(confirmed=False)
    assert executor.purge_expired(confirmed=True) == []

    manifest = executor.store.load(run_id)
    manifest["created_at"] = (datetime.now(UTC) - timedelta(days=31)).isoformat()
    executor.store.save(manifest)
    results = executor.purge_expired(confirmed=True)
    assert results[0].status == "purged"
    purged_manifest = executor.store.load(run_id)
    _, held = executor.store.resolve_entry(purged_manifest, purged_manifest["entries"][0])
    assert not held.exists()
    assert purged_manifest["entries"][0]["last_purge_status"] == "purged"


def test_move_failure_is_recorded_as_failure(tmp_path, aged_file, monkeypatch):
    source_root = tmp_path / "source"
    aged_file(source_root / "old.zip", b"archive" * 200, 40)
    item = item_for(source_root, "old.zip")
    executor = FileExecutor(RunStore(tmp_path / "state"))

    def fail_move(*args, **kwargs):
        raise OSError("constructed move failure")

    monkeypatch.setattr("file_cleaner.quarantine._move", fail_move)
    run_id, results = executor.execute([PlannedAction(item, "quarantine")])

    assert results[0].status == "failed"
    assert executor.store.load(run_id)["entries"][0]["status"] == "failed"
    assert item.path.exists()


def test_one_run_cannot_mix_scan_roots(tmp_path, aged_file):
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    aged_file(first_root / "old.zip", b"first" * 300, 40)
    aged_file(second_root / "old.zip", b"second" * 300, 40)
    actions = [
        PlannedAction(item_for(first_root, "old.zip"), "quarantine"),
        PlannedAction(item_for(second_root, "old.zip"), "quarantine"),
    ]
    with pytest.raises(SafetyError):
        FileExecutor(RunStore(tmp_path / "state")).execute(actions)
