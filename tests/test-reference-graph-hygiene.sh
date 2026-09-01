#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

python3 - "$ROOT" <<'PY' || fail "reference graph hygiene contract violated"
import sys
from pathlib import Path

root = Path(sys.argv[1])
if (root / "shared" / "reference").exists():
    raise SystemExit("Team must not keep shared/reference; Base owns runtime references")
if (root / "shared" / "rules").exists():
    raise SystemExit("Team must not keep shared/rules; Base owns runtime rules")
PY

echo "[PASS] reference graph hygiene"
