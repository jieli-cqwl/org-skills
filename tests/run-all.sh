#!/usr/bin/env bash
set -euo pipefail

# File responsibility: orchestrate repository validation suites from tests/gate-plan.json.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="full"
PROFILE=0
LIST_ONLY=0
FORMAT="text"

usage() {
  cat <<'USAGE'
Usage:
  bash tests/run-all.sh [--full|--quick|--release|--preflight] [--profile] [--list] [--format=json]

Options:
  --full         Run the complete regression suite. This is the default.
  --quick        Run the high-signal local canary gate.
  --release      Run the release regression suite.
  --preflight    Run syntax, shellcheck, and lightweight preflight checks.
  --profile      Print elapsed seconds for each executed step.
  --list         Print the planned steps without executing them.
  --format=json  Print machine-readable JSON with --list.
  -h, --help     Show this help text.
USAGE
}

fail() {
  printf '[run-all][ERROR] %s\n' "$*" >&2
  exit 1
}

SYNTAX_SHELL_FILES=(
  "install.sh"
  "uninstall.sh"
  "tests/run-all.sh"
  "tests/run-focused.sh"
  "tests/test-run-focused-runner-contract.sh"
  "tests/test-run-all-runner-contract.sh"
  "tests/test-product-director-team-pilot-contract.sh"
  "tests/test-product-director-real-transcript-dogfood.sh"
  "tests/test-standard-chain-invocation-policy.sh"
  "tests/test-overview-skill-contract.sh"
  "tests/test-entry-doc-source-contract.sh"
  "tests/test-test-assertion-boundary-contract.sh"
  "tests/test-install-runtime-quick-canary.sh"
  "tests/test-team-install-lifecycle.sh"
  "tests/test-standard-chain-validator-stack.sh"
  "tests/test-standard-chain-field-consumption-contract.sh"
  "tests/test-context-contract-validator.sh"
  "tests/test-skill-output-and-gate-contract.sh"
  "tests/test-codex-subagent-dispatch-guard.sh"
  "tests/test-managed-doc-output-contract.sh"
  "shared/skills/test-design/scripts/preflight_check.sh"
  "shared/skills/test-design/scripts/completion_check.sh"
  "shared/skills/research/scripts/completion_check.sh"
  "shared/skills/delivery-owner/scripts/completion_check.sh"
  "shared/skills/delivery-owner/scripts/intake_preflight_check.sh"
  "shared/skills/delivery-owner/scripts/task_packet_check.sh"
)

SHELLCHECK_FILES=(
  "${SYNTAX_SHELL_FILES[@]}"
  "tools/validate-contracts.sh"
  "tools/dev/validate-contracts.sh"
  "tools/install/generate-all-openai-yaml.sh"
  "tools/github/apply-branch-protection.sh"
  "tools/migration/retire-dot-claude.sh"
)

