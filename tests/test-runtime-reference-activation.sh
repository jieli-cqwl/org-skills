#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=tests/lib/test-env.sh
. "$ROOT/tests/lib/test-env.sh"
ensure_test_rg

CLAUDE_PROBE="$ROOT/tools/dev/probe-claude-capabilities.sh"
CODEX_PROBE="$ROOT/tools/dev/probe-codex-capabilities.sh"
CODEX_HOOKS_PROBE="$ROOT/tools/dev/probe-codex-hooks.sh"
INSTALLER="$ROOT/install.sh"

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

assert_present() {
  local pattern="$1"
  local file="$2"
  rg -n "$pattern" "$file" >/dev/null 2>&1 || fail "missing pattern in $file: $pattern"
}

assert_absent() {
  local pattern="$1"
  local file="$2"
  if rg -n "$pattern" "$file" >/dev/null 2>&1; then
    fail "unexpected pattern in $file: $pattern"
  fi
}

assert_reference_probe_contract() {
  local file="$1"
  local runtime_name="$2"

  assert_present 'Entry Absolute Runtime Link Activation' "$file"
  assert_present 'Rule Absolute Runtime Link Activation' "$file"
  assert_present 'Runtime Entry Reference Activation Probe' "$file"
  assert_present 'Runtime Rule Reference Activation Probe' "$file"
  assert_present 'Runtime Rule Contract Activation Probe' "$file"
  assert_present '运行时入口绝对路径引用探针' "$file"
  assert_present '运行时规则绝对路径引用探针' "$file"
  assert_present 'probe-home' "$file"
  assert_present "prompt=\"\\\$trigger\"" "$file"
  assert_present 'REF_MISSING' "$file"
  assert_present 'RULE_DOC_MISSING' "$file"
  assert_present 'RULE_REF_MISSING' "$file"
  assert_absent 'reference/runtime-reference-probe\.md' "$file"

  if [ "$runtime_name" = "claude" ]; then
    assert_present '\.claude/reference/runtime-entry-reference-probe\.md' "$file"
    assert_present '\.claude/reference/runtime-rule-reference-probe\.md' "$file"
    assert_present '\.claude/rules/completion-claims\.md' "$file"
    assert_present '\.claude/CLAUDE\.md' "$file"
    assert_present "HOME=\"\\\$probe_home\"" "$file"
    assert_present 'Use the Bash tool to run' "$file"
    assert_present "cat \\\$reference_path" "$file"
    assert_present "reference_path" "$file"
    assert_present "cat \\\$read_path" "$file"
  else
    assert_present '\.codex/reference/runtime-entry-reference-probe\.md' "$file"
    assert_present '\.codex/reference/runtime-rule-reference-probe\.md' "$file"
    assert_present '\.codex/rules/completion-claims\.md' "$file"
    assert_present '\.codex/AGENTS\.md' "$file"
    assert_present "HOME=\"\\\$probe_home\"" "$file"
    assert_present '1\. Read ' "$file"
    assert_present "reference_path" "$file"
    assert_present "read_path" "$file"
  fi
}

