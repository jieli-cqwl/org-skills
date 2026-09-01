#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
. "$ROOT/tests/lib/install-test-env.sh"
install_test_init

if grep -Eq 'ORG_STATE_ROOT=' "$ROOT/tests/lib/install-test-env.sh"; then
  install_test_fail "install-test-env.sh must not set ORG_STATE_ROOT"
fi

assert_team_payload() {
  local home="$1"
  python3 - "$home" "$(install_test_state_root "$home")" <<'PY'
import json
import sys
from pathlib import Path

home = Path(sys.argv[1])
state = Path(sys.argv[2])
forbidden = {
    "skill-pull",
    "brainstorming",
    "darwin-skill",
    "grilling",
    "lib",
    "qft-branch-flow-workspace",
    "skill-creator",
}
claude_only = {"code-review-fix", "doc-review-fix"}
for target, rel in (("claude", Path(".claude") / "skills"), ("codex", Path(".agents") / "skills")):
    skills_dir = home / rel
    assert (skills_dir / "product-director" / "SKILL.md").is_file(), skills_dir
    names = {path.name for path in skills_dir.iterdir() if path.is_dir()} if skills_dir.is_dir() else set()
    assert not (forbidden & names), (target, sorted(forbidden & names))
    assert not any(name.endswith("-workspace") for name in names), (target, names)
    if target == "claude":
        assert claude_only <= names, names
    else:
        assert names.isdisjoint(claude_only), names
    manifest = json.loads((state / "team-skills" / target / "installed.json").read_text())
    assert manifest["schema_version"] == 1
    assert manifest["repo_id"] == "team-skills"
    assert manifest["target"] == target
    requires = manifest["requires"]
    assert len(requires) == 1
    assert requires[0]["repo_id"] == "base-config"
    assert requires[0]["target"] == "same"
    assert "assistant" in requires[0]["resource_ids"]
    assert "systematic-debugging" not in requires[0]["resource_ids"]
    ids = {resource["resource_id"] for resource in manifest["resources"]}
    assert "product-director" in ids
    assert "hooks" in ids
    assert "agents" in ids
    assert "protocols" in ids
    assert "runtime" in ids
    assert "post_compact.sh" not in ids
    assert "skill-pull" not in ids
    assert "lib" not in ids
    if target == "claude":
        assert claude_only <= ids
    else:
        assert ids.isdisjoint(claude_only)
        assert any(
            entry.get("kind") == "codex-agent" and "developer" in str(entry.get("section") or "")
            for entry in manifest["structured_entries"]
        ), manifest["structured_entries"]
        assert (home / ".codex" / "agents" / "developer.toml").is_file()
    assert not (home / ".org-skills-state").exists()
    assert not (state / "codex" / "codex-hooks-baseline.json").exists()
    assert not (state / "claude" / "claude-settings-baseline.json").exists()

claude_manifest = json.loads((state / "team-skills" / "claude" / "installed.json").read_text())
hook_roots = [
    Path(resource["resource_root"])
    for resource in claude_manifest["resources"]
    if resource["resource_id"] == "hooks"
]
assert hook_roots, "claude hooks resource missing"
assert (home / ".claude" / "hooks" / "post_compact.sh").is_file()
assert any(str(home / ".claude" / "hooks") == str(root) for root in hook_roots)
base_manifest = json.loads((state / "base-config" / "claude" / "installed.json").read_text())
base_ids = {resource["resource_id"] for resource in base_manifest["resources"]}
assert "post_compact.sh" not in base_ids
assert (home / ".claude" / "CLAUDE.md").is_file()
assert (home / ".claude" / "protocols" / "phase-selection-protocol.md").is_file()
assert (home / ".claude" / "shared" / "runtime" / "standard-chain-catalog.json").is_file()
assert (home / ".codex" / "AGENTS.md").is_file()
PY
}

