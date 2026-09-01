#!/usr/bin/env bash
# shellcheck disable=SC2016
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILL="$ROOT/shared/skills/delivery-owner/SKILL.md"
INTAKE="$ROOT/shared/skills/delivery-owner/scripts/intake_preflight_check.sh"
PACKET="$ROOT/shared/skills/delivery-owner/scripts/task_packet_check.sh"
COMPLETION="$ROOT/shared/skills/delivery-owner/scripts/completion_check.sh"
REPLAY_CHECK="$ROOT/shared/skills/delivery-owner/scripts/behavior_replay_check.sh"
MANIFEST="$ROOT/shared/skills/delivery-owner/scripts/manifest.json"
REPLAY="$ROOT/shared/skills/delivery-owner/evals/minimal-behavior-replay.md"
LIFECYCLE="$ROOT/shared/skills/delivery-owner/evals/lifecycle-review.json"
PHASE="$ROOT/tests/fixtures/standard-chain-foundation/golden-pilot/sample-feature/phase-1"
TMP_DIR="$(mktemp -d "$ROOT/tests/.tmp.delivery-owner.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT
rm -rf "$ROOT/shared/skills/delivery-owner/scripts/__pycache__"

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local needle="$1"
  local file="$2"
  grep -Fq -- "$needle" "$file" || fail "$file missing: $needle"
}

assert_not_contains() {
  local needle="$1"
  local file="$2"
  if grep -Fq -- "$needle" "$file"; then
    fail "$file should not contain: $needle"
  fi
}

assert_missing() {
  local path="$1"
  [ ! -e "$path" ] || fail "unexpected retained file: ${path#"$ROOT"/}"
}

[ -f "$SKILL" ] || fail "missing active delivery-owner skill"
[ -x "$INTAKE" ] || fail "missing intake preflight wrapper"
[ -x "$PACKET" ] || fail "missing task packet wrapper"
[ -x "$COMPLETION" ] || fail "missing delivery readiness wrapper"
[ -x "$REPLAY_CHECK" ] || fail "missing behavior replay wrapper"
test -f "$MANIFEST" || fail "missing delivery-owner script manifest"
test -f "$REPLAY" || fail "missing delivery-owner minimal behavior replay"
test -f "$LIFECYCLE" || fail "missing delivery-owner lifecycle review"

PLAN_REVIEW="$ROOT/shared/skills/delivery-owner/references/plan-review.md"
DISPATCH_PACKET="$ROOT/shared/skills/delivery-owner/references/dispatch-packet.md"
FOLLOWUP_LOOPS="$ROOT/shared/skills/delivery-owner/references/followup-loops.md"
STATUS_TEMPLATE="$ROOT/shared/skills/delivery-owner/templates/status-card.template.md"
DECISION_TEMPLATE="$ROOT/shared/skills/delivery-owner/templates/user-decision-package.template.md"
REPORT_TEMPLATE="$ROOT/shared/skills/delivery-owner/templates/delivery-report.template.md"

for required_resource in \
  "$PLAN_REVIEW" \
  "$DISPATCH_PACKET" \
  "$FOLLOWUP_LOOPS" \
  "$STATUS_TEMPLATE" \
  "$DECISION_TEMPLATE" \
  "$REPORT_TEMPLATE"
do
  test -f "$required_resource" || fail "missing delivery-owner resource: ${required_resource#"$ROOT"/}"
done

bash "$REPLAY_CHECK" --replay "$REPLAY" >"$TMP_DIR/replay-check.json"
python3 - "$TMP_DIR/replay-check.json" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "PASS"
assert payload["decision"] == "REPLAY_CONTRACT_READY"
assert payload["case_count"] == 4
PY
python3 - "$REPLAY" "$TMP_DIR/replay-bad-missing-progress-file.md" <<'PY'
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])
text = source.read_text(encoding="utf-8")
marker = "## Replay 4: two no-progress rounds replay"
before, after = text.split(marker, 1)
after = after.replace("next_owner: user", "next_owner: fixer agent", 1)
target.write_text(before + marker + after, encoding="utf-8")
PY
set +e
bash "$REPLAY_CHECK" --replay "$TMP_DIR/replay-bad-missing-progress-file.md" >"$TMP_DIR/replay-bad-missing-progress-file.json"
replay_bad_rc=$?
set -e
[ "$replay_bad_rc" -ne 0 ] || fail "behavior replay check should fail when no-progress keeps dispatching fixer agent"
python3 - "$TMP_DIR/replay-bad-missing-progress-file.json" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "BLOCKED"
assert payload["decision"] == "REPLAY_CONTRACT_BLOCKED"
assert payload["failure_code"] in {"REPLAY_REQUIRED_TERM_MISSING", "REPLAY_FORBIDDEN_TERM_PRESENT"}
assert payload["section"] == "two no-progress rounds replay"
PY

STATUS_TEMPLATE="$ROOT/shared/skills/delivery-owner/templates/status-card.template.md"
DECISION_TEMPLATE="$ROOT/shared/skills/delivery-owner/templates/user-decision-package.template.md"
REPORT_TEMPLATE="$ROOT/shared/skills/delivery-owner/templates/delivery-report.template.md"

