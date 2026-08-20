from __future__ import annotations

import errno
import json
import os
import shutil
import stat
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import ActionResult, PlannedAction
from .policy import organization_group
from .safety import SafetyError, confined_path, private_directory, private_file, sha256_file

SCHEMA_VERSION = 1


def default_state_root() -> Path:
    return Path("~/.local/share/file-cleaner").expanduser()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _run_id(now: datetime | None = None) -> str:
    value = now or _utc_now()
    return f"{value.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _move(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(source, destination)
    except OSError as error:
        if error.errno != errno.EXDEV:
            raise
        shutil.move(str(source), str(destination))


class RunStore:
    def __init__(self, state_root: Path | None = None):
        self.state_root = (state_root or default_state_root()).expanduser().absolute()
        self.runs_root = self.state_root / "runs"
        self.quarantine_root = self.state_root / "quarantine"

    def _validate_layout(self) -> None:
        for path in (self.state_root, self.runs_root, self.quarantine_root):
            if path.is_symlink():
                raise SafetyError(f"Private state path may not be a symlink: {path}")

    def initialize(self) -> None:
        self._validate_layout()
        private_directory(self.state_root)
        private_directory(self.runs_root)
        private_directory(self.quarantine_root)

    def manifest_path(self, run_id: str) -> Path:
        if not run_id or any(
            char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            for char in run_id
        ):
            raise SafetyError("Invalid run identifier.")
        return confined_path(self.runs_root, Path(f"{run_id}.json"))

    def quarantine_run_root(self, run_id: str) -> Path:
        return confined_path(self.quarantine_root, Path(run_id))

    def create(self, scan_root: Path, *, now: datetime | None = None) -> dict:
        self.initialize()
        created = now or _utc_now()
        run_id = _run_id(created)
        private_directory(self.quarantine_run_root(run_id))
        private_directory(self.quarantine_run_root(run_id) / "files")
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "created_at": created.isoformat(),
            "scan_root": str(scan_root.resolve()),
            "entries": [],
        }
        self.save(manifest)
        return manifest

    def save(self, manifest: dict) -> None:
        self._validate_layout()
        path = self.manifest_path(manifest["run_id"])
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(temporary, flags, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                descriptor = -1
                handle.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary.exists():
                temporary.unlink()
        private_file(path)

    def load(self, run_id: str) -> dict:
        self._validate_layout()
        path = self.manifest_path(run_id)
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SafetyError(f"Cannot read run {run_id}: {error}") from error
        if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("run_id") != run_id:
            raise SafetyError("Unsupported or mismatched run record.")
        scan_root = Path(manifest.get("scan_root", ""))
        if not scan_root.is_absolute():
            raise SafetyError("Run record has an invalid scan root.")
        for entry in manifest.get("entries", []):
            self.resolve_entry(manifest, entry)
        return manifest

    def list_runs(self) -> list[dict]:
        self._validate_layout()
        if not self.runs_root.exists():
            return []
        runs = []
        for path in sorted(self.runs_root.glob("*.json"), reverse=True):
            try:
                runs.append(self.load(path.stem))
            except SafetyError:
                continue
        return runs

    def resolve_entry(self, manifest: dict, entry: dict) -> tuple[Path, Path]:
        source_relative = Path(entry.get("source_relative", ""))
        scan_root = Path(manifest["scan_root"]).resolve()
        source = confined_path(scan_root, source_relative)
        if entry.get("destination_base") is None and entry.get("destination_relative") is None:
            return source, source
        destination_relative = Path(entry.get("destination_relative", ""))
        if entry.get("destination_base") == "quarantine":
            destination_base = self.quarantine_run_root(manifest["run_id"])
        elif entry.get("destination_base") == "scan_root":
            destination_base = scan_root
        else:
            raise SafetyError("Run record has an invalid destination base.")
        destination = confined_path(destination_base, destination_relative)
        return source, destination


class FileExecutor:
    def __init__(self, store: RunStore | None = None):
        self.store = store or RunStore()

    def _revalidate(self, plan: PlannedAction) -> tuple[bool, str]:
        item = plan.snapshot
        if plan.action == "quarantine" and item.recommendation != "quarantine":
            return False, "Deterministic policy does not authorize quarantine for this file."
        if plan.action == "organize" and item.recommendation != "organize":
            return False, "Deterministic policy does not authorize organization for this file."
        try:
            if item.path.is_symlink():
                return False, "Source became a symlink after preview."
            current = item.path.stat()
        except OSError as error:
            return False, f"Source is no longer available: {error}"
        if not stat.S_ISREG(current.st_mode):
            return False, "Source is no longer a regular file."
        if current.st_size != item.size or current.st_mtime_ns != item.mtime_ns:
            return False, "Source changed after preview."
        try:
            resolved = item.path.resolve(strict=True)
            resolved.relative_to(item.root.resolve())
        except (OSError, ValueError):
            return False, "Source no longer resolves inside the selected folder."
        if item.sha256 and sha256_file(item.path) != item.sha256:
            return False, "Source content changed after preview."
        if item.exact_duplicate_of:
            try:
                if not item.exact_duplicate_of.is_file() or item.exact_duplicate_of.is_symlink():
                    return False, "The copy selected to keep is no longer available."
                if sha256_file(item.exact_duplicate_of) != item.sha256:
                    return False, "The copy selected to keep no longer matches."
            except OSError as error:
                return False, f"Could not recheck the copy selected to keep: {error}"
        return True, "Revalidated immediately before action."

    def execute(self, actions: Iterable[PlannedAction]) -> tuple[str | None, list[ActionResult]]:
        actions = list(actions)
        if not actions:
            return None, []
        roots = {action.snapshot.root.resolve() for action in actions}
        if len(roots) != 1:
            raise SafetyError("A run may operate on only one selected folder.")
        manifest = self.store.create(roots.pop())
        run_id = manifest["run_id"]
        results: list[ActionResult] = []

        for plan in actions:
            item = plan.snapshot
            valid, reason = self._revalidate(plan)
            if not valid:
                manifest["entries"].append(
                    {
                        "action": plan.action,
                        "source_relative": str(item.relative_path),
                        "destination_base": None,
                        "destination_relative": None,
                        "size": item.size,
                        "sha256": item.sha256,
                        "status": "skipped",
                        "reason": reason,
                        "recorded_at": _utc_now().isoformat(),
                    }
                )
                self.store.save(manifest)
                results.append(
                    ActionResult(
                        plan.action, str(item.path), None, "skipped", reason, item.size, item.sha256
                    )
                )
                continue

            if plan.action == "quarantine":
                destination_base = "quarantine"
                destination_relative = Path("files") / item.relative_path
                destination = confined_path(
                    self.store.quarantine_run_root(run_id), destination_relative
                )
            elif plan.action == "organize":
                destination_base = "scan_root"
                group = plan.destination_group or organization_group(item.extension)
                destination_relative = Path("_Organized") / group / item.relative_path
                destination = confined_path(item.root, destination_relative)
            else:
                results.append(
                    ActionResult(
                        str(plan.action),
                        str(item.path),
                        None,
                        "failed",
                        "Unsupported action.",
                        item.size,
                        item.sha256,
                    )
                )
                continue

            destination = _unique_path(destination)
            if destination_base == "quarantine":
                destination_relative = destination.relative_to(
                    self.store.quarantine_run_root(run_id)
                )
            else:
                destination_relative = destination.relative_to(item.root)
            entry = {
                "action": plan.action,
                "source_relative": str(item.relative_path),
                "destination_base": destination_base,
                "destination_relative": str(destination_relative),
                "size": item.size,
                "sha256": item.sha256,
                "status": "pending",
                "reason": reason,
                "recorded_at": _utc_now().isoformat(),
            }
            manifest["entries"].append(entry)
            self.store.save(manifest)
            try:
                _move(item.path, destination)
                entry["status"] = "succeeded"
                entry["completed_at"] = _utc_now().isoformat()
                result = ActionResult(
                    plan.action,
                    str(item.path),
                    str(destination),
                    "succeeded",
                    reason,
                    item.size,
                    item.sha256,
                )
            except OSError as error:
                entry["status"] = "failed"
                entry["reason"] = str(error)
                entry["completed_at"] = _utc_now().isoformat()
                result = ActionResult(
                    plan.action,
                    str(item.path),
                    str(destination),
                    "failed",
                    str(error),
                    item.size,
                    item.sha256,
                )
            self.store.save(manifest)
            results.append(result)
        return run_id, results

    def restore(self, run_id: str, *, quarantine_only: bool = False) -> list[ActionResult]:
        manifest = self.store.load(run_id)
        results: list[ActionResult] = []
        for entry in reversed(manifest["entries"]):
            if entry.get("status") not in {"succeeded", "pending"}:
                continue
            if quarantine_only and entry.get("action") != "quarantine":
                continue
            source, destination = self.store.resolve_entry(manifest, entry)
            if source.exists():
                reason = "Original path is occupied; nothing was overwritten."
                entry.update(
                    last_restore_status="skipped",
                    last_restore_reason=reason,
                    last_restore_at=_utc_now().isoformat(),
                )
                results.append(
                    ActionResult(
                        entry["action"],
                        str(destination),
                        str(source),
                        "skipped",
                        reason,
                        entry["size"],
                        entry.get("sha256"),
                    )
                )
                continue
            if not destination.is_file() or destination.is_symlink():
                reason = "Held file is missing or unsafe."
                entry.update(
                    last_restore_status="skipped",
                    last_restore_reason=reason,
                    last_restore_at=_utc_now().isoformat(),
                )
                results.append(
                    ActionResult(
                        entry["action"],
                        str(destination),
                        str(source),
                        "skipped",
                        reason,
                        entry["size"],
                        entry.get("sha256"),
                    )
                )
                continue
            if entry.get("sha256") and sha256_file(destination) != entry["sha256"]:
                reason = "Held file content no longer matches the record."
                entry.update(
                    last_restore_status="skipped",
                    last_restore_reason=reason,
                    last_restore_at=_utc_now().isoformat(),
                )
                results.append(
                    ActionResult(
                        entry["action"],
                        str(destination),
                        str(source),
                        "skipped",
                        reason,
                        entry["size"],
                        entry.get("sha256"),
                    )
                )
                continue
            try:
                _move(destination, source)
                entry["status"] = "restored"
                entry.update(
                    last_restore_status="restored",
                    last_restore_reason="Restored to the original path.",
                    last_restore_at=_utc_now().isoformat(),
                )
                results.append(
                    ActionResult(
                        entry["action"],
                        str(destination),
                        str(source),
                        "restored",
                        "Restored to the original path.",
                        entry["size"],
                        entry.get("sha256"),
                    )
                )
            except OSError as error:
                entry.update(
                    last_restore_status="failed",
                    last_restore_reason=str(error),
                    last_restore_at=_utc_now().isoformat(),
                )
                results.append(
                    ActionResult(
                        entry["action"],
                        str(destination),
                        str(source),
                        "failed",
                        str(error),
                        entry["size"],
                        entry.get("sha256"),
                    )
                )
        self.store.save(manifest)
        return results

    def purge_expired(
        self, *, days: int = 30, confirmed: bool = False, now: datetime | None = None
    ) -> list[ActionResult]:
        if not confirmed:
            raise SafetyError("Permanent purge requires explicit confirmation.")
        cutoff = (now or _utc_now()) - timedelta(days=days)
        results: list[ActionResult] = []
        for manifest in self.store.list_runs():
            try:
                created_at = datetime.fromisoformat(manifest["created_at"])
            except (KeyError, ValueError):
                continue
            if created_at > cutoff:
                continue
            attempted = False
            for entry in manifest["entries"]:
                if entry.get("action") != "quarantine" or entry.get("status") not in {
                    "succeeded",
                    "pending",
                }:
                    continue
                attempted = True
                source, destination = self.store.resolve_entry(manifest, entry)
                if source.exists():
                    reason = "Original path is occupied; held file retained."
                    entry.update(
                        last_purge_status="skipped",
                        last_purge_reason=reason,
                        last_purge_at=_utc_now().isoformat(),
                    )
                    results.append(
                        ActionResult(
                            "purge",
                            str(destination),
                            None,
                            "skipped",
                            reason,
                            entry["size"],
                            entry.get("sha256"),
                        )
                    )
                    continue
                if not destination.is_file() or destination.is_symlink():
                    reason = "Held file is missing or unsafe."
                    entry.update(
                        last_purge_status="skipped",
                        last_purge_reason=reason,
                        last_purge_at=_utc_now().isoformat(),
                    )
                    results.append(
                        ActionResult(
                            "purge",
                            str(destination),
                            None,
                            "skipped",
                            reason,
                            entry["size"],
                            entry.get("sha256"),
                        )
                    )
                    continue
                if entry.get("sha256") and sha256_file(destination) != entry["sha256"]:
                    reason = "Held file content no longer matches the record."
                    entry.update(
                        last_purge_status="skipped",
                        last_purge_reason=reason,
                        last_purge_at=_utc_now().isoformat(),
                    )
                    results.append(
                        ActionResult(
                            "purge",
                            str(destination),
                            None,
                            "skipped",
                            reason,
                            entry["size"],
                            entry.get("sha256"),
                        )
                    )
                    continue
                try:
                    destination.unlink()
                    entry["status"] = "purged"
                    entry.update(
                        last_purge_status="purged",
                        last_purge_reason="Permanently removed after confirmed expiry review.",
                        last_purge_at=_utc_now().isoformat(),
                    )
                    results.append(
                        ActionResult(
                            "purge",
                            str(destination),
                            None,
                            "purged",
                            "Permanently removed after confirmed expiry review.",
                            entry["size"],
                            entry.get("sha256"),
                        )
                    )
                except OSError as error:
                    entry.update(
                        last_purge_status="failed",
                        last_purge_reason=str(error),
                        last_purge_at=_utc_now().isoformat(),
                    )
                    results.append(
                        ActionResult(
                            "purge",
                            str(destination),
                            None,
                            "failed",
                            str(error),
                            entry["size"],
                            entry.get("sha256"),
                        )
                    )
            if attempted:
                self.store.save(manifest)
        return results
