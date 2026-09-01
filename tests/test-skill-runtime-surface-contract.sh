#!/usr/bin/env bash
# 文件职责：验证 Team Skill 运行面自动/手动/禁用策略由显式合同驱动。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTRACT="$ROOT/contracts/skill-runtime-surface.json"
APPLY_TOOL="$ROOT/tools/skills/apply_skill_runtime_surface.py"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

[ -s "$CONTRACT" ] || fail "missing skill runtime surface contract"
[ -x "$APPLY_TOOL" ] || fail "missing executable skill runtime surface tool"

python3 - "$ROOT" "$CONTRACT" <<'PY'
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
contract_path = Path(sys.argv[2])
contract = json.loads(contract_path.read_text(encoding="utf-8"))

limits = contract.get("limits", {})
auto_limit = limits.get("max_auto_invoked_skills")
if not isinstance(auto_limit, int) or auto_limit <= 0:
    raise SystemExit("contracts/skill-runtime-surface.json: limits.max_auto_invoked_skills must be positive integer")

skills = contract.get("skills")
if not isinstance(skills, dict) or not skills:
    raise SystemExit("contracts/skill-runtime-surface.json: skills must be a non-empty object")

TEAM = {
    "cli-updater", "commit", "consistency-audit", "deep-research",
    "delivery-estimator", "delivery-owner", "design", "developer",
    "feishu-docs", "fix", "github-repo-radar", "overview",
    "product-director", "product-manager", "project-memory", "prompt",
    "qa", "qft-branch-flow", "qft-group-chat-export", "refactor",
    "research", "review", "rules-manager", "scan", "security",
    "skill-quality-audit", "tech-lead", "test-design", "ux", "verify",
    "worktree",
}
CLAUDE_ONLY = {"code-review-fix", "doc-review-fix"}
if set(skills) != TEAM | CLAUDE_ONLY:
    raise SystemExit(
        "surface keys must be Team ∪ Claude-only: "
        f"missing={sorted((TEAM | CLAUDE_ONLY) - set(skills))} "
        f"extra={sorted(set(skills) - (TEAM | CLAUDE_ONLY))}"
    )
for banned in ("brainstorming", "skill-creator", "skill-pull", "darwin-skill", "grilling"):
    if banned in skills:
        raise SystemExit(f"{banned} must not be installed from Team surface")

valid_modes = {"auto", "manual", "off"}
valid_execution_kinds = {"skill", "orchestrator", "agent_backed"}
valid_codex_execution = {
    "inline",
    "subagent_clean",
    "subagent_fork",
    "subagent_parallel",
}
auto_skills = []
manual_skills = []
source_dirs = {}
for name, entry in sorted(skills.items()):
    mode = entry.get("mode")
    if mode not in valid_modes:
        raise SystemExit(f"{name}: mode must be one of {sorted(valid_modes)}")
    reason = str(entry.get("reason", "")).strip()
    owner = str(entry.get("owner", "")).strip()
    if not reason or not owner:
        raise SystemExit(f"{name}: reason and owner are required")
    execution_kind = str(entry.get("execution_kind", "skill")).strip()
    if execution_kind not in valid_execution_kinds:
        raise SystemExit(f"{name}: execution_kind must be one of {sorted(valid_execution_kinds)}")
    codex_execution = entry.get("codex_execution")
    if codex_execution is not None and codex_execution not in valid_codex_execution:
        raise SystemExit(f"{name}: codex_execution must be one of {sorted(valid_codex_execution)}")
    allow_nested_agents = entry.get("allow_nested_agents")
    if allow_nested_agents is not None and not isinstance(allow_nested_agents, bool):
        raise SystemExit(f"{name}: allow_nested_agents must be boolean when present")
    if execution_kind == "agent_backed":
        if mode != "manual":
            raise SystemExit(f"{name}: agent_backed skills must be manual-only")
        if codex_execution is not None:
            raise SystemExit(f"{name}: agent_backed skills must not define generic codex_execution")
        if not str(entry.get("agent_type", "")).strip():
            raise SystemExit(f"{name}: agent_backed skills require agent_type")
        dispatchers = entry.get("dispatchers")
        if not isinstance(dispatchers, list) or not all(isinstance(item, str) and item for item in dispatchers):
            raise SystemExit(f"{name}: agent_backed skills require non-empty dispatchers")
        if allow_nested_agents is not False:
            raise SystemExit(f"{name}: agent_backed skills must set allow_nested_agents=false")
    if execution_kind == "orchestrator":
        if codex_execution not in {None, "inline"}:
            raise SystemExit(f"{name}: orchestrator skills must execute inline and own their internal dispatch")
        if allow_nested_agents is not True:
            raise SystemExit(f"{name}: orchestrator skills must set allow_nested_agents=true")
    source_dir = str(entry.get("source_dir", "")).strip()
    if source_dir:
        source_dirs[source_dir] = name
    if mode == "auto":
        auto_skills.append(name)
    if mode == "manual":
        manual_skills.append(name)

