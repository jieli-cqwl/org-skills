# Repository Split Plan 3: Personal Extraction

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `personal-skills` snapshot repository with exactly 14 installable Skills, Personal source locks, adapters, surfaces, and a Personal-owned installer, then prove rejected Skills and Team machinery do not cross the boundary.

**Architecture:** Copy Personal vendor trees from the monolith into a sibling snapshot repo. Personal owns its own source-sync adapters. Generic `skill-pull` stays in Daily; Personal only declares a maintenance-only edge. This machine does not install Personal during cutover. Prove install lifecycle in a temporary HOME only.

**Tech Stack:** Git snapshot repo, Python installer using Plan 1 types, YAML source lock, JSON runtime surface, isolated-HOME bash tests.

**Spec:** `docs/superpowers/specs/2026-08-31--repository-split-and-clean-runtime-migration--design.md`

**Depends on:** Plan 1 Task 1 inventory green; Plan 1 Task 2 tag `pre-split-2026-08-31` pushed before vendor extraction; Plan 1 Task 4 `tree_digest.py` exists before Personal installer tasks. Remotes confirmed before Personal `git push`. Copy digest bytes; do not import the Base checkout.

**Unblocks:** Plan 4 deletion of Personal-owned monolith paths.

**Forbidden:** Installing Personal on this machine. Copying hooks/agents/protocols/standard-chain. Copying Grill, Superpowers, Anthropic, Vercel, `skill-pull`, or `to-prd`'s Grill sibling trees. Vendoring Daily `skill-pull` into Personal. Deleting monolith sources (Plan 4). Copying `.claude/skills/darwin-skill` generated cards.

## Global Constraints

- Same installer CLI, state root, lock, manifest schema, digest, conflict, drift, and `--target all` rules as Plan 1.
- Personal `repo_id` is `personal-skills`. Personal `requires` is `[]`.
- Personal Skill count is 14.
- `skill-pull` is maintenance-only. Personal install must not require Daily to be installed.
- `to-prd` lock remains `mattpocock/skills@2454c95dc305c158b21a0cdafeb728879dd0359a`. Do not use the Grill ref.
- Darwin source of truth is `community/alchaincyf/`, not `.claude/skills/darwin-skill/` cards/TSV.
- No hooks, agents, protocols, or standard-chain runtime.
- Tests must not grep Skill Markdown prose.
- Python tests that import `tools.*` must `sys.path.insert(0, str(ROOT))` or run with `PYTHONPATH="$ROOT"`.
- Create Personal `tests/lib/install-test-env.sh` as a new helper (same names as Plan 1 Base helper). Do not source the monolith helper.

## File Structure

Create `/Users/lijieli/personal-skills/`:

```text
vendor/alchaincyf/darwin-skill/
vendor/nextlevelbuilder/ui-ux-pro-max/
vendor/panniantong/agent-reach/
vendor/markdown-viewer/architecture/
vendor/baoyu/baoyu-markdown-to-html/
vendor/epiral/bb-browser/
vendor/alirezarezvani/code-to-prd/
vendor/safishamsi/graphify/
vendor/op7418/humanizer-zh/
vendor/pleaseprompto/notebooklm/
vendor/othmanadi/planning-with-files/
vendor/github/prd/
vendor/mattpocock/to-prd/
vendor/zhaono1/self-improving-agent/
adapters/codex/
sources/SOURCES.yaml
contracts/dependencies.yaml
contracts/skill-runtime-surface.json
tools/source-sync/
tools/install/tree_digest.py
tools/install/repo_install.py
tools/skills/apply_skill_runtime_surface.py
install.sh
tests/
VERSION
README.md
AGENTS.md
CLAUDE.md
PROVENANCE.md
.github/workflows/test.yml
.gitignore
```

Keep vendor layout aligned with Daily's "vendor/<upstream-owner>/<skill>" pattern. Do not invent a second folder for the same Skill.

Monolith copy map:

| monolith | Personal |
|---|---|
| `community/alchaincyf/skills/darwin-skill` | `vendor/alchaincyf/darwin-skill` |
| `community/alchaincyf/codex/skills/darwin-skill` | `adapters/codex/alchaincyf/darwin-skill` |
| `community/nextlevelbuilder/skills/ui-ux-pro-max` | `vendor/nextlevelbuilder/ui-ux-pro-max` |
| `community/nextlevelbuilder/codex/skills/ui-ux-pro-max` | `adapters/codex/nextlevelbuilder/ui-ux-pro-max` |
| `community/panniantong/skills/agent-reach` | `vendor/panniantong/agent-reach` |
| `community/panniantong/codex/skills/agent-reach` | `adapters/codex/panniantong/agent-reach` |
| `community/open-skills/skills/architecture` | `vendor/markdown-viewer/architecture` |
| `community/open-skills/skills/baoyu-markdown-to-html` | `vendor/baoyu/baoyu-markdown-to-html` |
| `community/open-skills/skills/bb-browser` | `vendor/epiral/bb-browser` |
| `community/open-skills/codex/skills/bb-browser` | `adapters/codex/epiral/bb-browser` |
| `community/open-skills/skills/code-to-prd` | `vendor/alirezarezvani/code-to-prd` |
| `community/open-skills/skills/graphify` | `vendor/safishamsi/graphify` |
| `community/open-skills/skills/humanizer-zh` | `vendor/op7418/humanizer-zh` |
| `community/open-skills/codex/skills/humanizer-zh` | `adapters/codex/op7418/humanizer-zh` |
| `community/open-skills/skills/notebooklm` | `vendor/pleaseprompto/notebooklm` |
| `community/open-skills/codex/skills/notebooklm` | `adapters/codex/pleaseprompto/notebooklm` |
| `community/open-skills/skills/planning-with-files` | `vendor/othmanadi/planning-with-files` |
| `community/open-skills/skills/prd` | `vendor/github/prd` |
| `community/open-skills/skills/to-prd` | `vendor/mattpocock/to-prd` |
| `community/open-skills/skills/self-improving-agent` | `vendor/zhaono1/self-improving-agent` |

Copy Personal-only sync scripts:

```text
tools/community/sync_alchaincyf_skills_from_upstream.py
tools/community/sync_nextlevelbuilder_skills_from_upstream.py
tools/community/sync_panniantong_skills_from_upstream.py
tools/community/sync_skills_sh_skills_from_upstream.py
```

Rewrite their default roots to Personal vendor paths. The skills.sh sync script in Personal must only accept Personal source names; Daily mermaid/prompt-optimizer stay Daily.

## Personal Skill inventory (14)

```text
agent-reach
architecture
baoyu-markdown-to-html
bb-browser
code-to-prd
darwin-skill
graphify
humanizer-zh
notebooklm
planning-with-files
prd
self-improving-agent
to-prd
ui-ux-pro-max
```

---

### Task 1: Personal inventory test and snapshot scaffold

**Files:**
- Create: `/Users/lijieli/personal-skills/`
- Test: `/Users/lijieli/personal-skills/tests/test-personal-inventory.py`
- Create: `/Users/lijieli/personal-skills/tests/lib/install-test-env.sh` in Task 3, not Task 1.

**Interfaces:**
- Consumes: spec Personal inventory.
- Produces: failing tests that become the Plan 3 gate.

- [ ] **Step 1: Write the failing inventory test**