run_bash_syntax_checks() {
  local file

  for file in "${SYNTAX_SHELL_FILES[@]}"; do
    bash -n "$ROOT/$file"
  done
  python3 -m py_compile "$ROOT/tests/test-install-script-contract.py"
  python3 -m py_compile "$ROOT/tests/test-team-inventory.py"
  python3 -m py_compile "$ROOT/tools/install/repo_install.py"
  python3 -m py_compile "$ROOT/tests/test-github-workflow-contract.py"
  python3 -m py_compile "$ROOT/tests/test-github-branch-protection-contract.py"
  python3 -m py_compile "$ROOT/tools/community/audit_codex_hook_trust.py"
  python3 -m py_compile "$ROOT/tools/community/render_runtime_placeholders.py"
  python3 -m py_compile "$ROOT/tests/test-render-runtime-placeholders.py"
  python3 -m py_compile "$ROOT/tests/test-one-human-agent-team-architecture-map.py"
  python3 -m py_compile "$ROOT/shared/hooks/managed/codex_subagent_dispatch_guard.py"
  python3 -m py_compile "$ROOT/tools/community/validate_context_contract.py"
  python3 -m py_compile "$ROOT/tools/community/recover_context.py"
  python3 -m py_compile "$ROOT/tools/community/update_active_doc_scope.py"
  python3 -m py_compile "$ROOT/tools/community/validate_co_creation_ledger.py"
  python3 -m py_compile "$ROOT/tools/community/validate_standard_chain_field_consumption.py"
  python3 -m py_compile "$ROOT/tools/community/validate_standard_chain_field_decision_matrix.py"
  python3 -m py_compile "$ROOT/tools/community/standard_chain_negative_cases.py"
  python3 -m py_compile "$ROOT/tools/community/check_test_signal_assertions.py"
  python3 -m py_compile "$ROOT/tools/community/check_test_signal_python.py"
  python3 -m py_compile "$ROOT/tools/community/check_test_signal_rules.py"
  python3 -m py_compile "$ROOT/tools/community/check_test_signal_shell.py"
  python3 -m py_compile "$ROOT/tools/community/gate_plan.py"
  python3 -m py_compile "$ROOT/tools/community/validate_episode_package.py"
  python3 -m py_compile "$ROOT/shared/skills/delivery-owner/scripts/task_packet_check.py"
  python3 -m py_compile "$ROOT/tools/eval/scripts/validate_stage2_design_package.py"
  python3 -m py_compile "$ROOT/tools/eval/scripts/validate_stage2_design_materials.py"
  python3 -m py_compile "$ROOT/tools/eval/scripts/validate_stage2_test_design_package.py"
  python3 -m py_compile "$ROOT/tools/eval/scripts/validate_stage2_test_design_materials.py"
  python3 -m py_compile "$ROOT/shared/skills/test-design/scripts/review_digest.py"
  python3 -m py_compile "$ROOT/tools/eval/scripts/validate_stage2_tech_lead_package.py"
  python3 -m py_compile "$ROOT/tools/eval/scripts/validate_stage2_tech_lead_materials.py"
  python3 -m py_compile "$ROOT/shared/skills/product-manager/scripts/preflight_check.py"
  python3 -m py_compile "$ROOT/shared/skills/verify/scripts/preflight_check.py"
  python3 -m py_compile "$ROOT"/shared/skills/delivery-estimator/scripts/*.py
  python3 -m py_compile "$ROOT/shared/skills/skill-quality-audit/scripts/validate_skill_audit_report.py"
  python3 -m py_compile "$ROOT/shared/skills/research/scripts/validate_retain_evidence.py"
}

run_shellcheck() {
  local files=()
  local file

  for file in "${SHELLCHECK_FILES[@]}"; do
    files+=("$ROOT/$file")
  done
  shellcheck -x "${files[@]}"
}

case "${1:-}" in
  --internal-syntax-checks)
    run_bash_syntax_checks
    exit 0
    ;;
  --internal-shellcheck)
    run_shellcheck
    exit 0
    ;;
esac

while [ "$#" -gt 0 ]; do
  case "$1" in
    --full)
      MODE="full"
      shift
      ;;
    --quick)
      MODE="quick"
      shift
      ;;
    --release)
      MODE="release"
      shift
      ;;
    --preflight)
      MODE="preflight"
      shift
      ;;
    --profile)
      PROFILE=1
      shift
      ;;
    --list)
      LIST_ONLY=1
      shift
      ;;
    --format=json)
      FORMAT="json"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown option: $1"
      ;;
  esac
done

if [ "$LIST_ONLY" -eq 1 ]; then
  python3 "$ROOT/tools/community/gate_plan.py" --repo-root "$ROOT" --mode "$MODE" --list --format "$FORMAT"
else
  if [ "$PROFILE" -eq 1 ]; then
    python3 "$ROOT/tools/community/gate_plan.py" --repo-root "$ROOT" --mode "$MODE" --run --profile-output
  else
    python3 "$ROOT/tools/community/gate_plan.py" --repo-root "$ROOT" --mode "$MODE" --run
  fi
  echo "All tests passed"
fi
