"""
Configuration settings for the downloads cleanup tool
"""

# File age threshold (days)
OLD_FILE_DAYS = 30

# Safety: Minimum age before allowing deletion (days)
MIN_AGE_FOR_DELETION = 7  # Never delete files newer than this

# Size threshold for large files (bytes)
LARGE_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# File extensions to categorize
INSTALLER_EXTENSIONS = ['.dmg', '.pkg', '.exe', '.msi', '.deb', '.rpm', '.app']
ARCHIVE_EXTENSIONS = ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz']
TEMP_EXTENSIONS = ['.tmp', '.temp', '.part', '.download', '.crdownload']
DOCUMENT_EXTENSIONS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.bmp', '.webp']
VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv']

# Critical file types - NEVER suggest for deletion
CRITICAL_EXTENSIONS = [
    '.key', '.pem', '.p12', '.pfx',  # Certificates/keys
    '.env', '.ssh', '.gpg',          # Credentials
    '.license', '.lic',              # Licenses
    '.keychain', '.keystore',        # Key stores
    '.sqlite', '.db',                # Databases
    '.wallet', '.dat'                # Crypto/important data
]

# Size rules
MIN_FILE_SIZE = 1024  # Don't bother with files < 1KB (they take no space)
IGNORE_SMALL_FILES = True  # Skip files smaller than MIN_FILE_SIZE
MAX_FILE_SIZE_FOR_CONTENT_ANALYSIS = 10 * 1024 * 1024  # 10MB limit if we analyze contents

# File type specific rules
FILE_TYPE_RULES = {
    # Extension: (min_age_days, never_delete)
    '.dmg': (14, False),      # Installers - keep for 2 weeks minimum
    '.pkg': (14, False),
    '.exe': (14, False),
    '.zip': (30, False),      # Archives - keep for 1 month minimum
    '.pdf': (60, False),      # Documents - keep for 2 months minimum
    '.doc': (60, False),
    '.docx': (60, False),
    '.key': (0, True),        # Critical files - never delete
    '.pem': (0, True),
    '.env': (0, True),
}

# Protected file patterns (never delete these)
PROTECTED_PATTERNS = [
    'important',
    'backup',
    'credentials',
    'password',
    'license',
    'certificate',
    'work',
    'project',
    'invoice',
    'receipt',
    'tax',
    'contract'
]

# Whitelist specific filenames (exact matches, case-insensitive)
WHITELIST_FILES = [
    'readme.md',
    'license',
    '.env',
    'config.json'
]

# Organization folder structure
ORGANIZATION_FOLDERS = {
    "Documents": ['.pdf', '.doc', '.docx', '.txt', '.odt', '.rtf'],
    "Images": ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.bmp', '.webp'],
    "Videos": ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv'],
    "Audio": ['.mp3', '.wav', '.flac', '.aac', '.m4a'],
    "Archives": ['.zip', '.rar', '.7z', '.tar', '.gz'],
    "Installers": ['.dmg', '.pkg', '.exe', '.msi', '.app'],
    "Screenshots": [],  # Based on filename pattern
    "Code": ['.py', '.js', '.java', '.cpp', '.c', '.go', '.rs'],
    "Data": ['.csv', '.json', '.xml', '.sql', '.db'],
    "Old_Downloads": []  # Files > 30 days
}

# Duplicate detection settings
CHECK_DUPLICATES_BY_HASH = True  # Use MD5 hash for true duplicate detection
DUPLICATE_MIN_SIZE = 1024  # Don't hash files smaller than 1KB

# AI Configuration
AI_ENABLED = True
# Model selection based on latest analysis (April 2025)
# GPT-4.1 Mini offers best value: 1M context, 83% cheaper than GPT-4o, matches performance
AI_MODEL = "gpt-4o-mini"  # Using stable model until gpt-4.1-mini is available
AI_TEMPERATURE = 0.3
AI_BATCH_SIZE = 20  # Files to analyze per request

# Structured Output Schema for AI categorization
AI_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "categorizations": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["safe_to_delete", "might_be_important", "keep"]
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1
                    },
                    "reason": {
                        "type": "string"
                    }
                },
                "required": ["category", "confidence", "reason"],
                "additionalProperties": False
            }
        }
    },
    "required": ["categorizations"],
    "additionalProperties": False
}

# Available models (as of 2025)
AVAILABLE_MODELS = {
    "gpt-4o-mini": {"cost": "low", "performance": "good", "reasoning": "good"},
    "gpt-4o": {"cost": "medium", "performance": "excellent", "reasoning": "excellent"},
    "o4-mini": {"cost": "low", "performance": "good", "reasoning": "excellent"},
    "o3": {"cost": "high", "performance": "excellent", "reasoning": "superior"},
    "gpt-3.5-turbo": {"cost": "lowest", "performance": "adequate", "reasoning": "basic"}
}

# UI settings
MAX_FILES_DISPLAY = 10  # Max files to show per category
CONFIRM_EACH_CATEGORY = True  # Ask for confirmation per category
CREATE_LOG_FILE = True  # Create a log of deleted files
SHOW_PROGRESS_BARS = True  # Show progress during operations

# Backup settings
CREATE_BACKUP_BEFORE_DELETE = False  # Copy files before deletion
BACKUP_FOLDER_NAME = "_Backup_Before_Delete" 