install_test_case_start "missing Base fails before writing Team files"
home="$(install_test_new_home team-missing-base)"
log="$(install_test_log_path team-missing-base)"
set +e
install_test_run_install_allow_failure "$home" "$log" --target claude
rc=$?
set -e
install_test_assert_failure "$rc" "Team install without Base"
install_test_assert_file_contains "$log" "base-config" "names base-config"
install_test_assert_file_contains "$log" "assistant" "names a missing Base resource id"
install_test_assert_path_absent "$home/.claude/skills/product-director/SKILL.md" "no Team skill written"
install_test_assert_path_absent "$(install_test_state_root "$home")/team-skills" "no Team state written"
install_test_assert_path_absent "$home/.org-skills-state" "legacy state unused"
install_test_case_pass "missing Base fails before writing Team files"

install_test_case_start "Base then Team installs Team payload only"
home="$(install_test_new_home team-install)"
install_test_run_base "$home" "$(install_test_log_path team-install-base)" --target all
install_test_run_install "$home" "$(install_test_log_path team-install-team)" --target all
assert_team_payload "$home"
install_test_case_pass "Base then Team installs Team payload only"

install_test_case_start "missing systematic-debugging does not fail install; check_skill_edge names Daily"
home="$(install_test_new_home team-edge)"
install_test_run_base "$home" "$(install_test_log_path team-edge-base)" --target claude
install_test_run_install "$home" "$(install_test_log_path team-edge-team)" --target claude
install_test_assert_file_exists "$home/.claude/skills/fix/SKILL.md" "fix skill installed"
install_test_assert_path_absent "$home/.claude/skills/systematic-debugging" "Daily skill not cloned by install"
edge_log="$(install_test_log_path team-edge-check)"
set +e
install_test_run_env "$home" python3 - "$ROOT" "$home" >"$edge_log" 2>&1 <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root))
from tools.install.repo_install import InstallError, check_skill_edge

try:
    check_skill_edge("fix")
except InstallError as exc:
    sys.stderr.write(exc.format() + "\n")
    raise SystemExit(1)
raise SystemExit("check_skill_edge(fix) should fail when systematic-debugging is absent")
PY
rc=$?
set -e
install_test_assert_failure "$rc" "check_skill_edge(fix) should fail"
install_test_assert_file_contains "$edge_log" "daily-skills" "names Daily owner"
install_test_assert_file_contains "$edge_log" "systematic-debugging" "names required Skill"
install_test_assert_path_absent "$home/.claude/skills/systematic-debugging" "check_skill_edge must not clone Daily"
install_test_case_pass "missing systematic-debugging does not fail install; check_skill_edge names Daily"

install_test_case_start "drift on a Team Skill stops upgrade and uninstall"
home="$(install_test_new_home team-drift)"
install_test_run_base "$home" "$(install_test_log_path team-drift-base)" --target claude
install_test_run_install "$home" "$(install_test_log_path team-drift-install)" --target claude
printf '\nmutated\n' >> "$home/.claude/skills/product-director/SKILL.md"
set +e
install_test_run_install_allow_failure "$home" "$(install_test_log_path team-drift-upgrade)" --target claude
up_rc=$?
install_test_run_install_allow_failure "$home" "$(install_test_log_path team-drift-uninstall)" --target claude --uninstall
un_rc=$?
set -e
install_test_assert_failure "$up_rc" "drift upgrade"
install_test_assert_failure "$un_rc" "drift uninstall"
install_test_assert_file_contains "$(install_test_log_path team-drift-upgrade)" "drift" "upgrade drift code"
install_test_assert_file_contains "$(install_test_log_path team-drift-uninstall)" "drift" "uninstall drift code"
install_test_assert_file_exists "$home/.claude/skills/product-director/SKILL.md" "drifted skill remains"
install_test_case_pass "drift on a Team Skill stops upgrade and uninstall"

install_test_case_start "unowned destination is conflict"
home="$(install_test_new_home team-conflict)"
install_test_run_base "$home" "$(install_test_log_path team-conflict-base)" --target claude
mkdir -p "$home/.claude/skills/product-director"
printf 'foreign\n' > "$home/.claude/skills/product-director/SKILL.md"
log="$(install_test_log_path team-conflict)"
set +e
install_test_run_install_allow_failure "$home" "$log" --target claude
rc=$?
set -e
install_test_assert_failure "$rc" "conflict should fail"
install_test_assert_file_contains "$log" "conflict" "conflict message"
install_test_assert_file_contains "$home/.claude/skills/product-director/SKILL.md" "foreign" "left untouched"
install_test_assert_path_absent "$(install_test_state_root "$home")/team-skills/claude/installed.json" "no Team manifest on conflict"
install_test_case_pass "unowned destination is conflict"