assert_contains "current_gap:" "$STATUS_TEMPLATE"
assert_contains "gap_owner:" "$STATUS_TEMPLATE"
assert_contains "next_owner:" "$STATUS_TEMPLATE"
assert_contains "progress_signal:" "$STATUS_TEMPLATE"
assert_contains "gap_judgment_changed" "$STATUS_TEMPLATE"
assert_not_contains "owner_changed" "$STATUS_TEMPLATE"
assert_not_contains "progress_signal: new_evidence" "$STATUS_TEMPLATE"
assert_contains "consecutive_no_progress_count:" "$STATUS_TEMPLATE"
assert_contains "owner_action_consumption:" "$STATUS_TEMPLATE"
assert_contains "stale_evidence_refs:" "$STATUS_TEMPLATE"
assert_contains "decision_boundary:" "$STATUS_TEMPLATE"
assert_contains "resume_condition:" "$STATUS_TEMPLATE"

assert_contains "decision_needed:" "$DECISION_TEMPLATE"
assert_contains "evidence_refs:" "$DECISION_TEMPLATE"
assert_contains "required_user_answer:" "$DECISION_TEMPLATE"
assert_contains "resume_condition:" "$DECISION_TEMPLATE"
assert_contains "next_action_after_decision:" "$DECISION_TEMPLATE"

assert_contains "dev_verify_summary:" "$REPORT_TEMPLATE"
assert_contains "qa_fix_summary:" "$REPORT_TEMPLATE"
assert_contains "commit_result:" "$REPORT_TEMPLATE"
assert_contains "open_risks:" "$REPORT_TEMPLATE"
assert_contains "evidence_refs:" "$REPORT_TEMPLATE"

for obsolete in \
  "$ROOT/shared/skills/delivery-owner/references/routing-and-packet.md" \
  "$ROOT/shared/skills/delivery-owner/references/evidence-and-followup.md" \
  "$ROOT/shared/skills/delivery-owner/references/intake-and-state.md" \
  "$ROOT/shared/skills/delivery-owner/references/escalation-and-signoff.md" \
  "$ROOT/shared/skills/delivery-owner/scripts/control_decision_check.sh" \
  "$ROOT/shared/skills/delivery-owner/scripts/control_decision_check.py" \
  "$ROOT/shared/skills/delivery-owner/scripts/control_decision_support.py" \
  "$ROOT/shared/skills/delivery-owner/scripts/__pycache__"
do
assert_missing "$obsolete"
done
assert_missing "$ROOT/shared/skills/delivery-owner-h"
assert_missing "$ROOT/tools/community/validate_delivery_owner_commit_preflight.py"

jq empty "$MANIFEST" >/dev/null || fail "delivery-owner manifest must be valid JSON"
python3 "$ROOT/tools/skill_quality/check_skill_body_quality.py" "$SKILL" >/tmp/delivery-owner-body-quality.json
python3 "$ROOT/tools/skill_quality/check_skill_package_quality.py" "$ROOT/shared/skills/delivery-owner" >/tmp/delivery-owner-package-quality.json
python3 -m py_compile \
  "$ROOT/shared/skills/delivery-owner/scripts/intake_preflight_check.py" \
  "$ROOT/shared/skills/delivery-owner/scripts/task_packet_check.py" \
  "$ROOT/shared/skills/delivery-owner/scripts/behavior_replay_check.py"
rm -rf "$ROOT/shared/skills/delivery-owner/scripts/__pycache__"
bash -n "$COMPLETION" || fail "completion wrapper must pass shell syntax"
bash -n "$REPLAY_CHECK" || fail "behavior replay wrapper must pass shell syntax"

python3 - "$MANIFEST" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
ids = {item.get("id") for item in manifest.get("scripts", [])}
if "control-decision-check" in ids:
    raise SystemExit("manifest must not expose old control-decision-check")
for expected in {"intake-preflight-check", "task-packet-check", "completion-check", "behavior-replay-check"}:
    if expected not in ids:
        raise SystemExit(f"manifest missing {expected}")
completion = next(item for item in manifest["scripts"] if item.get("id") == "completion-check")
external = set(completion.get("external_commands", []))
for command in {"mktemp", "rm"}:
    if command not in external:
        raise SystemExit(f"completion-check manifest missing external command {command}")
PY

bash "$INTAKE" --phase-dir "$PHASE" >"$TMP_DIR/intake-pass.json"
python3 - "$TMP_DIR/intake-pass.json" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "PASS"
assert payload["decision"] == "ACCEPTED"
assert payload["safe_for_baseline_audit"] is True
assert payload["safe_to_dispatch"] is False
assert payload["task_count"] >= 1
assert payload["qa_handoff_count"] >= 1
PY

cp -R "$PHASE/.." "$TMP_DIR/missing-task-contract-fields-feature"
MISSING_TASK_CONTRACT_PHASE="$TMP_DIR/missing-task-contract-fields-feature/phase-1"
jq 'del(.tasks[0].test_refs, .tasks[0].decision_refs, .tasks[0].shared_files, .tasks[0].evidence_target)' \
  "$MISSING_TASK_CONTRACT_PHASE/tasks.json" \
  >"$MISSING_TASK_CONTRACT_PHASE/tasks.tmp"
mv "$MISSING_TASK_CONTRACT_PHASE/tasks.tmp" \
  "$MISSING_TASK_CONTRACT_PHASE/tasks.json"
