"""
Enhanced duplicate detection using file hashing
"""

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
from collections import defaultdict

def calculate_file_hash(file_path: Path, algorithm: str = 'md5', chunk_size: int = 8192) -> str:
    """
    Calculate hash of a file using specified algorithm.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm ('md5', 'sha1', 'sha256')
        chunk_size: Size of chunks to read at a time
    
    Returns:
        Hex digest of the file hash
    """
    hash_func = getattr(hashlib, algorithm)()
    
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(chunk_size):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    except (IOError, OSError) as e:
        raise Exception(f"Error reading file {file_path}: {e}")

def find_duplicates_by_hash(file_paths: List[Path], min_size: int = 1024) -> Dict[str, List[Path]]:
    """
    Find duplicate files by comparing their hashes.
    
    Args:
        file_paths: List of file paths to check
        min_size: Minimum file size to hash (skip small files for performance)
    
    Returns:
        Dictionary mapping hash to list of duplicate file paths
    """
    # First, group files by size (optimization - only same-size files can be duplicates)
    size_groups = defaultdict(list)
    
    for file_path in file_paths:
        try:
            size = file_path.stat().st_size
            if size >= min_size:  # Skip very small files
                size_groups[size].append(file_path)
        except OSError:
            continue
    
    # Now hash only files that have the same size
    hash_groups = defaultdict(list)
    
    for size, paths in size_groups.items():
        if len(paths) < 2:  # No duplicates possible
            continue
            
        for file_path in paths:
            try:
                file_hash = calculate_file_hash(file_path)
                hash_groups[file_hash].append(file_path)
            except Exception:
                continue
    
    # Return only groups with actual duplicates
    return {
        hash_val: paths 
        for hash_val, paths in hash_groups.items() 
        if len(paths) > 1
    }

def find_duplicates_by_name_pattern(file_paths: List[Path]) -> Dict[str, List[Path]]:
    """
    Find files that appear to be duplicates based on naming patterns.
    E.g., "document.pdf", "document (1).pdf", "document (2).pdf"
    
    Args:
        file_paths: List of file paths to check
    
    Returns:
        Dictionary mapping base name to list of potential duplicate paths
    """
    name_groups = defaultdict(list)
    
    for file_path in file_paths:
        name = file_path.name
        stem = file_path.stem
        suffix = file_path.suffix
        
        # Remove common duplicate patterns
        base_name = stem
        for pattern in [r' \(\d+\)', r' - Copy', r' copy', r'_\d+$']:
            base_name = re.sub(pattern, '', base_name, flags=re.IGNORECASE)
        
        # Group by base name + extension
        key = f"{base_name}{suffix}".lower()
        name_groups[key].append(file_path)
    
    # Return only groups with potential duplicates
    return {
        name: paths 
        for name, paths in name_groups.items() 
        if len(paths) > 1
    }

def analyze_duplicate_sets(duplicates: Dict[str, List[Path]]) -> List[Tuple[Path, List[Path]]]:
    """
    Analyze duplicate sets and recommend which to keep.
    
    Args:
        duplicates: Dictionary of hash -> list of duplicate paths
    
    Returns:
        List of tuples (file_to_keep, files_to_remove)
    """
    recommendations = []
    
    for hash_val, paths in duplicates.items():
        # Sort by various criteria to find the "best" file to keep
        sorted_paths = sorted(paths, key=lambda p: (
            # Prefer files NOT in Downloads
            'downloads' not in str(p).lower(),
            # Prefer files with cleaner names (no (1), (2), etc)
            not any(f'({i})' in p.name for i in range(10)),
            # Prefer newest files (most recent version)
            -p.stat().st_mtime
        ))
        
        keep = sorted_paths[0]
        remove = sorted_paths[1:]
        
        recommendations.append((keep, remove))
    
    return recommendations

def get_duplicate_summary(duplicates: Dict[str, List[Path]]) -> Dict[str, Any]:
    """
    Get summary statistics about duplicates found.
    
    Args:
        duplicates: Dictionary of hash -> list of duplicate paths
    
    Returns:
        Summary dictionary with statistics
    """
    total_duplicates = sum(len(paths) - 1 for paths in duplicates.values())
    total_size_wasted = 0
    
    for paths in duplicates.values():
        if len(paths) > 1:
            file_size = paths[0].stat().st_size
            total_size_wasted += file_size * (len(paths) - 1)
    
    return {
        'duplicate_sets': len(duplicates),
        'total_duplicate_files': total_duplicates,
        'space_wasted_bytes': total_size_wasted,
        'potential_space_savings': humanize.naturalsize(total_size_wasted) if 'humanize' in globals() else f"{total_size_wasted} bytes"
    }

# Example usage in main cleanup script:
"""
# In the categorize_files method:
if config.CHECK_DUPLICATES_BY_HASH:
    duplicates = find_duplicates_by_hash(
        [f.path for f in self.file_infos],
        min_size=config.DUPLICATE_MIN_SIZE
    )
    
    for hash_val, duplicate_paths in duplicates.items():
        # Skip the first file (keep it), mark others as duplicates
        for dup_path in duplicate_paths[1:]:
            file_info = next((f for f in self.file_infos if f.path == dup_path), None)
            if file_info:
                self.categories["exact_duplicates"].append(file_info)
""" 