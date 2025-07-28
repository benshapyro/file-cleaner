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
# from duplicate_detector import DuplicateDetector  # TODO: Implement class or use functions directly
import logging

# Load environment variables
load_dotenv()

console = Console()

class ActionType(Enum):
    DELETE = "delete"
    ORGANIZE = "organize"
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
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.file_infos: List[FileInfo] = []
        self.categories: Dict[str, List[FileInfo]] = defaultdict(list)
        
        # Organization folders
        self.org_folders = {
            "Documents": ['.pdf', '.doc', '.docx', '.txt', '.odt', '.rtf'],
            "Images": ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.bmp', '.webp'],
            "Videos": ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv'],
            "Archives": ['.zip', '.rar', '.7z', '.tar', '.gz'],
            "Installers": ['.dmg', '.pkg', '.exe', '.msi', '.app'],
            "Screenshots": [],  # Based on filename
            "Old_Downloads": []  # Files > 30 days
        }
        
    def scan_downloads(self) -> None:
        """Scan downloads folder and collect file information using parallel processing"""
        console.print("[bold blue]Scanning Downloads folder...[/bold blue]")
        
        # Get all items in the downloads folder
        items = [item for item in self.downloads_path.iterdir() if item.is_file() and not item.name.startswith('.')]
        
        # Use parallel processing to scan files
        with Progress() as progress:
            task = progress.add_task("[cyan]Scanning files...", total=len(items))
            
            with ThreadPoolExecutor(max_workers=8) as executor:
                # Submit all file scanning tasks
                future_to_item = {executor.submit(self._scan_single_file, item): item for item in items}
                
                # Process completed tasks
                for future in as_completed(future_to_item):
                    progress.update(task, advance=1)
                    file_info = future.result()
                    if file_info:
                        self.file_infos.append(file_info)
        
        console.print(f"[green]✓ Scanned {len(self.file_infos)} files[/green]")
    
    def _scan_single_file(self, item: Path) -> Optional[FileInfo]:
        """Scan a single file and return FileInfo or None if error"""
        try:
            stat = item.stat()
            return FileInfo(
                path=item,
                name=item.name,
                size=stat.st_size,
                modified_time=datetime.fromtimestamp(stat.st_mtime),
                created_time=datetime.fromtimestamp(stat.st_ctime),
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
    
    def categorize_files(self) -> None:
        """Categorize files using rules and AI"""
        console.print("\n[bold blue]Analyzing files...[/bold blue]")
        
        # Import safety settings from config
        import config
        
        # Rule-based categorization first
        for file_info in self.file_infos:
            # Safety check: Skip critical file types
            if file_info.extension in config.CRITICAL_EXTENSIONS:
                console.print(f"[yellow]Skipping critical file: {file_info.name}[/yellow]")
                continue
            
            # Safety check: Skip protected files
            if any(pattern.lower() in file_info.name.lower() for pattern in config.PROTECTED_PATTERNS):
                continue
            
            # Safety check: Skip whitelisted files
            if file_info.name.lower() in [f.lower() for f in config.WHITELIST_FILES]:
                continue
            
            # Safety check: Apply file type specific rules
            if file_info.extension in config.FILE_TYPE_RULES:
                min_age, never_delete = config.FILE_TYPE_RULES[file_info.extension]
                if never_delete or file_info.age_days < min_age:
                    continue
            
            # Safety check: Skip files newer than minimum age
            if file_info.age_days < config.MIN_AGE_FOR_DELETION:
                continue
            
            # Skip very small files if configured
            if config.IGNORE_SMALL_FILES and file_info.size < config.MIN_FILE_SIZE:
                continue
            
            # Old files
            if file_info.age_days > 30:
                self.categories["old_files"].append(file_info)
            
            # Installers and disk images
            if file_info.extension in ['.dmg', '.pkg', '.exe', '.msi', '.deb', '.rpm']:
                self.categories["installers"].append(file_info)
            
            # Archives
            if file_info.extension in ['.zip', '.rar', '.7z', '.tar', '.gz']:
                self.categories["archives"].append(file_info)
            
            # Screenshots
            if 'screenshot' in file_info.name.lower() or 'screen shot' in file_info.name.lower():
                self.categories["screenshots"].append(file_info)
            
            # Duplicates (simple version - files with (1), (2) etc in name)
            if any(f'({i})' in file_info.name for i in range(1, 10)):
                self.categories["duplicates"].append(file_info)
            
            # Large files (> 100MB)
            if file_info.size > 100 * 1024 * 1024:
                self.categories["large_files"].append(file_info)
        
        # Use AI for uncategorized or ambiguous files
        uncategorized = [f for f in self.file_infos if not any(f in files for files in self.categories.values())]
        if uncategorized:
            self._ai_categorize(uncategorized[:20])  # Limit to first 20 for demo
    
    def _ai_categorize(self, files: List[FileInfo]) -> None:
        """Use AI to analyze and categorize files with Structured Outputs"""
        if not AI_ENABLED:
            return
            
        try:
            file_list = "\n".join([f"- {f.name} ({f.size_human}, {f.age_days} days old, type: {f.category})" 
                                  for f in files])
            
            prompt = f"""Analyze these files from a Downloads folder and categorize each one.
Consider file age, type, and name patterns. Provide confidence score (0-1) and reasoning.

Categories:
- safe_to_delete: temporary files, old downloads, cache files, installers over 30 days old
- might_be_important: documents that might be needed, recent work files, projects
- keep: clearly important files, personal documents, active projects

Files to analyze:
{file_list}"""

            response = self.client.chat.completions.create(
                model=AI_MODEL,  # Using GPT-4.1 Mini from config
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
            categorizations = result.get("categorizations", {})
            
            console.print("[cyan]AI Analysis Results:[/cyan]")
            for file_info in files:
                if file_info.name in categorizations:
                    cat_info = categorizations[file_info.name]
                    category = cat_info["category"]
                    confidence = cat_info["confidence"]
                    reason = cat_info["reason"]
                    
                    # Only add to AI suggested if confidence is high enough
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
        
        category_info = {
            "old_files": ("Old Files (>30 days)", "Files that haven't been modified in over a month"),
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
            
            category_size = 0
            for f in files[:10]:  # Show first 10
                table.add_row(
                    f.name,
                    f.size_human,
                    f"{f.age_days} days",
                    f.modified_time.strftime("%Y-%m-%d")
                )
                category_size += f.size
            
            if len(files) > 10:
                table.add_row("...", f"+ {len(files) - 10} more files", "", "")
            
            console.print(table)
            console.print(f"[dim]{description}[/dim]")
            console.print(f"Total size: [bold]{humanize.naturalsize(category_size)}[/bold]\n")
            
            # Ask user what to do with this category
            if mode == "organize":
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
        
        if file_info.age_days > 30:
            return self.downloads_path / "_Organized" / "Old_Downloads"
        
        # Default to category-based folder
        category_folders = {
            "old_files": "Old_Downloads",
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
        
        for category, (files, action) in selections.items():
            if action == ActionType.DELETE:
                delete_files.extend(files)
            elif action == ActionType.ORGANIZE:
                organize_files.extend([(f, category) for f in files])
        
        if dry_run:
            if delete_files:
                console.print(f"\n[bold yellow]DRY RUN: Would delete {len(delete_files)} files[/bold yellow]")
            if organize_files:
                console.print(f"[bold yellow]DRY RUN: Would organize {len(organize_files)} files[/bold yellow]")
            return
        
        # Final confirmation
        actions = []
        if delete_files:
            actions.append(f"delete {len(delete_files)} files")
        if organize_files:
            actions.append(f"organize {len(organize_files)} files")
        
        if not questionary.confirm(
            f"Are you sure you want to {' and '.join(actions)}?", 
            default=False
        ).ask():
            console.print("[yellow]Operation cancelled.[/yellow]")
            return
        
        # Create log file
        log_path = self.downloads_path / f"cleanup_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
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
        
        console.print(f"\n[bold green]✓ Operation complete![/bold green]")
        if delete_files:
            console.print(f"Moved {len(delete_files)} files to trash.")
        if organize_files:
            console.print(f"Organized {len(organize_files)} files into folders.")
        console.print(f"Log saved to: {log_path.name}")

@click.command()
@click.option('--dry-run', is_flag=True, help='Show what would be done without doing it')
@click.option('--path', help='Custom downloads path (default: ~/Downloads)')
@click.option('--mode', type=click.Choice(['clean', 'organize', 'both']), default='both', 
              help='Operation mode: clean (delete only), organize (move only), or both')
def main(dry_run: bool, path: Optional[str], mode: str):
    """Smart Downloads folder cleanup and organization tool"""
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        console.print("[bold red]Error: OPENAI_API_KEY environment variable not set![/bold red]")
        console.print("Please set it in a .env file or export it in your terminal.")
        sys.exit(1)
    
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
        # Ask user preference
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