set +e
bash "$INTAKE" --phase-dir "$MISSING_TASK_CONTRACT_PHASE" >"$TMP_DIR/intake-missing-task-contract-fields.json"
missing_task_contract_rc=$?
set -e
[ "$missing_task_contract_rc" -ne 0 ] || fail "intake preflight should fail when tasks omit dispatch contract fields"
python3 - "$TMP_DIR/intake-missing-task-contract-fields.json" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "BLOCKED"
assert payload["decision"] == "NEEDS_BASELINE"
assert payload["failure_code"] == "TASK_CONTRACT_DRIFT"
assert payload["owner"] == "tech-lead"
reason = payload["reason"]
for field in ("test_refs", "decision_refs", "shared_files", "evidence_target"):
    assert field in reason
assert payload["safe_to_dispatch"] is False
assert payload["safe_for_baseline_audit"] is False
PY

cp -R "$PHASE/.." "$TMP_DIR/missing-test-design-consumption-feature"
MISSING_TEST_DESIGN_CONSUMPTION_PHASE="$TMP_DIR/missing-test-design-consumption-feature/phase-1"
jq '.obligation_source_refs = []' \
  "$MISSING_TEST_DESIGN_CONSUMPTION_PHASE/plan.json" \
  >"$MISSING_TEST_DESIGN_CONSUMPTION_PHASE/plan.tmp"
mv "$MISSING_TEST_DESIGN_CONSUMPTION_PHASE/plan.tmp" \
  "$MISSING_TEST_DESIGN_CONSUMPTION_PHASE/plan.json"
jq '(.tasks[] | .test_refs) |= map(select((contains("qa_handoff_contract:") or contains("cross_unit_obligations:") or contains("#traceability_matrix:")) | not))' \
  "$MISSING_TEST_DESIGN_CONSUMPTION_PHASE/tasks.json" \
  >"$MISSING_TEST_DESIGN_CONSUMPTION_PHASE/tasks.tmp"
mv "$MISSING_TEST_DESIGN_CONSUMPTION_PHASE/tasks.tmp" \
  "$MISSING_TEST_DESIGN_CONSUMPTION_PHASE/tasks.json"
set +e
bash "$INTAKE" --phase-dir "$MISSING_TEST_DESIGN_CONSUMPTION_PHASE" >"$TMP_DIR/intake-missing-test-design-consumption.json"
missing_test_design_consumption_rc=$?
set -e
[ "$missing_test_design_consumption_rc" -ne 0 ] || fail "intake preflight should fail when tech-lead baseline omits test-design obligation consumption"
python3 - "$TMP_DIR/intake-missing-test-design-consumption.json" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "BLOCKED"
assert payload["decision"] == "NEEDS_BASELINE"
assert payload["failure_code"] == "TEST_DESIGN_OBLIGATION_DRIFT"
assert payload["owner"] == "tech-lead"
assert "test-design obligations" in payload["reason"]
assert payload["safe_to_dispatch"] is False
assert payload["safe_for_baseline_audit"] is False
PY

cp -R "$PHASE/.." "$TMP_DIR/kickoff-only-feature"
KICKOFF_ONLY_PHASE="$TMP_DIR/kickoff-only-feature/phase-1"
rm -f \
  "$KICKOFF_ONLY_PHASE/code-review-result.json" \
  "$KICKOFF_ONLY_PHASE/qa-result.json" \
  "$KICKOFF_ONLY_PHASE/consistency-audit-result.json" \
  "$KICKOFF_ONLY_PHASE/signoff-package.json" \
  "$KICKOFF_ONLY_PHASE/user-decision.json" \
  "$KICKOFF_ONLY_PHASE/unit-1/tasks/T1/developer-report.json" \
  "$KICKOFF_ONLY_PHASE/unit-1/tasks/T1/verify-result.json" \
  "$KICKOFF_ONLY_PHASE/unit-1/tasks/T2/developer-report.json" \
  "$KICKOFF_ONLY_PHASE/unit-1/tasks/T2/verify-result.json"
bash "$INTAKE" --phase-dir "$KICKOFF_ONLY_PHASE" >"$TMP_DIR/intake-kickoff-only.json"
python3 - "$TMP_DIR/intake-kickoff-only.json" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "PASS"
assert payload["safe_for_baseline_audit"] is True
assert payload["safe_to_dispatch"] is False
PY

mkdir -p "$TMP_DIR/missing-tasks"
set +e
bash "$INTAKE" --phase-dir "$TMP_DIR/missing-tasks" >"$TMP_DIR/intake-fail.json"
intake_rc=$?
set -e
[ "$intake_rc" -ne 0 ] || fail "intake preflight should fail when tasks.json is missing"
python3 - "$TMP_DIR/intake-fail.json" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "BLOCKED"
assert payload["decision"] == "NEEDS_INPUT"
assert payload["safe_to_dispatch"] is False
assert payload["safe_for_baseline_audit"] is False
PY

cp -R "$PHASE/.." "$TMP_DIR/missing-qa-handoff-feature"
MISSING_QA_PHASE="$TMP_DIR/missing-qa-handoff-feature/phase-1"
jq 'del(.qa_handoff_contract)' \
  "$MISSING_QA_PHASE/unit-1/test-cases.json" \
  >"$MISSING_QA_PHASE/unit-1/test-cases.tmp"
mv "$MISSING_QA_PHASE/unit-1/test-cases.tmp" \
  "$MISSING_QA_PHASE/unit-1/test-cases.json"
