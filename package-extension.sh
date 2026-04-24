#!/bin/bash
# Package the TruthNuke Chrome extension into a distributable zip file.
# Usage: ./package-extension.sh

set -e

SCRIPT_DIR="$(dirname "$0")"
OUTPUT="$SCRIPT_DIR/truthnuke-extension.zip"
EXTENSION_DIR="$SCRIPT_DIR/extension"

if [ ! -d "$EXTENSION_DIR" ]; then
  echo "Error: extension/ directory not found."
  exit 1
fi

# Remove old zip if it exists
rm -f "$OUTPUT"

# Create zip from the extension directory
# -r recursive, -j don't store directory paths (we wrap in a folder)
(cd "$SCRIPT_DIR" && zip -r "$OUTPUT" extension/ \
  -x "extension/.DS_Store" \
  -x "extension/generate_icons.html" \
  -x "extension/__pycache__/*")

FILE_SIZE=$(du -h "$OUTPUT" | cut -f1)
echo ""
echo "✅ Packaged: $OUTPUT ($FILE_SIZE)"
echo "   Users can unzip and load the 'extension' folder in chrome://extensions/"
