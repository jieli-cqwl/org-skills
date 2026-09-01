#!/usr/bin/env bash
# File role: Team no longer owns shared/reference; Base owns those runtime files.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REFERENCE_DIR="$ROOT/shared/reference"

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

test ! -e "$REFERENCE_DIR" || fail "Team must not keep shared/reference; Base owns runtime references"

echo "[PASS] reference decision rules"