if len(auto_skills) > auto_limit:
    raise SystemExit(f"auto skill count exceeds contract limit: {len(auto_skills)} > {auto_limit}")
if auto_skills:
    raise SystemExit(f"Team surface has no auto skills; found {auto_skills}")

expected_codex_execution = {
    "github-repo-radar": "subagent_clean",
    "overview": "subagent_clean",
    "research": "subagent_clean",
}
for name, codex_execution in expected_codex_execution.items():
    entry = skills[name]
    if entry.get("execution_kind", "skill") != "skill":
        raise SystemExit(f"{name}: expected normal skill execution_kind")
    if entry.get("codex_execution") != codex_execution:
        raise SystemExit(f"{name}: codex_execution must be {codex_execution}")

expected_orchestrators = {
    "delivery-owner",
    "scan",
    "skill-quality-audit",
}
for name in expected_orchestrators:
    entry = skills[name]
    if entry.get("execution_kind") != "orchestrator":
        raise SystemExit(f"{name}: execution_kind must be orchestrator")
    if entry.get("codex_execution") != "inline":
        raise SystemExit(f"{name}: orchestrator codex_execution must be inline")

expected_agent_backed = {
    "consistency-audit": ("consistency-auditor", {"delivery-owner", "tech-lead"}),
    "developer": ("developer", {"delivery-owner"}),
    "fix": ("fixer", {"delivery-owner"}),
    "qa": ("qa", {"delivery-owner"}),
    "verify": ("verifier", {"delivery-owner"}),
}
actual_agent_backed = {
    name
    for name, entry in skills.items()
    if entry.get("execution_kind", "skill") == "agent_backed"
}
if actual_agent_backed != set(expected_agent_backed):
    raise SystemExit(
        "agent_backed skill set mismatch: "
        f"missing={sorted(set(expected_agent_backed) - actual_agent_backed)} "
        f"extra={sorted(actual_agent_backed - set(expected_agent_backed))}"
    )
for name, (agent_type, required_dispatchers) in expected_agent_backed.items():
    entry = skills[name]
    if entry.get("agent_type") != agent_type:
        raise SystemExit(f"{name}: agent_type must be {agent_type}")
    dispatchers = set(entry.get("dispatchers", []))
    missing_dispatchers = sorted(required_dispatchers - dispatchers)
    if missing_dispatchers:
        raise SystemExit(f"{name}: dispatchers missing {missing_dispatchers}")

def require_routing_tokens(name: str, tokens: list[str]) -> None:
    routing_text = " ".join(
        str(skills[name].get(key, ""))
        for key in ("description", "routing_boundary")
    ).lower()
    missing = [token for token in tokens if token.lower() not in routing_text]
    if missing:
        raise SystemExit(f"{name}: missing routing boundary tokens: {missing}")


require_routing_tokens("research", ["evidence-backed", "outside installable agent skill"])
for manual_name in [
    "github-repo-radar",
    "overview",
    "prompt",
    "qft-group-chat-export",
    "refactor",
    "review",
    "research",
    "security",
]:
    if manual_name not in manual_skills:
        raise SystemExit(f"{manual_name} should be manual-only")

for root_dir, required in (
    ("shared/skills", TEAM),
    ("claude/skills", CLAUDE_ONLY),
):
    base = root / root_dir
    found = {path.parent.name for path in base.glob("*/SKILL.md")}
    missing = sorted(required - found)
    if missing:
        raise SystemExit(f"{root_dir}: missing Team Skill roots {missing}")
    for skill_file in base.glob("*/SKILL.md"):
        name = skill_file.parent.name
        if name.endswith("-workspace") or name in {"lib", "skill-pull"}:
            continue
        if name not in skills:
            raise SystemExit(f"{skill_file}: missing from Team runtime surface contract")
        text = skill_file.read_text(encoding="utf-8")
        match = re.search(r"^name:\s*['\"]?([^'\"\n]+)", text, re.MULTILINE)
        skill_name = match.group(1).strip() if match else name
        if skill_file.parent.name in source_dirs and skill_name != source_dirs[skill_file.parent.name]:
            raise SystemExit(f"{skill_file}: source_dir maps to {source_dirs[skill_file.parent.name]}, got {skill_name}")
        entry = skills.get(skill_name) or skills.get(name)
        if entry and entry.get("mode") == "auto":
            frontmatter = text.split("---\n", 2)[1]
            if re.search(r"^hidden:\s*true\s*$", frontmatter, re.MULTILINE):
                raise SystemExit(f"{skill_file}: auto skill source must not declare hidden=true")

qft_skill = root / "shared/skills/qft-group-chat-export/SKILL.md"
if not qft_skill.is_file():
    raise SystemExit("shared/skills/qft-group-chat-export/SKILL.md should be repo-managed")
if (root / "shared/skills/qft-group-chat-export/config.local.json").exists():
    raise SystemExit("shared/skills/qft-group-chat-export/config.local.json must stay local-only")

