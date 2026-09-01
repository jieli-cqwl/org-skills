#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$ROOT/tests/run-all.sh"

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

plan_count() {
  local key="$1"
  local plan="$2"

  grep "^${key}=" <<<"$plan" | cut -d= -f2
}

help_output="$(bash "$RUNNER" --help)"
assert_contains "--quick" "$help_output" "help output"
assert_contains "--full" "$help_output" "help output"
assert_contains "--release" "$help_output" "help output"
assert_contains "--profile" "$help_output" "help output"
assert_contains "--list" "$help_output" "help output"
assert_contains "--format=json" "$help_output" "help output"

full_plan="$(bash "$RUNNER" --full --list)"
quick_plan="$(bash "$RUNNER" --quick --list)"
release_plan="$(bash "$RUNNER" --release --list)"
quick_json="$(bash "$RUNNER" --quick --list --format=json)"
runner_source="$(<"$RUNNER")"

assert_contains "tests/run-focused.sh" "$runner_source" "run-all focused runner syntax coverage"
assert_contains "tests/test-run-focused-runner-contract.sh" "$runner_source" "run-all focused runner contract syntax coverage"
assert_contains "tests/test-team-install-lifecycle.sh" "$runner_source" "run-all team install lifecycle syntax coverage"
assert_contains "tests/test-product-director-team-pilot-contract.sh" "$runner_source" "run-all product-director team pilot syntax coverage"
assert_contains "shared/skills/delivery-owner/scripts/completion_check.sh" "$runner_source" "run-all shell syntax coverage"
assert_contains "shared/skills/delivery-owner/scripts/intake_preflight_check.sh" "$runner_source" "run-all shell syntax coverage"
assert_contains "shared/skills/delivery-owner/scripts/task_packet_check.sh" "$runner_source" "run-all shell syntax coverage"
assert_not_contains "shared/skills/delivery-owner/scripts/control_decision_check.sh" "$runner_source" "run-all shell syntax coverage"

focused_runner_contract="$(bash "$ROOT/tests/test-run-focused-runner-contract.sh")"
assert_contains "run-focused runner contract ok" "$focused_runner_contract" "focused runner contract"

assert_contains "mode=full" "$full_plan" "full plan"
assert_contains "mode=quick" "$quick_plan" "quick plan"
assert_contains "mode=release" "$release_plan" "release plan"
assert_contains "steps=" "$full_plan" "full plan"
assert_contains "steps=" "$quick_plan" "quick plan"
assert_contains "steps=" "$release_plan" "release plan"

python3 - "$quick_json" <<'PY'
import json
import sys

plan = json.loads(sys.argv[1])
if plan.get("mode") != "quick":
    raise SystemExit("quick json plan must report mode=quick")
steps = plan.get("steps")
if not isinstance(steps, list) or not steps:
    raise SystemExit("quick json plan must include non-empty steps")
if len(steps) > 36:
    raise SystemExit(f"quick should stay a small canary plan, got {len(steps)} steps")
required_areas = {
    "preflight",
    "contracts",
    "standard-chain",
    "context",
    "install-runtime",
    "hooks-manifest",
    "skill-evals",
    "runtime-surface",
    "assertion-boundary",
}
areas = {step.get("area") for step in steps}
missing = sorted(required_areas - areas)
if missing:
    raise SystemExit(f"quick plan missing required areas: {missing}")
for step in steps:
    step_id = step.get("id")
    tags = set(step.get("tags", []))
    forbidden = {"full-only", "release-only", "dogfood", "e2e", "live", "migration", "install-heavy"}
    exemptions = {"product-director-real-transcript-dogfood": {"dogfood"}}
    blocked = sorted(tags & (forbidden - exemptions.get(step_id, set())))
    if blocked:
        raise SystemExit(f"quick step {step_id} has forbidden tags: {blocked}")
    timeout = step.get("timeout_sec")
    if not isinstance(timeout, int) or timeout <= 0 or timeout > 120:
        raise SystemExit(f"quick step {step.get('id')} must have timeout_sec in 1..120")
PY

full_steps="$(plan_count steps "$full_plan")"
quick_steps="$(plan_count steps "$quick_plan")"
release_steps="$(plan_count steps "$release_plan")"

[ "$full_steps" -gt "$quick_steps" ] || fail "full plan should have more steps than quick plan"
[ "$release_steps" -gt "$full_steps" ] || fail "release plan should add release-only checks beyond the full plan"
[ "$quick_steps" -le 36 ] || fail "quick plan should stay below 36 canary steps"

