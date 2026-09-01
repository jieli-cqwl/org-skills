#!/usr/bin/env bash
set -euo pipefail

# File responsibility: shared helpers for install.sh integration tests. The
# helpers keep HOME/state/logs isolated per case and only reuse process-local
# baselines created by a real install run.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=tests/lib/test-env.sh
. "$ROOT/tests/lib/test-env.sh"

INSTALL_TEST_TMP_ROOT=""
INSTALL_TEST_CURRENT_CASE=""
INSTALL_TEST_CURRENT_LOG=""
INSTALL_TEST_BASELINE_HOME=""
INSTALL_TEST_CASE_COUNT=0

install_test_fail() {
  printf '[FAIL] %s\n' "$*" >&2
  if [ -n "${INSTALL_TEST_CURRENT_LOG:-}" ] && [ -f "$INSTALL_TEST_CURRENT_LOG" ]; then
    printf 'install log: %s\n' "$INSTALL_TEST_CURRENT_LOG" >&2
    printf 'last output:\n' >&2
    tail -40 "$INSTALL_TEST_CURRENT_LOG" >&2 || true
  fi
  exit 1
}

install_test_case_start() {
  INSTALL_TEST_CURRENT_CASE="$1"
  INSTALL_TEST_CASE_COUNT=$((INSTALL_TEST_CASE_COUNT + 1))
  printf '[CASE] %s\n' "$INSTALL_TEST_CURRENT_CASE"
}

install_test_case_pass() {
  printf '[PASS] %s\n' "$1"
}

install_test_init() {
  INSTALL_TEST_TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/org-install-tests.XXXXXX")"
  trap install_test_cleanup EXIT
}

install_test_cleanup() {
  if [ -z "${INSTALL_TEST_TMP_ROOT:-}" ]; then
    return 0
  fi

  if [ "${KEEP_TEST_HOME:-0}" = "1" ]; then
    printf '[KEEP_TEST_HOME] %s\n' "$INSTALL_TEST_TMP_ROOT"
    return 0
  fi

  chmod -R u+w "$INSTALL_TEST_TMP_ROOT" 2>/dev/null || true
  rm -rf "$INSTALL_TEST_TMP_ROOT"
}

install_test_slug() {
  printf '%s\n' "$1" | tr -c '[:alnum:]_.-' '-'
}

install_test_log_path() {
  local name
  name="$(install_test_slug "$1")"
  printf '%s/%s.log\n' "$INSTALL_TEST_TMP_ROOT" "$name"
}

install_test_new_home() {
  local name="$1"
  local home_dir="$INSTALL_TEST_TMP_ROOT/$name"

  rm -rf "$home_dir"
  mkdir -p "$home_dir/.claude" "$home_dir/.codex"
  printf '{"hooks":{}}\n' > "$home_dir/.claude/settings.json"
  printf 'model = "gpt-5"\n' > "$home_dir/.codex/config.toml"
  printf '%s\n' "$home_dir"
}

install_test_state_root() {
  printf '%s/.local/state/skill-repos\n' "$1"
}

install_test_pythonpath() {
  if [ -n "${PYTHONPATH:-}" ]; then
    printf '%s:%s\n' "$ROOT" "$PYTHONPATH"
  else
    printf '%s\n' "$ROOT"
  fi
}

install_test_run_env() {
  local home_dir="$1"
  shift
  env -u ORG_STATE_ROOT \
    HOME="$home_dir" \
    SKILL_REPO_STATE_ROOT="$(install_test_state_root "$home_dir")" \
    PYTHONPATH="$(install_test_pythonpath)" \
    PYTHONDONTWRITEBYTECODE=1 \
    "$@"
}

install_test_run_install_allow_failure() {
  local home_dir="$1"
  local log_file="$2"
  local restore_errexit=0
  shift 2

  case "$-" in
    *e*) restore_errexit=1 ;;
  esac
  INSTALL_TEST_CURRENT_LOG="$log_file"
  mkdir -p "$(dirname "$log_file")"
  set +e
  install_test_run_env "$home_dir" bash "$ROOT/install.sh" "$@" >"$log_file" 2>&1
  local rc=$?
  if [ "$restore_errexit" -eq 1 ]; then
    set -e
  fi
  return "$rc"
}

