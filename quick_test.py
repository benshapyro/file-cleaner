#!/usr/bin/env python3
"""Quick test script to verify Downloads Cleanup Tool setup"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("🔍 Downloads Cleanup Tool - Setup Verification\n")

# Test 1: Python Version
print("1. Python Version Check:")
python_version = sys.version_info
if python_version.major >= 3 and python_version.minor >= 7:
    print(f"   ✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
else:
    print(f"   ❌ Python {python_version.major}.{python_version.minor} (Need 3.7+)")

# Test 2: API Key
print("\n2. API Key Check:")
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("   ❌ OPENAI_API_KEY not found in environment")
    print("   💡 Create .env file: cp env.example .env")
elif api_key == "your_openai_api_key_here":
    print("   ❌ API key not configured (still using placeholder)")
    print("   💡 Edit .env and add your actual API key")
else:
    print(f"   ✅ API key found ({api_key[:8]}...)")

# Test 3: Required Packages
print("\n3. Package Dependencies:")
packages = {
    "openai": "OpenAI API",
    "click": "CLI framework",
    "rich": "Terminal UI",
    "questionary": "Interactive prompts",
    "send2trash": "Safe file deletion",
    "humanize": "Human-readable sizes",
    "dotenv": "Environment variables"
}

all_packages_ok = True
for package, description in packages.items():
    try:
        if package == "dotenv":
            import dotenv
        else:
            __import__(package)
        print(f"   ✅ {package} ({description})")
    except ImportError:
        print(f"   ❌ {package} ({description}) - Not installed")
        all_packages_ok = False

if not all_packages_ok:
    print("   💡 Run: pip install -r requirements.txt")

# Test 4: OpenAI Connection
print("\n4. OpenAI API Connection:")
if api_key and api_key != "your_openai_api_key_here":
    try:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use known working model
            messages=[{"role": "user", "content": "Say 'API working'"}],
            max_tokens=10
        )
        print("   ✅ API connection successful")
        print(f"   📝 Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"   ❌ API error: {str(e)[:100]}...")
        if "model" in str(e).lower():
            print("   💡 Model might not exist. Check config.py")
else:
    print("   ⏭️  Skipping (no API key)")

# Test 5: File Access
print("\n5. Downloads Folder Access:")
downloads = os.path.expanduser("~/Downloads")
if os.path.exists(downloads):
    if os.access(downloads, os.R_OK):
        files = [f for f in os.listdir(downloads) if not f.startswith('.')]
        print(f"   ✅ Downloads folder accessible")
        print(f"   📁 Found {len(files)} visible files")
        if len(files) > 0:
            print(f"   📄 Sample files: {', '.join(files[:3])}")
            if len(files) > 3:
                print(f"      ... and {len(files) - 3} more")
    else:
        print("   ❌ No read permission for Downloads folder")
else:
    print("   ❌ Downloads folder not found at ~/Downloads")

# Test 6: Model Configuration
print("\n6. Model Configuration:")
try:
    from config import AI_MODEL, AI_ENABLED
    print(f"   📋 Configured model: {AI_MODEL}")
    print(f"   🤖 AI enabled: {AI_ENABLED}")
    if AI_MODEL == "gpt-4.1-mini":
        print("   ⚠️  Note: GPT-4.1 Mini is a future model (April 2025)")
        print("   💡 If not available, change to 'gpt-4o-mini' in config.py")
except ImportError as e:
    print(f"   ❌ Error loading config: {e}")

# Summary
print("\n" + "="*50)
print("SUMMARY:")
issues = []

if not api_key or api_key == "your_openai_api_key_here":
    issues.append("Configure API key in .env file")
if not all_packages_ok:
    issues.append("Install missing packages")
if not os.path.exists(downloads):
    issues.append("Downloads folder not accessible")

if issues:
    print("❌ Setup incomplete. Please fix:")
    for issue in issues:
        print(f"   • {issue}")
else:
    print("✅ All checks passed! Ready to run:")
    print("   • Test: python cleanup_downloads.py --dry-run")
    print("   • Organize: python cleanup_downloads.py --mode organize")
    print("   • Clean: python cleanup_downloads.py --mode clean") 