assert_contains "bash $ROOT/tests/test-team-install-lifecycle.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-install-core.sh --group basic" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-install-core.sh --group runtime-noise" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-install-core.sh --group runtime-idempotent" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-install-core.sh --group runtime-product-split" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-install-core.sh --group claude-agents" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-install-core.sh --group codex-agent-model-config" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-install-core.sh --group codex-agent-config-file" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-install-core.sh --group codex-agent-file-contracts" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-install-core.sh --group codex-local-edit" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-install-runtime-quick-canary.sh --group codex-install" "$quick_plan" "quick plan"
assert_contains "bash $ROOT/tests/test-install-runtime-quick-canary.sh --group claude-hook-launcher" "$quick_plan" "quick plan"
assert_contains "bash $ROOT/tests/test-install-runtime-quick-canary.sh --group hook-checks" "$quick_plan" "quick plan"
assert_contains "python3 $ROOT/tests/test-install-script-contract.py" "$quick_plan" "quick plan"
assert_not_contains "test-install-runtime-smoke.sh" "$quick_plan" "quick plan"
assert_not_contains "test-skill-pull" "$quick_plan" "quick plan"
assert_not_contains "shared/assistant.md" "$quick_plan" "quick plan"
assert_contains "bash $ROOT/tests/test-install-runtime-quick-canary.sh --group codex-install" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-install-runtime-quick-canary.sh --group claude-hook-launcher" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-install-runtime-quick-canary.sh --group hook-checks" "$full_plan" "full plan"
assert_contains "python3 $ROOT/tests/test-install-script-contract.py" "$full_plan" "full plan"
assert_contains "python3 $ROOT/tests/test-install-script-contract.py" "$release_plan" "release plan"
assert_not_contains "test-install-runtime-smoke.sh" "$full_plan" "full plan"
assert_not_contains "test-install-safety.sh" "$full_plan" "full plan"
assert_not_contains "test-install-runtime.sh" "$full_plan" "full plan"
assert_not_contains "test-install-migration.sh" "$full_plan" "full plan"
assert_not_contains "ownership-inventory" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-standard-chain-readiness-gate.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-developer-effectiveness-review-evals.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-developer-runtime-proof-contract.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-developer-runtime-failure-matrix.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-standard-chain-runtime-layering-contract.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-standard-chain-episode-package.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-standard-chain-harness-capability-eval.sh" "$full_plan" "full plan"
assert_contains "python3 $ROOT/tests/test-github-workflow-contract.py" "$full_plan" "full plan"
assert_contains "python3 $ROOT/tests/test-github-branch-protection-contract.py" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-skill-quality-standard.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-shared-skill-package-quality-baseline.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-skill-body-quality-static-audit.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-skill-quality-detection-fixtures.sh" "$full_plan" "full plan"
assert_not_contains "test-install-smoke.sh" "$full_plan" "full plan"
assert_not_contains "test-install-systematic.sh" "$full_plan" "full plan"
assert_not_contains "test-install-runtime-audit.sh" "$full_plan" "full plan"

assert_contains "bash $ROOT/tools/validate-contracts.sh" "$quick_plan" "quick plan"
assert_contains "bash $ROOT/tests/test-entry-doc-source-contract.sh" "$quick_plan" "quick plan"
assert_contains "bash $ROOT/tests/test-test-assertion-boundary-contract.sh" "$quick_plan" "quick plan"
assert_contains "bash $ROOT/tests/test-product-director-team-pilot-contract.sh" "$quick_plan" "quick plan"
assert_contains "bash $ROOT/tests/test-product-director-real-transcript-dogfood.sh" "$quick_plan" "quick plan"
assert_contains "bash $ROOT/tests/test-product-director-team-pilot-contract.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-product-director-real-transcript-dogfood.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-product-director-team-pilot-contract.sh" "$release_plan" "release plan"
assert_contains "bash $ROOT/tests/test-product-director-real-transcript-dogfood.sh" "$release_plan" "release plan"
assert_contains "bash $ROOT/tests/test-standard-chain-field-consumption-contract.sh" "$quick_plan" "quick plan"
assert_not_contains "test-standard-chain-validator-stack.sh" "$quick_plan" "quick plan"
assert_contains "bash $ROOT/tests/test-standard-chain-validator-stack.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-standard-chain-validator-stack.sh" "$release_plan" "release plan"
assert_contains "bash $ROOT/tests/test-context-contract-validator.sh" "$quick_plan" "quick plan"
assert_contains "bash $ROOT/tests/test-skill-output-and-gate-contract.sh --scope static" "$quick_plan" "quick plan"
assert_contains "bash $ROOT/tests/test-skill-output-and-gate-contract.sh --scope runtime" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-skill-output-and-gate-contract.sh --scope runtime" "$release_plan" "release plan"
assert_contains "bash $ROOT/tests/test-skill-runtime-surface-contract.sh" "$quick_plan" "quick plan"
assert_contains "bash $ROOT/tests/test-skill-eval-contracts.sh" "$quick_plan" "quick plan"
assert_not_contains "test-design-dogfood-e2e.sh" "$quick_plan" "quick plan"
assert_not_contains "test-product-manager-dogfood-e2e.sh" "$quick_plan" "quick plan"
assert_not_contains "test-install-migration.sh" "$quick_plan" "quick plan"
assert_not_contains "test-standard-chain-harness-capability-eval.sh" "$quick_plan" "quick plan"
assert_not_contains "test-developer-effectiveness-review-evals.sh" "$quick_plan" "quick plan"
assert_contains "bash $ROOT/tests/test-stage2-product-director-handoff.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-stage2-confirmed-brief-package.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-stage2-product-manager-package.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-stage2-design-package.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-stage2-test-design-package.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-stage2-tech-lead-package.sh" "$full_plan" "full plan"

