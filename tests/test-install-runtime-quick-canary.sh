#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=tests/lib/install-test-env.sh
. "$ROOT/tests/lib/install-test-env.sh"

GROUP="all"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --group)
      GROUP="${2:-}"
      [ -n "$GROUP" ] || install_test_fail "--group requires a value"
      shift 2
      ;;
    -h|--help)
      cat <<'USAGE'
Usage: bash tests/test-install-runtime-quick-canary.sh [--group all|codex-install|claude-hook-launcher|hook-checks]
USAGE
      exit 0
      ;;
    *)
      install_test_fail "unknown option: $1"
      ;;
  esac
done

case "$GROUP" in
  all|codex-install|claude-hook-launcher|hook-checks) ;;
  *) install_test_fail "unknown runtime quick canary group: $GROUP" ;;
esac

install_test_init

if [ "$GROUP" = "all" ] || [ "$GROUP" = "codex-install" ]; then
  install_test_case_start "runtime-quick-canary: Base then Team Codex payload"
  home_dir="$(install_test_new_home runtime-quick-canary)"
  install_test_run_base "$home_dir" "$(install_test_log_path runtime-quick-canary-base)" --target all
  install_test_run_install "$home_dir" "$(install_test_log_path runtime-quick-canary-install)" --target all
  install_test_assert_file_exists "$home_dir/.codex/AGENTS.md" "Base Codex assistant remains after Team install"
  install_test_assert_file_exists "$home_dir/.codex/rules/completion-claims.md" "Base rules remain after Team install"
  install_test_assert_file_exists "$home_dir/.codex/reference/测试规范.md" "Base reference remains after Team install"
  install_test_assert_file_exists "$home_dir/.agents/skills/product-director/SKILL.md" "Team Codex skill present"
  install_test_assert_path_absent "$home_dir/.agents/skills/skill-creator" "Daily skill-creator absent"
  install_test_assert_path_absent "$home_dir/.agents/skills/brainstorming" "Superpowers skill absent"
  install_test_assert_path_absent "$home_dir/.agents/skills/skill-pull" "skill-pull absent"
  install_test_assert_file_exists "$home_dir/.codex/hooks.json" "codex runtime should include hooks.json"
  install_test_assert_file_contains "$home_dir/.codex/hooks.json" "context_contract_validator.py" "codex context hook should be registered"
  install_test_assert_path_absent "$home_dir/.org-skills-state" "legacy state unused"
  install_test_case_pass "runtime-quick-canary: Base then Team Codex payload"
fi

if [ "$GROUP" = "all" ] || [ "$GROUP" = "claude-hook-launcher" ]; then
  install_test_case_start "runtime-quick-canary: Claude Team hooks and payload"
  home_dir="$(install_test_new_home runtime-quick-canary-claude-hook-launcher)"
  install_test_run_base "$home_dir" "$(install_test_log_path runtime-quick-canary-claude-base)" --target claude
  install_test_run_install "$home_dir" "$(install_test_log_path runtime-quick-canary-claude-hook-launcher-install)" --target claude
  install_test_assert_file_exists "$home_dir/.claude/skills/product-director/SKILL.md" "Team Claude skill present"
  install_test_assert_path_absent "$home_dir/.claude/skills/skill-creator" "Daily skill-creator absent"
  install_test_assert_path_absent "$home_dir/.claude/skills/brainstorming" "Superpowers skill absent"
  install_test_assert_file_exists "$home_dir/.claude/hooks/post_compact.sh" "Team post_compact hook present"
  install_test_assert_file_contains "$home_dir/.claude/settings.json" "context_contract_validator.py" "claude context hook should be registered"
  install_test_assert_file_exists "$home_dir/.claude/CLAUDE.md" "Base assistant remains after Team install"
  install_test_case_pass "runtime-quick-canary: Claude Team hooks and payload"
fi

if [ "$GROUP" = "all" ] || [ "$GROUP" = "hook-checks" ]; then
  install_test_case_start "runtime-quick-canary: task verify ruff lint is scoped to changed files"
  workspace="$INSTALL_TEST_TMP_ROOT/task-verify-scope-workspace"
  mkdir -p "$workspace/vendor"
  (
    cd "$workspace"
    git init -q
    printf '%s\n' 'print(f"upstream lint debt")' > vendor/upstream.py
    printf '%s\n' 'print("clean")' > changed.py
    git add .
    git -c user.name=test -c user.email=test@example.com commit -q -m init
    printf '%s\n' 'print("clean changed")' > changed.py
  )
  verify_log="$(install_test_log_path runtime-quick-canary-task-verify-scope)"
  printf '{"cwd":"%s"}' "$workspace" | COMMENT_CHECK_MODE=warn bash "$ROOT/claude/hooks/task_verify.sh" >"$verify_log" 2>&1 || install_test_fail "task verify should ignore unchanged upstream lint debt"
  install_test_assert_file_not_contains "$verify_log" "vendor/upstream.py" "task verify should not lint unchanged Python files"
  install_test_case_pass "runtime-quick-canary: task verify ruff lint is scoped to changed files"

  install_test_case_start "runtime-quick-canary: task verify warn details stay out of hook output"
  workspace="$INSTALL_TEST_TMP_ROOT/task-verify-warn-report-workspace"
  report_dir="$INSTALL_TEST_TMP_ROOT/task-verify-reports"
  mkdir -p "$workspace" "$report_dir"
  (
    cd "$workspace"
    git init -q
    git -c user.name=test -c user.email=test@example.com commit --allow-empty -q -m init
    printf '%s\n' 'def sample():' '    return 1' > target.py
  )
  verify_log="$(install_test_log_path runtime-quick-canary-task-verify-warn-report)"
  printf '{"cwd":"%s"}' "$workspace" | CLAUDE_TASK_VERIFY_REPORT_DIR="$report_dir" COMMENT_CHECK_MODE=warn bash "$ROOT/claude/hooks/task_verify.sh" >"$verify_log" 2>&1 || install_test_fail "task verify warn mode should not block task completion"
  install_test_assert_file_contains "$verify_log" "完整报告：" "task verify warn output should point to the full report"
  install_test_assert_file_not_contains "$verify_log" "函数注释缺失" "task verify warn output should not inline detailed findings"
  report_line=$(grep -F "完整报告：" "$verify_log" | tail -1)
  report_path="${report_line##*完整报告：}"
  [ -f "$report_path" ] || install_test_fail "task verify warn report should exist: $report_path"
  install_test_assert_file_contains "$report_path" "函数注释缺失" "task verify warn report should keep detailed findings"
  install_test_case_pass "runtime-quick-canary: task verify warn details stay out of hook output"
fi

printf '\nInstall runtime quick canary passed: %d\n' "$INSTALL_TEST_CASE_COUNT"
