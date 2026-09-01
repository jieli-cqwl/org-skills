#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$ROOT/tests/run-focused.sh"

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local needle="$1"
  local haystack="$2"
  local label="$3"

  if ! grep -Fq -- "$needle" <<<"$haystack"; then
    fail "$label missing: $needle"
  fi
}

assert_not_contains() {
  local needle="$1"
  local haystack="$2"
  local label="$3"

  if grep -Fq -- "$needle" <<<"$haystack"; then
    fail "$label should not include: $needle"
  fi
}

bash -n "$RUNNER"

help_output="$(bash "$RUNNER" --help)"
assert_contains "design" "$help_output" "help output"
assert_contains "research" "$help_output" "help output"
assert_contains "skill-quality-audit" "$help_output" "help output"
assert_contains "standard-chain" "$help_output" "help output"
assert_contains "product-stage2" "$help_output" "help output"
assert_contains "install-runtime" "$help_output" "help output"
assert_contains "docs-context" "$help_output" "help output"
assert_contains "codex-runtime" "$help_output" "help output"
assert_contains "--list" "$help_output" "help output"
assert_contains "--format=json" "$help_output" "help output"

design_plan="$(bash "$RUNNER" design --list)"
design_json="$(bash "$RUNNER" design --list --format=json)"
research_plan="$(bash "$RUNNER" research --list)"
standard_chain_plan="$(bash "$RUNNER" standard-chain --list)"
install_runtime_plan="$(bash "$RUNNER" install-runtime --list)"

assert_contains "profile=design" "$design_plan" "design plan"
assert_contains "steps=" "$design_plan" "design plan"
assert_contains "bash $ROOT/tests/test-design-skill-governance-redesign.sh" "$design_plan" "design plan"
assert_contains "bash $ROOT/tests/test-design-architect-capability-contract.sh" "$design_plan" "design plan"
assert_contains "python3 $ROOT/tests/test-design-architect-contract.py" "$design_plan" "design plan"
assert_contains "bash $ROOT/tests/test-design-dogfood-e2e.sh" "$design_plan" "design plan"
assert_contains "bash $ROOT/tests/test-stage2-design-package.sh" "$design_plan" "design plan"
assert_contains "bash $ROOT/tests/test-standard-chain-login-homepage-pilot.sh" "$design_plan" "design plan"
assert_contains "bash $ROOT/tests/test-standard-chain-feedback-thanks-pilot.sh" "$design_plan" "design plan"
assert_contains "bash $ROOT/tests/test-skill-output-and-gate-contract.sh" "$design_plan" "design plan"
assert_not_contains "tests/test-install-runtime.sh" "$design_plan" "design plan"
assert_not_contains "tests/test-product-manager-dogfood-e2e.sh" "$design_plan" "design plan"
assert_not_contains "tests/test-release-metadata.sh" "$design_plan" "design plan"

python3 - "$design_json" <<'PY'
import json
import sys

plan = json.loads(sys.argv[1])
if plan.get("profile") != "design":
    raise SystemExit("design json plan must report profile=design")
steps = plan.get("steps")
if not isinstance(steps, list) or not steps:
    raise SystemExit("design json plan must include non-empty steps")
if not all(isinstance(step.get("command"), list) for step in steps):
    raise SystemExit("design json steps must keep command arrays")
PY

assert_contains "profile=research" "$research_plan" "research plan"
assert_contains "bash $ROOT/tests/test-research-skill-contract.sh" "$research_plan" "research plan"
assert_not_contains "tests/test-design-dogfood-e2e.sh" "$research_plan" "research plan"

assert_contains "profile=standard-chain" "$standard_chain_plan" "standard-chain plan"
assert_contains "bash $ROOT/tests/test-standard-chain-validator-stack.sh" "$standard_chain_plan" "standard-chain plan"
assert_contains "bash $ROOT/tests/test-standard-chain-readiness-gate.sh" "$standard_chain_plan" "standard-chain plan"
assert_not_contains "tests/test-product-manager-dogfood-e2e.sh" "$standard_chain_plan" "standard-chain plan"

assert_contains "profile=install-runtime" "$install_runtime_plan" "install-runtime plan"
assert_contains "bash $ROOT/tests/test-team-install-lifecycle.sh" "$install_runtime_plan" "install-runtime plan"
assert_contains "bash $ROOT/tests/test-install-runtime-quick-canary.sh" "$install_runtime_plan" "install-runtime plan"
assert_not_contains "tests/test-install-runtime.sh" "$install_runtime_plan" "install-runtime plan"
assert_not_contains "tests/test-install-runtime-smoke.sh" "$install_runtime_plan" "install-runtime plan"

if bash "$RUNNER" unknown --list >/tmp/org_run_focused_unknown.out 2>&1; then
  fail "unknown profile should fail"
fi
unknown_output="$(</tmp/org_run_focused_unknown.out)"
assert_contains "unknown profile" "$unknown_output" "unknown profile output"
assert_contains "design" "$unknown_output" "unknown profile output"
assert_contains "research" "$unknown_output" "unknown profile output"

echo "run-focused runner contract ok"
