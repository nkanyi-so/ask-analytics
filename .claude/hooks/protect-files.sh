#!/bin/bash
# PreToolUse hook for Edit|Write: blocks secrets, lockfiles, generated ground truth and git internals.
# Exit 2 blocks the edit and sends the stderr message back to Claude as feedback.
INPUT=$(cat)
FILE_PATH=$(printf '%s' "$INPUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)

case "$FILE_PATH" in
  .env|*/.env|.env.local|*/.env.local|uv.lock|*/uv.lock|package-lock.json|*/package-lock.json|*/.git/*)
    echo "Blocked: $FILE_PATH is protected (secrets, lockfile or git internals). Use uv or npm for dependencies and never touch .env." >&2
    exit 2
    ;;
  data/ground_truth.json|*/data/ground_truth.json|data/events.jsonl|*/data/events.jsonl)
    echo "Blocked: $FILE_PATH is generated. Change scripts/seed.py and run make seed." >&2
    exit 2
    ;;
esac
exit 0
