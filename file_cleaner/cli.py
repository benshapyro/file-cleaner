from __future__ import annotations

import json
import stat
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import click
import humanize
from rich.console import Console
from rich.table import Table

from . import __version__
from .ai import analyze, request_count
from .credentials import CredentialError, get_api_key, store_api_key
from .models import FileSnapshot, PlannedAction
from .policy import categorize, organization_group
from .quarantine import FileExecutor, RunStore
from .safety import SafetyError
from .scanner import scan_folder

console = Console()


def _path(value: str | None) -> Path:
    return Path(value).expanduser() if value else Path.home() / "Downloads"


def _scan(path: Path, recursive: bool) -> list[FileSnapshot]:
    try:
        return categorize(scan_folder(path, recursive=recursive))
    except (OSError, SafetyError) as error:
        raise click.ClickException(str(error)) from error


def _maybe_add_ai(files: list[FileSnapshot], enabled: bool) -> None:
    if not enabled:
        return
    candidates = [item for item in files if item.category in {"unknown", "media"}]
    count = request_count(candidates)
    console.print(
        f"AI mode will send [bold]{len(candidates)} filenames[/bold], "
        "sizes, ages, and local categories "
        f"in approximately [bold]{count} request(s)[/bold]. File contents stay local."
    )
    if not click.confirm("Allow these network requests for this run?", default=False):
        raise click.Abort()
    try:
        api_key, source = get_api_key()
    except CredentialError as error:
        raise click.ClickException(str(error)) from error
    if not api_key:
        raise click.ClickException("No AI credential found. Run: file-cleaner configure-ai")
    console.print(
        f"Using an AI credential from {source}; the credential will not be displayed or logged."
    )
    try:
        analyze(candidates, api_key)
    except Exception as error:
        raise click.ClickException(
            f"AI analysis failed; no file actions were taken: {error}"
        ) from error


def _summary(files: list[FileSnapshot]) -> None:
    by_recommendation = Counter(item.recommendation for item in files)
    table = Table(title=f"Scan summary: {len(files)} files")
    table.add_column("Recommendation")
    table.add_column("Files", justify="right")
    table.add_column("Size", justify="right")
    for recommendation in ("quarantine", "organize", "review", "keep"):
        selected = [item for item in files if item.recommendation == recommendation]
        table.add_row(
            recommendation.capitalize(),
            str(by_recommendation[recommendation]),
            humanize.naturalsize(sum(item.size for item in selected)),
        )
    console.print(table)


def _details(files: list[FileSnapshot], recommendations: set[str] | None = None) -> None:
    selected = [
        item for item in files if recommendations is None or item.recommendation in recommendations
    ]
    if not selected:
        return
    table = Table(title="Complete file preview", show_lines=True)
    table.add_column("Recommendation", no_wrap=True)
    table.add_column("File")
    table.add_column("Size", justify="right")
    table.add_column("Reason")
    for item in selected:
        reason = item.reason + (f" AI note: {item.ai_note}" if item.ai_note else "")
        table.add_row(
            item.recommendation, str(item.relative_path), humanize.naturalsize(item.size), reason
        )
    console.print(table)


def _results(results) -> None:
    counts = Counter(item.status for item in results)
    sizes = Counter()
    for item in results:
        sizes[item.status] += item.size
    table = Table(title="Actual results")
    table.add_column("Result")
    table.add_column("Files", justify="right")
    table.add_column("Size", justify="right")
    for status in ("succeeded", "restored", "purged", "skipped", "failed"):
        if counts[status]:
            table.add_row(
                status.capitalize(), str(counts[status]), humanize.naturalsize(sizes[status])
            )
    console.print(table)
    for item in results:
        if item.status in {"skipped", "failed"}:
            console.print(f"[yellow]{item.status}: {item.source}: {item.reason}[/yellow]")


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__)
def main() -> None:
    """Guided, reversible file cleanup for macOS."""


@main.command()
@click.argument("path", required=False)
@click.option(
    "--recursive", is_flag=True, help="Include nested folders without following symlinks."
)
@click.option(
    "--ai", "ai_enabled", is_flag=True, help="Explicitly allow AI organization notes for this run."
)
@click.option("--details", "show_details", is_flag=True, help="Show every scanned file and reason.")
@click.option("--json-output", is_flag=True, help="Print the full result as JSON.")
def scan(
    path: str | None, recursive: bool, ai_enabled: bool, show_details: bool, json_output: bool
) -> None:
    """Read-only local scan. PATH defaults to Downloads."""
    files = _scan(_path(path), recursive)
    _maybe_add_ai(files, ai_enabled)
    if json_output:
        click.echo(json.dumps([item.public_dict() for item in files], indent=2))
        return
    _summary(files)
    if show_details:
        _details(files)
    elif any(item.similar_names for item in files):
        console.print(
            "Similar filenames are flagged for comparison but are not treated as duplicates."
        )


