#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=tests/lib/install-test-env.sh
. "$ROOT/tests/lib/install-test-env.sh"
GENERATE_OPENAI_YAML="$ROOT/tools/install/generate-all-openai-yaml.sh"

install_test_init

fail() {
  install_test_fail "$*"
}

manual_policy() {
  local skill="$1"
  [ -f "$CODEX_SKILLS_DIR/$skill/agents/openai.yaml" ] \
    && grep -Fq 'allow_implicit_invocation: false' "$CODEX_SKILLS_DIR/$skill/agents/openai.yaml"
}

# shellcheck disable=SC2016 # Assert the literal fallback expression in the maintenance script.
grep -Fq 'SRC_CODEX_SKILLS="${CODEX_SKILLS_DIR:-$HOME/.agents/skills}"' "$GENERATE_OPENAI_YAML" || fail "openai yaml maintenance script should default to official ~/.agents/skills"
! grep -Eq 'SRC_CODEX_SKILLS=.*\\.codex/skills' "$GENERATE_OPENAI_YAML" || fail "openai yaml maintenance script should not default to legacy ~/.codex/skills"

home_dir="$(install_test_new_home adapter-codex)"
CODEX_SKILLS_DIR="$home_dir/.agents/skills"
install_test_run_base "$home_dir" "$(install_test_log_path adapter-base)" --target codex
install_test_run_install "$home_dir" "$(install_test_log_path adapter-team)" --target codex

[ ! -e "$home_dir/.codex/skills/code-review-fix" ] || fail "codex runtime should not keep claude-only skill in legacy ~/.codex/skills"
[ ! -e "$CODEX_SKILLS_DIR/code-review-fix" ] || fail "codex runtime should not install claude-only skill code-review-fix"
[ ! -e "$CODEX_SKILLS_DIR/doc-review-fix" ] || fail "codex runtime should not install claude-only skill doc-review-fix"
[ ! -e "$CODEX_SKILLS_DIR/skill-creator" ] || fail "Daily skill-creator must not install from Team"
[ ! -e "$CODEX_SKILLS_DIR/brainstorming" ] || fail "Superpowers skills must not install from Team"
[ ! -e "$CODEX_SKILLS_DIR/skill-pull" ] || fail "skill-pull must not install from Team"

[ -f "$CODEX_SKILLS_DIR/feishu-docs/SKILL.md" ] || fail "feishu-docs should install as a codex skill"
manual_policy feishu-docs || fail "feishu-docs should disable Codex implicit invocation"
[ -f "$CODEX_SKILLS_DIR/deep-research/SKILL.md" ] || fail "deep-research should install as a codex skill"
manual_policy deep-research || fail "deep-research should disable Codex implicit invocation"
manual_policy product-director || fail "product-director should disable Codex implicit invocation"
manual_policy tech-lead || fail "tech-lead should disable Codex implicit invocation"
manual_policy commit || fail "commit should disable Codex implicit invocation"
manual_policy github-repo-radar || fail "github-repo-radar should disable Codex implicit invocation"
grep -Fq 'codex_execution: subagent_clean' "$CODEX_SKILLS_DIR/github-repo-radar/agents/openai.yaml" \
  || fail "github-repo-radar should expose subagent_clean Codex execution"
manual_policy refactor || fail "refactor should disable Codex implicit invocation"
manual_policy security || fail "security should disable Codex implicit invocation"
manual_policy research || fail "research should install with implicit invocation disabled"
grep -Fq 'codex_execution: subagent_clean' "$CODEX_SKILLS_DIR/research/agents/openai.yaml" \
  || fail "research should expose subagent_clean Codex execution"
manual_policy overview || fail "overview should install with implicit invocation disabled"
grep -Fq 'codex_execution: subagent_clean' "$CODEX_SKILLS_DIR/overview/agents/openai.yaml" \
  || fail "overview should expose subagent_clean Codex execution"
manual_policy scan || fail "scan should install with implicit invocation disabled"
grep -Fq 'execution_kind: orchestrator' "$CODEX_SKILLS_DIR/scan/agents/openai.yaml" \
  || fail "scan should expose orchestrator execution kind"
grep -Fq 'allow_nested_agents: true' "$CODEX_SKILLS_DIR/scan/agents/openai.yaml" \
  || fail "scan should allow internal dispatch"
manual_policy consistency-audit || fail "consistency-audit should install with implicit invocation disabled"
grep -Fq 'execution_kind: agent_backed' "$CODEX_SKILLS_DIR/consistency-audit/agents/openai.yaml" \
  || fail "consistency-audit should expose agent-backed execution kind"
grep -Fq 'agent_type: consistency-auditor' "$CODEX_SKILLS_DIR/consistency-audit/agents/openai.yaml" \
  || fail "consistency-audit should expose consistency-auditor agent type"
grep -Fq 'allow_nested_agents: false' "$CODEX_SKILLS_DIR/consistency-audit/agents/openai.yaml" \
  || fail "consistency-audit should forbid nested generic agents"

[ -f "$home_dir/.codex/hooks.json" ] || fail "codex runtime should render hooks.json"
grep -Fq 'hooks = true' "$home_dir/.codex/config.toml" || fail "codex runtime should enable hooks feature"
! grep -Eq '^[[:space:]]*codex_hooks[[:space:]]*=' "$home_dir/.codex/config.toml" || fail "codex runtime should not keep deprecated codex_hooks feature"
grep -Fq 'block_dangerous.sh' "$home_dir/.codex/hooks.json" || fail "codex hooks.json missing managed dangerous bash hook"
grep -Fq 'context_contract_validator.py' "$home_dir/.codex/hooks.json" || fail "codex hooks.json missing context validator hook"
grep -Fq 'codex_user_prompt_submit.py' "$home_dir/.codex/hooks.json" || fail "codex hooks.json missing active skill tracker"
grep -Fq 'codex_subagent_dispatch_guard.py' "$home_dir/.codex/hooks.json" || fail "codex hooks.json missing subagent dispatch guard"
grep -Fq 'codex_stop_dispatch.py' "$home_dir/.codex/hooks.json" || fail "codex hooks.json missing stop dispatcher"
! grep -Fq 'codex_context_continuity.py' "$home_dir/.codex/hooks.json" || fail "codex context continuity should not install by default"

echo "[PASS] codex skill adapter"
