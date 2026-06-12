#!/usr/bin/env python3
"""
Smart Downloads Folder Cleanup Tool
Analyzes files in Downloads folder and suggests items to clean up using AI
"""

import os
import sys
import json
import shutil
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict
from dataclasses import dataclass, asdict
from enum import Enum
import time
import mimetypes
from concurrent.futures import ThreadPoolExecutor, as_completed
import click
import humanize
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, track
from rich.panel import Panel
from rich import print as rprint
import questionary
from dotenv import load_dotenv
from openai import OpenAI
from send2trash import send2trash
from config import *
from duplicate_detector import find_duplicates_by_hash
import logging
import threading
import subprocess

# Load environment variables
load_dotenv()

console = Console()

class ActionType(Enum):
    DELETE = "delete"
    ORGANIZE = "organize"
    ARCHIVE = "archive"
    SKIP = "skip"

@dataclass
class FileInfo:
    """Represents a file with its metadata"""
    path: Path
    name: str
    size: int
    modified_time: datetime
    created_time: datetime
    file_type: str
    extension: str
    category: str = "unknown"  # File category for organization
    
    @property
    def age_days(self) -> int:
        """Calculate file age in days"""
        return (datetime.now() - self.modified_time).days
    
    @property
    def size_human(self) -> str:
        """Return human-readable size"""
        return humanize.naturalsize(self.size)

