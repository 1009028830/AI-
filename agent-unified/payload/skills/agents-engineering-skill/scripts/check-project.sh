#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)

if command -v python3 >/dev/null 2>&1 &&
    python3 -c 'import sys; raise SystemExit(sys.version_info[0] != 3)' >/dev/null 2>&1; then
    exec python3 "$SCRIPT_DIR/check_project.py" "$@"
fi

if command -v python >/dev/null 2>&1 &&
    python -c 'import sys; raise SystemExit(sys.version_info[0] != 3)' >/dev/null 2>&1; then
    exec python "$SCRIPT_DIR/check_project.py" "$@"
fi

echo "Python 3 was not found. Install Python 3 or run check_project.py with its full path." >&2
exit 2
