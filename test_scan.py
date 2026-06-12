#!/usr/bin/env python3
"""
Test script to scan Downloads folder and show categorization without interactive prompts
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import humanize
from rich.console import Console
from rich.table import Table
from config import *

console = Console()

def scan_downloads():
    """Scan and categorize Downloads folder"""
    downloads_path = Path(os.path.expanduser("~/Downloads"))
    
    if not downloads_path.exists():
        console.print(f"[red]Downloads folder not found: {downloads_path}[/red]")
        return
    
    # Get all files
    files = []
    for item in downloads_path.iterdir():
        if item.is_file() and not item.name.startswith('.'):
            try:
                stat = item.stat()
                files.append({
                    'path': item,
                    'name': item.name,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime),
                    'extension': item.suffix.lower(),
                    'age_days': (datetime.now() - datetime.fromtimestamp(stat.st_mtime)).days
                })
            except:
                pass
    
    console.print(f"\n[bold]Found {len(files)} files in Downloads[/bold]\n")
    
    # Categorize files
    categories = defaultdict(list)
    
    for f in files:
        # Skip protected files
        if f['extension'] in CRITICAL_EXTENSIONS:
            categories['protected'].append(f)
            continue
            
        # Skip files that are too new
        if f['age_days'] < MIN_AGE_FOR_DELETION:
            categories['too_new'].append(f)
            continue
            
        # Categorize by type and age
        if f['age_days'] > OLD_FILE_DAYS:
            categories['old_files'].append(f)
        elif f['extension'] in INSTALLER_EXTENSIONS:
            categories['installers'].append(f)
        elif f['extension'] in ARCHIVE_EXTENSIONS:
            categories['archives'].append(f)
        elif 'screenshot' in f['name'].lower() or 'screen shot' in f['name'].lower():
            categories['screenshots'].append(f)
        elif f['size'] > LARGE_FILE_SIZE:
            categories['large_files'].append(f)
        elif f['extension'] in TEMP_EXTENSIONS:
            categories['temp_files'].append(f)
        elif f['extension'] in DOCUMENT_EXTENSIONS:
            categories['documents'].append(f)
        elif f['extension'] in IMAGE_EXTENSIONS:
            categories['images'].append(f)
        elif f['extension'] in VIDEO_EXTENSIONS:
            categories['videos'].append(f)
        else:
            categories['other'].append(f)
    
    # Display results
    category_info = {
        "protected": ("🔒 Protected Files", "Never delete these"),
        "too_new": ("🆕 Too New", f"Files < {MIN_AGE_FOR_DELETION} days old"),
        "old_files": ("📅 Old Files", f"Files > {OLD_FILE_DAYS} days old"),
        "installers": ("💿 Installers", "Software installers (.dmg, .pkg, etc)"),
        "archives": ("📦 Archives", "Compressed files (.zip, .rar, etc)"),
        "screenshots": ("📸 Screenshots", "Screen captures"),
        "large_files": ("🗄️ Large Files", f"Files > {humanize.naturalsize(LARGE_FILE_SIZE)}"),
        "temp_files": ("🗑️ Temp Files", "Temporary and partial downloads"),
        "documents": ("📄 Documents", "PDFs, Word docs, etc"),
        "images": ("🖼️ Images", "Photos and images"),
        "videos": ("🎬 Videos", "Video files"),
        "other": ("❓ Other", "Uncategorized files")
    }
    
    for category, files_list in categories.items():
        if not files_list:
            continue
            
        title, description = category_info.get(category, (category, ""))
        
        # Calculate total size
        total_size = sum(f['size'] for f in files_list)
        
        # Create table
        table = Table(title=f"{title} ({len(files_list)} files, {humanize.naturalsize(total_size)})")
        table.add_column("File", style="cyan", no_wrap=False, width=50)
        table.add_column("Size", style="green")
        table.add_column("Age", style="yellow")
        table.add_column("Modified", style="blue")
        
        # Show first 5 files
        for f in sorted(files_list, key=lambda x: x['size'], reverse=True)[:5]:
            table.add_row(
                f['name'][:50] + ('...' if len(f['name']) > 50 else ''),
                humanize.naturalsize(f['size']),
                f"{f['age_days']} days",
                f['modified'].strftime("%Y-%m-%d")
            )
        
        if len(files_list) > 5:
            table.add_row("...", f"+ {len(files_list) - 5} more", "", "")
        
        console.print(table)
        console.print(f"[dim]{description}[/dim]\n")
    
    # Summary
    console.print("\n[bold]Summary:[/bold]")
    
    deletable_categories = ['old_files', 'installers', 'archives', 'screenshots', 'temp_files', 'large_files']
    deletable_files = []
    for cat in deletable_categories:
        deletable_files.extend(categories.get(cat, []))
    
    if deletable_files:
        deletable_size = sum(f['size'] for f in deletable_files)
        console.print(f"💾 Potentially deletable: {len(deletable_files)} files ({humanize.naturalsize(deletable_size)})")
    
    organizable_categories = ['documents', 'images', 'videos']
    organizable_files = []
    for cat in organizable_categories:
        organizable_files.extend(categories.get(cat, []))
    
    if organizable_files:
        organizable_size = sum(f['size'] for f in organizable_files)
        console.print(f"📁 Could organize: {len(organizable_files)} files ({humanize.naturalsize(organizable_size)})")
    
    protected_count = len(categories.get('protected', [])) + len(categories.get('too_new', []))
    if protected_count:
        console.print(f"🔒 Protected/Too new: {protected_count} files")

if __name__ == "__main__":
    scan_downloads()