set +e
bash "$INTAKE" --phase-dir "$MISSING_QA_PHASE" >"$TMP_DIR/intake-missing-qa.json"
missing_qa_rc=$?
set -e
[ "$missing_qa_rc" -ne 0 ] || fail "intake preflight should fail when qa_handoff_contract is missing"
python3 - "$TMP_DIR/intake-missing-qa.json" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "BLOCKED"
assert payload["decision"] == "NEEDS_BASELINE"
assert payload["failure_code"] == "MISSING_QA_HANDOFF"
assert payload["owner"] == "test-design"
assert payload["safe_to_dispatch"] is False
assert payload["safe_for_baseline_audit"] is False
PY

cp -R "$PHASE/.." "$TMP_DIR/missing-plan-readiness-feature"
MISSING_PLAN_PHASE="$TMP_DIR/missing-plan-readiness-feature/phase-1"
jq 'del(.planning_readiness)' \
  "$MISSING_PLAN_PHASE/plan.json" \
  >"$MISSING_PLAN_PHASE/plan.tmp"
mv "$MISSING_PLAN_PHASE/plan.tmp" \
  "$MISSING_PLAN_PHASE/plan.json"
set +e
bash "$INTAKE" --phase-dir "$MISSING_PLAN_PHASE" >"$TMP_DIR/intake-missing-plan-readiness.json"
missing_plan_readiness_rc=$?
set -e
[ "$missing_plan_readiness_rc" -ne 0 ] || fail "intake preflight should fail when planning_readiness is missing"
python3 - "$TMP_DIR/intake-missing-plan-readiness.json" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "BLOCKED"
assert payload["decision"] == "NEEDS_BASELINE"
assert payload["failure_code"] == "PLAN_NOT_READY"
assert payload["owner"] == "tech-lead"
assert payload["safe_for_baseline_audit"] is False
assert payload["safe_to_dispatch"] is False
PY

cp -R "$PHASE/.." "$TMP_DIR/missing-cross-unit-obligations-feature"
MISSING_CROSS_UNIT_PHASE="$TMP_DIR/missing-cross-unit-obligations-feature/phase-1"
jq 'del(.cross_unit_obligations)' \
  "$MISSING_CROSS_UNIT_PHASE/unit-1/test-cases.json" \
  >"$MISSING_CROSS_UNIT_PHASE/unit-1/test-cases.tmp"
mv "$MISSING_CROSS_UNIT_PHASE/unit-1/test-cases.tmp" \
  "$MISSING_CROSS_UNIT_PHASE/unit-1/test-cases.json"
set +e
bash "$INTAKE" --phase-dir "$MISSING_CROSS_UNIT_PHASE" >"$TMP_DIR/intake-missing-cross-unit-obligations.json"
missing_cross_unit_rc=$?
set -e
[ "$missing_cross_unit_rc" -ne 0 ] || fail "intake preflight should fail when cross_unit_obligations is missing"
python3 - "$TMP_DIR/intake-missing-cross-unit-obligations.json" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "BLOCKED"
assert payload["decision"] == "NEEDS_BASELINE"
assert payload["failure_code"] == "MISSING_CROSS_UNIT_OBLIGATIONS"
assert payload["owner"] == "test-design"
assert payload["safe_for_baseline_audit"] is False
assert payload["safe_to_dispatch"] is False
PY

cp -R "$PHASE/.." "$TMP_DIR/director-lock-drift-feature"
DIRECTOR_LOCK_DRIFT_PHASE="$TMP_DIR/director-lock-drift-feature/phase-1"
jq '.director_confirmation.locked_field_digest = "sha256:0000000000000000000000000000000000000000000000000000000000000000"' \
  "$DIRECTOR_LOCK_DRIFT_PHASE/phase-prd.json" \
  >"$DIRECTOR_LOCK_DRIFT_PHASE/phase-prd.tmp"
mv "$DIRECTOR_LOCK_DRIFT_PHASE/phase-prd.tmp" \
  "$DIRECTOR_LOCK_DRIFT_PHASE/phase-prd.json"
set +e
bash "$INTAKE" --phase-dir "$DIRECTOR_LOCK_DRIFT_PHASE" >"$TMP_DIR/intake-director-lock-drift.json"
director_lock_drift_rc=$?
set -e
[ "$director_lock_drift_rc" -ne 0 ] || fail "intake preflight should fail when director lock digest drifts"
python3 - "$TMP_DIR/intake-director-lock-drift.json" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "BLOCKED"
assert payload["decision"] == "NEEDS_BASELINE"
assert payload["failure_code"] == "DIRECTOR_LOCK_DRIFT"
assert payload["owner"] == "product-manager"
assert payload["safe_for_baseline_audit"] is False
assert payload["safe_to_dispatch"] is False
PY

cat >"$TMP_DIR/packet-pass.json" <<'JSON'
{
  "task_ref": "artifact://tasks/sample-feature.phase-1.tasks@tasks-v2#task-T1",
  "role": "developer",
  "goal": "Implement AC-T1-1 only",
  "forbidden_scope": ["docs/sample-feature/phase-1/tasks.json", "docs/sample-feature/phase-1/test-cases.json", "docs/sample-feature/phase-1/phase-prd.json"],
  "input_refs": ["artifact://tasks/sample-feature.phase-1.tasks@tasks-v2#plan-version"],
  "expected_evidence": ["developer preflight PASS", "RED output", "GREEN output", "REFACTOR or no-op note", "developer-report.json"],
  "stop_condition": "AC-T1-1 green or scope/AC blocked",
  "forbidden_actions": [
    "do not violate scope boundary: do not modify files listed in forbidden_scope",
    "do not modify baseline or AC",
    "do not commit or release",
    "do not conclude for other roles"
  ]
}
JSON
bash "$PACKET" --packet "$TMP_DIR/packet-pass.json" >"$TMP_DIR/packet-pass.out"
python3 - "$TMP_DIR/packet-pass.out" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "PASS"
assert payload["decision"] == "DISPATCH_READY"
assert payload["role"] == "developer"
PY

