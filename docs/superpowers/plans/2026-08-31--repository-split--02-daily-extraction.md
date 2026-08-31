# Repository Split Plan 2: Daily Extraction

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `daily-skills` snapshot repository with exactly 42 installable Skills, source locks, Codex adapters, runtime-surface policy, Grill/Obsidian fetches, checkout-scoped `skill-pull`, and a Daily-owned installer.

**Architecture:** Copy Daily-owned vendor trees out of the monolith without rewriting Superpowers bytes. Fetch Grill and Obsidian at locked refs because they are absent from Git. Keep vendor directories source-pure; put Codex adapters and runtime-surface outside vendor trees. Implement Daily's installer independently; do not import Base or Team installer code.

**Tech Stack:** Git snapshot repo, Python installer using Plan 1 types, YAML source lock, JSON runtime surface, isolated-HOME bash tests.

**Spec:** `docs/superpowers/specs/2026-08-31--repository-split-and-clean-runtime-migration--design.md`

**Depends on:** Plan 1 Task 1 inventory green; Plan 1 Task 2 tag `pre-split-2026-08-31` pushed before vendor extraction; Plan 1 Task 4 `tree_digest.py` exists before Daily installer tasks. Remotes confirmed before Daily `git push`. Base installer types from Plan 1 Global Constraints. Copy digest bytes; do not import the Base checkout.

**Unblocks:** Plan 4 deletion of Daily-owned monolith paths; Plan 5 local Daily install.

**Forbidden:** Deleting monolith `community/` or `shared/skills/skill-pull` (Plan 4). Installing Daily onto this machine. Fetching sibling repos at install time. Vendoring a generic source-sync library into Personal. Polluting `vendor/superpowers/`.

## Global Constraints

- Same installer CLI, state root, lock, manifest schema, digest, conflict, drift, and `--target all` rules as Plan 1.
- Daily `repo_id` is `daily-skills`. Daily `requires` is `[]`.
- Daily installable Skill count is 42. Inventories of Daily, Personal, and Team are disjoint.
- Superpowers vendor tree is a pure upstream mirror. No overlay, adapter, runtime frontmatter, or source header under `vendor/superpowers/`.
- Grill lock: `https://github.com/mattpocock/skills` @ `bb1c760d559872044e76d18216c87165fa69908a`.
- Obsidian lock: `https://github.com/kepano/obsidian-skills` @ `a1dc48e68138490d522c04cbf5822214c6eb1202`.
- Anthropic, Superpowers, Vercel, Mermaid, prompt-optimizer refs stay the values in current `community/SOURCES.yaml`.
- `mattpocock` `to-prd` is Personal, different ref (`2454c95dc305c158b21a0cdafeb728879dd0359a`). Daily must not copy it.
- `skill-pull` is checkout-scoped. Commit and push stay explicit user actions.
- `--target all` installs Daily Skills to both Claude and Codex unless a Skill's own surface contract forbids a target. Obsidian is not Codex-only.
- No hooks, agents, protocols, or standard-chain runtime in Daily.
- Tests must not grep Skill Markdown prose.
- Python tests that import `tools.*` must `sys.path.insert(0, str(ROOT))` or run with `PYTHONPATH="$ROOT"`.
- Create Daily `tests/lib/install-test-env.sh` as a new helper (same names as Plan 1 Base helper). Do not source the monolith helper.

## File Structure

Create `/Users/lijieli/daily-skills/`:

```text
first-party/skills/skill-pull/
vendor/anthropic/
vendor/superpowers/
vendor/vercel/
vendor/awesome-copilot/prompt-optimizer/
vendor/softaworks/mermaid-diagrams/
vendor/obsidian/
vendor/mattpocock/
adapters/codex/
sources/SOURCES.yaml
contracts/dependencies.yaml
contracts/skill-runtime-surface.json
contracts/superpowers-boundary.yaml
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

Monolith sources to copy (do not delete yet):

```text
shared/skills/skill-pull/
community/anthropic/
community/superpowers/
community/vercel/
community/open-skills/skills/mermaid-diagrams
community/open-skills/skills/prompt-optimizer
contracts/superpowers-boundary.yaml
tools/community/check_superpowers_upstream_fidelity.py
tools/community/sync_anthropic_skills_from_upstream.py
tools/community/sync_canonical_from_upstream.py
tools/community/sync_vercel_skills_from_upstream.py
tools/community/source_lock_check.py  # split; Daily keeps Daily keys only
tools/skills/apply_skill_runtime_surface.py
```

## Daily Skill inventory (42)

```text
agent-browser
algorithmic-art
brainstorming
brand-guidelines
canvas-design
claude-api
dispatching-parallel-agents
doc-coauthoring
docx
domain-modeling
executing-plans
find-skills
finishing-a-development-branch
frontend-design
grill-me
grill-with-docs
grilling
internal-comms
mcp-builder
mermaid-diagrams
obsidian-cli
obsidian-markdown
pdf
pptx
prompt-optimizer
receiving-code-review
requesting-code-review
skill-creator
skill-pull
slack-gif-creator
subagent-driven-development
systematic-debugging
test-driven-development
theme-factory
using-git-worktrees
using-superpowers
verification-before-completion
web-artifacts-builder
webapp-testing
writing-plans
writing-skills
xlsx
```

Skill runtime destinations:

| target | resource_root |
|---|---|
| claude | `$HOME/.claude/skills/<skill>` |
| codex | `$HOME/.agents/skills/<skill>` |

`resource_id` equals the Skill name. `kind` is `tree`.

---

### Task 1: Daily inventory and empty snapshot repo

**Files:**
- Create: `/Users/lijieli/daily-skills/` git repo
- Create: `/Users/lijieli/daily-skills/tests/test-daily-inventory.py`
- Create: `/Users/lijieli/daily-skills/tests/lib/install-test-env.sh` (Task 4 may land the helper; Task 1 only needs inventory tests)

**Interfaces:**
- Consumes: Plan 1 `DAILY_SKILLS` allowlist.
- Produces: `list_installable_skills(repo_root: Path) -> set[str]` that returns exactly 42 names after later tasks fill the tree.

- [ ] **Step 1: Write the failing inventory test**

```python
# tests/test-daily-inventory.py
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAILY_SKILLS = {
    "agent-browser", "algorithmic-art", "brainstorming", "brand-guidelines",
    "canvas-design", "claude-api", "dispatching-parallel-agents", "doc-coauthoring",
    "docx", "domain-modeling", "executing-plans", "find-skills",
    "finishing-a-development-branch", "frontend-design", "grill-me",
    "grill-with-docs", "grilling", "internal-comms", "mcp-builder",
    "mermaid-diagrams", "obsidian-cli", "obsidian-markdown", "pdf", "pptx",
    "prompt-optimizer", "receiving-code-review", "requesting-code-review",
    "skill-creator", "skill-pull", "slack-gif-creator",
    "subagent-driven-development", "systematic-debugging",
    "test-driven-development", "theme-factory", "using-git-worktrees",
    "using-superpowers", "verification-before-completion",
    "web-artifacts-builder", "webapp-testing", "writing-plans",
    "writing-skills", "xlsx",
}
FORBIDDEN = {
    "architecture-blueprint-generator", "job-description-analyzer",
    "resume-ats-optimizer", "resume-bullet-writer", "resume-tailor",
    "tailored-resume-generator", "tech-resume-optimizer",
    "code-review-fix", "doc-review-fix", "darwin-skill", "fix",
    "qft-branch-management", "lib", "qft-branch-flow-workspace",
}