```python
# tests/test-personal-inventory.py
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PERSONAL = {
    "agent-reach", "architecture", "baoyu-markdown-to-html", "bb-browser",
    "code-to-prd", "darwin-skill", "graphify", "humanizer-zh", "notebooklm",
    "planning-with-files", "prd", "self-improving-agent", "to-prd",
    "ui-ux-pro-max",
}
REJECTED = {
    "architecture-blueprint-generator", "job-description-analyzer",
    "resume-ats-optimizer", "resume-bullet-writer", "resume-tailor",
    "tailored-resume-generator", "tech-resume-optimizer",
}
TEAM_LEAK = {
    "fix", "qa", "product-director", "skill-pull", "code-review-fix",
    "qft-branch-management", "lib",
}
DAILY_LEAK = {
    "brainstorming", "grilling", "skill-creator", "systematic-debugging",
}


class PersonalInventoryTests(unittest.TestCase):
    def test_count(self) -> None:
        self.assertEqual(len(PERSONAL), 14)

    def test_rejected_and_foreign_absent(self) -> None:
        found = {p.parent.name for p in ROOT.glob("**/SKILL.md")}
        self.assertTrue(found.isdisjoint(REJECTED | TEAM_LEAK | DAILY_LEAK))

    def test_no_team_machinery(self) -> None:
        for name in ("hooks", "agents", "protocols", "contracts/standard-chain.yaml"):
            self.assertFalse((ROOT / name).exists() if "/" not in name else (ROOT / Path(name)).exists())
        self.assertFalse((ROOT / "shared").exists())
        self.assertFalse((ROOT / "first-party" / "skills" / "skill-pull").exists())

    def test_no_generated_darwin_cards(self) -> None:
        self.assertEqual(list(ROOT.glob("**/cards/review-result-card.*")), [])
        self.assertEqual(list(ROOT.glob("**/results.tsv")), [])
```

- [ ] **Step 2: Run to verify fail**

```bash
python3 /Users/lijieli/personal-skills/tests/test-personal-inventory.py
```

Expected: FAIL missing repo.

- [ ] **Step 3: Scaffold repo**

```bash
mkdir -p /Users/lijieli/personal-skills
git -C /Users/lijieli/personal-skills init
```

`PROVENANCE.md` records `pre-split-2026-08-31` and every Personal third-party ref from current `community/SOURCES.yaml`. `CLAUDE.md` only imports `AGENTS.md`. `VERSION` is `0.1.0`.

- [ ] **Step 4: Commit scaffold**

```bash
git -C /Users/lijieli/personal-skills add PROVENANCE.md VERSION README.md AGENTS.md CLAUDE.md tests/test-personal-inventory.py
git -C /Users/lijieli/personal-skills commit -m "chore: scaffold personal-skills snapshot"
```

Task 1 green gate is `test_count` plus absence checks. Add `test_every_skill_has_skill_md` (`found == PERSONAL`) in Task 2 after vendors land; do not run it as a Task 1 gate.

---

### Task 2: Copy Personal vendor trees, adapters, and source lock

**Files:**
- Create vendor/adapter trees from the copy map.
- Create: `sources/SOURCES.yaml` with Personal keys only.
- Copy Personal sync scripts into `tools/source-sync/`.

**Interfaces:**
- Consumes: tagged monolith community trees.
- Produces: 14 Skill roots; Darwin canonical source without generated cards.

- [ ] **Step 1: Write failing source-lock test**

```python
# tests/test-personal-source-lock.py
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "alchaincyf_darwin_skill",
    "nextlevelbuilder_ui_ux_pro_max",
    "panniantong_agent_reach",
    "skills_sh_bb_browser",
    "skills_sh_alirezarezvani_code_to_prd",
    "skills_sh_baoyu_markdown_to_html",
    "skills_sh_github_prd",
    "skills_sh_graphify",
    "skills_sh_markdown_viewer_architecture",
    "skills_sh_humanizer_zh",
    "skills_sh_mattpocock_to_prd",
    "skills_sh_notebooklm",
    "skills_sh_othmanadi_planning_with_files",
    "skills_sh_self_improving_agent",
}


class PersonalSourceLockTests(unittest.TestCase):
    def test_keys_and_to_prd_ref(self) -> None:
        lock = yaml.safe_load((ROOT / "sources" / "SOURCES.yaml").read_text())
        self.assertEqual(set(lock["sources"]), EXPECTED)
        self.assertNotIn("superpowers", lock["sources"])
        self.assertNotIn("mattpocock_grill", lock["sources"])
        self.assertEqual(
            lock["sources"]["skills_sh_mattpocock_to_prd"]["ref"],
            "2454c95dc305c158b21a0cdafeb728879dd0359a",
        )
        self.assertEqual(
            lock["sources"]["alchaincyf_darwin_skill"]["ref"],
            "2fbaf4171e453d5c66fc8109a296ae89c4772bc3",
        )
```

