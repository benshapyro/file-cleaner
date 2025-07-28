# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Set up virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the tool (dry-run mode recommended first)
python cleanup_downloads.py --dry-run
python cleanup_downloads.py --mode organize
python cleanup_downloads.py --mode clean

# Run tests
python quick_test.py         # Basic setup verification
python test_structured_outputs.py  # Test AI model integration
```

## Architecture Overview

**File Cleaner** is a macOS terminal tool for organizing and cleaning Downloads folders using AI-powered categorization. The codebase follows a single-module design with clear separation of concerns:

### Core Components

- **cleanup_downloads.py**: Main application entry point with `DownloadsCleaner` class
  - Parallel file scanning using ThreadPoolExecutor
  - Rule-based categorization with AI fallback for ambiguous files
  - Interactive CLI using Rich and Questionary libraries

- **config.py**: Central configuration hub
  - Safety rules (7 layers of protection)
  - File categorization patterns and extensions
  - AI model settings (uses GPT-4o-mini for cost efficiency)
  - Critical files protection lists

- **duplicate_detector.py**: (TODO) Duplicate detection logic - not yet integrated

### Key Design Patterns

1. **Safety-First Architecture**: Multiple protection layers before any file operation
   - Critical extension blocking (`.key`, `.pem`, `.env`)
   - Pattern-based protection ("important", "password", etc.)
   - Minimum age requirements per file type
   - All deletions go to Trash, never permanent

2. **AI Integration**: OpenAI Structured Outputs for reliable categorization
   - Batch processing (20 files at a time)
   - Confidence scoring for AI decisions
   - Fallback to rule-based categorization

3. **Parallel Processing**: File scanning uses thread pools for performance
   - 8 worker threads for concurrent stat operations
   - Progress tracking with Rich progress bars

## Environment Setup

Create a `.env` file with:
```
OPENAI_API_KEY=your_api_key_here
```

## Critical Safety Rules

When modifying the code, maintain these safety invariants:

1. **Never permanently delete files** - Always use `send2trash`
2. **Respect all 7 safety layers** in `config.py`
3. **Default to conservative** - When in doubt, don't delete
4. **Log all operations** - Create detailed logs for accountability

## Testing Approach

Test files simulate various scenarios:
- `quick_test.py`: Verifies basic setup and dependencies
- `test_structured_outputs.py`: Tests AI model integration and response parsing

When adding features, create corresponding test files to verify functionality before integration.