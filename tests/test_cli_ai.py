import json
from pathlib import Path

from click.testing import CliRunner

from cleanup_downloads import legacy_arguments
from file_cleaner.ai import analyze, metadata_payload
from file_cleaner.cli import main
from file_cleaner.quarantine import FileExecutor, RunStore


def snapshot(root: Path):
    return {
        str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def test_scan_is_read_only_and_does_not_touch_ai(tmp_path, aged_file, monkeypatch):
    aged_file(tmp_path / "archive.zip", b"archive" * 200, 40)
    before = snapshot(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("AI/network boundary was crossed")

    monkeypatch.setattr("file_cleaner.cli.analyze", forbidden)
    result = CliRunner().invoke(main, ["scan", str(tmp_path), "--details"])

    assert result.exit_code == 0, result.output
    assert snapshot(tmp_path) == before
    assert "Quarantine" in result.output


def test_invalid_scan_root_returns_nonzero_exit_code():
    result = CliRunner().invoke(main, ["scan", str(Path.home())])
    assert result.exit_code != 0
    assert "Refusing to scan" in result.output


def test_clean_defaults_to_no_actions(tmp_path, aged_file):
    source = aged_file(tmp_path / "archive.zip", b"archive" * 200, 40)
    result = CliRunner().invoke(main, ["clean", str(tmp_path)], input="n\n")
    assert result.exit_code == 0, result.output
    assert source.exists()
    assert "Nothing changed" in result.output


def test_guided_clean_reports_actual_move_and_undoes_it(tmp_path, aged_file, monkeypatch):
    source_root = tmp_path / "source"
    source = aged_file(source_root / "archive.zip", b"archive" * 200, 40)
    executor = FileExecutor(RunStore(tmp_path / "state"))
    monkeypatch.setattr("file_cleaner.cli.FileExecutor", lambda *args, **kwargs: executor)

    clean_result = CliRunner().invoke(main, ["clean", str(source_root)], input="y\ny\n")

    assert clean_result.exit_code == 0, clean_result.output
    assert "Succeeded" in clean_result.output
    assert not source.exists()
    run_id = executor.store.list_runs()[0]["run_id"]

    undo_result = CliRunner().invoke(main, ["undo", run_id])

    assert undo_result.exit_code == 0, undo_result.output
    assert "Restored" in undo_result.output
    assert source.exists()


def test_ai_payload_contains_metadata_but_not_contents(tmp_path, aged_file):
    content = b"TOP SECRET CONTENT"
    aged_file(tmp_path / "mystery.bin", content, 40)
    from file_cleaner.policy import categorize
    from file_cleaner.scanner import scan_folder

    payload = metadata_payload(categorize(scan_folder(tmp_path)))
    encoded = json.dumps(payload).encode()
    assert b"mystery.bin" in encoded
    assert content not in encoded


def test_ai_requires_per_run_consent_before_credential_or_network(tmp_path, aged_file, monkeypatch):
    aged_file(tmp_path / "mystery.bin", b"unknown" * 200, 40)

    def forbidden(*args, **kwargs):
        raise AssertionError("credential or network boundary crossed before consent")

    monkeypatch.setattr("file_cleaner.cli.get_api_key", forbidden)
    monkeypatch.setattr("file_cleaner.cli.analyze", forbidden)
    result = CliRunner().invoke(main, ["scan", str(tmp_path), "--ai"], input="n\n")

    assert result.exit_code != 0
    assert "Allow these network requests" in result.output


def test_ai_is_advisory_and_cannot_change_recommendation(tmp_path, aged_file):
    aged_file(tmp_path / "mystery.bin", b"unknown" * 200, 40)
    from file_cleaner.policy import categorize
    from file_cleaner.scanner import scan_folder

    files = categorize(scan_folder(tmp_path))

    class FakeCompletions:
        def create(self, **kwargs):
            class Message:
                content = '{"notes":[{"id":0,"note":"Put this in Miscellaneous."}]}'

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeClient:
        def __init__(self, **kwargs):
            class Chat:
                completions = FakeCompletions()

            self.chat = Chat()

    before = files[0].recommendation
    analyze(files, "unused-test-key", client_factory=FakeClient)
    assert files[0].recommendation == before == "keep"
    assert files[0].ai_note == "Put this in Miscellaneous."


def test_archive_review_is_inventory_only(tmp_path, aged_file):
    archive = aged_file(tmp_path / "_Archive" / "old.zip", b"archive", 400)
    before = snapshot(tmp_path)
    result = CliRunner().invoke(main, ["archive-review", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "read-only" in result.output
    assert "unknown" in result.output
    assert archive.exists()
    assert snapshot(tmp_path) == before


def test_legacy_dry_run_maps_to_strict_local_scan():
    assert legacy_arguments(["--dry-run", "--path", "/tmp/example"]) == [
        "scan",
        "/tmp/example",
        "--details",
    ]