- [ ] **Step 2: Run to verify fail**

```bash
python3 /Users/lijieli/personal-skills/tests/test-personal-source-lock.py
```

Expected: FAIL missing lock.

- [ ] **Step 3: Copy trees**

Use `cp -R` from the tagged monolith. Do not copy:

- `.claude/skills/darwin-skill/cards/`
- `.claude/skills/darwin-skill/results.tsv`
- Daily vendor trees
- `community/open-skills/skills/mermaid-diagrams`
- `community/open-skills/skills/prompt-optimizer`

Rewrite sync script default paths. `sync_skills_sh_skills_from_upstream.py` in Personal must fail if asked to sync mermaid or prompt-optimizer.

- [ ] **Step 4: Run inventory and lock tests**

```bash
python3 /Users/lijieli/personal-skills/tests/test-personal-inventory.py
python3 /Users/lijieli/personal-skills/tests/test-personal-source-lock.py
```

Expected: lock PASS. Task 1 inventory assertions that require `contracts/skill-runtime-surface.json` run in Task 3, not here.

- [ ] **Step 5: Commit**

```bash
git -C /Users/lijieli/personal-skills add vendor adapters sources tools/source-sync
git -C /Users/lijieli/personal-skills commit -m "feat: import Personal vendor trees from pre-split-2026-08-31"
```

---

### Task 3: Personal dependencies, surface, and installer

**Files:**
- Create: `contracts/dependencies.yaml`
- Create: `contracts/skill-runtime-surface.json`
- Create: `tools/install/tree_digest.py` (copy Plan 1; do not import Base)
- Create: `tools/install/repo_install.py`
- Create: `install.sh`
- Create: `tests/lib/install-test-env.sh`
- Test: `tests/test-install-lifecycle.sh`
- Test: `tests/test-personal-dependencies.py`

**Interfaces:**
- Consumes: Plan 1 installer types.
- Produces: Personal installer with empty `requires`; maintenance-only `skill-pull` edge that does not block install.

- [ ] **Step 1: Write failing tests**

```python
# tests/test-personal-dependencies.py
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class PersonalDependencyTests(unittest.TestCase):
    def test_install_has_no_repo_requires(self) -> None:
        data = yaml.safe_load((ROOT / "contracts" / "dependencies.yaml").read_text())
        self.assertEqual(data.get("repo_requires", []), [])
        edges = data.get("maintenance_edges", [])
        self.assertEqual(len(edges), 1)
        edge = edges[0]
        self.assertEqual(edge["caller"], "personal-source-update")
        self.assertEqual(edge["required_unit"], "skill-pull")
        self.assertEqual(edge["owner"], "daily-skills")
        self.assertEqual(edge["scope"], "maintenance-only")

    def test_surface_keys_match_inventory(self) -> None:
        import json
        surface = json.loads((ROOT / "contracts" / "skill-runtime-surface.json").read_text())
        self.assertEqual(
            set(surface["skills"]),
            {
                "agent-reach", "architecture", "baoyu-markdown-to-html", "bb-browser",
                "code-to-prd", "darwin-skill", "graphify", "humanizer-zh", "notebooklm",
                "planning-with-files", "prd", "self-improving-agent", "to-prd",
                "ui-ux-pro-max",
            },
        )
        self.assertNotIn("qft-branch-management", surface["skills"])
        self.assertNotIn("skill-pull", surface["skills"])
```

Lifecycle tests in a temp HOME:

