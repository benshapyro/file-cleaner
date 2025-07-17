# File Cleaner 🧹

An intelligent macOS terminal tool that helps you clean and organize files using AI-powered categorization and smart rules. Primarily designed for Downloads folders but configurable for any directory.

## Features

- 🤖 **AI-Powered Categorization** - Uses OpenAI GPT models to intelligently categorize ambiguous files
- 🔒 **7 Layers of Safety** - Multiple protection mechanisms to prevent accidental deletion of important files
- 📁 **Dual Modes** - Choose between cleaning (delete) or organizing (move to folders)
- ⚡ **Parallel Processing** - Fast file scanning with multi-threading
- 🗑️ **Safe Deletion** - All files go to Trash, never permanently deleted
- 📊 **Rich Terminal UI** - Beautiful, interactive interface with progress bars
- 📝 **Detailed Logging** - Track all operations for accountability

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd file-cleaner
   ```

2. **Set up environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure OpenAI API**
   ```bash
   cp env.example .env
   # Edit .env and add your OpenAI API key
   ```

4. **Run the tool**
   ```bash
   # Dry run (see what would happen without making changes)
   python cleanup_downloads.py --dry-run
   
   # Organize files into folders
   python cleanup_downloads.py --mode organize
   
   # Clean up (delete) files
   python cleanup_downloads.py --mode clean
   ```

## Safety Features

The tool includes multiple safety mechanisms:

1. **Critical File Protection** - Never touches .key, .pem, .env, .ssh files
2. **Pattern Protection** - Skips files with keywords like "important", "password", "credentials"
3. **Age Protection** - Default 7-day minimum age before deletion
4. **File Type Rules** - Different minimum ages for different file types
5. **Whitelist** - Specific files that are always protected
6. **Size Filtering** - Ignores tiny files (< 1KB)
7. **Trash Only** - Never permanently deletes, always moves to Trash

## Documentation

- 📖 [Setup Guide](SETUP.md) - Detailed installation and configuration
- 🚀 [Implementation Plan](implementation.md) - Development roadmap and architecture
- 🔮 [Future Features](FUTURE_FEATURES.md) - Planned enhancements and priorities
- 📊 [Performance Guide](PERFORMANCE_OPTIMIZATIONS.md) - Optimization strategies
- 🤖 [Model Selection](MODEL_SELECTION_GUIDE.md) - AI model comparison and selection
- ✅ [Preflight Checklist](PREFLIGHT_CHECKLIST.md) - Pre-run verification steps

## Project Structure

```
file-cleaner/
├── cleanup_downloads.py    # Main application
├── config.py              # Configuration and safety rules
├── duplicate_detector.py  # Duplicate file detection (future integration)
├── requirements.txt       # Python dependencies
├── env.example           # Example environment configuration
└── docs/                 # Documentation files
```

## Testing

Run the test suite:
```bash
# Quick setup verification
python quick_test.py

# Test structured outputs
python test_structured_outputs.py

# Basic functionality tests
python cleanup_downloads.py --dry-run
```

## Contributing

See [FUTURE_FEATURES.md](FUTURE_FEATURES.md) for planned enhancements. Priority features include:
- Smart duplicate detection
- Undo functionality
- Batch processing rules

## Requirements

- Python 3.7+
- macOS (primary platform, Linux/Windows support planned)
- OpenAI API key (for AI features)

## License

This project is open source. See LICENSE file for details.

## Acknowledgments

Built with:
- OpenAI GPT models for intelligent categorization
- Rich for beautiful terminal UI
- Click for CLI framework
- Questionary for interactive prompts

---

**⚠️ Note**: This tool is in active development. Always use `--dry-run` first to preview changes before actual cleanup. 