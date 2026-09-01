#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
if [ -n "${PYTHONPATH:-}" ]; then
  export PYTHONPATH="$ROOT:$PYTHONPATH"
else
  export PYTHONPATH="$ROOT"
fi
exec python3 "$ROOT/tools/install/repo_install.py" "$@"