assert_probe_stability_contract() {
  assert_present 'If following the instructions in that file requires reading another file, continue with the required tool call\(s\)\.' "$CLAUDE_PROBE"
  assert_present '\-\-disable-slash-commands' "$CLAUDE_PROBE"
  assert_present 'REFERENCE_PROBE_TIMEOUT_SECONDS=.*180' "$CLAUDE_PROBE"
  assert_present 'AGENT_DELEGATE_TIMEOUT_SECONDS=.*240' "$CLAUDE_PROBE"
  assert_present "timeout \"\\\$REFERENCE_PROBE_TIMEOUT_SECONDS\"" "$CLAUDE_PROBE"
  assert_present "timeout \"\\\$AGENT_DELEGATE_TIMEOUT_SECONDS\"" "$CLAUDE_PROBE"
  assert_present 'FAIL_COUNT=0' "$CLAUDE_PROBE"
  assert_present 'FAIL_COUNT=' "$CLAUDE_PROBE"
  assert_present 'claude capability probe recorded %s failure\(s\)' "$CLAUDE_PROBE"
  assert_absent "cp -R \"\\\$HOME/\\.codex\" \"\\\$probe_home/\\.codex\"" "$CLAUDE_PROBE"
  assert_absent "cp -R \"\\\$CODEX_HOME\" \"\\\$probe_home/\\.codex\"" "$CODEX_PROBE"
  assert_present 'copy_runtime_context' "$CODEX_PROBE"
  assert_present 'FAIL_COUNT=0' "$CODEX_PROBE"
  assert_present 'FAIL_COUNT=' "$CODEX_PROBE"
  assert_present 'codex capability probe recorded %s failure\(s\)' "$CODEX_PROBE"
  assert_present 'fail_check "Codex 全局 hooks 探针脚本执行失败"' "$CODEX_PROBE"
  assert_present 'fail_check "Codex hooks 尚未全部 trusted/managed"' "$CODEX_PROBE"
  assert_present 'fail_check "Codex hooks trust 探针未返回 ready 状态"' "$CODEX_PROBE"
  assert_present 'pass "Codex hooks trust 状态已就绪"' "$CODEX_PROBE"
  assert_present 'AUDIT_RC=0' "$CODEX_HOOKS_PROBE"
  assert_present 'hook_readiness=trust-status' "$CODEX_HOOKS_PROBE"
  assert_present 'audit_codex_hook_trust\.py' "$CODEX_HOOKS_PROBE"
  assert_present 'codex hooks trust audit failed' "$CODEX_HOOKS_PROBE"
  assert_present 'require-all-enabled' "$CODEX_HOOKS_PROBE"
  assert_present '\-\-require-ready' "$CODEX_HOOKS_PROBE"
  assert_absent '\-\-require-ready' "$INSTALLER"
  assert_absent 'require-all-enabled' "$INSTALLER"
  assert_absent 'timeout 20 codex' "$CODEX_HOOKS_PROBE"
  assert_absent 'timeout 60 codex' "$CODEX_HOOKS_PROBE"
  assert_absent 'codex --enable hooks exec' "$CODEX_HOOKS_PROBE"
  assert_absent 'codex --enable codex_hooks exec' "$CODEX_HOOKS_PROBE"
}

assert_reference_probe_contract "$CLAUDE_PROBE" "claude"
assert_reference_probe_contract "$CODEX_PROBE" "codex"
assert_probe_stability_contract

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
mkdir -p "$TMP_DIR/bin"

cat > "$TMP_DIR/bin/codex" <<'EOF'
#!/usr/bin/env bash
cat >/dev/null
exit 7
EOF
chmod +x "$TMP_DIR/bin/codex"
if PATH="$TMP_DIR/bin:$PATH" bash "$CODEX_PROBE" >/tmp/runtime_capabilities_probe.out 2>&1; then
  cat /tmp/runtime_capabilities_probe.out >&2
  fail "codex capabilities probe should fail when codex exec fails"
fi
assert_present 'codex capability probe recorded [0-9]+ failure' /tmp/runtime_capabilities_probe.out

mkdir -p "$TMP_DIR/probe-partial-hooks"
awk '/^printf '\''codex_bin=%s\\n'\''/ { exit } { print }' "$CODEX_PROBE" > "$TMP_DIR/probe-partial-hooks/probe-codex-capabilities.sh"
cat >> "$TMP_DIR/probe-partial-hooks/probe-codex-capabilities.sh" <<'EOF'
printf 'codex_bin=%s\n' "$(command -v codex 2>/dev/null || echo unknown)"
run_probe "Global Hooks" probe_global_hooks

if [ "${FAIL_COUNT:-0}" -ne 0 ]; then
  printf '\n[SUMMARY] codex capability probe recorded %s failure(s)\n' "$FAIL_COUNT" >&2
  exit 1
fi
EOF
chmod +x "$TMP_DIR/probe-partial-hooks/probe-codex-capabilities.sh"
cat > "$TMP_DIR/probe-partial-hooks/probe-codex-hooks.sh" <<'EOF'
#!/usr/bin/env bash
printf 'Codex hook audit: total=1 enabled=1 audited=1\n'
printf 'ready=1 not_ready=0 extra_not_ready=0\n'
exit 7
EOF
chmod +x "$TMP_DIR/probe-partial-hooks/probe-codex-hooks.sh"
if PATH="$TMP_DIR/bin:$PATH" bash "$TMP_DIR/probe-partial-hooks/probe-codex-capabilities.sh" >/tmp/runtime_capabilities_partial_hooks.out 2>&1; then
  cat /tmp/runtime_capabilities_partial_hooks.out >&2
  fail "codex capabilities probe should fail when child hooks probe exits non-zero even if it printed all events"
fi
assert_present 'Codex 全局 hooks 探针脚本执行失败' /tmp/runtime_capabilities_partial_hooks.out
assert_absent 'Codex hooks trust 状态已就绪' /tmp/runtime_capabilities_partial_hooks.out

echo "[PASS] runtime reference activation"