install_test_run_install() {
  local home_dir="$1"
  local log_file="$2"
  shift 2

  install_test_run_install_allow_failure "$home_dir" "$log_file" "$@" || {
    local rc=$?
    install_test_fail "install command failed with exit $rc"
  }
}

BASE_CHECKOUT="${BASE_CHECKOUT:-/Users/lijieli/base-config}"

install_test_run_base_allow_failure() {
  local home_dir="$1"
  local log_file="$2"
  local restore_errexit=0
  shift 2

  case "$-" in
    *e*) restore_errexit=1 ;;
  esac
  INSTALL_TEST_CURRENT_LOG="$log_file"
  mkdir -p "$(dirname "$log_file")"
  [ -x "$BASE_CHECKOUT/install.sh" ] || install_test_fail "Base installer missing at $BASE_CHECKOUT/install.sh"
  set +e
  install_test_run_env "$home_dir" bash "$BASE_CHECKOUT/install.sh" "$@" >"$log_file" 2>&1
  local rc=$?
  if [ "$restore_errexit" -eq 1 ]; then
    set -e
  fi
  return "$rc"
}

install_test_run_base() {
  local home_dir="$1"
  local log_file="$2"
  shift 2

  install_test_run_base_allow_failure "$home_dir" "$log_file" "$@" || {
    local rc=$?
    install_test_fail "Base install command failed with exit $rc"
  }
}

install_test_run_install_fake_openspec_allow_failure() {
  local home_dir="$1"
  local log_file="$2"
  local restore_errexit=0
  shift 2

  case "$-" in
    *e*) restore_errexit=1 ;;
  esac
  INSTALL_TEST_CURRENT_LOG="$log_file"
  mkdir -p "$(dirname "$log_file")"
  set +e
  run_with_fake_openspec "$home_dir" install_test_run_env "$home_dir" bash "$ROOT/install.sh" "$@" >"$log_file" 2>&1
  local rc=$?
  if [ "$restore_errexit" -eq 1 ]; then
    set -e
  fi
  return "$rc"
}

install_test_run_install_fake_openspec() {
  local home_dir="$1"
  local log_file="$2"
  shift 2

  install_test_run_install_fake_openspec_allow_failure "$home_dir" "$log_file" "$@" || {
    local rc=$?
    install_test_fail "install command failed with exit $rc"
  }
}

install_test_create_baseline_home() {
  local name="${1:-baseline}"

  INSTALL_TEST_BASELINE_HOME="$(install_test_new_home "$name")"
  install_test_run_base "$INSTALL_TEST_BASELINE_HOME" "$(install_test_log_path "$name-base")" --target all
  install_test_run_install "$INSTALL_TEST_BASELINE_HOME" "$(install_test_log_path "$name")" --target all
  printf '%s\n' "$INSTALL_TEST_BASELINE_HOME"
}

install_test_rewrite_cloned_paths() {
  local old_home="$1"
  local new_home="$2"

  OLD_HOME="$old_home" NEW_HOME="$new_home" python3 <<'PY'
from __future__ import annotations

import os
from pathlib import Path

old = os.environ["OLD_HOME"].encode()
new = os.environ["NEW_HOME"].encode()
root = Path(os.environ["NEW_HOME"])

for path in root.rglob("*"):
    if not path.is_file() or path.is_symlink():
        continue
    try:
        data = path.read_bytes()
    except OSError:
        continue
    if old not in data:
        continue
    path.write_bytes(data.replace(old, new))
PY
}

install_test_clone_baseline_home() {
  local name="$1"
  local target="$INSTALL_TEST_TMP_ROOT/$name"

  [ -n "$INSTALL_TEST_BASELINE_HOME" ] || install_test_fail "baseline home has not been created"
  rm -rf "$target"
  cp -a "$INSTALL_TEST_BASELINE_HOME" "$target"
  install_test_rewrite_cloned_paths "$INSTALL_TEST_BASELINE_HOME" "$target"
  printf '%s\n' "$target"
}

