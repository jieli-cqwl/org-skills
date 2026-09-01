#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_ENTRY="$ROOT/CLAUDE.md"
AGENTS_ENTRY="$ROOT/AGENTS.md"
PROJECT_MEMORY_SKILL="$ROOT/shared/skills/project-memory/SKILL.md"
PROJECT_MEMORY_AUDIT="$ROOT/shared/skills/project-memory/references/audit-checklist.md"
README="$ROOT/README.md"
MAX_AGENTS_LINES=34

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

test -f "$CLAUDE_ENTRY" || fail "missing Claude project memory entry"
test -f "$AGENTS_ENTRY" || fail "missing Codex project instruction entry"

expected_claude="$(mktemp "${TMPDIR:-/tmp}/claude-entry.XXXXXX")"
trap 'rm -f "$expected_claude"' EXIT
printf '# CLAUDE.md\n\n@AGENTS.md\n' >"$expected_claude"
cmp -s "$expected_claude" "$CLAUDE_ENTRY" \
  || fail "CLAUDE.md should only import AGENTS.md"

line_count="$(wc -l <"$AGENTS_ENTRY" | tr -d ' ')"
[ "$line_count" -le "$MAX_AGENTS_LINES" ] \
  || fail "AGENTS.md should stay concise: $line_count lines > $MAX_AGENTS_LINES"

head -n 1 "$AGENTS_ENTRY" | grep -Fx '# AGENTS.md' >/dev/null \
  || fail "AGENTS.md should be the shared project instruction entry"
grep -Eq 'bash tests/run-all\.sh --quick' "$AGENTS_ENTRY" \
  || fail "AGENTS.md should keep the Team quick gate command"
grep -Eq 'bash install\.sh --target all --dry-run' "$AGENTS_ENTRY" \
  || fail "AGENTS.md should keep the Team install dry-run command"
grep -Eq 'team-skills' "$AGENTS_ENTRY" \
  || fail "AGENTS.md should name team-skills ownership"
grep -Eq 'Daily' "$AGENTS_ENTRY" \
  || fail "AGENTS.md should say Superpowers lives in Daily"
grep -Eq 'tools/community/check_test_signal_assertions\.py' "$AGENTS_ENTRY" \
  || fail "AGENTS.md should point at the low-signal assertion checker"
grep -Eq '测试断言边界' "$AGENTS_ENTRY" \
  || fail "AGENTS.md should keep the test-signal assertion boundary"
! grep -Eq 'shared/assistant\.md' "$AGENTS_ENTRY" \
  || fail "AGENTS.md should not point at moved shared/assistant.md"
! grep -Fq 'shared/rules/*.md' "$AGENTS_ENTRY" \
  || fail "AGENTS.md should not point at moved shared/rules"
! grep -Fq 'community/superpowers/skills' "$AGENTS_ENTRY" \
  || fail "AGENTS.md should not point at moved Superpowers mirror"
! grep -Eq 'tests/fixtures/test-assertion-boundary/low-signal-prose-assertions\.baseline' "$AGENTS_ENTRY" \
  || fail "AGENTS.md should not document a low-signal assertion baseline"
! grep -Eq '只约束开发本仓' "$AGENTS_ENTRY" \
  || fail "AGENTS.md should not contain scope-only filler"
! grep -Eq '只约束开发本仓' "$README" \
  || fail "README should not describe entry docs as scope-only filler"

grep -Eq '@AGENTS\.md' "$PROJECT_MEMORY_SKILL" \
  || fail "project-memory should generate Claude import syntax"
grep -Eq '@AGENTS\.md' "$PROJECT_MEMORY_AUDIT" \
  || fail "project-memory audit should validate Claude import syntax"
! grep -Eq 'tail -n\+2 CLAUDE\.md' "$PROJECT_MEMORY_SKILL" \
  || fail "project-memory should not require duplicated CLAUDE/AGENTS bodies"
! grep -Eq 'tail -n\+2 CLAUDE\.md' "$PROJECT_MEMORY_AUDIT" \
  || fail "project-memory audit should not require duplicated CLAUDE/AGENTS bodies"

printf '[PASS] entry doc source contract\n'
