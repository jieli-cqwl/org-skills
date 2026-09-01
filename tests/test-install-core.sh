#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=tests/lib/install-test-env.sh
. "$ROOT/tests/lib/install-test-env.sh"

GROUP="all"

usage() {
  cat <<'USAGE'
Usage: bash tests/test-install-core.sh [--group all|basic|runtime-noise|runtime-idempotent|runtime-product-split|claude-agents|codex-agent-model-config|codex-agent-config-file|codex-agent-config|codex-agent-file-contracts|codex-local-edit|codex-agent-files]
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --group)
      [ "$#" -ge 2 ] || install_test_fail "--group 缺少参数"
      GROUP="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      install_test_fail "未知参数: $1"
      ;;
  esac
done

case "$GROUP" in
  all|basic|runtime-noise|runtime-idempotent|runtime-product-split|claude-agents|codex-agent-model-config|codex-agent-config-file|codex-agent-config|codex-agent-file-contracts|codex-local-edit|codex-agent-files) ;;
  *) install_test_fail "未知 install-core group: $GROUP" ;;
esac

should_run_group() {
  [ "$GROUP" = "all" ] || [ "$GROUP" = "$1" ]
}

assert_team_not_daily() {
  local home_dir="$1"
  local label="$2"

  install_test_assert_file_exists "$home_dir/.claude/skills/product-director/SKILL.md" "$label product-director present"
  install_test_assert_path_absent "$home_dir/.claude/skills/skill-creator" "$label skill-creator absent"
  install_test_assert_path_absent "$home_dir/.agents/skills/skill-creator" "$label Codex skill-creator absent"
  install_test_assert_path_absent "$home_dir/.claude/skills/brainstorming" "$label brainstorming absent"
  install_test_assert_path_absent "$home_dir/.claude/skills/skill-pull" "$label skill-pull absent"
  install_test_assert_file_exists "$home_dir/.claude/CLAUDE.md" "$label Base assistant remains after Team install"
}

install_test_init

if should_run_group basic; then
  install_test_case_start "core: dry-run writes no Team state"
  home_dir="$(install_test_new_home core-dry-run)"
  install_test_run_base "$home_dir" "$(install_test_log_path core-dry-run-base)" --target all
  log_file="$(install_test_log_path core-dry-run)"
  install_test_run_install "$home_dir" "$log_file" --target all --dry-run
  install_test_assert_path_absent "$(install_test_state_root "$home_dir")/team-skills" "dry-run should not create Team state"
  install_test_assert_path_absent "$home_dir/.claude/skills/product-director" "dry-run should not write Team skills"
  install_test_case_pass "core: dry-run writes no Team state"

  install_test_case_start "core: Base then Team installs product-director not skill-creator"
  home_dir="$(install_test_new_home core-team-payload)"
  install_test_run_base "$home_dir" "$(install_test_log_path core-team-payload-base)" --target all
  install_test_run_install "$home_dir" "$(install_test_log_path core-team-payload)" --target all
  assert_team_not_daily "$home_dir" "core payload"
  install_test_assert_file_exists "$home_dir/.codex/agents/developer.toml" "Codex developer.toml"
  install_test_assert_path_absent "$home_dir/.org-skills-state" "legacy state unused"
  install_test_case_pass "core: Base then Team installs product-director not skill-creator"

  install_test_case_start "core: unowned Team skill destination is conflict"
  home_dir="$(install_test_new_home core-conflict)"
  install_test_run_base "$home_dir" "$(install_test_log_path core-conflict-base)" --target claude
  mkdir -p "$home_dir/.claude/skills/product-director"
  printf 'local-only\n' > "$home_dir/.claude/skills/product-director/SKILL.md"
  log_file="$(install_test_log_path core-conflict)"
  set +e
  install_test_run_install_allow_failure "$home_dir" "$log_file" --target claude
  rc=$?
  set -e
  install_test_assert_failure "$rc" "conflict install should fail"
  install_test_assert_file_contains "$log_file" "conflict" "conflict message"
  install_test_assert_file_contains "$home_dir/.claude/skills/product-director/SKILL.md" "local-only" "existing conflict file should stay unchanged"
  install_test_case_pass "core: unowned Team skill destination is conflict"
fi

if should_run_group runtime-noise || should_run_group runtime-idempotent || should_run_group runtime-product-split; then
  install_test_case_start "core: Team reinstall is digest-safe when unchanged"
  home_dir="$(install_test_new_home core-reinstall)"
  install_test_run_base "$home_dir" "$(install_test_log_path core-reinstall-base)" --target claude
  install_test_run_install "$home_dir" "$(install_test_log_path core-reinstall-1)" --target claude
  install_test_run_install "$home_dir" "$(install_test_log_path core-reinstall-2)" --target claude
  assert_team_not_daily "$home_dir" "reinstall"
  install_test_case_pass "core: Team reinstall is digest-safe when unchanged"
fi

if should_run_group claude-agents; then
  install_test_case_start "core: Claude agents are Team resources"
  home_dir="$(install_test_new_home core-claude-agents)"
  install_test_run_base "$home_dir" "$(install_test_log_path core-claude-agents-base)" --target claude
  install_test_run_install "$home_dir" "$(install_test_log_path core-claude-agents)" --target claude
  install_test_assert_file_exists "$home_dir/.claude/agents/developer.md" "Claude developer agent"
  install_test_assert_file_exists "$home_dir/.claude/agents/verifier.md" "Claude verifier agent"
  assert_team_not_daily "$home_dir" "claude-agents"
  install_test_case_pass "core: Claude agents are Team resources"
fi

if should_run_group codex-agent-model-config || should_run_group codex-agent-config || should_run_group codex-agent-config-file || should_run_group codex-agent-file-contracts || should_run_group codex-agent-files || should_run_group codex-local-edit; then
  install_test_case_start "core: Codex agents are structured Team entries"
  home_dir="$(install_test_new_home core-codex-agents)"
  install_test_run_base "$home_dir" "$(install_test_log_path core-codex-agents-base)" --target codex
  install_test_run_install "$home_dir" "$(install_test_log_path core-codex-agents)" --target codex
  install_test_assert_file_exists "$home_dir/.codex/agents/developer.toml" "developer.toml"
  install_test_assert_file_contains "$home_dir/.codex/config.toml" "[agents.developer]" "structured developer identity"
  install_test_assert_path_absent "$(install_test_state_root "$home_dir")/codex/codex-hooks-baseline.json" "no whole-file hooks baseline"
  install_test_assert_path_absent "$home_dir/.agents/skills/skill-creator" "Daily skill-creator absent"
  install_test_assert_file_exists "$home_dir/.agents/skills/product-director/SKILL.md" "product-director present"
  install_test_case_pass "core: Codex agents are structured Team entries"
fi

printf '\nInstall core tests passed: %d\n' "$INSTALL_TEST_CASE_COUNT"