install_test_case_start "target-all validates both first and reports visible partial success"
home="$(install_test_new_home team-partial)"
install_test_run_base "$home" "$(install_test_log_path team-partial-base)" --target all
mkdir -p "$home/.agents/skills/product-director"
printf 'foreign\n' > "$home/.agents/skills/product-director/SKILL.md"
log="$(install_test_log_path team-partial)"
set +e
install_test_run_install_allow_failure "$home" "$log" --target all
rc=$?
set -e
install_test_assert_failure "$rc" "all-target must not claim success"
install_test_assert_file_exists "$home/.claude/skills/product-director/SKILL.md" "claude installed"
install_test_assert_file_contains "$home/.agents/skills/product-director/SKILL.md" "foreign" "codex left untouched"
install_test_assert_file_contains "$log" "claude" "completed target named"
install_test_assert_file_contains "$log" "conflict" "codex conflict named"
install_test_case_pass "target-all validates both first and reports visible partial success"

install_test_case_start "uninstall removes Team resources and leaves Base for Base uninstall"
home="$(install_test_new_home team-un)"
install_test_run_base "$home" "$(install_test_log_path team-un-base)" --target claude
install_test_run_install "$home" "$(install_test_log_path team-un-team)" --target claude
install_test_run_install "$home" "$(install_test_log_path team-un-team-un)" --target claude --uninstall
install_test_assert_path_absent "$home/.claude/skills/product-director" "Team skill removed"
install_test_assert_path_absent "$(install_test_state_root "$home")/team-skills/claude/installed.json" "Team manifest removed"
install_test_assert_file_exists "$home/.claude/CLAUDE.md" "Base assistant remains"
install_test_assert_file_exists "$home/.claude/rules/code-changes.md" "Base rule remains"
install_test_run_base "$home" "$(install_test_log_path team-un-base-un)" --target claude --uninstall
install_test_assert_path_absent "$home/.claude/CLAUDE.md" "Base assistant removed after Team uninstall"
install_test_assert_path_absent "$home/.org-skills-state" "legacy state unused"
install_test_case_pass "uninstall removes Team resources and leaves Base for Base uninstall"

install_test_case_start "corrupt Codex hooks.json fails closed"
home="$(install_test_new_home team-corrupt-hooks)"
install_test_run_base "$home" "$(install_test_log_path team-corrupt-hooks-base)" --target codex
mkdir -p "$home/.codex"
printf '{not-json\n' > "$home/.codex/hooks.json"
log="$(install_test_log_path team-corrupt-hooks)"
set +e
install_test_run_install_allow_failure "$home" "$log" --target codex
rc=$?
set -e
install_test_assert_failure "$rc" "corrupt hooks.json should fail"
install_test_assert_path_absent "$home/.codex/agents/developer.toml" "no silent partial agent file"
install_test_assert_path_absent "$home/.agents/skills/product-director" "no Team skill written"
install_test_assert_file_contains "$home/.codex/hooks.json" "{not-json" "corrupt file left in place"
install_test_case_pass "corrupt Codex hooks.json fails closed"

install_test_case_start "mid-write agents.developer section fails closed"
home="$(install_test_new_home team-corrupt-agent)"
install_test_run_base "$home" "$(install_test_log_path team-corrupt-agent-base)" --target codex
mkdir -p "$home/.codex"
printf '[agents.developer]\ndescription = "incomplete\n' > "$home/.codex/config.toml"
log="$(install_test_log_path team-corrupt-agent)"
set +e
install_test_run_install_allow_failure "$home" "$log" --target codex
rc=$?
set -e
install_test_assert_failure "$rc" "mid-write agent section should fail"
install_test_assert_path_absent "$home/.codex/agents/developer.toml" "no silent partial agent file"
install_test_assert_file_contains "$home/.codex/config.toml" 'description = "incomplete' "corrupt config left in place"
install_test_case_pass "mid-write agents.developer section fails closed"

printf '[PASS] team install lifecycle (%s cases)\n' "$INSTALL_TEST_CASE_COUNT"
