#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
. "$ROOT/tests/lib/install-test-env.sh"
install_test_init

BASE_CHECKOUT="${BASE_CHECKOUT:-/Users/lijieli/base-config}"
DAILY_CHECKOUT="${DAILY_CHECKOUT:-/Users/lijieli/daily-skills}"

case "$BASE_CHECKOUT" in
  */tests/fixtures/base-config-cutover-start|*/tests/fixtures/base-config-cutover-start/)
    install_test_fail "cutover E2E must not use the CI Base fixture as the cutover source"
    ;;
esac

[ -x "$BASE_CHECKOUT/install.sh" ] || install_test_fail "Base installer missing at $BASE_CHECKOUT/install.sh"
[ -x "$DAILY_CHECKOUT/install.sh" ] || install_test_fail "Daily installer missing at $DAILY_CHECKOUT/install.sh"

seed_cutover_home() {
  local home="$1"
  mkdir -p "$home/.claude/skills/product-director" "$home/.claude/skills/learned" "$home/.claude/skills/resume-tailor"
  printf 'old-team\n' > "$home/.claude/skills/product-director/SKILL.md"
  printf 'keep\n' > "$home/.claude/skills/learned/note.md"
  printf 'reject\n' > "$home/.claude/skills/resume-tailor/SKILL.md"
  mkdir -p "$home/.org-skills-state/archive" "$home/.org-skills-state/claude"
  printf 'backup\n' > "$home/.org-skills-state/archive/dot-claude-git.tar.gz"
  printf '%s\n' "$home/.claude/skills/product-director" > "$home/.org-skills-state/claude/installed-manifest"
}

run_cleaner() {
  local home="$1"
  shift
  env -u ORG_STATE_ROOT \
    HOME="$home" \
    SKILL_REPO_STATE_ROOT="$home/.local/state/skill-repos" \
    PYTHONPATH="$ROOT" \
    PYTHONDONTWRITEBYTECODE=1 \
    python3 "$ROOT/tools/migration/clean_runtime_cutover.py" \
    --home "$home" \
    --base "$BASE_CHECKOUT" \
    --daily "$DAILY_CHECKOUT" \
    "$@"
}

run_installer() {
  local home="$1"
  local checkout="$2"
  local log="$3"
  INSTALL_TEST_CURRENT_LOG="$log"
  mkdir -p "$(dirname "$log")"
  env -u ORG_STATE_ROOT \
    HOME="$home" \
    SKILL_REPO_STATE_ROOT="$home/.local/state/skill-repos" \
    PYTHONPATH="$ROOT" \
    PYTHONDONTWRITEBYTECODE=1 \
    bash "$checkout/install.sh" --target all >"$log" 2>&1 \
    || install_test_fail "installer failed: $checkout"
}

assert_after_remove() {
  local home="$1"
  local label="$2"
  install_test_assert_path_absent "$home/.claude/skills/product-director" "$label product-director removed"
  install_test_assert_path_absent "$home/.claude/skills/resume-tailor" "$label resume-tailor removed"
  install_test_assert_file_exists "$home/.claude/skills/learned/note.md" "$label learned preserved"
  [ -d "$home/.org-skills-state" ] || install_test_fail "$label ~/.org-skills-state should remain after remove"
}

assert_final_runtime() {
  local home="$1"
  local label="$2"
  install_test_assert_file_exists "$home/.claude/CLAUDE.md" "$label claude assistant"
  install_test_assert_file_exists "$home/.claude/rules/code-changes.md" "$label claude rules"
  install_test_assert_file_exists "$home/.codex/AGENTS.md" "$label codex assistant"
  install_test_assert_file_exists "$home/.codex/rules/code-changes.md" "$label codex rules"
  install_test_assert_file_exists "$home/.claude/skills/brainstorming/SKILL.md" "$label claude brainstorming"
  install_test_assert_file_exists "$home/.claude/skills/grilling/SKILL.md" "$label claude grilling"
  install_test_assert_file_exists "$home/.claude/skills/obsidian-markdown/SKILL.md" "$label claude obsidian"
  install_test_assert_file_exists "$home/.agents/skills/skill-pull/SKILL.md" "$label codex skill-pull"
  install_test_assert_file_exists "$home/.agents/skills/grilling/SKILL.md" "$label codex grilling"
  install_test_assert_path_absent "$home/.claude/skills/product-director" "$label team skill absent"
  install_test_assert_path_absent "$home/.claude/skills/darwin-skill" "$label personal skill absent"
  install_test_assert_path_absent "$home/.claude/hooks/post_compact.sh" "$label team hook absent"
  install_test_assert_path_absent "$home/.org-skills-state" "$label legacy state retired"
  install_test_assert_file_exists "$home/.local/state/skill-repos/base-config/claude/installed.json" "$label base claude manifest"
  install_test_assert_file_exists "$home/.local/state/skill-repos/daily-skills/codex/installed.json" "$label daily codex manifest"
  install_test_assert_path_absent "$home/.local/state/skill-repos/team-skills" "$label team state absent"
  install_test_assert_path_absent "$home/.local/state/org-runtime-cutover" "$label cutover journal retired"
  cmp -s "$home/.claude/skills/learned/note.md" <(printf 'keep\n') \
    || install_test_fail "$label learned bytes changed"
}