class DailyInventoryTests(unittest.TestCase):
    def test_count_and_disjoint_forbidden(self) -> None:
        self.assertEqual(len(DAILY_SKILLS), 42)

    def test_every_skill_has_skill_md(self) -> None:
        found = {p.parent.name for p in ROOT.glob("**/SKILL.md")}
        self.assertEqual(found, DAILY_SKILLS)

    def test_forbidden_names_absent(self) -> None:
        present = {p.parent.name for p in ROOT.glob("**/SKILL.md")}
        self.assertTrue(present.isdisjoint(FORBIDDEN))

    def test_no_hooks_agents_protocols(self) -> None:
        for name in ("hooks", "agents", "protocols"):
            self.assertFalse((ROOT / name).exists(), name)
            self.assertFalse((ROOT / "shared" / name).exists(), name)

    def test_superpowers_vendor_has_no_adapters(self) -> None:
        vendor = ROOT / "vendor" / "superpowers"
        self.assertTrue(vendor.exists())
        self.assertEqual(list(vendor.glob("**/agents/openai.yaml")), [])
        self.assertFalse((vendor / "codex").exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 /Users/lijieli/daily-skills/tests/test-daily-inventory.py
```

Expected: FAIL missing repo or missing `SKILL.md`.

- [ ] **Step 3: Init repo and PROVENANCE.md**

```bash
mkdir -p /Users/lijieli/daily-skills
git -C /Users/lijieli/daily-skills init
```

`PROVENANCE.md` records `pre-split-2026-08-31`, monolith URL/SHA, and third-party refs. `VERSION` is `0.1.0`. `CLAUDE.md` only imports `AGENTS.md`.

- [ ] **Step 4: Commit scaffold**

```bash
git -C /Users/lijieli/daily-skills add PROVENANCE.md VERSION README.md AGENTS.md CLAUDE.md tests/test-daily-inventory.py
git -C /Users/lijieli/daily-skills commit -m "chore: scaffold daily-skills snapshot"
```

Keep `test_count_and_disjoint_forbidden` as the Task 1 green gate. Do not run `test_every_skill_has_skill_md` until Task 3 has fetched Grill/Obsidian. Daily Codex adapters come from `community/anthropic/codex` and `community/vercel/codex` only. `community/open-skills/codex/skills` is Personal (`bb-browser`, `humanizer-zh`, `notebooklm`); do not copy it.

---

### Task 2: Copy existing Daily vendor trees, adapters, and source lock

**Files:**
- Create Daily vendor/adapter/source-lock files listed above.
- Copy Superpowers fidelity checker and Daily-only sync scripts into `tools/source-sync/`.
- Rewrite `contracts/superpowers-boundary.yaml` paths from `community/superpowers/skills` to `vendor/superpowers/skills`.

**Interfaces:**
- Consumes: tagged monolith trees.
- Produces: Daily source lock containing only Daily sources; Superpowers bytes identical to monolith lock.

- [ ] **Step 1: Write failing fidelity/source-lock tests**

```python
# tests/test-daily-source-lock.py
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COPIED_SOURCES = {
    "anthropic_skills",
    "superpowers",
    "vercel_skills",
    "vercel_agent_browser",
    "skills_sh_github_prompt_optimizer",
    "skills_sh_softaworks_mermaid_diagrams",
}
FETCHED_SOURCES = {
    "mattpocock_grill",
    "kepano_obsidian",
}
EXPECTED_SOURCES = COPIED_SOURCES | FETCHED_SOURCES
FORBIDDEN_SOURCES = {
    "alchaincyf_darwin_skill",
    "nextlevelbuilder_ui_ux_pro_max",
    "panniantong_agent_reach",
    "skills_sh_mattpocock_to_prd",
}


class DailySourceLockTests(unittest.TestCase):
    def test_copied_lock_keys(self) -> None:
        lock = yaml.safe_load((ROOT / "sources" / "SOURCES.yaml").read_text())
        self.assertTrue(COPIED_SOURCES.issubset(lock["sources"]))
        self.assertTrue(set(lock["sources"]).isdisjoint(FORBIDDEN_SOURCES))
        self.assertEqual(
            lock["sources"]["superpowers"]["ref"],
            "b36e0829c6d0140e93cfef2ca599b1b07d4a7797",
        )

    def test_fetched_lock_keys(self) -> None:
        lock = yaml.safe_load((ROOT / "sources" / "SOURCES.yaml").read_text())
        self.assertEqual(set(lock["sources"]), EXPECTED_SOURCES)
        self.assertEqual(
            lock["sources"]["mattpocock_grill"]["ref"],
            "bb1c760d559872044e76d18216c87165fa69908a",
        )
        self.assertEqual(
            lock["sources"]["kepano_obsidian"]["ref"],
            "a1dc48e68138490d522c04cbf5822214c6eb1202",
        )

    def test_superpowers_boundary_paths(self) -> None:
        text = (ROOT / "contracts" / "superpowers-boundary.yaml").read_text()
        self.assertIn("vendor/superpowers/skills", text)
        self.assertNotIn("community/superpowers", text)
```

Also copy/adapt `tests/test-superpowers-upstream-fidelity.sh` so the checker root is Daily and the mirror path is `vendor/superpowers/skills`.

- [ ] **Step 2: Run to verify fail**

```bash
python3 /Users/lijieli/daily-skills/tests/test-daily-source-lock.py
```

Expected: FAIL missing `sources/SOURCES.yaml`.

- [ ] **Step 3: Copy and relayout**

Copy mapping:

| monolith | Daily |
|---|---|
| `community/anthropic/skills` | `vendor/anthropic/skills` |
| `community/anthropic/codex/skills` | `adapters/codex/anthropic/` |
| `community/superpowers/skills` | `vendor/superpowers/skills` |
| `community/vercel/skills` | `vendor/vercel/skills` |
| `community/vercel/codex/skills` | `adapters/codex/vercel/` |
| `community/open-skills/skills/mermaid-diagrams` | `vendor/softaworks/mermaid-diagrams/` |
| `community/open-skills/skills/prompt-optimizer` | `vendor/awesome-copilot/prompt-optimizer/` |
| `shared/skills/skill-pull` | `first-party/skills/skill-pull` |

Keep Superpowers bytes byte-for-byte. Rewrite sync scripts' default paths to Daily layout. `source_lock_check.py` in Daily must list only `EXPECTED_SOURCES`. Scope paths in `SOURCES.yaml` must point at Daily vendor paths.

Do not copy Personal vendor trees. Do not copy `to-prd`.

- [ ] **Step 4: Prove Superpowers fidelity**

```bash
python3 /Users/lijieli/daily-skills/tools/source-sync/check_superpowers_upstream_fidelity.py
python3 /Users/lijieli/daily-skills/tests/test-daily-source-lock.py
```

Expected: fidelity PASS against lock ref `b36e0829c6d0140e93cfef2ca599b1b07d4a7797`. `test_copied_lock_keys` PASS. `test_fetched_lock_keys` stays FAIL until Task 3; do not run that method as a Task 2 gate.

- [ ] **Step 5: Commit copied vendors**

```bash
git -C /Users/lijieli/daily-skills add vendor adapters first-party contracts tools/source-sync sources
git -C /Users/lijieli/daily-skills commit -m "feat: import Daily vendor trees from pre-split-2026-08-31"
```

---

### Task 3: Fetch Grill and Obsidian at locked refs

**Files:**
- Create: `vendor/mattpocock/{grill-me,grilling,grill-with-docs,domain-modeling}/`
- Create: `vendor/obsidian/{obsidian-cli,obsidian-markdown}/`
- Modify: `sources/SOURCES.yaml` with `mattpocock_grill` and `kepano_obsidian`.

**Interfaces:**
- Consumes: network fetch of locked refs.
- Produces: four Grill Skill roots and two Obsidian Skill roots with `SKILL.md`.

- [ ] **Step 1: Write a fetch-identity test**

```python
# tests/test-grill-obsidian-lock.py
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRILL = ["grill-me", "grilling", "grill-with-docs", "domain-modeling"]
OBSIDIAN = ["obsidian-cli", "obsidian-markdown"]


class GrillObsidianTests(unittest.TestCase):
    def test_skill_roots_exist(self) -> None:
        for name in GRILL:
            self.assertTrue((ROOT / "vendor" / "mattpocock" / name / "SKILL.md").is_file(), name)
        for name in OBSIDIAN:
            self.assertTrue((ROOT / "vendor" / "obsidian" / name / "SKILL.md").is_file(), name)

    def test_lock_refs_are_reachable_from_provenance(self) -> None:
        text = (ROOT / "PROVENANCE.md").read_text()
        self.assertIn("bb1c760d559872044e76d18216c87165fa69908a", text)
        self.assertIn("a1dc48e68138490d522c04cbf5822214c6eb1202", text)
```

- [ ] **Step 2: Run to verify fail**

```bash
python3 /Users/lijieli/daily-skills/tests/test-grill-obsidian-lock.py
```

Expected: FAIL missing `SKILL.md`.

- [ ] **Step 3: Fetch into a bounded temp clone and copy Skill roots**

```bash
tmp="$(mktemp -d "${TMPDIR:-/tmp}/daily-fetch.XXXXXX")"
git clone --filter=blob:none https://github.com/mattpocock/skills.git "$tmp/mattpocock"
git -C "$tmp/mattpocock" checkout --detach bb1c760d559872044e76d18216c87165fa69908a
git clone --filter=blob:none https://github.com/kepano/obsidian-skills.git "$tmp/obsidian"
git -C "$tmp/obsidian" checkout --detach a1dc48e68138490d522c04cbf5822214c6eb1202
```

Locate each Skill by `SKILL.md` whose frontmatter `name:` matches, or by directory name. Copy only those Skill roots into `vendor/mattpocock/<name>` and `vendor/obsidian/<name>`. Fail closed if any of the six names is missing. Do not copy the rest of those upstream repos. Record upstream path mapping in `PROVENANCE.md`. Remove `$tmp` after copy.

If network fetch fails, stop. Do not substitute runtime copies from `~/.claude` or `~/.agents`.

- [ ] **Step 4: Run tests**

```bash
python3 /Users/lijieli/daily-skills/tests/test-grill-obsidian-lock.py
python3 /Users/lijieli/daily-skills/tests/test-daily-source-lock.py
```

Expected: PASS lock keys including Grill/Obsidian.

- [ ] **Step 5: Commit**

```bash
git -C /Users/lijieli/daily-skills add vendor/mattpocock vendor/obsidian sources/SOURCES.yaml PROVENANCE.md
git -C /Users/lijieli/daily-skills commit -m "feat: vendor Grill and Obsidian at locked refs"
```

---

### Task 4: Runtime surface, Grill dependencies, and Daily installer

**Files:**
- Create: `contracts/skill-runtime-surface.json` with exactly the 42 Daily keys.
- Create: `contracts/dependencies.yaml`
- Create: `tools/install/tree_digest.py` (copy Plan 1 implementation; do not import from Base checkout)
- Create: `tools/install/repo_install.py`
- Create: `tools/skills/apply_skill_runtime_surface.py` (copy from monolith)
- Create: `install.sh`
- Create: `tests/lib/install-test-env.sh`
- Test: `tests/test-install-lifecycle.sh`
- Test: `tests/test-daily-dependencies.py`

**Interfaces:**
- Consumes: Plan 1 installer types; Daily Skill trees; surface contract.
- Produces: Daily installer that stages Skills, applies surface, overlays Codex adapters outside vendor trees, writes tree-digest manifests.

- [ ] **Step 1: Write failing dependency and installer tests**

```python
# tests/test-daily-dependencies.py
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class DailyDependencyTests(unittest.TestCase):
    def test_hard_edges_only(self) -> None:
        data = yaml.safe_load((ROOT / "contracts" / "dependencies.yaml").read_text())
        edges = {(e["caller"], e["required_unit"]) for e in data["edges"]}
        self.assertEqual(
            edges,
            {
                ("grill-me", "grilling"),
                ("grill-with-docs", "grilling"),
                ("grill-with-docs", "domain-modeling"),
            },
        )
        for edge in data["edges"]:
            self.assertEqual(edge["scope"], "runtime-invocation")
            self.assertEqual(edge["owner"], "daily-skills")

    def test_no_repo_requires(self) -> None:
        data = yaml.safe_load((ROOT / "contracts" / "dependencies.yaml").read_text())
        self.assertEqual(data.get("repo_requires", []), [])
```

Lifecycle tests (bash) must cover:

1. `--dry-run` writes no `$HOME/.claude/skills` and no state.
2. `--target all` installs all 42 Skills to Claude and Codex, including Grill and Obsidian.
3. Superpowers installed trees are not required to match vendor bytes after surface apply; vendor trees stay pure. Assert vendor `brainstorming/SKILL.md` digest equals locked upstream, and installed copy may differ only in declared runtime-surface fields.
4. Unowned existing Skill directory is conflict.
5. Digest drift stops upgrade/uninstall.
6. Upgrade removes a file deleted from the Skill tree.
7. Uninstall removes only owned Skill trees.
8. Missing `grilling` while a plan contains `grill-me` fails with owner `daily-skills` and Skill `grilling`. Cover this with `validate_internal_skill_edges(plan)` unit tests. Do not add a hidden `--skills` install filter. Default full-repo Daily install includes all four Grill Skills and therefore satisfies the edges.
9. No `~/.org-skills-state` and no hooks directory created.
10. `lib` and `*-workspace` names are absent from the installed skill dir.

- [ ] **Step 2: Run to verify fail**

```bash
python3 /Users/lijieli/daily-skills/tests/test-daily-dependencies.py
bash /Users/lijieli/daily-skills/tests/test-install-lifecycle.sh
```

Expected: FAIL missing installer/contracts.

Add `test_surface_keys_match_inventory` to `tests/test-daily-inventory.py` in this task:

```python
    def test_surface_keys_match_inventory(self) -> None:
        import json
        surface = json.loads((ROOT / "contracts" / "skill-runtime-surface.json").read_text())
        self.assertEqual(set(surface["skills"]), DAILY_SKILLS)
```

- [ ] **Step 3: Implement contracts and installer**

`contracts/dependencies.yaml`:

```yaml
schema_version: 1
repo_requires: []
edges:
  - caller: grill-me
    scope: runtime-invocation
    required_unit: grilling
    owner: daily-skills
  - caller: grill-with-docs
    scope: runtime-invocation
    required_unit: grilling
    owner: daily-skills
  - caller: grill-with-docs
    scope: runtime-invocation
    required_unit: domain-modeling
    owner: daily-skills
```

Surface JSON: copy Daily keys from current `contracts/skill-runtime-surface.json`. Add `grill-me`, `grilling`, `grill-with-docs`, `domain-modeling`, `obsidian-cli`, `obsidian-markdown` as `mode: manual` unless upstream frontmatter already implies auto; default manual for newly fetched Skills. Do not copy Team or Personal keys.

Installer staging:

1. Copy each Skill tree from its vendor or first-party root into a temp stage.
2. Overlay `adapters/codex/<vendor>/<skill>/` onto Codex stage only.
3. Run `apply_skill_runtime_surface.py --runtime claude|codex`.
4. Record one `resource_id` per Skill with `kind: tree`.
5. Shared parent `$HOME/.claude/skills` is a container, not an owned resource.

Copy `tree_digest.py` bytes from Base after Plan 1 Task 4; do not `sys.path` to `/Users/lijieli/base-config`.

Internal Grill edges: `validate_internal_skill_edges(plan)` fails if a caller Skill is in the plan and its required unit is not. Full-repo Daily install includes all four Grill Skills.

- [ ] **Step 4: Run tests**

```bash
python3 /Users/lijieli/daily-skills/tests/test-daily-inventory.py
python3 /Users/lijieli/daily-skills/tests/test-daily-dependencies.py
bash /Users/lijieli/daily-skills/tests/test-install-lifecycle.sh
python3 /Users/lijieli/daily-skills/tools/source-sync/check_superpowers_upstream_fidelity.py
```

Expected: all PASS. Inventory test now finds 42 `SKILL.md` files.

- [ ] **Step 5: Commit**

```bash
git -C /Users/lijieli/daily-skills add contracts tools/install tools/skills install.sh tests
git -C /Users/lijieli/daily-skills commit -m "feat: install Daily skills with Grill dependency edges"
```

---

### Task 5: Rewrite `skill-pull` as checkout-scoped updater

**Files:**
- Modify: `first-party/skills/skill-pull/SKILL.md`
- Modify: `first-party/skills/skill-pull/scripts/skill_pull_lib.py`
- Modify: `first-party/skills/skill-pull/scripts/run_update.py`
- Modify: `first-party/skills/skill-pull/scripts/check_candidates.py`
- Test: `tests/test-skill-pull-scripts.py` (behavioral, not Markdown prose)

**Interfaces:**
- Consumes: the checkout's `sources/SOURCES.yaml` and that checkout's source-sync adapters.
- Produces: working-tree updates only. No `git commit`, no `git push`, no `install.sh` as a required side effect.

- [ ] **Step 1: Write failing behavior tests**

```python
# tests/test-skill-pull-scripts.py
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = (ROOT / "first-party/skills/skill-pull/scripts/skill_pull_lib.py").read_text()
RUN = (ROOT / "first-party/skills/skill-pull/scripts/run_update.py").read_text()


class SkillPullBehaviorTests(unittest.TestCase):
    def test_managed_sources_are_daily_only(self) -> None:
        ns: dict = {}
        ast.parse(LIB)
        self.assertIn("anthropic_skills", LIB)
        self.assertIn("mattpocock_grill", LIB)
        self.assertIn("kepano_obsidian", LIB)
        self.assertNotIn("alchaincyf_darwin_skill", LIB)
        self.assertNotIn("skills_sh_mattpocock_to_prd", LIB)

    def test_run_update_does_not_push_or_commit(self) -> None:
        tree = ast.parse(RUN)
        called = [n.func.attr if isinstance(n.func, ast.Attribute) else ""
                  for n in ast.walk(tree) if isinstance(n, ast.Call)]
        text = RUN
        self.assertNotIn("git push", text)
        self.assertNotIn("git commit", text)
        self.assertNotIn("fast-forward", text.lower())

    def test_reads_checkout_sources_yaml(self) -> None:
        self.assertIn("sources/SOURCES.yaml", LIB)
        self.assertNotIn("community/SOURCES.yaml", LIB)
```

Also add a temp-checkout test: copy Daily `sources/SOURCES.yaml` into a temp dir without Personal keys; `load_sources(temp)` returns Daily names only and refuses to write paths outside that checkout.

- [ ] **Step 2: Run to verify fail**

```bash
python3 /Users/lijieli/daily-skills/tests/test-skill-pull-scripts.py
```

Expected: FAIL because copied `skill-pull` still references `community/SOURCES.yaml` and push/main flow.

- [ ] **Step 3: Implement checkout-scoped `skill-pull`**

Required behavior:

1. CWD/repo root is the checkout being updated.
2. Read only that checkout's `sources/SOURCES.yaml`.
3. Load adapters only from that checkout's `tools/source-sync/`.
4. Change only paths owned by those source entries.
5. Verify locked ref, subtree fidelity, license/provenance metadata recorded in `sources/SOURCES.yaml` notes, adapters, surfaces, and `bash tests/run-all.sh`.
6. Print diff and validation result.
7. Do not commit, push, fast-forward `main`, or run install as a hidden step.
8. Timeout every git/network call (`DEFAULT_TIMEOUT_SECONDS = 30`).

Rewrite `MANAGED_SOURCE_NAMES` to Daily keys only.

- [ ] **Step 4: Run tests**

```bash
python3 /Users/lijieli/daily-skills/tests/test-skill-pull-scripts.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /Users/lijieli/daily-skills add first-party/skills/skill-pull tests/test-skill-pull-scripts.py
git -C /Users/lijieli/daily-skills commit -m "feat: make skill-pull checkout-scoped"
```

---

### Task 6: Daily gate and push

**Files:**
- Create: `tests/run-all.sh`
- Create: `.github/workflows/test.yml`

**Interfaces:**
- Consumes: confirmed `daily-skills` remote.
- Produces: pushed Daily HEAD that Plan 4 may delete against.

- [ ] **Step 1: Add `tests/run-all.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
python3 tests/test-daily-inventory.py
python3 tests/test-daily-source-lock.py
python3 tests/test-grill-obsidian-lock.py
python3 tests/test-daily-dependencies.py
python3 tests/test-skill-pull-scripts.py
python3 tools/source-sync/check_superpowers_upstream_fidelity.py
bash tests/test-install-lifecycle.sh
echo "[PASS] daily-skills gates"
```

- [ ] **Step 2: Run Daily gate and monolith quick gate**

```bash
bash /Users/lijieli/daily-skills/tests/run-all.sh
cd /Users/lijieli/org-claude-skills && bash tests/run-all.sh --quick
```

Expected: Daily PASS; monolith `bash tests/run-all.sh --quick` stays green. Daily must not have mutated this machine's runtime.

- [ ] **Step 3: Push**

```bash
git -C /Users/lijieli/daily-skills remote add origin <confirmed daily-skills URL>
git -C /Users/lijieli/daily-skills push -u origin HEAD:main
git -C /Users/lijieli/daily-skills tag -a daily-skills-cutover-start -m "Daily snapshot from pre-split-2026-08-31"
git -C /Users/lijieli/daily-skills push origin daily-skills-cutover-start
git -C /Users/lijieli/daily-skills ls-remote origin HEAD
```

Stop if the remote is unconfirmed or the GitHub repo is missing.

---

## Plan 2 acceptance

1. Exactly 42 Daily Skills, each with `SKILL.md`.
2. Grill and Obsidian match locked refs; they were fetched, not copied from local runtime.
3. Superpowers vendor is byte-faithful; adapters live under `adapters/codex/`.
4. Surface keys == Daily inventory; rejected/Team/Personal names absent.
5. Hard edges are the three Grill edges only.
6. Installer lifecycle tests pass; no hooks/state legacy.
7. `skill-pull` cannot commit/push and reads `sources/SOURCES.yaml`.
8. Daily remote HEAD is pushed.
9. Monolith still contains Daily sources (Plan 4 deletes them).

## Handoff

- Plan 3 is independent after Plan 1 inventory.
- Plan 4 may delete Daily-owned monolith paths only after this remote SHA exists.
- Team `fix -> systematic-debugging` is a Plan 4 declaration, not a Daily repo-level require.