bash "$PACKET" \
  --packet "$TMP_DIR/packet-pass.json" \
  --authorize-dispatch \
  --session-id "dispatch-session" \
  --dispatch-state-dir "$TMP_DIR/dispatch-auth" \
  --ttl-seconds 300 \
  >"$TMP_DIR/packet-dispatch-auth.out"
python3 - "$TMP_DIR/packet-dispatch-auth.out" "$TMP_DIR/dispatch-auth/dispatch-session.json" <<'PY'
import json
import sys
from datetime import datetime

payload = json.load(open(sys.argv[1], encoding="utf-8"))
token = json.load(open(sys.argv[2], encoding="utf-8"))
assert payload["status"] == "PASS"
assert payload["decision"] == "DISPATCH_READY"
assert payload["role"] == "developer"
assert payload["dispatch_authorization_ref"] == sys.argv[2]
assert token["schema_version"] == 1
assert token["session_id"] == "dispatch-session"
assert token["role"] == "developer"
assert token["authorized_by"] == "delivery-owner"
assert token["task_ref"] == payload["task_ref"]
assert len(token["packet_sha256"]) == 64
assert datetime.fromisoformat(token["expires_at"])
PY

mkdir -p "$TMP_DIR/active-skills"
jq -n '{session_id: "inferred-session", skill: "delivery-owner", updated_at: "2026-07-03T00:00:00+00:00"}' \
  >"$TMP_DIR/active-skills/inferred-session.json"
ORG_CODEX_ACTIVE_SKILLS_STATE_DIR="$TMP_DIR/active-skills" bash "$PACKET" \
  --packet "$TMP_DIR/packet-pass.json" \
  --authorize-dispatch \
  --dispatch-state-dir "$TMP_DIR/inferred-dispatch-auth" \
  >"$TMP_DIR/packet-inferred-dispatch-auth.out"
python3 - "$TMP_DIR/packet-inferred-dispatch-auth.out" "$TMP_DIR/inferred-dispatch-auth/inferred-session.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
token = json.load(open(sys.argv[2], encoding="utf-8"))
assert payload["status"] == "PASS"
assert payload["dispatch_authorization_ref"] == sys.argv[2]
assert token["session_id"] == "inferred-session"
assert token["role"] == "developer"
PY

cat >"$TMP_DIR/packet-legacy-scope-fail.json" <<'JSON'
{
  "task_ref": "artifact://tasks/sample-feature.phase-1.tasks@tasks-v2#task-T1",
  "role": "developer",
  "goal": "Implement AC-T1-1 only",
  "scope": ["src/feature.ts", "tests/feature.test.ts"],
  "forbidden_scope": ["docs/sample-feature/phase-1/tasks.json", "docs/sample-feature/phase-1/test-cases.json", "docs/sample-feature/phase-1/phase-prd.json"],
  "input_refs": ["artifact://tasks/sample-feature.phase-1.tasks@tasks-v2#plan-version"],
  "expected_evidence": ["developer preflight PASS", "RED output", "GREEN output", "REFACTOR or no-op note", "developer-report.json"],
  "stop_condition": "AC-T1-1 green or scope/AC blocked",
  "forbidden_actions": [
    "do not violate scope boundary: do not modify files listed in forbidden_scope",
    "do not modify baseline or AC",
    "do not commit or release",
    "do not conclude for other roles"
  ]
}
JSON
set +e
bash "$PACKET" --packet "$TMP_DIR/packet-legacy-scope-fail.json" >"$TMP_DIR/packet-legacy-scope-fail.out"
legacy_scope_rc=$?
set -e
[ "$legacy_scope_rc" -ne 0 ] || fail "task packet check should reject legacy top-level scope even when forbidden_scope exists"
python3 - "$TMP_DIR/packet-legacy-scope-fail.out" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "BLOCKED"
assert payload["decision"] == "PACKET_BLOCKED"
assert payload["failure_code"] == "PACKET_UNSAFE"
assert "scope" in payload["fields"]
PY

cat >"$TMP_DIR/packet-path-with-done-pass.json" <<'JSON'
{
  "task_ref": "artifact://tasks/done-feature.phase-1.tasks@tasks-v2#task-T1",
  "role": "developer",
  "goal": "Implement AC-T1-1 only",
  "forbidden_scope": ["docs/done-feature/phase-1/tasks.json", "docs/done-feature/phase-1/test-cases.json"],
  "input_refs": ["artifact://tasks/done-feature.phase-1.tasks@tasks-v2#plan-version"],
  "expected_evidence": ["developer preflight PASS", "RED output", "GREEN output", "REFACTOR or no-op note", "developer-report.json"],
  "stop_condition": "AC-T1-1 green or scope/AC blocked",
  "forbidden_actions": [
    "do not violate scope boundary: do not modify files listed in forbidden_scope",
    "do not modify baseline or AC",
    "do not commit or release",
    "do not conclude for other roles"
  ]
}
JSON
bash "$PACKET" --packet "$TMP_DIR/packet-path-with-done-pass.json" >"$TMP_DIR/packet-path-with-done-pass.out"
python3 - "$TMP_DIR/packet-path-with-done-pass.out" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "PASS"
assert payload["decision"] == "DISPATCH_READY"
assert payload["role"] == "developer"
PY

