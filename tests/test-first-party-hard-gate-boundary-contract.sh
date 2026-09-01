#!/usr/bin/env bash
# shellcheck disable=SC2016
# File role: prove non-standard first-party HARD-GATE sections stay focused on blocking invariants.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

assert_file() {
  test -f "$1" || fail "missing file: ${1#"$ROOT"/}"
}

assert_present() {
  local needle="$1" file="$2"
  grep -Fq "$needle" "$file" || fail "missing content in ${file#"$ROOT"/}: $needle"
}

assert_absent() {
  local needle="$1" file="$2"
  if grep -Fq "$needle" "$file"; then
    fail "unexpected content in ${file#"$ROOT"/}: $needle"
  fi
}

hard_gate_block() {
  awk '
    /^## HARD-GATE$/ { in_block = 1; next }
    in_block && /^## / { exit }
    in_block { print }
  ' "$1"
}

assert_hard_gate_absent() {
  local needle="$1" file="$2" block
  block="$(hard_gate_block "$file")"
  test -n "$block" || fail "missing HARD-GATE block in ${file#"$ROOT"/}"
  ! grep -Fq "$needle" <<<"$block" || fail "HARD-GATE contains execution detail in ${file#"$ROOT"/}: $needle"
}

SCOPED_SKILLS=(
  "$ROOT/shared/skills/deep-research/SKILL.md"
  "$ROOT/shared/skills/feishu-docs/SKILL.md"
  "$ROOT/shared/skills/skill-quality-audit/SKILL.md"
)

for file in "${SCOPED_SKILLS[@]}"; do
  assert_file "$file"
  assert_hard_gate_absent 'references/' "$file"
  assert_hard_gate_absent 'Trigger:' "$file"
  assert_hard_gate_absent 'Read:' "$file"
  assert_hard_gate_absent 'Expect:' "$file"
  assert_hard_gate_absent 'Consume:' "$file"
  assert_hard_gate_absent 'Evidence:' "$file"
  assert_hard_gate_absent 'Sync:' "$file"
  assert_hard_gate_absent '/reference/' "$file"
  assert_hard_gate_absent 'scripts/' "$file"
  assert_hard_gate_absent 'python3 ' "$file"
  assert_hard_gate_absent 'bash ' "$file"
done

assert_hard_gate_absent 'scripts/render_report.py' "$ROOT/shared/skills/deep-research/SKILL.md"
assert_hard_gate_absent 'scripts/validate_skill_audit_report.py' "$ROOT/shared/skills/skill-quality-audit/SKILL.md"

assert_present 'references/source-policy.md' "$ROOT/shared/skills/deep-research/SKILL.md"
assert_present 'references/methodology.md' "$ROOT/shared/skills/deep-research/SKILL.md"
assert_present 'references/arxiv-policy.md' "$ROOT/shared/skills/deep-research/SKILL.md"
assert_present 'scripts/render_report.py' "$ROOT/shared/skills/deep-research/SKILL.md"
assert_present 'references/auth-and-config.md' "$ROOT/shared/skills/feishu-docs/SKILL.md"
assert_present 'references/audit-dimensions.md' "$ROOT/shared/skills/skill-quality-audit/SKILL.md"
assert_absent '{{RUNTIME_HOME}}/reference/Skill质量标准.md' "$ROOT/shared/skills/skill-quality-audit/SKILL.md"
assert_present 'scripts/validate_skill_audit_report.py' "$ROOT/shared/skills/skill-quality-audit/SKILL.md"

printf '[PASS] first-party hard-gate boundary contract\n'
