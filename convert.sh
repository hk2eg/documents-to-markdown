#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
source venv/bin/activate

if [ $# -eq 0 ]; then
    echo "No file specified — running batch mode on input/ folder..."
    python convert_doc.py --batch
else
    python convert_doc.py "$@"
fi

echo ""
echo "Press Enter to exit..."
read