cat >"$TMP_DIR/packet-review-pass.json" <<'JSON'
{
  "task_ref": "artifact://tasks/sample-feature.phase-1.tasks@tasks-v2#batch-review",
  "role": "review",
  "goal": "Review verified implementation batch before QA handoff",
  "forbidden_scope": ["src/", "tests/", "docs/sample-feature/phase-1/tasks.json", "docs/sample-feature/phase-1/test-cases.json"],
  "input_refs": ["tasks.json#batch", "developer-report.json#T1", "verify-result.json#T1", "git diff base..head"],
  "expected_evidence": ["Strengths", "Issues", "Recommendations", "Assessment", "code-review-result.json"],
  "stop_condition": "Assessment Yes with no blocking issues or exact review issue reported",
  "forbidden_actions": [
    "do not violate scope boundary: do not modify files listed in forbidden_scope",
    "do not modify baseline or AC",
    "do not commit or release",
    "do not conclude for other roles"
  ]
}
JSON
bash "$PACKET" --packet "$TMP_DIR/packet-review-pass.json" >"$TMP_DIR/packet-review-pass.out"
python3 - "$TMP_DIR/packet-review-pass.out" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "PASS"
assert payload["decision"] == "DISPATCH_READY"
assert payload["role"] == "review"
PY

cat >"$TMP_DIR/packet-consistency-auditor-pass.json" <<'JSON'
{
  "task_ref": "artifact://phase/sample-feature.phase-1#baseline-consistency-audit",
  "role": "consistency-auditor",
  "goal": "Run baseline advisory consistency audit before delivery-owner dispatches implementation",
  "forbidden_scope": ["brief.json", "phase-prd.json", "plan.json", "tasks.json", "design.json", "test-cases.json"],
  "input_refs": ["brief.json", "phase-prd.json", "artifact-registry.json", "plan.json", "tasks.json", "design.json", "test-cases.json", "qa_handoff_contract", "cross_unit_obligations"],
  "expected_evidence": ["advisory_only", "findings", "required_owner_action", "consistency-audit-result.json"],
  "stop_condition": "No blocked owner action remains, or exact upstream owner action is reported",
  "forbidden_actions": ["禁止越界修改 forbidden_scope 中的文件", "禁止修改 baseline、AC 或验收标准", "禁止执行 commit/release", "禁止替其他角色签收或接受风险"]
}
JSON
bash "$PACKET" --packet "$TMP_DIR/packet-consistency-auditor-pass.json" >"$TMP_DIR/packet-consistency-auditor-pass.out"
python3 - "$TMP_DIR/packet-consistency-auditor-pass.out" <<'PY'
import json
import sys

payload = json.loads(open(sys.argv[1], encoding="utf-8").read())
assert payload["status"] == "PASS"
assert payload["role"] == "consistency-auditor"
PY

cat >"$TMP_DIR/packet-final-consistency-auditor-pass.json" <<'JSON'
{
  "task_ref": "artifact://phase/sample-feature.phase-1#consistency-audit",
  "role": "consistency-auditor",
  "goal": "Run full advisory consistency audit before commit handoff",
  "forbidden_scope": ["docs/sample-feature/phase-1/tasks.json", "docs/sample-feature/phase-1/test-cases.json", "docs/sample-feature/phase-1/phase-prd.json"],
  "input_refs": ["brief.json", "phase-prd.json", "artifact-registry.json", "plan.json", "tasks.json", "design.json", "test-cases.json", "developer-report.json", "verify-result.json", "code-review-result.json", "qa-result.json", "delivery-state.json", "signoff-package.json"],
  "expected_evidence": ["advisory_only", "findings", "required_owner_action", "consistency-audit-result.json"],
  "stop_condition": "No blocked owner action or exact owner action reported",
  "forbidden_actions": [
    "do not violate scope boundary: do not modify files listed in forbidden_scope",
    "do not modify baseline or AC",
    "do not commit or release",
    "do not conclude for other roles"
  ]
}
JSON
bash "$PACKET" --packet "$TMP_DIR/packet-final-consistency-auditor-pass.json" >"$TMP_DIR/packet-final-consistency-auditor-pass.out"
python3 - "$TMP_DIR/packet-final-consistency-auditor-pass.out" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "PASS"
assert payload["decision"] == "DISPATCH_READY"
assert payload["role"] == "consistency-auditor"
PY

