# Downloads Cleanup Tool - Setup Guide

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up OpenAI API Key
Create a `.env` file in the project directory:
```bash
echo "OPENAI_API_KEY=your_api_key_here" > .env
```

Get your API key from: https://platform.openai.com/api-keys

### 3. Make Script Executable
```bash
chmod +x cleanup_downloads.py
```

### 4. Run the Tool
```bash
# Basic usage - asks whether to clean, organize, or both
python cleanup_downloads.py

# Clean mode only (delete files)
python cleanup_downloads.py --mode clean

# Organize mode only (sort files into folders)
python cleanup_downloads.py --mode organize

# Both modes (default)
python cleanup_downloads.py --mode both

# Dry run - see what would happen without making changes
python cleanup_downloads.py --dry-run

# Custom path
python cleanup_downloads.py --path /path/to/folder
```

## Model Selection & Costs

The tool uses OpenAI's API for intelligent file analysis. By default, it uses **gpt-4o-mini** which offers the best balance of performance and cost.

### Available Models (as of 2025)
- **gpt-4o-mini** (default) - Best value, ~$0.15 per 1M input tokens
- **gpt-3.5-turbo** - Cheapest option, basic performance
- **gpt-4o** - Premium performance, higher cost
- **o4-mini** - Advanced reasoning, good value
- **o3** - Best reasoning, highest cost

To change the model, edit `config.py`:
```python
AI_MODEL = "gpt-4o-mini"  # Change to your preferred model
```

### Estimated Costs
- Typical cleanup session: < $0.01
- Large folder (1000+ files): ~$0.05-0.10
- The AI only analyzes file names and metadata, not contents

## How It Works

### Cleanup Mode
1. **Scans** your Downloads folder for all files
2. **Categorizes** files using smart rules:
   - Old files (>30 days)
   - Installers (.dmg, .pkg, etc.)
   - Archives (.zip, .rar, etc.) 
   - Screenshots
   - Duplicates (files with (1), (2) in names)
   - Large files (>100MB)
3. **Uses AI** to analyze ambiguous files
4. **Shows recommendations** in organized categories
5. **Asks for confirmation** before moving files to trash
6. **Creates a log** of all actions taken

### Organization Mode
1. **Analyzes** all files in Downloads
2. **Suggests organization** into folders:
   - `_Organized/Documents/` - PDFs, Word docs, etc.
   - `_Organized/Images/` - Photos and graphics
   - `_Organized/Videos/` - Video files
   - `_Organized/Archives/` - Zip files and archives
   - `_Organized/Screenshots/` - Screen captures
   - `_Organized/Old_Downloads/` - Files older than 30 days
   - And more...
3. **Lets you choose** per category: Organize, Delete, or Skip
4. **Handles duplicates** by renaming with _1, _2, etc.
5. **Creates organized structure** within Downloads folder

## Safety Features

- Files are moved to **Trash**, not permanently deleted
- **Multiple confirmations** required before any action
- **Detailed log file** created in Downloads folder
- **Hidden files** are ignored by default
- **Dry run mode** to preview without making changes
- **Protected patterns** - never touches important files
- **Time protection** - won't delete very recent files
- **Critical file types** - never suggests deleting .key, .pem, .env, etc.
- **Small file protection** - ignores files under 1KB (configurable)
- **File type age rules** - different minimum ages for different file types

## Configuration

Edit `config.py` to customize:
- File age thresholds
- Size limits
- Protected file patterns
- Organization folder structure
- AI model settings
- File type categories

## Tips

- Start with `--dry-run` to see what would happen
- Use organization mode to sort files without deleting
- The tool is conservative - it won't do anything without your approval
- Check the log file after operations to see what was done
- Files in Trash can be restored if needed
- Organized files go into `_Organized/` subfolder in Downloads

## Example Output

```
Downloads Cleanup & Organization Tool
Intelligently analyze, clean, and organize your Downloads folder

Scanning Downloads folder...
Found 127 files

What would you like to do?
> Organize files into folders
  Clean up (delete) files  
  Both (organize some, delete others)

Screenshots (23 files)
├── Screenshot 2024-01-15.png    2.3 MB    5 days
├── Screenshot 2024-01-14.png    1.8 MB    6 days
└── ... + 21 more files
Total size: 48.2 MB

What would you like to do with these screenshots?
> Organize into folders
  Delete
  Skip
``` 