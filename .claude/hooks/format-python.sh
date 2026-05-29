#!/usr/bin/env bash
# Post-Edit/Write hook: format and lint Python files.
#
# Reads a Claude Code PostToolUse JSON payload from stdin, extracts the
# edited file path, and runs ruff format + ruff check --fix on it if it
# ends in .py. Silently no-ops if:
#   - the file isn't a .py
#   - ruff isn't available (e.g., uv not yet set up)
#   - we're outside the project root

set -euo pipefail

payload="$(cat)"
file_path="$(printf '%s' "$payload" | /usr/bin/jq -r '.tool_input.file_path // empty')"

# No file path → nothing to do.
[ -n "$file_path" ] || exit 0

# Only Python.
case "$file_path" in
  *.py) ;;
  *) exit 0 ;;
esac

# File must still exist (skip deletions).
[ -f "$file_path" ] || exit 0

project_root="/Users/barrytandy/Dev/Afrolabs/Vibe Check"

# Project root must hold a pyproject.toml before uv-run-ing anything.
if [ -f "$project_root/pyproject.toml" ]; then
  ( cd "$project_root" && uv run ruff format "$file_path" >/dev/null 2>&1 || true )
  ( cd "$project_root" && uv run ruff check --fix "$file_path" >/dev/null 2>&1 || true )
else
  # Pre-bootstrap: try a globally-installed ruff if present.
  if command -v ruff >/dev/null 2>&1; then
    ruff format "$file_path" >/dev/null 2>&1 || true
    ruff check --fix "$file_path" >/dev/null 2>&1 || true
  fi
fi

exit 0
