#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

test -d "$ROOT/shared/skills" || fail "missing shared/skills Team source directory"
test -d "$ROOT/shared/protocols" || fail "missing shared/protocols"
test -d "$ROOT/shared/runtime" || fail "missing shared/runtime"
test -d "$ROOT/shared/agents" || fail "missing shared/agents"
test -d "$ROOT/shared/agents/claude" || fail "missing shared/agents/claude"
test -d "$ROOT/shared/agents/codex" || fail "missing shared/agents/codex"
test -d "$ROOT/shared/hooks" || fail "missing shared/hooks"
test -d "$ROOT/shared/skills/lib" || fail "lib must remain in-tree"
test -d "$ROOT/shared/skills/qft-branch-flow-workspace" || fail "workspace must remain in-tree"
test ! -f "$ROOT/shared/skills/lib/SKILL.md" || fail "lib must not be installable"
test ! -e "$ROOT/community" || fail "community vendor tree must not remain in Team"
test ! -e "$ROOT/shared/assistant.md" || fail "Base assistant must not remain in Team"
test ! -e "$ROOT/shared/rules" || fail "Base rules must not remain in Team"
test ! -e "$ROOT/shared/reference" || fail "Base reference must not remain in Team"
test ! -e "$ROOT/shared/skills/skill-pull" || fail "skill-pull must not remain in Team"
test ! -d "$ROOT/codex/skills" || fail "codex/skills should not remain as a maintained source tree"
test ! -d "$ROOT/codex/agents" || fail "codex/agents should not remain as a maintained source tree"
test ! -d "$ROOT/claude/reference" || fail "claude/reference should not remain as a maintained source tree"
test ! -d "$ROOT/claude/rules" || fail "claude/rules should not remain as a maintained source tree"
test ! -f "$ROOT/claude/hooks/lib/common.sh" || fail "claude/hooks/lib/common.sh should be sourced from shared/hooks/lib/common.sh"

for skill in product-director product-manager design test-design tech-lead delivery-owner developer review verify qa fix worktree commit ux feishu-docs deep-research; do
  skill_file="$ROOT/shared/skills/$skill/SKILL.md"
  test -f "$skill_file" || fail "missing skill source for manual-only check: $skill_file"
  grep -Fq 'disable-model-invocation: true' "$skill_file" || fail "manual-only skill should declare disable-model-invocation in source: $skill"
done

echo "[PASS] single-source layout"
