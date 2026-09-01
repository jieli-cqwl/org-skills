#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

check_doc_shared_refs() {
  local source_file ref
  local docs_dir="$ROOT/docs"

  [ -d "$docs_dir" ] || return 0

  while IFS= read -r source_file; do
    [ -f "$source_file" ] || continue

    while IFS= read -r ref; do
      [ -n "$ref" ] || continue
      [ -f "$ROOT/$ref" ] || fail "$source_file 引用了缺失共享文档: $ref"
    done < <(
      {
        grep -ohE '\]\([^)]*shared/(protocols|skills/[^/]+/references)/[^)#]+\.md' "$source_file" || true
      } | sed -E 's/^.*shared/shared/' | sort -u
    )
  done < <(find "$docs_dir" -type f -name '*.md' ! -path '*/archive/*' | sort)
}

check_doc_shared_refs

echo "[PASS] doc reference integrity"