1. `--dry-run` is a no-op.
2. `--target all` installs 14 Skills to Claude and Codex.
3. Unowned destination is conflict.
4. Drift stops upgrade/uninstall.
5. Uninstall removes owned trees only.
6. Install succeeds with Daily not installed (`<state-root>/daily-skills` absent).
7. No hooks/agents/protocols created.
8. Rejected Skill names absent from installed dirs.
9. State path is `skill-repos/personal-skills/<target>/installed.json`, not `~/.org-skills-state`.

- [ ] **Step 2: Run to verify fail**

```bash
python3 /Users/lijieli/personal-skills/tests/test-personal-dependencies.py
bash /Users/lijieli/personal-skills/tests/test-install-lifecycle.sh
```

Expected: FAIL missing installer.

- [ ] **Step 3: Implement**

`contracts/dependencies.yaml`:

```yaml
schema_version: 1
repo_requires: []
edges: []
maintenance_edges:
  - caller: personal-source-update
    scope: maintenance-only
    required_unit: skill-pull
    owner: daily-skills
```

Surface: copy the 14 Personal keys from current `contracts/skill-runtime-surface.json`. Do not add `skill-pull`.

Installer staging copies vendor Skill trees, overlays Codex adapters, applies surface, records tree digests. Missing `skill-pull` must not fail `install.sh`. A future `tools/source-sync` wrapper may check for `skill-pull` at maintenance time only; do not build a resolver.

- [ ] **Step 4: Run tests including inventory surface assertion**

```bash
python3 /Users/lijieli/personal-skills/tests/test-personal-inventory.py
python3 /Users/lijieli/personal-skills/tests/test-personal-dependencies.py
bash /Users/lijieli/personal-skills/tests/test-install-lifecycle.sh
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /Users/lijieli/personal-skills add contracts tools/install tools/skills install.sh tests
git -C /Users/lijieli/personal-skills commit -m "feat: install Personal skills without Daily prerequisite"
```

---

### Task 4: Personal gate and push; do not install locally

**Files:**
- Create: `tests/run-all.sh`
- Create: `.github/workflows/test.yml`

**Interfaces:**
- Consumes: confirmed `personal-skills` remote.
- Produces: pushed Personal HEAD. Local runtime unchanged.

- [ ] **Step 1: Add gate**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
python3 tests/test-personal-inventory.py
python3 tests/test-personal-source-lock.py
python3 tests/test-personal-dependencies.py
bash tests/test-install-lifecycle.sh
echo "[PASS] personal-skills gates"
```

- [ ] **Step 2: Run Personal gate and monolith quick gate**

```bash
bash /Users/lijieli/personal-skills/tests/run-all.sh
cd /Users/lijieli/org-claude-skills && bash tests/run-all.sh --quick
```

Expected: both PASS. Confirm this machine's `~/.claude/skills` and `~/.agents/skills` were not written by Personal tests (tests use temp HOME).

- [ ] **Step 3: Push**

```bash
git -C /Users/lijieli/personal-skills remote add origin <confirmed personal-skills URL>
git -C /Users/lijieli/personal-skills push -u origin HEAD:main
git -C /Users/lijieli/personal-skills tag -a personal-skills-cutover-start -m "Personal snapshot from pre-split-2026-08-31"
git -C /Users/lijieli/personal-skills push origin personal-skills-cutover-start
git -C /Users/lijieli/personal-skills ls-remote origin HEAD
```

Do not run `install.sh` against the real `$HOME`.

---

## Plan 3 acceptance

1. Exactly 14 Personal Skills; rejected seven absent.
2. No hooks/agents/protocols/`skill-pull`/Team Skills.
3. Darwin cards/TSV absent; Darwin vendor tree present.
4. `to-prd` ref is `2454c95`, not the Grill ref.
5. Install lifecycle passes in temp HOME without Daily installed.
6. Personal remote HEAD is pushed.
7. This machine does not have Personal manifests under the new state root.

## Handoff

- Plan 4 may delete Personal-owned monolith paths only after this remote SHA exists.
- Plan 5 must not install Personal on this machine.