install_test_current_version_tag() {
  python3 - "$ROOT" <<'PY'
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
targets = ["VERSION", "install.sh", "uninstall.sh", "shared", "claude", "codex", "community", "contracts", "tools", "tests", ".github"]
ignored_dirs = {".git", "__pycache__"}
ignored_files = {".DS_Store"}


def is_runtime_pruned_skill_tree(path: Path) -> bool:
    rel = os.path.relpath(path, root)
    parts = rel.split(os.sep)
    internal_dirs = {"evals", "fixtures", "examples", "selves"}
    for index, part in enumerate(parts):
        if part != "skills":
            continue
        if len(parts) > index + 1 and parts[index + 1].endswith("-workspace"):
            return True
        if len(parts) > index + 2 and any(p in internal_dirs for p in parts[index + 2 :]):
            return True
    return False


def repo_fingerprint() -> str:
    paths: list[Path] = []
    for target in targets:
        path = root / target
        if path.is_file():
            if path.name not in ignored_files and not path.name.endswith(".pyc"):
                paths.append(path)
        elif path.is_dir():
            for dirpath, dirnames, filenames in os.walk(path):
                current = Path(dirpath)
                dirnames[:] = sorted(
                    name for name in dirnames if name not in ignored_dirs and not is_runtime_pruned_skill_tree(current / name)
                )
                for filename in sorted(filenames):
                    if filename in ignored_files or filename.endswith(".pyc"):
                        continue
                    file_path = current / filename
                    if not is_runtime_pruned_skill_tree(file_path):
                        paths.append(file_path)

    digest = hashlib.sha1()
    for path in sorted(paths, key=os.fspath):
        rel = os.path.relpath(path, root)
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        if path.is_symlink():
            digest.update(b"LINK->")
            digest.update(os.readlink(path).encode("utf-8"))
            continue
        if not path.is_file():
            continue
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    return digest.hexdigest()[:8]


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)


version_base = (root / "VERSION").read_text(encoding="utf-8").strip()
rev = git("rev-parse", "--short", "HEAD")
if rev.returncode == 0:
    git_hash = rev.stdout.strip()
    worktree_dirty = git("diff", "--quiet", "--ignore-submodules", "--").returncode != 0
    index_dirty = git("diff", "--cached", "--quiet", "--ignore-submodules", "--").returncode != 0
    if worktree_dirty or index_dirty:
        git_hash = f"{git_hash}-dirty-{repo_fingerprint()}"
else:
    git_hash = f"nogit-{repo_fingerprint()}"

print(f"{version_base}-{git_hash}")
PY
}

install_test_refresh_installed_version() {
  local home_dir="$1"
  local name="$2"
  local state_dir

  state_dir="$(install_test_state_root "$home_dir")/$name"
  mkdir -p "$state_dir"
  install_test_current_version_tag > "$state_dir/installed-version"
}

install_test_assert_file_exists() {
  local path="$1"
  local message="$2"

  [ -f "$path" ] || install_test_fail "$message: expected file exists at $path"
}

install_test_assert_dir_exists() {
  local path="$1"
  local message="$2"

  [ -d "$path" ] || install_test_fail "$message: expected directory exists at $path"
}

install_test_assert_path_absent() {
  local path="$1"
  local message="$2"

  [ ! -e "$path" ] || install_test_fail "$message: expected path absent at $path"
}

install_test_assert_file_contains() {
  local path="$1"
  local needle="$2"
  local message="$3"

  grep -aFq -- "$needle" "$path" || install_test_fail "$message: expected '$needle' in $path"
}

install_test_assert_file_not_contains() {
  local path="$1"
  local needle="$2"
  local message="$3"

  if grep -aFq -- "$needle" "$path"; then
    install_test_fail "$message: did not expect '$needle' in $path"
  fi
}