@main.command()
@click.argument("path", required=False)
@click.option(
    "--recursive", is_flag=True, help="Include nested folders without following symlinks."
)
@click.option(
    "--ai", "ai_enabled", is_flag=True, help="Explicitly allow AI organization notes for this run."
)
@click.option(
    "--only", type=click.Choice(["quarantine", "organize", "both"]), default="both", hidden=True
)
def clean(path: str | None, recursive: bool, ai_enabled: bool, only: str) -> None:
    """Preview recommendations, choose categories, then confirm actions."""
    files = _scan(_path(path), recursive)
    _maybe_add_ai(files, ai_enabled)
    _summary(files)
    actionable = {"quarantine", "organize"}
    if only != "both":
        actionable = {only}
    _details(files, actionable | {"review"})

    actions: list[PlannedAction] = []
    quarantine = [
        item for item in files if item.recommendation == "quarantine" and "quarantine" in actionable
    ]
    organize = [
        item for item in files if item.recommendation == "organize" and "organize" in actionable
    ]
    if quarantine and click.confirm(
        f"Select all {len(quarantine)} quarantine recommendations?", default=False
    ):
        actions.extend(PlannedAction(item, "quarantine") for item in quarantine)
    if organize and click.confirm(
        f"Select all {len(organize)} organization recommendations?", default=False
    ):
        actions.extend(
            PlannedAction(item, "organize", organization_group(item.extension)) for item in organize
        )
    if not actions:
        console.print("No actions selected. Nothing changed.")
        return
    console.print(
        f"Selected {len(actions)} action(s). "
        "Every file will be rechecked immediately before moving."
    )
    if not click.confirm("Apply these selected actions now?", default=False):
        console.print("Cancelled. Nothing changed.")
        return
    run_id, results = FileExecutor().execute(actions)
    _results(results)
    if run_id:
        console.print(f"Recovery run: [bold]{run_id}[/bold]. Undo with: file-cleaner undo {run_id}")


@main.command()
@click.argument("run_id")
def undo(run_id: str) -> None:
    """Reverse successful organization and quarantine moves from RUN_ID."""
    try:
        results = FileExecutor().restore(run_id)
    except SafetyError as error:
        raise click.ClickException(str(error)) from error
    _results(results)


@main.group()
def quarantine() -> None:
    """List, restore, or permanently purge held files."""


@quarantine.command("list")
def quarantine_list() -> None:
    runs = RunStore().list_runs()
    table = Table(title="Recoverable runs")
    table.add_column("Run")
    table.add_column("Created")
    table.add_column("Held files", justify="right")
    table.add_column("Held size", justify="right")
    for run in runs:
        held = [
            entry
            for entry in run["entries"]
            if entry["action"] == "quarantine" and entry["status"] in {"succeeded", "pending"}
        ]
        table.add_row(
            run["run_id"],
            run["created_at"],
            str(len(held)),
            humanize.naturalsize(sum(entry["size"] for entry in held)),
        )
    console.print(table)


@quarantine.command("restore")
@click.argument("run_id")
def quarantine_restore(run_id: str) -> None:
    try:
        results = FileExecutor().restore(run_id, quarantine_only=True)
    except SafetyError as error:
        raise click.ClickException(str(error)) from error
    _results(results)


@quarantine.command("purge")
@click.option("--older-than", type=click.IntRange(min=30), default=30, show_default=True)
def quarantine_purge(older_than: int) -> None:
    store = RunStore()
    eligible = []
    cutoff = datetime.now(UTC).timestamp() - older_than * 86400
    for run in store.list_runs():
        try:
            if datetime.fromisoformat(run["created_at"]).timestamp() > cutoff:
                continue
        except (KeyError, ValueError):
            continue
        eligible.extend(
            entry
            for entry in run["entries"]
            if entry["action"] == "quarantine" and entry["status"] in {"succeeded", "pending"}
        )
    eligible_size = humanize.naturalsize(sum(entry["size"] for entry in eligible))
    console.print(f"Eligible for permanent deletion: {len(eligible)} files ({eligible_size}).")
    if not eligible:
        return
    phrase = click.prompt(
        "Type PURGE to permanently delete these held files", default="", show_default=False
    )
    if phrase != "PURGE":
        console.print("Cancelled. Nothing changed.")
        return
    try:
        results = FileExecutor(store).purge_expired(days=older_than, confirmed=True)
    except SafetyError as error:
        raise click.ClickException(str(error)) from error
    _results(results)


@main.command("archive-review")
@click.argument("path", required=False)
def archive_review(path: str | None) -> None:
    """Read-only inventory of the legacy _Archive folder."""
    root = _path(path)
    archive = root / "_Archive"
    if not archive.exists():
        console.print(f"No legacy archive found at {archive}.")
        return
    files = [item for item in archive.rglob("*") if item.is_file() and not item.is_symlink()]
    archive_size = humanize.naturalsize(sum(item.stat().st_size for item in files))
    console.print(f"Legacy archive inventory: {len(files)} files ({archive_size}).")
    console.print(
        "This command is read-only. Missing usage metadata is unknown and never "
        "authorizes deletion."
    )


@main.command("configure-ai")
def configure_ai() -> None:
    """Store an optional OpenAI credential in macOS Keychain."""
    value = click.prompt("OpenAI API key", hide_input=True, confirmation_prompt=True)
    try:
        store_api_key(value)
    except CredentialError as error:
        raise click.ClickException(str(error)) from error
    console.print("Credential stored in macOS Keychain. It was not displayed or logged.")


@main.command()
def doctor() -> None:
    """Check local installation and safety configuration without network access."""
    failures = []
    console.print(f"Python: {sys.version.split()[0]}")
    console.print(f"State folder: {RunStore().state_root}")
    legacy = Path.cwd() / ".env"
    if legacy.exists():
        mode = stat.S_IMODE(legacy.stat().st_mode)
        if mode & 0o077:
            failures.append(f"Legacy {legacy} permissions are {oct(mode)}; change them to 0o600.")
        else:
            console.print("Legacy .env permissions are private; macOS Keychain is still preferred.")
    console.print("Network check: skipped by design.")
    if failures:
        for failure in failures:
            console.print(f"[red]{failure}[/red]")
        raise click.ClickException("Doctor found configuration problems.")
    console.print("Local checks passed.")


if __name__ == "__main__":
    main()