install_base_then_daily() {
  local home="$1"
  local slug="$2"
  run_installer "$home" "$BASE_CHECKOUT" "$(install_test_log_path "$slug-base")"
  run_installer "$home" "$DAILY_CHECKOUT" "$(install_test_log_path "$slug-daily")"
}

finish_cutover() {
  local home="$1"
  local slug="$2"
  install_base_then_daily "$home" "$slug"
  run_cleaner "$home" --target all --phase verify --apply
  run_cleaner "$home" --phase retire-legacy-state --apply
  assert_final_runtime "$home" "$slug"
}

install_test_case_start "apply without --phase is forbidden"
no_phase_home="$(install_test_new_home cutover-no-phase)"
seed_cutover_home "$no_phase_home"
set +e
run_cleaner "$no_phase_home" --target all --apply
no_phase_rc=$?
set -e
[ "$no_phase_rc" -ne 0 ] || install_test_fail "--apply without --phase must fail"
install_test_assert_file_exists "$no_phase_home/.claude/skills/product-director/SKILL.md" "no-phase must not mutate"
install_test_case_pass "apply without --phase is forbidden"

install_test_case_start "isolated Base+Daily happy path"
home="$(install_test_new_home cutover-e2e)"
export HOME="$home"
export SKILL_REPO_STATE_ROOT="$home/.local/state/skill-repos"
export PYTHONPATH="$ROOT"
seed_cutover_home "$home"
run_cleaner "$home" --target all --phase remove --apply
assert_after_remove "$home" "happy-path"
finish_cutover "$home" "happy-path"
install_test_case_pass "isolated Base+Daily happy path"

install_test_case_start "resume after kill in the middle of remove"
resume_home="$(install_test_new_home cutover-e2e-resume)"
seed_cutover_home "$resume_home"
set +e
ORG_CUTOVER_INTERRUPT_AFTER=1 run_cleaner "$resume_home" --target all --phase remove --apply
resume_kill_rc=$?
set -e
[ "$resume_kill_rc" -ne 0 ] || install_test_fail "interrupted remove must exit non-zero"
[ -d "$resume_home/.org-skills-state" ] || install_test_fail "interrupt must leave legacy state"
install_test_assert_file_exists "$resume_home/.claude/skills/learned/note.md" "interrupt preserves learned"
run_cleaner "$resume_home" --target all --phase remove --apply
assert_after_remove "$resume_home" "resume"
finish_cutover "$resume_home" "resume"
install_test_case_pass "resume after kill in the middle of remove"

install_test_case_start "verify failure keeps legacy state and creates no backup"
fail_home="$(install_test_new_home cutover-verify-fail)"
seed_cutover_home "$fail_home"
before_tarballs="$(find "$fail_home" -name '*.tar.gz' | wc -l | tr -d ' ')"
set +e
run_cleaner "$fail_home" --target all --phase verify --apply
verify_rc=$?
set -e
[ "$verify_rc" -ne 0 ] || install_test_fail "verify must fail before Base+Daily install"
[ -d "$fail_home/.org-skills-state" ] || install_test_fail "verify failure must not delete legacy state"
install_test_assert_file_exists "$fail_home/.org-skills-state/archive/dot-claude-git.tar.gz" "planted archive remains"
after_tarballs="$(find "$fail_home" -name '*.tar.gz' | wc -l | tr -d ' ')"
[ "$before_tarballs" = "$after_tarballs" ] || install_test_fail "verify failure must not create a new backup archive"
install_test_assert_file_exists "$fail_home/.claude/skills/product-director/SKILL.md" "verify must not remove old skills"
install_test_case_pass "verify failure keeps legacy state and creates no backup"