install_test_assert_exit_code() {
  local expected="$1"
  local actual="$2"
  local message="$3"

  [ "$expected" -eq "$actual" ] || install_test_fail "$message: expected exit $expected, got $actual"
}

install_test_assert_success() {
  local actual="$1"
  local message="$2"

  [ "$actual" -eq 0 ] || install_test_fail "$message: expected success, got exit $actual"
}

install_test_assert_failure() {
  local actual="$1"
  local message="$2"

  [ "$actual" -ne 0 ] || install_test_fail "$message: expected failure"
}

install_test_assert_control_plane_runtime_files() {
  local target_dir="$1"
  local label="$2"

  install_test_assert_file_exists "$target_dir/tools/community/validate_product_closure.py" "$label validate_product_closure.py"
  install_test_assert_file_exists "$target_dir/tools/community/validate_readiness_contract.py" "$label validate_readiness_contract.py"
  install_test_assert_file_exists "$target_dir/tools/community/validate_standard_chain_readiness.py" "$label validate_standard_chain_readiness.py"
  install_test_assert_file_exists "$target_dir/tools/community/validate_delivery_owner_input_readiness.py" "$label validate_delivery_owner_input_readiness.py"
  install_test_assert_file_exists "$target_dir/tools/community/validate_canonical_rules.py" "$label validate_canonical_rules.py"
  install_test_assert_file_exists "$target_dir/tools/community/validate_standard_chain_phase.py" "$label validate_standard_chain_phase.py"
  install_test_assert_file_exists "$target_dir/tools/community/authority_proof.py" "$label authority_proof.py"
  install_test_assert_file_exists "$target_dir/tools/community/manage_artifact_registry.py" "$label manage_artifact_registry.py"
  install_test_assert_file_exists "$target_dir/tools/community/normalize_canonical_artifact.py" "$label normalize_canonical_artifact.py"
  install_test_assert_file_exists "$target_dir/tools/community/canonical_rule_common.py" "$label canonical_rule_common.py"
  install_test_assert_file_exists "$target_dir/tools/community/canonical_design_rules.py" "$label canonical_design_rules.py"
  install_test_assert_file_exists "$target_dir/tools/community/canonical_design_confirmation_rules.py" "$label canonical_design_confirmation_rules.py"
  install_test_assert_file_exists "$target_dir/tools/community/canonical_design_errors.py" "$label canonical_design_errors.py"
  install_test_assert_file_exists "$target_dir/tools/community/canonical_design_trace_rules.py" "$label canonical_design_trace_rules.py"
  install_test_assert_file_exists "$target_dir/tools/community/canonical_test_case_rules.py" "$label canonical_test_case_rules.py"
  install_test_assert_file_exists "$target_dir/tools/community/update_delivery_state.py" "$label update_delivery_state.py"
  install_test_assert_file_exists "$target_dir/tools/community/delivery_owner_optional_artifacts.py" "$label delivery_owner_optional_artifacts.py"
  install_test_assert_file_exists "$target_dir/tools/community/delivery_owner_freshness.py" "$label delivery_owner_freshness.py"
  install_test_assert_file_exists "$target_dir/tools/community/standard_chain_readiness_rollback.py" "$label standard_chain_readiness_rollback.py"
  install_test_assert_file_exists "$target_dir/tools/community/runtime_yaml.py" "$label runtime_yaml.py"
  install_test_assert_file_exists "$target_dir/tools/community/simple_json_schema.py" "$label simple_json_schema.py"
  install_test_assert_file_exists "$target_dir/tools/community/validate_canonical_schema.py" "$label validate_canonical_schema.py"
  install_test_assert_file_exists "$target_dir/tools/community/validate_context_contract.py" "$label validate_context_contract.py"
  install_test_assert_file_exists "$target_dir/tools/community/recover_context.py" "$label recover_context.py"
  install_test_assert_file_exists "$target_dir/tools/community/update_active_doc_scope.py" "$label update_active_doc_scope.py"
  install_test_assert_file_exists "$target_dir/tools/community/canonical_ref_resolver.py" "$label canonical_ref_resolver.py"
  install_test_assert_file_exists "$target_dir/tools/community/write_user_decision.py" "$label write_user_decision.py"
  install_test_assert_file_exists "$target_dir/contracts/product-artifacts.yaml" "$label product-artifacts.yaml"
  install_test_assert_file_exists "$target_dir/contracts/canonical/registry-bundle.yaml" "$label canonical registry bundle"
  install_test_assert_file_exists "$target_dir/shared/runtime/standard-chain-catalog.json" "$label standard-chain catalog"
  install_test_assert_file_exists "$target_dir/shared/skills/lib/contracts/shared-core.schema.json" "$label shared skill core schema"
  install_test_assert_file_exists "$target_dir/shared/skills/developer/contracts/developer-report.schema.json" "$label developer report schema"
  install_test_assert_file_exists "$target_dir/shared/skills/developer/templates/developer-report.template.json" "$label developer report template"
}