for release_heavy_test in \
  "tests/test-team-install-lifecycle.sh" \
  "tests/test-install-core.sh --group basic" \
  "tests/test-install-core.sh --group runtime-noise" \
  "tests/test-install-core.sh --group runtime-idempotent" \
  "tests/test-install-core.sh --group runtime-product-split" \
  "tests/test-install-core.sh --group claude-agents" \
  "tests/test-install-core.sh --group codex-agent-model-config" \
  "tests/test-install-core.sh --group codex-agent-config-file" \
  "tests/test-install-core.sh --group codex-agent-file-contracts" \
  "tests/test-install-core.sh --group codex-local-edit" \
  "tests/test-platform-runtime-noise.sh" \
  "tests/test-codex-skill-adapter.sh"
do
  assert_not_contains "bash $ROOT/$release_heavy_test" "$quick_plan" "quick plan"
  assert_contains "bash $ROOT/$release_heavy_test" "$full_plan" "full plan"
  assert_contains "bash $ROOT/$release_heavy_test" "$release_plan" "release plan"
done

for moved_test in \
  "tests/test-product-eval-contract.sh" \
  "tests/test-product-context-signal-quality.sh" \
  "tests/test-developer-process-compliance-contract.sh" \
  "tests/test-standard-chain-skill-structure.sh"
do
  assert_not_contains "bash $ROOT/$moved_test" "$quick_plan" "quick plan"
  assert_contains "bash $ROOT/$moved_test" "$full_plan" "full plan"
  assert_contains "bash $ROOT/$moved_test" "$release_plan" "release plan"
done

assert_not_contains "bash $ROOT/tests/test-release-metadata.sh" "$quick_plan" "quick plan"
assert_not_contains "bash $ROOT/tests/test-release-metadata.sh" "$full_plan" "full plan"
assert_contains "bash $ROOT/tests/test-release-metadata.sh" "$release_plan" "release plan"

assert_not_contains "test-install-smoke.sh" "$quick_plan" "quick plan"
assert_not_contains "test-install-systematic.sh" "$quick_plan" "quick plan"
assert_not_contains "test-install-runtime-audit.sh" "$quick_plan" "quick plan"

python3 - "$quick_json" <<'PY'
import json
import sys

plan = json.loads(sys.argv[1])
for step in plan["steps"]:
    if step.get("id") in {
        "install-runtime",
        "rule-runtime-team-readiness-pack",
        "ownership-inventory",
        "skill-pull-contract",
        "skill-pull-scripts",
    }:
        raise SystemExit(f"{step.get('id')} must not be part of the quick plan")
PY

full_json="$(bash "$RUNNER" --full --list --format=json)"
python3 - "$full_json" <<'PY'
import json
import sys

plan = json.loads(sys.argv[1])
steps = {step.get("id"): step for step in plan["steps"]}
timeout = steps["team-install-lifecycle"].get("timeout_sec")
if not isinstance(timeout, int) or timeout < 900:
    raise SystemExit(f"team-install-lifecycle timeout_sec must be at least 900, got {timeout}")
if "install-runtime" in steps:
    raise SystemExit("monolith install-runtime must not remain in the full plan")
if "ownership-inventory" in steps:
    raise SystemExit("ownership-inventory must not remain in the full plan")

timeout = steps["design-skill-governance-redesign"].get("timeout_sec")
if timeout != 300:
    raise SystemExit(f"design-skill-governance-redesign timeout_sec must stay exactly 300, got {timeout}")
PY

if bash "$RUNNER" --does-not-exist >/tmp/org_run_all_bad_option.out 2>&1; then
  fail "unknown option should fail"
fi
grep -Fq "unknown option" /tmp/org_run_all_bad_option.out || fail "unknown option message missing"

echo "run-all runner contract ok"
