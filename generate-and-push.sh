#!/usr/bin/env bash
# ==============================================================================
# Top 1,000 GitHub Repositories Generator and Publisher
# Fetches top 1,000 repositories using gh-cli, builds HTML dashboard, and pushes.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Running Top 1,000 GitHub Repositories Generator ==="

if command -v python3 >/dev/null 2>&1 && [ -f "$SCRIPT_DIR/generate_and_push.py" ]; then
    echo "Executing Python generator..."
    python3 "$SCRIPT_DIR/generate_and_push.py"
elif command -v python >/dev/null 2>&1 && [ -f "$SCRIPT_DIR/generate_and_push.py" ]; then
    echo "Executing Python generator..."
    python "$SCRIPT_DIR/generate_and_push.py"
elif command -v node >/dev/null 2>&1 && [ -f "$SCRIPT_DIR/generate-and-push.js" ]; then
    echo "Executing JavaScript generator via Node.js..."
    node "$SCRIPT_DIR/generate-and-push.js"
elif command -v node >/dev/null 2>&1 && [ -f "$SCRIPT_DIR/generate-and-push.ts" ]; then
    echo "Executing TypeScript generator via Node.js..."
    node "$SCRIPT_DIR/generate-and-push.ts"
else
    echo "Error: Python 3 or Node.js is required to run the data collection." >&2
    exit 1
fi

echo "=== Generation and GitHub push complete ==="