install_test_run_installed_completion_check() {
  local home_dir="$1"
  local script="$2"
  local workspace="$3"
  local transcript_path="$4"
  local tool_name="$5"
  local file_path="$6"
  local payload

  payload="$(jq -nc \
    --arg cwd "$workspace" \
    --arg sid "install-runtime-gate" \
    --arg tp "$transcript_path" \
    --arg tn "$tool_name" \
    --arg fp "$file_path" \
    '{cwd:$cwd, session_id:$sid, transcript_path:$tp, tool_name:$tn, tool_input:{file_path:$fp}}')"

  env HOME="$home_dir" CODEX_HOME="$home_dir/.codex" CLAUDE_HOME="$home_dir/.claude" bash "$script" <<<"$payload"
}

install_test_assert_installed_control_plane_gates() {
  local home_dir="$1"
  local target_dir="$2"
  local label="$3"
  local skills_dir="${4:-$target_dir/skills}"
  local workspace="$home_dir/workspace-$label"
  local transcript="$workspace/transcript.log"
  local delivery_owner_input_output delivery_owner_output product_manager_output

  mkdir -p "$workspace/docs"
  cp -R "$ROOT/tests/fixtures/standard-chain-foundation/golden-pilot/sample-feature" "$workspace/docs/sample-feature"

  printf '%s\n' "docs/sample-feature/brief.json" > "$transcript"
  product_manager_output="$(install_test_log_path "${label}-product-manager-gate")"
  INSTALL_TEST_CURRENT_LOG="$product_manager_output"
  install_test_run_installed_completion_check \
    "$home_dir" \
    "$skills_dir/product-manager/scripts/completion_check.sh" \
    "$workspace" \
    "$transcript" \
    "Write" \
    "docs/sample-feature/brief.json" >"$product_manager_output" 2>&1 \
    || install_test_fail "$label installed product-manager gate should accept valid canonical fixture"

  printf '%s\n' "docs/sample-feature/phase-1/user-decision.json" > "$transcript"
  delivery_owner_output="$(install_test_log_path "${label}-delivery-owner-gate")"
  INSTALL_TEST_CURRENT_LOG="$delivery_owner_output"
  install_test_run_installed_completion_check \
    "$home_dir" \
    "$skills_dir/delivery-owner/scripts/completion_check.sh" \
    "$workspace" \
    "$transcript" \
    "Write" \
    "docs/sample-feature/phase-1/user-decision.json" >"$delivery_owner_output" 2>&1 \
    || install_test_fail "$label installed delivery-owner gate should accept valid canonical fixture"

  delivery_owner_input_output="$(install_test_log_path "${label}-delivery-owner-intake-preflight")"
  INSTALL_TEST_CURRENT_LOG="$delivery_owner_input_output"
  env HOME="$home_dir" CODEX_HOME="$home_dir/.codex" CLAUDE_HOME="$home_dir/.claude" bash "$skills_dir/delivery-owner/scripts/intake_preflight_check.sh" \
    --phase-dir "$workspace/docs/sample-feature/phase-1" >"$delivery_owner_input_output" 2>&1 \
    || install_test_fail "$label installed delivery-owner intake preflight should accept valid canonical fixture"
}