cat >"$TMP_DIR/packet-final-consistency-auditor-missing-runtime.json" <<'JSON'
{
  "task_ref": "artifact://phase/sample-feature.phase-1#consistency-audit",
  "role": "consistency-auditor",
  "goal": "Run full advisory consistency audit before commit handoff",
  "forbidden_scope": ["docs/sample-feature/phase-1/tasks.json", "docs/sample-feature/phase-1/test-cases.json", "docs/sample-feature/phase-1/phase-prd.json"],
  "input_refs": ["brief.json", "phase-prd.json", "artifact-registry.json", "code-review-result.json", "qa-result.json"],
  "expected_evidence": ["advisory_only", "findings", "required_owner_action", "consistency-audit-result.json"],
  "stop_condition": "No blocked owner action or exact owner action reported",
  "forbidden_actions": [
    "do not violate scope boundary: do not modify files listed in forbidden_scope",
    "do not modify baseline or AC",
    "do not commit or release",
    "do not conclude for other roles"
  ]
}
JSON
set +e
bash "$PACKET" --packet "$TMP_DIR/packet-final-consistency-auditor-missing-runtime.json" >"$TMP_DIR/packet-final-consistency-auditor-missing-runtime.out"
missing_runtime_rc=$?
set -e
[ "$missing_runtime_rc" -ne 0 ] || fail "final consistency-auditor packet should fail without baseline, test-case, developer, and verifier refs"
python3 - "$TMP_DIR/packet-final-consistency-auditor-missing-runtime.out" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "BLOCKED"
assert payload["decision"] == "PACKET_BLOCKED"
assert payload["failure_code"] == "PACKET_INPUT_INCOMPLETE"
for field in ["baseline_artifacts", "qa_handoff_obligations", "implementation_evidence", "verification_evidence"]:
    assert field in payload["fields"]
PY

cat >"$TMP_DIR/packet-object-refs-pass.json" <<'JSON'
{
  "task_ref": "artifact://tasks/sample-feature.phase-1.tasks@tasks-v2#task-T2",
  "role": "developer",
  "goal": "Close AC-T2-2 missing scope evidence only",
  "forbidden_scope": ["docs/sample-feature/phase-1/tasks.json", "docs/sample-feature/phase-1/test-cases.json", "docs/sample-feature/phase-1/phase-prd.json"],
  "input_refs": [
    {
      "ref": "artifact://tasks/sample-feature.phase-1.tasks@tasks-v2#task-T2",
      "path": "unavailable"
    },
    {
      "ref": "verify-result:AC-T2-2-missing-scope-evidence",
      "path": "unavailable"
    }
  ],
  "expected_evidence": [
    {"ref": "developer preflight PASS"},
    {"ref": "RED output"},
    {"ref": "GREEN output"},
    {"ref": "REFACTOR or no-op note"},
    {"ref": "developer-report.json"}
  ],
  "stop_condition": "AC-T2-2 scope evidence provided or exact blocker reported",
  "forbidden_actions": [
    "do not violate scope boundary: do not modify files listed in forbidden_scope",
    "do not modify baseline or AC",
    "do not commit or release",
    "do not conclude for other roles"
  ]
}
JSON
bash "$PACKET" --packet "$TMP_DIR/packet-object-refs-pass.json" >"$TMP_DIR/packet-object-refs-pass.out"
python3 - "$TMP_DIR/packet-object-refs-pass.out" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "PASS"
assert payload["decision"] == "DISPATCH_READY"
assert payload["role"] == "developer"
PY

cat >"$TMP_DIR/packet-fail.json" <<'JSON'
{
  "task_ref": "artifact://tasks/sample-feature.phase-1.tasks@tasks-v2#task-T1",
  "role": "developer",
  "goal": "Fix it",
  "forbidden_scope": "按需处理",
  "input_refs": ["artifact://tasks/sample-feature.phase-1.tasks@tasks-v2#plan-version"],
  "expected_evidence": "完成即可",
  "stop_condition": "done",
  "forbidden_actions": ["do not commit"]
}
JSON
set +e
bash "$PACKET" --packet "$TMP_DIR/packet-fail.json" >"$TMP_DIR/packet-fail.out"
packet_rc=$?
set -e
[ "$packet_rc" -ne 0 ] || fail "task packet check should fail on ambiguous packet"
python3 - "$TMP_DIR/packet-fail.out" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "BLOCKED"
assert payload["decision"] == "PACKET_BLOCKED"
assert payload["safe_to_dispatch"] is False
PY

cat >"$TMP_DIR/packet-ambiguous-variant.json" <<'JSON'
{
  "task_ref": "artifact://tasks/sample-feature.phase-1.tasks@tasks-v2#task-T1",
  "role": "developer",
  "goal": "Implement AC-T1-1 only",
  "forbidden_scope": "按需处理。",
  "input_refs": ["artifact://tasks/sample-feature.phase-1.tasks@tasks-v2#plan-version"],
  "expected_evidence": ["developer preflight PASS", "RED output", "GREEN output", "REFACTOR or no-op note", "developer-report.json"],
  "stop_condition": "done when ready",
  "forbidden_actions": [
    "do not violate scope boundary: do not modify files listed in forbidden_scope",
    "do not modify baseline or AC",
    "do not commit or release",
    "do not conclude for other roles"
  ]
}
JSON
set +e
bash "$PACKET" --packet "$TMP_DIR/packet-ambiguous-variant.json" >"$TMP_DIR/packet-ambiguous-variant.out"
ambiguous_variant_rc=$?
set -e
[ "$ambiguous_variant_rc" -ne 0 ] || fail "task packet check should fail on punctuated or embedded ambiguous values"
python3 - "$TMP_DIR/packet-ambiguous-variant.out" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "BLOCKED"
assert payload["decision"] == "PACKET_BLOCKED"
assert payload["failure_code"] == "PACKET_AMBIGUOUS"
assert "forbidden_scope" in payload["fields"] or "stop_condition" in payload["fields"]
PY

