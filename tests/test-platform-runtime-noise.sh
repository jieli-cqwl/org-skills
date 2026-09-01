#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=tests/lib/install-test-env.sh
. "$ROOT/tests/lib/install-test-env.sh"
ensure_test_rg
install_test_init
TMP_HOME="$(install_test_new_home platform-noise)"
CODEX_SKILLS_DIR="$TMP_HOME/.agents/skills"

fail() {
  install_test_fail "$*"
}

install_test_run_base "$TMP_HOME" "$(install_test_log_path platform-noise-base)" --target all
install_test_run_install "$TMP_HOME" "$(install_test_log_path platform-noise-team)" --target all

grep -Fxq '# CLAUDE.md' "$TMP_HOME/.claude/CLAUDE.md" || fail "claude entry doc title should be # CLAUDE.md"

codex_agent_toml_count="$(find "$TMP_HOME/.codex/agents" -maxdepth 1 -type f -name '*.toml' | wc -l | tr -d ' ')"
expected_codex_agent_toml_count="$(
  PYTHONPATH="$ROOT/tools/community" python3 - <<'PY'
from codex_runtime_agents import MANAGED_AGENT_ROLES

print(len(MANAGED_AGENT_ROLES))
PY
)"
[ "$codex_agent_toml_count" = "$expected_codex_agent_toml_count" ] \
  || fail "codex runtime should install exactly $expected_codex_agent_toml_count TOML agents, got $codex_agent_toml_count"
if find "$TMP_HOME/.codex/agents" -maxdepth 1 -type f -name '*.md' | grep -q .; then
  find "$TMP_HOME/.codex/agents" -maxdepth 1 -type f -name '*.md' >&2
  fail "codex runtime should not install Markdown agent adapters"
fi

if rg -n \
  -e '^# CLAUDE\.md$' \
  -e 'Claude Code Skill 创建与改进' \
  -e 'Claude 工作时需要查阅' \
  -e 'description 被注入 system prompt 后由 Claude 读取' \
  -e '过时文档隔离（Claude 不参考）' \
  "$TMP_HOME/.codex/AGENTS.md" \
  "$CODEX_SKILLS_DIR" \
  "$TMP_HOME/.codex/reference" \
  "$TMP_HOME/.codex/agents" >/tmp/org_platform_noise_rg.out 2>&1; then
  cat /tmp/org_platform_noise_rg.out >&2
  fail "codex runtime still contains claude-only noise"
fi

if rg -n \
  -e '先读并严格遵循' \
  -e '硬约束' \
  -e '完整方法论' \
  -e '可用工具' \
  -e 'Write 仅用于' \
  -e '禁止使用 Edit' \
  -e '禁止 Edit' \
  -e 'developer-report\.json' \
  -e 'verify-result\.json' \
  -e 'qa-result\.json' \
  -e 'code-review-result\.json' \
  -e 'consistency-audit-result\.json' \
  -e '\.codex/rules' \
  -e '\.agents/skills' \
  "$TMP_HOME/.codex/agents" >/tmp/org_platform_noise_agent_rg.out 2>&1; then
  cat /tmp/org_platform_noise_agent_rg.out >&2
  fail "codex runtime agents should keep platform-specific agent boundaries and avoid duplicated skill details"
fi

python3 - "$ROOT" "$CODEX_SKILLS_DIR" <<'PY' || fail "codex skill description budget exceeded"
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
skills_dir = Path(sys.argv[2])
max_total_chars = 10000
max_single_chars = 220
max_first_party_source_chars = 180


