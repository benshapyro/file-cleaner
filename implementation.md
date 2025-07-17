# Downloads Cleanup Script Implementation Plan

## Recent Updates (April 2025)

### Performance & API Enhancements
- ✅ **Migrated to GPT-4.1 Mini**: 83% cost reduction, 1M token context, half the latency
- ✅ **Implemented Structured Outputs**: Replaced JSON mode with strict schema adherence
- ✅ **Added Parallel File Scanning**: Using ThreadPoolExecutor with 8 workers
- ✅ **Enhanced AI Analysis**: Added confidence scores (0-1) and detailed reasoning
- ✅ **Improved Error Handling**: Better handling of AI refusals and edge cases

### Technical Improvements
- Using `response_format` with `json_schema` and `strict: true`
- Parallel processing reduces scan time for large directories
- AI provides confidence scores for each categorization
- Only suggests deletion when confidence >= 0.7

## Overview
A smart terminal-based tool to analyze and clean up the Downloads folder on macOS using OpenAI's API for intelligent file categorization.

## API Implementation Status (Updated 2025)

### OpenAI API Best Practices
- [x] Updated to latest models (gpt-4o-mini) - Done
  Using best value model with excellent performance
- [x] Implemented response_format for JSON - Done
  Ensures reliable JSON parsing from AI responses
- [x] Added comprehensive safety features - Done
  Time-based protection, whitelisting, protected patterns
- [x] Following latest function calling guidelines - Done
  Clear prompts, structured responses, error handling

### Current API Details
- **API Type**: Chat Completions API (stable, supported indefinitely)
- **Model**: gpt-4o-mini (best value as of 2025)
- **Safety**: Multiple layers of protection before any deletion
- **Cost**: Typical session < $0.01

## Implementation Steps

### Phase 1: Project Setup
- [x] Initialize Python project structure - Done
  Created project with proper file structure and dependencies
- [x] Create requirements.txt with dependencies - Done  
  Added all necessary packages including OpenAI, Rich, Click, etc.
- [x] Set up configuration for OpenAI API - Done
  Created config.py with all settings and environment variable support
- [x] Create main script file - Done
  Implemented cleanup_downloads.py with full basic functionality

### Phase 2: File Analysis Module
- [x] Implement Downloads folder scanner - Done
  Scans and collects metadata for all files
- [x] Create file metadata collector (name, size, created date, type) - Done
  FileInfo dataclass with all metadata
- [x] Build file categorization logic - Done
  Rule-based categorization for multiple file types
- [x] Implement duplicate detection - Done
  Basic duplicate detection by filename patterns

### Phase 3: AI Integration
- [x] Set up OpenAI API client - Done
  Integrated with error handling
- [x] Design prompts for file analysis - Done
  Structured prompts for consistent categorization
- [x] Implement batch processing for efficiency - Done
  Processes up to 20 files per API call
- [x] Create AI response parser - Done
  JSON parsing with fallback handling

### Phase 4: User Interface
- [x] Build terminal UI with rich/colorama - Done
  Beautiful tables and progress bars
- [x] Implement file listing with categories - Done
  Category-based display with metadata
- [x] Create interactive selection mechanism - Done
  Added organize/delete/skip options
- [x] Add confirmation prompts - Done
  Multiple levels of confirmation for safety

### Phase 5: Cleanup Actions
- [x] Implement safe deletion (move to trash) - Done
  Using send2trash for recoverable deletion
- [x] Create action logging - Done
  Detailed logs saved to Downloads folder
- [x] Add dry-run mode - Done
  Preview mode without actual changes
- [x] Build organization functionality - Done
  Files can be organized into folders instead of deletion

### Phase 6: Configuration & Safety
- [x] Add configuration file support - Done
  Comprehensive config.py with all settings
- [x] Implement file type whitelisting - Done
  Added WHITELIST_FILES and protected patterns
- [x] Create age-based rules - Done
  MIN_AGE_FOR_DELETION prevents deleting files < 7 days old
- [x] Add size thresholds - Done
  LARGE_FILE_SIZE and other thresholds configured

### Phase 6.5: Enhanced Safety Rules
- [x] Critical file type protection - Done
  Never suggest .key, .pem, .env, .ssh, .gpg files
- [x] Small file filtering - Done
  Skip files under 1KB to focus on space-saving
- [x] File type specific age rules - Done
  Different file types have different minimum ages
- [x] Comprehensive safety checks - Done
  Multiple layers of protection before any suggestion

### Phase 7: Testing & Polish
- [x] Add comprehensive error handling - Done
  Try/except blocks throughout
- [ ] Create unit tests
- [x] Add progress indicators - Done
  Rich progress bars for all operations
- [ ] Implement verbose/quiet modes

## Feature Priorities (Based on Value vs Difficulty)

### Already Implemented
1. **File Organization** - Move files to organized folders instead of deleting

### Recommended Priority Order
1. **Additional Safety** (High Value, Low Difficulty)
   - Time-based protection (never delete < 7 days)
   - Whitelist patterns and files
   - Backup before delete option

2. **Enhanced Duplicate Detection** (High Value, Medium Difficulty)
   - MD5/SHA hash comparison
   - Content-based duplicate finding

3. **Custom Rules** (Medium Value, Low Difficulty)
   - Per-file-type rules
   - User-defined categories
   - Custom organization schemes

4. **Performance Optimizations** (Medium Value, Medium Difficulty)
   - Parallel file scanning
   - AI response caching
   - Progressive loading

5. **Smarter AI Integration** (High Value, High Difficulty)
   - Content analysis for documents
   - GPT-4 Vision for images
   - Better batch optimization

## Key Design Decisions

### File Analysis Approach
1. **Quick scan**: First pass to collect basic metadata
2. **Smart analysis**: Use AI for suspicious/unclear files
3. **Content peek**: For text files, analyze first few lines
4. **Binary safety**: Never send binary content to AI

### AI Usage Strategy
- Batch multiple files in single API calls for efficiency
- Use structured prompts for consistent responses
- Fallback to rule-based logic if API fails

### Safety First
- All deletions go to Trash, not permanent delete
- Require explicit confirmation for each category
- Never touch system files or hidden files by default
- Keep detailed logs of all actions 