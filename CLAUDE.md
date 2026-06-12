# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Set up virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the tool (venv currently Python 3.9; code targets 3.9+)
python cleanup_downloads.py --dry-run            # Preview what would happen (recommended first)
python cleanup_downloads.py --mode organize      # Organize files into folders
python cleanup_downloads.py --mode clean         # Clean up (delete) files
python cleanup_downloads.py --mode both          # Interactive choice
python cleanup_downloads.py --mode review-archive # Review _Archive/ for never-opened files (via mdls)

# Run tests
python quick_test.py                       # Setup verification
python test_structured_outputs.py          # Test AI model integration

# Development testing with custom path
python cleanup_downloads.py --path ~/test-downloads --dry-run
```

## Linting and Type Checking

No linting or type checking tools are currently configured. When adding:
- Consider `ruff` for Python linting
- Consider `mypy` for type checking
- Update this section with the commands

## Architecture Overview

**File Cleaner** is a macOS terminal tool for organizing and cleaning Downloads folders using AI-powered categorization.

### Core Components

- **cleanup_downloads.py**: Main application with `DownloadsCleaner` class
  - Uses ThreadPoolExecutor for parallel file scanning (8 workers)
  - AI categorization via OpenAI Structured Outputs API
  - Interactive CLI using Rich (UI) and Questionary (prompts)
  - Click-based command-line interface

- **config.py**: Central configuration and safety rules
  - Protection rules (critical extensions, protected patterns, whitelist) and deletion gates (age/size/type rules)
  - File categorization mappings and extension rules — `ORGANIZATION_FOLDERS` is the single source of truth for organize destinations
  - AI model configuration and `AI_BATCH_SIZE` (files per AI request)

- **duplicate_detector.py**: Hash-based duplicate detection (integrated — runs first in `categorize_files()`)
  - `calculate_file_hash()`: MD5/SHA hash calculation
  - `find_duplicates_by_hash()`: Groups files by size then hash; newest copy is kept, older copies go to the `exact_duplicates` category

### Key Design Decisions

1. **Safety-First**: Two distinct layers, enforced in different places
   - *Protection checks* (critical extensions, protected patterns, whitelist) exclude a file from ALL operations — applied at the top of `categorize_files()`
   - *Deletion gates* (`_is_deletable()`: min age 7 days, per-type age floors, small-file rule) only block DELETE — enforced at the action layer in `process_files()`, so young files can still be organized/archived. Exact duplicates are exempt (a content-identical copy is always kept).
   - Never permanently deletes (uses `send2trash`)

2. **AI Integration**: Structured Outputs for reliable JSON responses
   - All uncategorized files processed in `AI_BATCH_SIZE` batches (no silent cap)
   - Confidence scoring in categorization; only ≥0.7 `safe_to_delete` lands in the `ai_suggested` bucket
   - Degrades gracefully to rule-based categorization when `OPENAI_API_KEY` is unset

3. **Performance**: Parallel processing for file system operations
   - ThreadPoolExecutor with 8 workers
   - Size-based grouping for duplicate detection
   - Progress tracking with Rich progress bars

### File Categorization Flow

1. **Rule-based categorization** (`categorize_files()`)
   - Hash-verified exact duplicates first
   - Screenshots and "(n)" name-pattern duplicates
   - Installers and archives by extension
   - Large files (`LARGE_FILE_SIZE`) and old files (`OLD_FILE_DAYS`) — thresholds live in config.py, not inline
   - Old files split into junk / documents (default action: archive) / media

2. **AI categorization** (`_ai_categorize()`)
   - All remaining uncategorized files, in `AI_BATCH_SIZE` batches
   - Returns structured JSON with categories and confidence

3. **User review** (`display_recommendations()`)
   - Interactive table display per category
   - Choose: Organize, Delete, Archive, or Skip
   - Dry-run mode lists exactly which files each action would touch

4. **Archive lifecycle** (`review_archive()`)
   - Old documents archived to `_Archive/` with a JSON manifest
   - `--mode review-archive` compares macOS `mdls` last-used dates (timezone-aware) against archive dates to find never-opened files

## Environment Variables

Create `.env` file:
```
OPENAI_API_KEY=your_api_key_here
```

## Testing Approach

- **quick_test.py**: Verifies environment, dependencies, and basic file operations
- **test_structured_outputs.py**: Tests OpenAI API integration and response parsing
- Manual testing: Use `--dry-run` flag and `--path` for test directories

## Critical Safety Invariants

When modifying code, maintain these safety rules:

1. **Always use `send2trash`** - Never use `os.remove()` or `shutil.rmtree()`
2. **Keep both safety layers intact** - Protection checks in `categorize_files()` exclude files entirely; `_is_deletable()` gates must be enforced wherever DELETE executes (`process_files()`)
3. **Default to conservative** - When uncertain, skip the file
4. **Maintain detailed logs** - All operations logged with timestamps to `LOG_DIRECTORY` (outside Downloads)