class DownloadsCleaner:
    """Main cleanup manager"""
    
    def __init__(self, downloads_path: Optional[str] = None):
        self.downloads_path = Path(downloads_path or os.path.expanduser("~/Downloads"))
        self._client: Optional[OpenAI] = None
        self.file_infos: List[FileInfo] = []
        self.categories: Dict[str, List[FileInfo]] = defaultdict(list)
        
        # Organization folders — single source of truth lives in config.py
        self.org_folders = ORGANIZATION_FOLDERS
        # Files failing deletion-safety gates (age/size): still organizable/archivable, never deletable
        self.non_deletable: Set[Path] = set()
        
    @property
    def client(self) -> OpenAI:
        """Lazy-initialize OpenAI client only when AI is actually needed"""
        if self._client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY not set. Run with AI_ENABLED=False or set the key.")
            self._client = OpenAI(api_key=api_key)
        return self._client

    def scan_downloads(self) -> None:
        """Scan downloads folder and collect file information using parallel processing"""
        console.print("[bold blue]Scanning Downloads folder...[/bold blue]")
        
        # Get all items in the downloads folder
        items = [item for item in self.downloads_path.iterdir() if item.is_file() and not item.name.startswith('.')]
        dirs = [item for item in self.downloads_path.iterdir() if item.is_dir() and not item.name.startswith('.') and item.name != "_Organized"]

        # Use parallel processing to scan files
        results: List[Optional[FileInfo]] = []
        scan_errors: Dict[str, int] = defaultdict(int)

        with Progress() as progress:
            task = progress.add_task("[cyan]Scanning files...", total=len(items))

            with ThreadPoolExecutor(max_workers=8) as executor:
                future_to_item = {executor.submit(self._scan_single_file, item): item for item in items}

                for future in as_completed(future_to_item):
                    progress.update(task, advance=1)
                    try:
                        file_info = future.result()
                        if file_info:
                            results.append(file_info)
                    except Exception as e:
                        error_type = type(e).__name__
                        scan_errors[error_type] = scan_errors.get(error_type, 0) + 1

        self.file_infos = results

        # Report directory sizes
        if dirs:
            dir_sizes: List[Tuple[Path, int]] = []
            for d in dirs:
                try:
                    total = sum(f.stat().st_size for f in d.rglob('*') if f.is_file())
                    dir_sizes.append((d, total))
                except (PermissionError, OSError):
                    pass
            dir_sizes.sort(key=lambda x: x[1], reverse=True)
            if dir_sizes:
                console.print(f"\n[bold blue]Subdirectories (not scanned, showing sizes):[/bold blue]")
                for d, size in dir_sizes[:10]:
                    console.print(f"  {d.name}/ — {humanize.naturalsize(size)}")

        console.print(f"\n[green]✓ Scanned {len(self.file_infos)} files[/green]")
        if scan_errors:
            for error_type, count in scan_errors.items():
                console.print(f"[dim]  Skipped {count} files ({error_type})[/dim]")
    
    def _scan_single_file(self, item: Path) -> Optional[FileInfo]:
        """Scan a single file and return FileInfo or None if error"""
        try:
            stat = item.stat()
            return FileInfo(
                path=item,
                name=item.name,
                size=stat.st_size,
                modified_time=datetime.fromtimestamp(stat.st_mtime),
                created_time=datetime.fromtimestamp(getattr(stat, 'st_birthtime', stat.st_ctime)),
                file_type=mimetypes.guess_type(str(item))[0] or "unknown",
                extension=item.suffix.lower(),
                category=self._get_file_category(item)
            )
        except Exception as e:
            console.print(f"[red]Error scanning {item.name}: {e}[/red]")
            return None
    
    def _get_file_category(self, item: Path) -> str:
        """Determine file category based on extension"""
        ext = item.suffix.lower()
        
        # Documents
        if ext in ['.pdf', '.doc', '.docx', '.txt', '.odt', '.rtf']:
            return "document"
        # Images
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp']:
            return "image"
        # Videos
        elif ext in ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv']:
            return "video"
        # Archives
        elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
            return "archive"
        # Installers
        elif ext in ['.dmg', '.pkg', '.exe', '.msi', '.app']:
            return "installer"
        # Audio
        elif ext in ['.mp3', '.wav', '.flac', '.aac', '.ogg']:
            return "audio"
        # Code
        elif ext in ['.py', '.js', '.html', '.css', '.java', '.cpp']:
            return "code"
        else:
            return "other"
    
    def _looks_disposable(self, file_info: FileInfo) -> bool:
        """Check if an old file looks like junk/temp rather than a real document"""
        name_lower = file_info.name.lower()

        # Temp file extensions are always disposable
        temp_exts = ['.tmp', '.temp', '.part', '.download', '.crdownload', '.log', '.bak']
        if file_info.extension in temp_exts:
            return True

        # Generic unnamed downloads (e.g., "download.pdf", "image.png", "file.txt")
        generic_names = ['download', 'untitled', 'new file', 'unknown', 'temp']
        if any(name_lower.startswith(g) for g in generic_names):
            return True

        # ChatGPT/AI-generated image downloads with generic names
        if name_lower.startswith('chatgpt image') or name_lower.startswith('dall-e'):
            return True

        # Files with only a hash-like name (e.g., "a1b2c3d4e5.pdf")
        stem = file_info.path.stem
        if len(stem) > 8 and all(c in '0123456789abcdef-_' for c in stem.lower()):
            return True

        return False

    def _is_deletable(self, file_info: FileInfo) -> bool:
        """Deletion-safety gates (age/size). Protection checks are handled upstream
        in categorize_files; these gates only decide whether DELETE is allowed."""
        import config
        if file_info.extension in config.FILE_TYPE_RULES:
            min_age, never_delete = config.FILE_TYPE_RULES[file_info.extension]
            if never_delete or file_info.age_days < min_age:
                return False
        if file_info.age_days < config.MIN_AGE_FOR_DELETION:
            return False
        if config.IGNORE_SMALL_FILES and file_info.size < config.MIN_FILE_SIZE:
            return False
        return True

    def categorize_files(self) -> None:
        """Categorize files using rules and AI"""
        console.print("\n[bold blue]Analyzing files...[/bold blue]")

        import config

        categorized: Set[Path] = set()
        eligible: List[FileInfo] = []
        self.non_deletable = set()

        # Protection checks exclude a file from everything; deletion gates only mark
        # it non-deletable so it can still be organized or archived.
        for file_info in self.file_infos:
            if file_info.extension in config.CRITICAL_EXTENSIONS:
                console.print(f"[yellow]Skipping critical file: {file_info.name}[/yellow]")
                continue
            if any(pattern.lower() in file_info.name.lower() for pattern in config.PROTECTED_PATTERNS):
                continue
            if file_info.name.lower() in [f.lower() for f in config.WHITELIST_FILES]:
                continue
            eligible.append(file_info)
            if not self._is_deletable(file_info):
                self.non_deletable.add(file_info.path)

        # Hash-based duplicate detection (most specific — check first)
        if config.CHECK_DUPLICATES_BY_HASH:
            duplicates = find_duplicates_by_hash(
                [f.path for f in eligible],
                min_size=config.DUPLICATE_MIN_SIZE
            )
            for hash_val, dup_paths in duplicates.items():
                # Keep the newest file, mark older copies for deletion
                dup_paths_sorted = sorted(dup_paths, key=lambda p: p.stat().st_mtime, reverse=True)
                # Mark the kept file so name-pattern detection skips it
                categorized.add(dup_paths_sorted[0])
                for dup_path in dup_paths_sorted[1:]:
                    file_info = next((f for f in eligible if f.path == dup_path), None)
                    if file_info and file_info.path not in categorized:
                        self.categories["exact_duplicates"].append(file_info)
                        categorized.add(file_info.path)

        # Rule-based categorization (each file goes into ONE primary category)
        for file_info in eligible:
            if file_info.path in categorized:
                continue

            # Screenshots (by filename pattern)
            if 'screenshot' in file_info.name.lower() or 'screen shot' in file_info.name.lower():
                self.categories["screenshots"].append(file_info)
                categorized.add(file_info.path)
            # Name-pattern duplicates — files with (1), (2) etc
            elif any(f'({i})' in file_info.name for i in range(1, 10)):
                self.categories["duplicates"].append(file_info)
                categorized.add(file_info.path)
            # Installers and disk images
            elif file_info.extension in ['.dmg', '.pkg', '.exe', '.msi', '.deb', '.rpm']:
                self.categories["installers"].append(file_info)
                categorized.add(file_info.path)
            # Archives
            elif file_info.extension in ['.zip', '.rar', '.7z', '.tar', '.gz']:
                self.categories["archives"].append(file_info)
                categorized.add(file_info.path)
            # Large files
            elif file_info.size > config.LARGE_FILE_SIZE:
                self.categories["large_files"].append(file_info)
                categorized.add(file_info.path)
            # Old files split by type
            elif file_info.age_days > config.OLD_FILE_DAYS:
                if self._looks_disposable(file_info):
                    self.categories["old_junk"].append(file_info)
                elif file_info.extension in ['.pdf', '.doc', '.docx', '.xls', '.xlsx',
                                              '.ppt', '.pptx', '.odt', '.rtf', '.pages',
                                              '.numbers', '.csv', '.key']:
                    self.categories["old_documents"].append(file_info)
                else:
                    self.categories["old_media"].append(file_info)
                categorized.add(file_info.path)

        # Use AI for uncategorized files, in batches (previously silently capped at 20)
        uncategorized = [f for f in eligible if f.path not in categorized]
        for start in range(0, len(uncategorized), AI_BATCH_SIZE):
            self._ai_categorize(uncategorized[start:start + AI_BATCH_SIZE])
    
    def _ai_categorize(self, files: List[FileInfo]) -> None:
        """Use AI to analyze and categorize files with Structured Outputs"""
        if not AI_ENABLED:
            return

        if not os.getenv("OPENAI_API_KEY"):
            console.print("[dim]Skipping AI categorization (OPENAI_API_KEY not set)[/dim]")
            return

        try:
            file_list = "\n".join([f"- {f.name} ({f.size_human}, {f.age_days} days old, type: {f.category})"
                                  for f in files])

            prompt = f"""Analyze these files from a Downloads folder and categorize each one.
Consider file age, type, and name patterns. Provide confidence score (0-1) and reasoning.
Return the exact filename as it appears below.

Categories:
- safe_to_delete: temporary files, old downloads, cache files, installers over 30 days old
- might_be_important: documents that might be needed, recent work files, projects
- keep: clearly important files, personal documents, active projects

Files to analyze:
{file_list}"""

            response = self.client.chat.completions.create(
                model=AI_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert file organization assistant. Analyze files carefully and provide detailed categorization with confidence scores."},
                    {"role": "user", "content": prompt}
                ],
                temperature=AI_TEMPERATURE,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "file_categorization",
                        "strict": True,
                        "schema": AI_RESPONSE_SCHEMA
                    }
                }
            )

            result = json.loads(response.choices[0].message.content)
            categorizations_list = result.get("categorizations", [])

            # Build lookup by filename
            categorizations = {item["filename"]: item for item in categorizations_list}

            console.print("[cyan]AI Analysis Results:[/cyan]")
            for file_info in files:
                cat_info = categorizations.get(file_info.name)
                if not cat_info:
                    continue
                category = cat_info["category"]
                confidence = cat_info["confidence"]
                reason = cat_info["reason"]

                if category == "safe_to_delete" and confidence >= 0.7:
                    self.categories["ai_suggested"].append(file_info)
                    console.print(f"  [green]✓[/green] {file_info.name}: {reason} [dim](confidence: {confidence:.0%})[/dim]")
                elif category == "might_be_important":
                    console.print(f"  [yellow]?[/yellow] {file_info.name}: {reason} [dim](confidence: {confidence:.0%})[/dim]")
                else:
                    console.print(f"  [blue]↗[/blue] {file_info.name}: {reason} [dim](confidence: {confidence:.0%})[/dim]")

        except Exception as e:
            console.print(f"[yellow]AI categorization failed: {e}[/yellow]")
    
    def display_recommendations(self, mode: str = "clean") -> Dict[str, Tuple[List[FileInfo], ActionType]]:
        """Display cleanup/organization recommendations and get user selections"""
        if mode == "organize":
            console.print("\n[bold green]File Organization Recommendations[/bold green]\n")
        else:
            console.print("\n[bold green]Cleanup Recommendations[/bold green]\n")
        
        total_size = 0
        all_recommendations = {}
        
        # Categories that should default to archive instead of delete
        archive_categories = {"old_documents"}

        category_info = {
            "exact_duplicates": ("Exact Duplicates (hash-verified)", "Identical files confirmed by content hash — newest version is kept"),
            "old_junk": ("Old Temp/Junk Files", "Temp files, generic downloads, and other disposable files older than 30 days"),
            "old_documents": ("Old Documents (>30 days)", "Work documents — archived for safety, reviewed later. Run --mode review-archive to check"),
            "old_media": ("Old Media & Misc (>30 days)", "Images, videos, and misc files older than 30 days"),
            "installers": ("Installers & Disk Images", "Installation files that can usually be re-downloaded"),
            "archives": ("Archive Files", "Zip files and other archives"),
            "screenshots": ("Screenshots", "Screen captures that accumulate over time"),
            "duplicates": ("Possible Duplicates", "Files with (1), (2) in names suggesting duplicates"),
            "large_files": ("Large Files (>100MB)", "Files taking up significant space"),
            "ai_suggested": ("AI Suggested", "Files the AI thinks are safe to delete")
        }
        
        for category, files in self.categories.items():
            if not files:
                continue
                
            title, description = category_info.get(category, (category, ""))
            
            table = Table(title=f"{title} ({len(files)} files)")
            table.add_column("File", style="cyan", no_wrap=False)
            table.add_column("Size", style="green")
            table.add_column("Age", style="yellow")
            table.add_column("Modified", style="blue")
            
            category_size = sum(f.size for f in files)
            for f in files[:10]:  # Show first 10
                table.add_row(
                    f.name,
                    f.size_human,
                    f"{f.age_days} days",
                    f.modified_time.strftime("%Y-%m-%d")
                )

            if len(files) > 10:
                table.add_row("...", f"+ {len(files) - 10} more files", "", "")
            
            console.print(table)
            console.print(f"[dim]{description}[/dim]")
            console.print(f"Total size: [bold]{humanize.naturalsize(category_size)}[/bold]\n")
            
            # Ask user what to do with this category
            if category in archive_categories:
                action = questionary.select(
                    f"What would you like to do with these {title.lower()}?",
                    choices=[
                        {"name": "Archive (move to _Archive/ for later review)", "value": ActionType.ARCHIVE},
                        {"name": "Delete", "value": ActionType.DELETE},
                        {"name": "Skip", "value": ActionType.SKIP}
                    ]
                ).ask()
            elif mode == "organize":
                action = questionary.select(
                    f"What would you like to do with these {title.lower()}?",
                    choices=[
                        {"name": "Organize into folders", "value": ActionType.ORGANIZE},
                        {"name": "Delete", "value": ActionType.DELETE},
                        {"name": "Skip", "value": ActionType.SKIP}
                    ]
                ).ask()
            else:
                if questionary.confirm(f"Delete these {title.lower()}?", default=False).ask():
                    action = ActionType.DELETE
                else:
                    action = ActionType.SKIP
            
            if action != ActionType.SKIP:
                all_recommendations[category] = (files, action)
                if action == ActionType.DELETE:
                    total_size += category_size
        
        if all_recommendations:
            if any(action == ActionType.DELETE for _, (_, action) in all_recommendations.items()):
                console.print(f"\n[bold]Total space to be freed: {humanize.naturalsize(total_size)}[/bold]")
        
        return all_recommendations
    
    def _get_organization_folder(self, file_info: FileInfo, category: str) -> Path:
        """Determine which organization folder a file should go to"""
        # Check by extension first
        for folder, extensions in self.org_folders.items():
            if file_info.extension in extensions:
                return self.downloads_path / "_Organized" / folder
        
        # Special cases
        if 'screenshot' in file_info.name.lower():
            return self.downloads_path / "_Organized" / "Screenshots"
        
        if file_info.age_days > OLD_FILE_DAYS:
            return self.downloads_path / "_Organized" / "Old_Downloads"
        
        # Default to category-based folder
        category_folders = {
            "old_junk": "Old_Downloads",
            "installers": "Installers",
            "archives": "Archives",
            "screenshots": "Screenshots",
            "duplicates": "Duplicates",
            "large_files": "Large_Files",
            "ai_suggested": "Misc"
        }
        
        folder_name = category_folders.get(category, "Misc")
        return self.downloads_path / "_Organized" / folder_name
    
    def process_files(self, selections: Dict[str, Tuple[List[FileInfo], ActionType]], dry_run: bool = False) -> None:
        """Execute the cleanup/organization based on user selections"""
        if not selections:
            console.print("[yellow]No files selected for processing.[/yellow]")
            return
        
        delete_files = []
        organize_files = []
        archive_files = []
        seen_paths: Set[Path] = set()

        withheld_count = 0
        for category, (files, action) in selections.items():
            if action == ActionType.DELETE:
                for f in files:
                    if f.path in seen_paths:
                        continue
                    # Deletion-safety gates enforced at the action layer; exact duplicates
                    # are exempt because a content-identical copy is always kept.
                    if category != "exact_duplicates" and f.path in self.non_deletable:
                        withheld_count += 1
                        continue
                    delete_files.append(f)
                    seen_paths.add(f.path)
            elif action == ActionType.ORGANIZE:
                for f in files:
                    if f.path not in seen_paths:
                        organize_files.append((f, category))
                        seen_paths.add(f.path)
            elif action == ActionType.ARCHIVE:
                for f in files:
                    if f.path not in seen_paths:
                        archive_files.append(f)
                        seen_paths.add(f.path)
        
        if withheld_count:
            console.print(f"[yellow]Safety: withheld {withheld_count} file(s) from deletion (younger than minimum age or protected by type rules). They can still be organized or archived.[/yellow]")

        if dry_run:
            def _preview(label: str, names: List[str]) -> None:
                console.print(f"\n[bold yellow]DRY RUN: Would {label} {len(names)} files[/bold yellow]")
                for name in names[:15]:
                    console.print(f"  [dim]- {name}[/dim]")
                if len(names) > 15:
                    console.print(f"  [dim]... and {len(names) - 15} more[/dim]")
            if delete_files:
                _preview("delete", [f.name for f in delete_files])
            if organize_files:
                _preview("organize", [f.name for f, _ in organize_files])
            if archive_files:
                _preview("archive (to _Archive/)", [f.name for f in archive_files])
            return

        # Final confirmation
        actions = []
        if delete_files:
            actions.append(f"delete {len(delete_files)} files")
        if organize_files:
            actions.append(f"organize {len(organize_files)} files")
        if archive_files:
            actions.append(f"archive {len(archive_files)} files")
        
        if not questionary.confirm(
            f"Are you sure you want to {' and '.join(actions)}?", 
            default=False
        ).ask():
            console.print("[yellow]Operation cancelled.[/yellow]")
            return
        
        # Create log file outside Downloads
        import config
        log_dir = Path(os.path.expanduser(config.LOG_DIRECTORY))
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"cleanup_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(log_path, 'w') as log_file:
            log_file.write(f"Downloads Cleanup Log - {datetime.now()}\n")
            log_file.write("=" * 50 + "\n\n")
            
            # Process deletions
            if delete_files:
                log_file.write("\nDELETED FILES:\n")
                for file_info in track(delete_files, description="Deleting files"):
                    try:
                        send2trash(str(file_info.path))
                        log_file.write(f"  ✓ {file_info.name} ({file_info.size_human})\n")
                    except Exception as e:
                        console.print(f"[red]Error deleting {file_info.name}: {e}[/red]")
                        log_file.write(f"  ✗ {file_info.name} - ERROR: {e}\n")
            
            # Process organization
            if organize_files:
                log_file.write("\nORGANIZED FILES:\n")
                for file_info, category in track(organize_files, description="Organizing files"):
                    try:
                        dest_folder = self._get_organization_folder(file_info, category)
                        dest_folder.mkdir(parents=True, exist_ok=True)
                        dest_path = dest_folder / file_info.name
                        
                        # Handle duplicates
                        if dest_path.exists():
                            base = dest_path.stem
                            ext = dest_path.suffix
                            counter = 1
                            while dest_path.exists():
                                dest_path = dest_folder / f"{base}_{counter}{ext}"
                                counter += 1
                        
                        file_info.path.rename(dest_path)
                        log_file.write(f"  ✓ {file_info.name} → {dest_folder.name}/\n")
                    except Exception as e:
                        console.print(f"[red]Error organizing {file_info.name}: {e}[/red]")
                        log_file.write(f"  ✗ {file_info.name} - ERROR: {e}\n")
        
            # Process archives
            if archive_files:
                archive_dir = self.downloads_path / "_Archive"
                archive_dir.mkdir(exist_ok=True)
                manifest_path = archive_dir / ".archive_manifest.json"

                # Load existing manifest
                manifest = {}
                if manifest_path.exists():
                    with open(manifest_path, 'r') as mf:
                        manifest = json.load(mf)

                log_file.write("\nARCHIVED FILES:\n")
                archive_date = datetime.now().isoformat()
                for file_info in track(archive_files, description="Archiving files"):
                    try:
                        dest_path = archive_dir / file_info.name
                        if dest_path.exists():
                            base = dest_path.stem
                            ext = dest_path.suffix
                            counter = 1
                            while dest_path.exists():
                                dest_path = archive_dir / f"{base}_{counter}{ext}"
                                counter += 1

                        file_info.path.rename(dest_path)
                        manifest[dest_path.name] = {
                            "archived_on": archive_date,
                            "original_path": str(file_info.path),
                            "size": file_info.size
                        }
                        log_file.write(f"  ✓ {file_info.name} → _Archive/\n")
                    except Exception as e:
                        console.print(f"[red]Error archiving {file_info.name}: {e}[/red]")
                        log_file.write(f"  ✗ {file_info.name} - ERROR: {e}\n")

                # Save manifest
                with open(manifest_path, 'w') as mf:
                    json.dump(manifest, mf, indent=2)

        console.print(f"\n[bold green]✓ Operation complete![/bold green]")
        if delete_files:
            console.print(f"Moved {len(delete_files)} files to trash.")
        if organize_files:
            console.print(f"Organized {len(organize_files)} files into folders.")
        if archive_files:
            console.print(f"Archived {len(archive_files)} files to _Archive/.")
            console.print(f"[dim]Run with --mode review-archive to check which ones you've never opened.[/dim]")
        console.print(f"Log saved to: {log_path}")