def frontmatter(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    parts = text.split("---\n", 2)
    if len(parts) != 3:
        return None
    return parts[1]


def description_from(front: str) -> str:
    lines = front.splitlines()
    for idx, line in enumerate(lines):
        if not line.startswith("description:"):
            continue
        value = line.split(":", 1)[1].strip()
        if value in {"|", ">"}:
            block = []
            for next_line in lines[idx + 1 :]:
                if next_line.startswith((" ", "\t")) or not next_line.strip():
                    block.append(next_line.strip())
                    continue
                break
            return " ".join(block).strip()
        return value.strip("'\"")
    return ""


rows = []
for skill_file in skills_dir.rglob("SKILL.md"):
    front = frontmatter(skill_file.read_text(encoding="utf-8"))
    if front is None:
        continue
    description = re.sub(r"\s+", " ", description_from(front)).strip()
    rows.append((len(description), skill_file.relative_to(skills_dir).as_posix()))

total = sum(length for length, _ in rows)
too_long = [(path, length) for length, path in rows if length > max_single_chars]

if total > max_total_chars or too_long:
    print(f"total_description_chars={total} max_total={max_total_chars}", file=sys.stderr)
    for path, length in sorted(too_long, key=lambda item: item[1], reverse=True)[:20]:
        print(f"{path}: description_chars={length}", file=sys.stderr)
    raise SystemExit(1)

first_party_too_long = []
first_party_mismatches = []
for source_file in sorted((root / "shared" / "skills").glob("*/SKILL.md")):
    source_front = frontmatter(source_file.read_text(encoding="utf-8"))
    if source_front is None:
        continue

    source_description = re.sub(r"\s+", " ", description_from(source_front)).strip()
    if len(source_description) > max_first_party_source_chars:
        first_party_too_long.append(
            (source_file.relative_to(root).as_posix(), len(source_description))
        )

    runtime_file = skills_dir / source_file.relative_to(root / "shared" / "skills")
    if not runtime_file.exists():
        continue
    runtime_front = frontmatter(runtime_file.read_text(encoding="utf-8"))
    runtime_description = re.sub(r"\s+", " ", description_from(runtime_front or "")).strip()
    if runtime_description != source_description:
        first_party_mismatches.append(
            (
                source_file.relative_to(root).as_posix(),
                source_description,
                runtime_description,
            )
        )

if first_party_too_long or first_party_mismatches:
    for path, length in first_party_too_long:
        print(
            f"{path}: first-party source description_chars={length} "
            f"max={max_first_party_source_chars}",
            file=sys.stderr,
        )
    for path, source_description, runtime_description in first_party_mismatches[:20]:
        print(
            f"{path}: runtime description must match first-party source "
            f"(source={source_description!r}, runtime={runtime_description!r})",
            file=sys.stderr,
        )
    raise SystemExit(1)
PY

python3 - "$TMP_HOME/.claude/skills" <<'PY' || fail "claude skill description budget exceeded"
import re
import sys
from pathlib import Path

skills_dir = Path(sys.argv[1])
max_active_skills = 40
max_total_chars = 10000
max_single_chars = 900


def frontmatter(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    parts = text.split("---\n", 2)
    if len(parts) != 3:
        return None
    return parts[1]


def scalar_from(front: str, key: str) -> str:
    for line in front.splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip("'\"")
    return ""


def description_from(front: str) -> str:
    lines = front.splitlines()
    for idx, line in enumerate(lines):
        if not line.startswith("description:"):
            continue
        value = line.split(":", 1)[1].strip()
        if value in {"|", ">"}:
            block = []
            for next_line in lines[idx + 1 :]:
                if next_line.startswith((" ", "\t")) or not next_line.strip():
                    block.append(next_line.strip())
                    continue
                break
            return " ".join(block).strip()
        return value.strip("'\"")
    return ""


rows = []
for skill_file in sorted(skills_dir.rglob("SKILL.md")):
    front = frontmatter(skill_file.read_text(encoding="utf-8"))
    if front is None:
        continue
    if scalar_from(front, "disable-model-invocation") == "true":
        continue
    description = re.sub(r"\s+", " ", description_from(front)).strip()
    rows.append((len(description), skill_file.relative_to(skills_dir).as_posix()))

total = sum(length for length, _ in rows)
too_long = [(path, length) for length, path in rows if length > max_single_chars]

if len(rows) > max_active_skills or total > max_total_chars or too_long:
    print(
        f"active_skills={len(rows)} max_active={max_active_skills} "
        f"total_description_chars={total} max_total={max_total_chars}",
        file=sys.stderr,
    )
    for path, length in sorted(too_long, key=lambda item: item[1], reverse=True)[:20]:
        print(f"{path}: description_chars={length}", file=sys.stderr)
    raise SystemExit(1)
PY

# shellcheck disable=SC2016 # Assert literal runtime paths rendered into skill docs.
grep -Fq 'bash $HOME/.claude/skills/overview/scripts/project-detect.sh' "$TMP_HOME/.claude/skills/overview/SKILL.md" \
  || fail "Claude overview skill should render script paths under ~/.claude/skills"
# shellcheck disable=SC2016 # Assert literal runtime paths rendered into skill docs.
grep -Fq 'bash $HOME/.agents/skills/overview/scripts/project-detect.sh' "$CODEX_SKILLS_DIR/overview/SKILL.md" \
  || fail "Codex overview skill should render script paths under ~/.agents/skills"
# shellcheck disable=SC2016 # Assert literal runtime paths rendered into skill docs.
grep -Fq 'bash $HOME/.claude/skills/scan/scripts/project-stats.sh' "$TMP_HOME/.claude/skills/scan/SKILL.md" \
  || fail "Claude scan skill should render script paths under ~/.claude/skills"
# shellcheck disable=SC2016 # Assert literal runtime paths rendered into skill docs.
grep -Fq 'bash $HOME/.agents/skills/scan/scripts/project-stats.sh' "$CODEX_SKILLS_DIR/scan/SKILL.md" \
  || fail "Codex scan skill should render script paths under ~/.agents/skills"
# shellcheck disable=SC2016 # Assert literal runtime paths rendered into skill docs.
grep -Fq '`$HOME/.agents/skills/skill-quality-audit/references/audit-dimensions.md`' "$CODEX_SKILLS_DIR/scan/references/skills-scan-rules.md" \
  || fail "Codex scan reference should route quality dimensions through the official skill root"

if rg -n '\{\{SKILLS_HOME\}\}|\$HOME/\.codex/skills' \
  "$TMP_HOME/.claude/skills/overview" \
  "$TMP_HOME/.claude/skills/scan" \
  "$CODEX_SKILLS_DIR/overview" \
  "$CODEX_SKILLS_DIR/scan" >/tmp/org_platform_noise_skill_paths.out 2>&1; then
  cat /tmp/org_platform_noise_skill_paths.out >&2
  fail "runtime first-party skill docs should not keep unresolved skill-root placeholders or legacy Codex skill paths"
fi

test ! -e "$ROOT/community" || fail "community vendor tree must not remain in Team"

if rg -n \
  --glob '!**/evals/**' \
  --glob '!**/fixtures/**' \
  --glob '!**/examples/**' \
  --glob '!**/selves/**' \
  --glob '!**/*-workspace/**' \
  '\.codex/skills' "$ROOT/shared/skills" >/tmp/org_platform_noise_legacy_codex_skills.out 2>&1; then
  cat /tmp/org_platform_noise_legacy_codex_skills.out >&2
  fail "shared skill packages should not mention legacy Codex skill root"
fi

echo "[PASS] platform runtime noise"
