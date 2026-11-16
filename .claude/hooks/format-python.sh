#!/bin/bash
# PostToolUse hook for Edit|Write: formats the edited Python file so diffs stay clean.
# Formatting only: lint auto-fixes (like removing "unused" imports mid-edit) are left to `make check`.
# Never blocks; does nothing until Phase 0 has created backend/pyproject.toml.
INPUT=$(cat)
FILE_PATH=$(printf '%s' "$INPUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)

case "$FILE_PATH" in
  *.py)
    if command -v uv >/dev/null 2>&1 && [ -f "$CLAUDE_PROJECT_DIR/backend/pyproject.toml" ]; then
      (cd "$CLAUDE_PROJECT_DIR/backend" && uv run --quiet ruff format --config pyproject.toml "$FILE_PATH" >/dev/null 2>&1)
    fi
    ;;
esac
exit 0
