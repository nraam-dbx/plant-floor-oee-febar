#!/usr/bin/env bash
# Sync all project collateral to the workspace folder (WORKSPACE_DIR).
# Keeps the workspace copy in step with the local repo. Run from anywhere.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$HERE/config.env"

echo "▶ Ensuring workspace folder $WORKSPACE_DIR ..."
databricks workspace mkdirs "$WORKSPACE_DIR" -p "$PROFILE" 2>/dev/null || true

echo "▶ Syncing $HERE → $WORKSPACE_DIR ..."
databricks sync "$HERE" "$WORKSPACE_DIR" -p "$PROFILE" \
  --exclude .venv --exclude __pycache__ --exclude .git --exclude '*.pyc' --exclude '.DS_Store'
echo "✅ synced"