cat >"$TMP_DIR/qa-packet-pass.json" <<'JSON'
{
  "task_ref": "artifact://tasks/sample-feature.phase-1.tasks@tasks-v2#qa",
  "role": "qa",
  "goal": "Validate required user paths after verified tasks",
  "forbidden_scope": ["src/", "tests/", "docs/sample-feature/phase-1/tasks.json", "docs/sample-feature/phase-1/test-cases.json"],
  "input_refs": [
    "artifact://qa-handoff/sample-feature.phase-1.unit-1@v1#qa_handoff_contract",
    "artifact://verify-result/sample-feature.phase-1.task-T1@v1#pass"
  ],
  "expected_evidence": ["QA_A result", "QA_B result", "QA_C result", "QA_D result", "qa-result.json"],
  "stop_condition": "All required QA paths pass or a reproducible issue is reported",
  "forbidden_actions": [
    "do not violate scope boundary: do not modify files listed in forbidden_scope",
    "do not modify baseline or AC",
    "do not commit or release",
    "do not conclude for other roles"
  ]
}
JSON
bash "$PACKET" --packet "$TMP_DIR/qa-packet-pass.json" >"$TMP_DIR/qa-packet-pass.out"
python3 - "$TMP_DIR/qa-packet-pass.out" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "PASS"
assert payload["role"] == "qa"
PY

cat >"$TMP_DIR/qa-packet-missing-verify.json" <<'JSON'
{
  "task_ref": "artifact://tasks/sample-feature.phase-1.tasks@tasks-v2#qa",
  "role": "qa",
  "goal": "Validate required user paths after verified tasks",
  "forbidden_scope": ["src/", "tests/", "docs/sample-feature/phase-1/tasks.json", "docs/sample-feature/phase-1/test-cases.json"],
  "input_refs": ["artifact://qa-handoff/sample-feature.phase-1.unit-1@v1#qa_handoff_contract"],
  "expected_evidence": ["QA_A result", "QA_B result", "QA_C result", "QA_D result", "qa-result.json"],
  "stop_condition": "All required QA paths pass or a reproducible issue is reported",
  "forbidden_actions": [
    "do not violate scope boundary: do not modify files listed in forbidden_scope",
    "do not modify baseline or AC",
    "do not commit or release",
    "do not conclude for other roles"
  ]
}
JSON
set +e
bash "$PACKET" --packet "$TMP_DIR/qa-packet-missing-verify.json" >"$TMP_DIR/qa-packet-missing-verify.out"
missing_verify_rc=$?
set -e
[ "$missing_verify_rc" -ne 0 ] || fail "qa task packet should fail without verify-result input ref"
python3 - "$TMP_DIR/qa-packet-missing-verify.out" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "BLOCKED"
assert payload["decision"] == "PACKET_BLOCKED"
assert payload["failure_code"] == "PACKET_INPUT_INCOMPLETE"
assert "verified_evidence" in payload["fields"]
PY

cat >"$TMP_DIR/verifier-packet-pass.json" <<'JSON'
{
  "task_ref": "artifact://tasks/sample-feature.phase-1.tasks@tasks-v2#task-T1",
  "role": "verifier",
  "goal": "Verify AC and scope for T1",
  "forbidden_scope": ["src/", "tests/", "docs/sample-feature/phase-1/tasks.json", "docs/sample-feature/phase-1/test-cases.json"],
  "input_refs": ["artifact://developer-report/sample-feature.phase-1.task-T1@v1#summary"],
  "expected_evidence": ["AC verification", "scope verification", "verify-result.json"],
  "stop_condition": "AC/scope PASS or exact missing gap is reported",
  "forbidden_actions": [
    "do not violate scope boundary: do not modify files listed in forbidden_scope",
    "do not modify baseline or AC",
    "do not commit or release",
    "do not conclude for other roles"
  ]
}
JSON
bash "$PACKET" --packet "$TMP_DIR/verifier-packet-pass.json" >"$TMP_DIR/verifier-packet-pass.out"
python3 - "$TMP_DIR/verifier-packet-pass.out" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "PASS"
assert payload["role"] == "verifier"
PY

cat >"$TMP_DIR/fixer-packet-pass.json" <<'JSON'
{
  "task_ref": "artifact://tasks/sample-feature.phase-1.tasks@tasks-v2#task-T1",
  "role": "fixer",
  "goal": "Root cause and minimal fix for the reported failure",
  "forbidden_scope": ["docs/sample-feature/phase-1/tasks.json", "docs/sample-feature/phase-1/test-cases.json", "docs/sample-feature/phase-1/phase-prd.json"],
  "input_refs": ["artifact://verify-result/sample-feature.phase-1.task-T1@v1#fail"],
  "expected_evidence": ["root cause", "minimal fix", "freshness check", "fix-result.json"],
  "stop_condition": "Failure fixed or exact blocker is reported",
  "forbidden_actions": [
    "do not violate scope boundary: do not modify files listed in forbidden_scope",
    "do not modify baseline or AC",
    "do not commit or release",
    "do not conclude for other roles"
  ]
}
JSON
bash "$PACKET" --packet "$TMP_DIR/fixer-packet-pass.json" >"$TMP_DIR/fixer-packet-pass.out"
python3 - "$TMP_DIR/fixer-packet-pass.out" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["status"] == "PASS"
assert payload["role"] == "fixer"
PY

echo "[PASS] delivery-owner SOP contract"