readme = (root / "README.md").read_text(encoding="utf-8")
retired_refs = [
    "shared/reference/Skill质量标准.md",
    "shared/reference/Skill能力有效性标准.md",
]
for retired in retired_refs:
    if retired in readme:
        raise SystemExit(f"README.md still treats retired reference as active truth: {retired}")
if "contracts/skill-runtime-surface.json" not in readme:
    raise SystemExit("README.md should document the skill runtime surface contract")
PY

mkdir -p \
  "$TMP_DIR/skills/cli-updater/agents" \
  "$TMP_DIR/skills/consistency-audit/agents" \
  "$TMP_DIR/skills/research/agents" \
  "$TMP_DIR/skills/scan/agents"
cat > "$TMP_DIR/skills/cli-updater/SKILL.md" <<'EOF_SKILL'
---
name: cli-updater
description: Check and update Claude/Codex CLI versions.
---

# CLI Updater
EOF_SKILL
cat > "$TMP_DIR/skills/cli-updater/agents/openai.yaml" <<'EOF_YAML'
interface:
  display_name: "CLI Updater"
policy:
  other_flag: true
EOF_YAML
cat > "$TMP_DIR/skills/consistency-audit/SKILL.md" <<'EOF_SKILL'
---
name: consistency-audit
description: Audit canonical delivery artifacts.
---

# Consistency Audit
EOF_SKILL
cat > "$TMP_DIR/skills/consistency-audit/agents/openai.yaml" <<'EOF_YAML'
interface:
  display_name: "Consistency Audit"
policy:
  allow_implicit_invocation: false
EOF_YAML
cat > "$TMP_DIR/skills/research/SKILL.md" <<'EOF_SKILL'
---
name: research
description: Investigate external evidence and options.
---

# Research
EOF_SKILL
cat > "$TMP_DIR/skills/research/agents/openai.yaml" <<'EOF_YAML'
interface:
  display_name: "Research"
policy:
  allow_implicit_invocation: false
EOF_YAML
cat > "$TMP_DIR/skills/scan/SKILL.md" <<'EOF_SKILL'
---
name: scan
description: Scan repository health.
---

# Scan
EOF_SKILL
cat > "$TMP_DIR/skills/scan/agents/openai.yaml" <<'EOF_YAML'
interface:
  display_name: "Scan"
policy:
  allow_implicit_invocation: false
EOF_YAML

python3 "$APPLY_TOOL" \
  --contract "$CONTRACT" \
  --skills-dir "$TMP_DIR/skills" \
  --runtime codex \
  --audit-json "$TMP_DIR/audit.json"

grep -Fq 'disable-model-invocation: true' "$TMP_DIR/skills/cli-updater/SKILL.md" \
  || fail "Codex manual-only SKILL.md should keep cross-runtime manual marker"
grep -Fq 'allow_implicit_invocation: false' "$TMP_DIR/skills/cli-updater/agents/openai.yaml" \
  || fail "Codex manual-only openai.yaml should disable implicit invocation"
grep -Fq 'other_flag: true' "$TMP_DIR/skills/cli-updater/agents/openai.yaml" \
  || fail "Codex manual-only policy merge should preserve existing policy keys"
[ "$(grep -c '^policy:' "$TMP_DIR/skills/cli-updater/agents/openai.yaml")" -eq 1 ] \
  || fail "Codex manual-only policy merge must not create duplicate policy roots"
grep -Fq 'codex_execution: subagent_clean' "$TMP_DIR/skills/research/agents/openai.yaml" \
  || fail "Codex research policy should expose subagent_clean execution"
grep -Fq 'execution_kind: agent_backed' "$TMP_DIR/skills/consistency-audit/agents/openai.yaml" \
  || fail "Codex consistency-audit policy should expose agent-backed execution"
grep -Fq 'agent_type: consistency-auditor' "$TMP_DIR/skills/consistency-audit/agents/openai.yaml" \
  || fail "Codex consistency-audit policy should expose agent type"
grep -Fq 'allow_nested_agents: false' "$TMP_DIR/skills/consistency-audit/agents/openai.yaml" \
  || fail "Codex consistency-audit policy should forbid nested generic agents"
! grep -Fq 'codex_execution:' "$TMP_DIR/skills/consistency-audit/agents/openai.yaml" \
  || fail "Codex agent-backed skills must not expose generic codex_execution"
grep -Fq 'execution_kind: orchestrator' "$TMP_DIR/skills/scan/agents/openai.yaml" \
  || fail "Codex scan policy should expose orchestrator execution kind"
grep -Fq 'allow_nested_agents: true' "$TMP_DIR/skills/scan/agents/openai.yaml" \
  || fail "Codex scan policy should allow its own internal dispatch"

python3 - "$TMP_DIR/audit.json" <<'PY'
import json
import sys
from pathlib import Path

audit = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if audit.get("runtime") != "codex":
    raise SystemExit("audit runtime mismatch")
if audit.get("auto_count") != 0 or audit.get("manual_count") != 4:
    raise SystemExit(f"unexpected audit counts: {audit}")
PY

printf '[PASS] skill runtime surface contract\n'
