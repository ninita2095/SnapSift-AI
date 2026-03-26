import os

# SnapSift AI — Configuration
# API key is read from environment variable (never hardcode it here)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Output folder name
OUTPUT_FOLDER = "SnapSift_Output"

# Duplicate detection sensitivity (0-10, lower = more strict)
HASH_SENSITIVITY = 5

# Minimum file size in bytes (files smaller than this are likely stickers)
MIN_FILE_SIZE = 50000

# Supported image extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.JPG', '.JPEG', '.PNG'}

# Batch size for AI classification (photos per API call)
BATCH_SIZE = 5