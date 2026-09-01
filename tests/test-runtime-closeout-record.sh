#!/usr/bin/env bash
# 文件职责：验证运行时安装链路的收口记录保留可追溯提交与验收命令。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHANGELOG="$ROOT/CHANGELOG.md"

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

assert_present() {
  local needle="$1"
  grep -Fq "$needle" "$CHANGELOG" || fail "missing closeout changelog evidence: $needle"
}

assert_present '3056999'
assert_present 'context_contract_validator.py'
assert_present 'Claude Code / Codex'
assert_present 'bash tests/run-all.sh --quick'
assert_present 'bash install.sh --target all --dry-run'

printf '[PASS] runtime closeout record\n'
