# Historical preflight checklist

> Use `file-cleaner doctor`, `file-cleaner scan`, and the current README instead. This is retained only for prototype history.

## Setup Requirements

### 1. Environment Setup ✅
- [ ] Copy `env.example` to `.env`
  ```bash
  cp env.example .env
  ```
- [ ] Add your OpenAI API key to `.env` file
  ```bash
  # Edit .env and replace 'your_openai_api_key_here' with actual key
  ```
- [ ] Get API key from: https://platform.openai.com/api-keys

### 2. Dependencies Installation ✅
- [ ] Install all required packages:
  ```bash
  pip install -r requirements.txt
  ```

### 3. Model Availability Check 🔍
- [ ] **Important**: GPT-4.1 Mini might not be available yet (released April 2025)
- [ ] If GPT-4.1 Mini is not available, fall back to `gpt-4o-mini` in `config.py`:
  ```python
  AI_MODEL = "gpt-4o-mini"  # Change from "gpt-4.1-mini" if not available
  ```

### 4. Test Components ✅

#### a. Test Structured Outputs
```bash
python test_structured_outputs.py
```
Expected: Should categorize 5 sample files with confidence scores

#### b. Test Basic Functionality (Dry Run)
```bash
python cleanup_downloads.py --dry-run
```
Expected: Should scan files without making any changes

#### c. Test File Organization Mode
```bash
python cleanup_downloads.py --mode organize --dry-run
```
Expected: Should show organization suggestions without moving files

### 5. Safety Checks ✅
- [ ] Verify critical files are protected:
  - Files with extensions: .key, .pem, .env, .ssh, .gpg, .license
  - Files with patterns: password, credentials, important, backup
- [ ] Check minimum age protection (default: 7 days)
- [ ] Confirm all deletions go to Trash (not permanent)

### 6. Performance Verification ✅
- [ ] Monitor parallel file scanning (should see progress bar)
- [ ] Check API response times
- [ ] Verify structured output parsing (no JSON errors)

## Common Issues & Solutions

### Issue 1: Model Not Found
**Error**: `The model 'gpt-4.1-mini' does not exist`
**Solution**: Change to `gpt-4o-mini` in config.py

### Issue 2: API Key Invalid
**Error**: `Incorrect API key provided`
**Solution**:
1. Check `.env` file exists (not just `env.example`)
2. Verify API key is correct and has no extra spaces
3. Ensure API key has proper permissions

### Issue 3: Import Errors
**Error**: `ModuleNotFoundError`
**Solution**: Run `pip install -r requirements.txt` again

### Issue 4: Permission Denied
**Error**: `Permission denied` when accessing Downloads
**Solution**:
1. Check file permissions: `ls -la ~/Downloads`
2. Run with proper permissions or change download path

### Issue 5: Structured Output Error
**Error**: `Invalid schema` or parsing errors
**Solution**: The API might not support structured outputs yet, fallback to JSON mode:
```python
response_format = {"type": "json_object"}  # Instead of json_schema
```

## Quick Test Script

Create `quick_test.py`:
```python
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Test 1: API Key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key or api_key == "your_openai_api_key_here":
    print("❌ API key not configured properly")
else:
    print("✅ API key found")

# Test 2: OpenAI Connection
try:
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Use known working model
        messages=[{"role": "user", "content": "Say 'API working'"}],
        max_tokens=10,
    )
    print("✅ OpenAI API connection successful")
except Exception as e:
    print(f"❌ OpenAI API error: {e}")

# Test 3: File Access
downloads = os.path.expanduser("~/Downloads")
if os.path.exists(downloads) and os.access(downloads, os.R_OK):
    print("✅ Downloads folder accessible")
    file_count = len([f for f in os.listdir(downloads) if not f.startswith(".")])
    print(f"   Found {file_count} files")
else:
    print("❌ Cannot access Downloads folder")
```

## Ready to Run Checklist

- [ ] `.env` file created with valid API key
- [ ] All dependencies installed
- [ ] Model availability confirmed (or fallback configured)
- [ ] Test script runs successfully
- [ ] Dry run completes without errors

## First Real Run

When ready, start with organization mode to be safe:
```bash
python cleanup_downloads.py --mode organize
```

Then try cleanup mode with careful review:
```bash
python cleanup_downloads.py --mode clean
```