def review_archive(downloads_path: Path, dry_run: bool = False) -> None:
    """Review archived files and identify which ones were never opened"""
    import subprocess

    archive_dir = downloads_path / "_Archive"
    if not archive_dir.exists():
        console.print("[yellow]No archive folder found. Run cleanup first to archive files.[/yellow]")
        return

    manifest_path = archive_dir / ".archive_manifest.json"
    manifest = {}
    if manifest_path.exists():
        with open(manifest_path, 'r') as mf:
            manifest = json.load(mf)

    if not manifest:
        console.print("[yellow]Archive is empty or has no manifest.[/yellow]")
        return

    console.print(Panel.fit(
        "[bold blue]Archive Review[/bold blue]\n"
        "Checking which archived files you've opened since archiving",
        border_style="blue"
    ))

    never_opened = []
    opened_since = []

    with Progress() as progress:
        task = progress.add_task("[cyan]Checking file access dates...", total=len(manifest))

        for filename, info in manifest.items():
            progress.update(task, advance=1)
            file_path = archive_dir / filename
            if not file_path.exists():
                continue

            # Manifest stamps are naive local time; make them timezone-aware before comparing
            archived_on = datetime.fromisoformat(info["archived_on"]).astimezone()

            # Get macOS "last used" date via mdls
            try:
                result = subprocess.run(
                    ["mdls", "-name", "kMDItemLastUsedDate", "-raw", str(file_path)],
                    capture_output=True, text=True, timeout=5
                )
                raw = result.stdout.strip()

                if raw and raw != "(null)":
                    # Parse "2026-03-15 14:30:00 +0000" including its UTC offset
                    last_used = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S %z")
                    if last_used > archived_on:
                        opened_since.append((filename, info, last_used))
                        continue
            except (subprocess.TimeoutExpired, ValueError):
                pass

            never_opened.append((filename, info))

    # Display results
    if never_opened:
        table = Table(title=f"Never Opened Since Archived ({len(never_opened)} files)")
        table.add_column("File", style="red", no_wrap=False)
        table.add_column("Size", style="green")
        table.add_column("Archived", style="yellow")
        table.add_column("Original Location", style="dim")

        total_size = 0
        for filename, info in never_opened:
            size = info.get("size", 0)
            total_size += size
            archived_date = info["archived_on"][:10]
            table.add_row(
                filename,
                humanize.naturalsize(size),
                archived_date,
                Path(info.get("original_path", "")).name
            )

        console.print(table)
        console.print(f"[bold]Safe to delete: {humanize.naturalsize(total_size)}[/bold]\n")

        if not dry_run:
            if questionary.confirm("Delete these never-opened files?", default=False).ask():
                for filename, info in track(never_opened, description="Deleting"):
                    file_path = archive_dir / filename
                    try:
                        send2trash(str(file_path))
                        del manifest[filename]
                    except Exception as e:
                        console.print(f"[red]Error deleting {filename}: {e}[/red]")

                # Update manifest
                with open(manifest_path, 'w') as mf:
                    json.dump(manifest, mf, indent=2)
                console.print(f"[green]✓ Deleted {len(never_opened)} unused files.[/green]")
        else:
            console.print(f"[bold yellow]DRY RUN: Would delete {len(never_opened)} files[/bold yellow]")
    else:
        console.print("[green]All archived files have been opened at least once — nothing to delete.[/green]")

    if opened_since:
        table = Table(title=f"Opened Since Archived ({len(opened_since)} files)")
        table.add_column("File", style="cyan", no_wrap=False)
        table.add_column("Size", style="green")
        table.add_column("Last Opened", style="blue")

        for filename, info, last_used in opened_since:
            table.add_row(
                filename,
                humanize.naturalsize(info.get("size", 0)),
                last_used.astimezone().strftime("%Y-%m-%d")
            )

        console.print(table)
        console.print("[dim]These files were used — consider moving them back to Downloads or keeping them.[/dim]\n")


