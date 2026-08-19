#!/bin/bash
# postToolUse hook: runs after fs_write/write tool calls.
# If the written file is a pyproject.toml, runs `uv sync` in that file's
# directory so new/updated dependencies get installed automatically.
set -euo pipefail

EVENT=$(cat)

# Extract file path(s) touched by the write tool. Supports both the
# `path` (single-file tools) and `operations[].path` (batch write tool) shapes.
paths=$(echo "$EVENT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
tool_input = data.get('tool_input', {}) or {}
found = []
if isinstance(tool_input.get('path'), str):
    found.append(tool_input['path'])
for op in tool_input.get('operations', []) or []:
    p = op.get('path')
    if isinstance(p, str):
        found.append(p)
print('\n'.join(found))
" 2>/dev/null || true)

if [ -z "$paths" ]; then
    exit 0
fi

while IFS= read -r path; do
    [ -z "$path" ] && continue
    base=$(basename "$path")
    if [ "$base" = "pyproject.toml" ]; then
        dir=$(dirname "$path")
        if command -v uv >/dev/null 2>&1; then
            echo "pyproject.toml changed at $path — running 'uv sync' in $dir" >&2
            (cd "$dir" && uv sync) >&2
        else
            echo "pyproject.toml changed at $path but 'uv' is not installed — skipping sync" >&2
        fi
    fi
done <<< "$paths"

exit 0