@click.command()
@click.option('--dry-run', is_flag=True, help='Show what would be done without doing it')
@click.option('--path', help='Custom downloads path (default: ~/Downloads)')
@click.option('--mode', type=click.Choice(['clean', 'organize', 'both', 'review-archive']), default='both',
              help='Operation mode: clean, organize, both, or review-archive')
def main(dry_run: bool, path: Optional[str], mode: str):
    """Smart Downloads folder cleanup and organization tool"""
    downloads_path = Path(path or os.path.expanduser("~/Downloads"))

    if mode == "review-archive":
        review_archive(downloads_path, dry_run=dry_run)
        return

    # Warn if AI features won't work (but don't crash — rule-based cleanup still works)
    if not os.getenv("OPENAI_API_KEY"):
        console.print("[yellow]Note: OPENAI_API_KEY not set — AI categorization disabled. Rule-based cleanup will still work.[/yellow]\n")

    # Display header
    console.print(Panel.fit(
        "[bold blue]Downloads Cleanup & Organization Tool[/bold blue]\n"
        "Intelligently analyze, clean, and organize your Downloads folder",
        border_style="blue"
    ))

    # Initialize cleaner
    cleaner = DownloadsCleaner(path)

    # Check if downloads folder exists
    if not cleaner.downloads_path.exists():
        console.print(f"[red]Downloads folder not found: {cleaner.downloads_path}[/red]")
        sys.exit(1)

    # Run cleanup process
    cleaner.scan_downloads()
    console.print(f"\nFound [bold]{len(cleaner.file_infos)}[/bold] files")

    if not cleaner.file_infos:
        console.print("[green]Downloads folder is already clean![/green]")
        return

    cleaner.categorize_files()

    if mode == "both":
        mode_choice = questionary.select(
            "What would you like to do?",
            choices=[
                {"name": "Organize files into folders", "value": "organize"},
                {"name": "Clean up (delete) files", "value": "clean"},
                {"name": "Both (organize some, delete others)", "value": "both"}
            ]
        ).ask()

        if mode_choice == "both":
            selections = cleaner.display_recommendations("organize")
        else:
            selections = cleaner.display_recommendations(mode_choice)
    else:
        selections = cleaner.display_recommendations(mode)

    cleaner.process_files(selections, dry_run=dry_run)

if __name__ == "__main__":
    main()