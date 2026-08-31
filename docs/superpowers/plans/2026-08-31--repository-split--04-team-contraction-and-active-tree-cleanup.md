# Repository Split Plan 4: Team Contraction And Active-Tree Cleanup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Contract the current repository into `team-skills` only: delete already-pushed Base/Daily/Personal sources, rewrite active refs and tests, keep every standard-chain hook/agent/protocol/runtime, and prune only unreferenced generated artifacts.

**Architecture:** Copy-then-delete. Prove Base, Daily, and Personal remotes still contain the moved bytes, then delete those paths from this repo. Replace the monolith installer with a Team-owned installer that installs Team resources only, checks Base on the same target, and records `fix -> systematic-debugging` as an invocation-time edge. Do not rewrite Git history. Do not rename the GitHub repo.

**Tech Stack:** Existing Team contracts/validators, new Team installer using Plan 1 types plus current `manage_codex_runtime.py` / hook registry, inbound-ref scanner, isolated-HOME tests.

**Spec:** `docs/superpowers/specs/2026-08-31--repository-split-and-clean-runtime-migration--design.md`

**Depends on:** Plans 1–3 remotes have pushed cutover-start tags. Inventory generator from Plan 1.

**Unblocks:** Plan 5 cleaner.

**Forbidden:** Deleting moved sources before destination `ls-remote` proof. History rewrite. Installing Team on this machine during cutover. Creating a Team-hosted composition matrix. Copying Base payload back into Team. Using `install.sh --uninstall` of the old monolith against real HOME.

## Global Constraints

- Same installer CLI, state root, lock, manifest schema, digest, conflict, drift, and `--target all` rules as Plan 1.
- Team `repo_id` is `team-skills`. Physical remote remains `https://github.com/jieli-cqwl/org-claude-skills.git` unless remotes.yaml says otherwise.
- Team `requires` is Base on the same target, listing every Base `resource_id` because `post_compact.sh` reloads the Base rules directory and Team Skills read six named Base files.
- Invocation-time edge `fix -> daily-skills/systematic-debugging` lives in `contracts/dependencies.yaml` and does **not** enter `installed.json.requires`.
- `shared/skills/lib/` and `shared/skills/qft-branch-flow-workspace/` stay in-tree and are never installed.
- Keep `shared/hooks/`, `claude/hooks/`, `shared/agents/`, `shared/protocols/`, `shared/runtime/`, standard-chain contracts, validators, tools, tests, fixtures, docs, examples.
- Delete `qft-branch-management` from `contracts/skill-runtime-surface.json`.
- Active refs must resolve in this repo. Historical designs may keep old `shared/assistant.md` paths as dated provenance.
- Tests must not grep Skill / Rule / Reference / Agent Markdown prose.
- Inbound-ref deletion is conservative: referenced eval summaries stay; unreferenced raw output is removed from HEAD.

## File Structure

Keep in Team:

```text
shared/skills/<team skills>
shared/skills/lib/
shared/skills/qft-branch-flow-workspace/
claude/skills/code-review-fix
claude/skills/doc-review-fix
shared/hooks/
claude/hooks/
shared/agents/
shared/protocols/
shared/runtime/
contracts/ except moved surface keys and superpowers-boundary
tools/community/ except Daily/Personal sync and Superpowers fidelity
tools/eval/ except Base-owned rule-runtime evaluator copies after Team tests no longer import them
tests/ for Team behavior
.github/workflows/ rewritten Team gates
install.sh rewritten
```

Delete from Team HEAD after destination proof:

```text
shared/assistant.md
shared/rules/
shared/reference/
shared/skills/skill-pull/
community/
contracts/superpowers-boundary.yaml
tools/community/check_superpowers_upstream_fidelity.py
tools/community/sync_anthropic_skills_from_upstream.py
tools/community/sync_vercel_skills_from_upstream.py
tools/community/sync_alchaincyf_skills_from_upstream.py
tools/community/sync_nextlevelbuilder_skills_from_upstream.py
tools/community/sync_panniantong_skills_from_upstream.py
tools/community/sync_skills_sh_skills_from_upstream.py
tools/community/sync_canonical_from_upstream.py
tools/community/source_lock_check.py
tools/eval/contracts/rule-runtime-eval.json          # after Team tests stop importing it
tools/eval/scripts/run_rule_runtime_eval.py          # after Team tests stop importing it
tools/eval/scenarios/assistant-entry/                # after Team tests stop importing it
tools/eval/scenarios/sql-schema-comments/
tests/test-superpowers-upstream-fidelity.sh
tests/test-skill-pull-contract.sh
tests/test-skill-pull-scripts.py
tests/test-ownership-inventory.py
.claude/skills/darwin-skill/cards/
.claude/skills/darwin-skill/results.tsv
tracked .superpowers/* (6 files today)
unreferenced tools/eval/results/**
findings.md, progress.md, task_plan.md after inbound-ref check
.claude/settings.local.json Base-path permission
tools/split/ownership_allowlists.py and generate_ownership_inventory.py after destination proof (keep tests/test-split-destination-proof.py)
```

Rewrite:

```text
AGENTS.md
README.md
install.sh
contracts/skill-runtime-surface.json
tests/test-entry-doc-source-contract.sh
tests/test-install-*.sh
tests/lib/install-test-env.sh
tests/gate-plan.json
.github/workflows/test.yml
```

Team installable Skills (31 + 2 Claude-only):

```text
cli-updater commit consistency-audit deep-research delivery-estimator
delivery-owner design developer feishu-docs fix github-repo-radar
overview product-director product-manager project-memory prompt qa
qft-branch-flow qft-group-chat-export refactor research review
rules-manager scan security skill-quality-audit tech-lead test-design
ux verify worktree
code-review-fix doc-review-fix
```

---

### Task 1: Fail-closed proof that destinations already own the moved bytes

**Files:**
- Test: `tests/test-split-destination-proof.py`

**Interfaces:**
- Consumes: remotes.yaml; Base/Daily/Personal local checkouts and `ls-remote`.
- Produces: `assert_destinations_pushed()` that Plan 4 deletion tests call first.

- [ ] **Step 1: Write the failing proof test**

```python
# tests/test-split-destination-proof.py
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REMOTES = ROOT / "docs/superpowers/specs/2026-08-31--repository-split-and-clean-runtime-migration--remotes.yaml"


def git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)
    return proc.stdout.strip()


class DestinationProofTests(unittest.TestCase):
    def test_remotes_confirmed_and_pushed(self) -> None:
        data = yaml.safe_load(REMOTES.read_text())
        self.assertTrue(data["confirmed"])
        for repo_id, url in data["repos"].items():
            if repo_id == "team-skills":
                continue
            local = Path("/Users/lijieli") / repo_id
            self.assertTrue((local / ".git").exists(), repo_id)
            remote = git(local, "ls-remote", "origin", "HEAD").split()[0]
            head = git(local, "rev-parse", "HEAD")
            self.assertEqual(remote, head, repo_id)

    def test_base_payload_still_in_base(self) -> None:
        base = Path("/Users/lijieli/base-config")
        self.assertTrue((base / "assistant.md").is_file())
        self.assertTrue((base / "rules" / "code-changes.md").is_file())

    def test_daily_has_42_and_personal_has_14(self) -> None:
        daily = {p.parent.name for p in Path("/Users/lijieli/daily-skills").glob("**/SKILL.md")}
        personal = {p.parent.name for p in Path("/Users/lijieli/personal-skills").glob("**/SKILL.md")}
        self.assertEqual(len(daily), 42)
        self.assertEqual(len(personal), 14)
        self.assertIn("skill-pull", daily)
        self.assertIn("darwin-skill", personal)
        self.assertNotIn("skill-pull", personal)
```

- [ ] **Step 2: Run to verify it fails if remotes are missing**

```bash
python3 tests/test-split-destination-proof.py
```

If this fails because remotes are unconfirmed, stop the entire plan. Do not delete sources.

- [ ] **Step 3: No implementation beyond making sibling paths and remotes.yaml real from Plans 1–3.** If tests fail, return to those plans.

- [ ] **Step 4: Once green, commit the proof test only**

```bash
git add tests/test-split-destination-proof.py
git commit -m "test: require pushed Base Daily Personal before Team contraction"
```

---

### Task 2: Team inventory, surface split, and dependency contract

**Files:**
- Create: `contracts/dependencies.yaml`
- Modify: `contracts/skill-runtime-surface.json`
- Test: `tests/test-team-inventory.py`

**Interfaces:**
- Consumes: spec Team inventories.
- Produces: Team surface keys == Team Skills; `qft-branch-management` gone; `skill-pull` gone.

- [ ] **Step 1: Write failing tests**

```python
# tests/test-team-inventory.py
from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
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
NON_INSTALLABLE = {"lib", "qft-branch-flow-workspace"}


class TeamInventoryTests(unittest.TestCase):
    def test_first_party_skill_roots(self) -> None:
        roots = {p.parent.name for p in (ROOT / "shared/skills").glob("*/SKILL.md")}
        self.assertEqual(roots, TEAM)
        self.assertTrue((ROOT / "shared/skills/lib").is_dir())
        self.assertFalse((ROOT / "shared/skills/lib/SKILL.md").exists())
        self.assertTrue((ROOT / "shared/skills/qft-branch-flow-workspace").is_dir())
        self.assertFalse((ROOT / "shared/skills/skill-pull").exists())
        self.assertFalse((ROOT / "community").exists())
        self.assertFalse((ROOT / "shared/assistant.md").exists())
        self.assertFalse((ROOT / "shared/rules").exists())
        self.assertFalse((ROOT / "shared/reference").exists())

    def test_claude_only(self) -> None:
        found = {p.parent.name for p in (ROOT / "claude/skills").glob("*/SKILL.md")}
        self.assertEqual(found, CLAUDE_ONLY)

    def test_surface_is_team_only(self) -> None:
        surface = json.loads((ROOT / "contracts/skill-runtime-surface.json").read_text())
        self.assertEqual(set(surface["skills"]), TEAM | CLAUDE_ONLY)
        self.assertNotIn("qft-branch-management", surface["skills"])
        self.assertNotIn("skill-pull", surface["skills"])
        self.assertNotIn("brainstorming", surface["skills"])

    def test_dependencies(self) -> None:
        data = yaml.safe_load((ROOT / "contracts/dependencies.yaml").read_text())
        self.assertEqual(data["repo_requires"][0]["repo_id"], "base-config")
        self.assertEqual(data["repo_requires"][0]["target"], "same")
        ids = set(data["repo_requires"][0]["resource_ids"])
        self.assertIn("assistant", ids)
        self.assertIn("rules/code-changes.md", ids)
        self.assertIn("reference/测试规范.md", ids)
        edges = {(e["caller"], e["required_unit"], e["owner"]) for e in data["edges"]}
        self.assertEqual(edges, {("fix", "systematic-debugging", "daily-skills")})
        self.assertEqual(data["edges"][0]["scope"], "runtime-invocation")
```

- [ ] **Step 2: Run to verify fail**

```bash
python3 tests/test-team-inventory.py
```

Expected: FAIL because `community/` and `shared/assistant.md` still exist and surface still has mixed keys.

- [ ] **Step 3: Do not delete trees yet. First split the surface and add `contracts/dependencies.yaml`.**

`contracts/dependencies.yaml`:

```yaml
schema_version: 1
repo_requires:
  - repo_id: base-config
    target: same
    resource_ids:
      - assistant
      - rules/code-changes.md
      - rules/completion-claims.md
      - rules/document-governance.md
      - rules/execution-control.md
      - reference/authentication-and-authorization.md
      - reference/code-comments.md
      - reference/code-structure-reuse.md
      - reference/constants-and-configuration.md
      - reference/error-handling.md
      - reference/impact-analysis.md
      - reference/performance-and-efficiency.md
      - reference/协作判断.md
      - reference/技术方案设计.md
      - reference/测试规范.md
edges:
  - caller: fix
    scope: runtime-invocation
    required_unit: systematic-debugging
    owner: daily-skills
optional_edges:
  - caller: qa
    unit: webapp-testing
    owner: daily-skills
    class: optional
```

Remove every non-Team key from `contracts/skill-runtime-surface.json`, including `qft-branch-management` and `skill-pull`.

Keep `shared/assistant.md` until Task 4 so current tests still have a source; the inventory test's "assistant.md absent" assertion is expected red until Task 4. Split `test_first_party_skill_roots` assertions: put "assistant/community absent" into `test_contracted_tree` and run that only after deletion.

- [ ] **Step 4: Run the surface/dependency assertions**

Make the test file accept a `--phase surface` or split classes so surface/deps can pass before deletion.

- [ ] **Step 5: Commit**

```bash
git add contracts/dependencies.yaml contracts/skill-runtime-surface.json tests/test-team-inventory.py
git commit -m "feat: declare Team Base dependency and split runtime surface"
```

---

### Task 3: Rewrite Team installer around retained ownership

**Files:**
- Replace: `install.sh` with a Team-owned wrapper + `tools/install/repo_install.py`
- Keep: `tools/community/manage_codex_runtime.py`, `shared/hooks/registry.json`, `tools/community/render_hook_registry.py`, `tools/skills/apply_skill_runtime_surface.py`
- Modify: `tests/lib/install-test-env.sh` to use `SKILL_REPO_STATE_ROOT`
- Test: `tests/test-team-install-lifecycle.sh`

**Interfaces:**
- Consumes: Plan 1 types; Base reverse-dep already implemented in Base; Team hook/agent structured config.
- Produces: Team installer that never copies Base files, never copies Daily/Personal Skills, never installs `lib` or `*-workspace`.

- [ ] **Step 1: Write failing lifecycle tests**

Cases:

1. Isolated HOME, Base **not** installed: `bash install.sh --target claude` fails naming `base-config` and the missing resource ids. No Team files written.
2. Install Base from `/Users/lijieli/base-config` into the same HOME, then Team install succeeds.
3. Team install writes Team Skills, hooks, agents, protocols, runtime catalogs. Assert `product-director/SKILL.md` exists. Assert `skill-pull`, `brainstorming`, `darwin-skill`, `grilling` are absent. Assert `lib` and `qft-branch-flow-workspace` absent from runtime skill dirs.
4. Codex target writes agents via existing `manage_codex_runtime.py` identities. Assert `developer.toml` exists. Record structured entries in the Team manifest; do not restore whole-file `config.toml` baselines.
5. Claude-only Skills exist on Claude target and are absent on Codex target.
6. Missing `systematic-debugging` does **not** fail Team install. A dedicated `check_skill_edge("fix")` helper fails with owner `daily-skills` and Skill `systematic-debugging` and does not clone Daily.
7. Drift on a Team Skill stops upgrade/uninstall.
8. Unowned destination conflict.
9. `--target all` validates both first.
10. Uninstall removes Team resources whose digests match, leaves Base files in place, and then Base uninstall succeeds.
11. State is `skill-repos/team-skills/<target>/installed.json`. `~/.org-skills-state` is not created.
12. `post_compact.sh` is installed as a Team hook resource, not as Base.

Keep using isolated HOME. Do not run against the real user runtime.

- [ ] **Step 2: Run to verify fail**

```bash
bash tests/test-team-install-lifecycle.sh
```

Expected: FAIL because current `install.sh` still copies Base/Daily/Personal and uses `ORG_STATE_ROOT`.

- [ ] **Step 3: Implement Team installer**

Replace payload selection in `install.sh`. Preferred shape: thin bash wrapper calling `tools/install/repo_install.py`, which:

1. Renders Team Skills from `shared/skills/<name>` and `claude/skills/<name>`.
2. Calls `prune_internal_skill_roots` equivalent: drop `*-workspace`, `evals/`, `fixtures/`, `examples/`, `selves/` from staged Skills.
3. Applies Team-only runtime surface.
4. Copies `shared/hooks` + `claude/hooks` as hook resources.
5. Copies `shared/agents/claude` / `shared/agents/codex`.
6. Copies `shared/protocols` and `shared/runtime`.
7. Uses `render_hook_registry.py` + `manage_codex_runtime.py` for structured entries. Record each JSON/TOML identity in `structured_entries`.
8. Reads Base `installed.json` from the same state root/target and verifies every required Base `resource_id` plus the live files at Base destinations. Does not import Base Python.
9. Never copies `assistant.md` / `rules/` / `reference/` from anywhere.

Keep `tools/community/manage_codex_runtime.py` behavior for agent sections, but stop writing `~/.org-skills-state` and stop restoring `codex-hooks-baseline.json`.

Keep the monolith helper names `install_test_run_install` / `install_test_run_install_allow_failure`. Do not rename them to Base's `install_test_run`. Point new Team lifecycle tests at `SKILL_REPO_STATE_ROOT`. Rewrite or delete callers that still assert community Skill installs from this repo.

Add a Team lifecycle case: corrupt `~/.codex/hooks.json` or a mid-write `[agents.developer]` section → install fails closed and does not write a silent partial agent file.

Add a `--target all` case: Claude succeeds, Codex hits an unowned conflict → visible partial success, not all-target success.

- [ ] **Step 4: Run Team install tests plus a focused subset of surviving install tests**

```bash
bash tests/test-team-install-lifecycle.sh
bash tests/test-install-core.sh --group basic
```

Replace `test-install-core.sh` groups that encode monolith composition (community Skills + Base files from this repo). Keep only Team-relevant groups. Remaining cases must install Base from `/Users/lijieli/base-config` first, then Team. Expect `skill-creator` **absent** (Daily). Expect `product-director` present. Do not keep a green test that installs Daily or Personal Skills from this repo.

- [ ] **Step 5: Commit**

```bash
git add install.sh uninstall.sh tools/install tests/lib/install-test-env.sh tests/test-team-install-lifecycle.sh tests/test-install-core.sh
git commit -m "feat: install Team resources only and require Base"
```

`uninstall.sh` either becomes a wrapper to `install.sh --uninstall` or is deleted if unused; do not leave a path that restores whole-file baselines.

---

### Task 4: Delete moved sources and rewrite active refs

**Files:**
- Delete moved trees listed in File Structure.
- Modify: `AGENTS.md`, `README.md`, `tests/test-entry-doc-source-contract.sh`, `tests/gate-plan.json`, `.github/workflows/test.yml`
- Delete: Daily/Personal-only tests that cannot survive contraction.

**Interfaces:**
- Consumes: destination proof from Task 1.
- Produces: Team worktree with no Base payload, no `community/`, no `skill-pull`.

- [ ] **Step 1: Write failing contracted-tree test**

Enable `test_contracted_tree` from Task 2. Add:

```python
    def test_active_docs_do_not_point_at_moved_shared_payload(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text()
        self.assertNotIn("shared/assistant.md", agents)
        self.assertNotIn("shared/rules/*.md", agents)
        self.assertNotIn("community/superpowers/skills", agents)
        self.assertIn("team-skills", agents)
```

- [ ] **Step 2: Run to verify fail**

```bash
python3 tests/test-team-inventory.py
bash tests/test-entry-doc-source-contract.sh
```

Expected: FAIL on remaining `shared/assistant.md` references.

- [ ] **Step 3: Delete and rewrite**

Before `git rm`:

```bash
python3 tests/test-split-destination-proof.py
```

Must PASS.

Then `git rm` moved paths. Rewrite `AGENTS.md`:

- Commands stay Team gates: `bash tests/run-all.sh --quick`, `bash install.sh --target all --dry-run`.
- Instruction sources: Team does not own runtime assistant/rules/reference. Say Team Skills consume Base rules/references at the installed runtime paths.
- Skill sources: `shared/skills/` is Team first-party; Superpowers lives in Daily.
- Keep test-signal-assertion rule and `CLAUDE.md` import-only rule.
- Keep `MAX_AGENTS_LINES=34` or raise it only if Team-required lines exceed it; do not pad.

Rewrite `tests/test-entry-doc-source-contract.sh` to match the new `AGENTS.md` contracts. Do not grep Rule/Reference Markdown bodies.

Remove from `tests/run-all.sh` (`SYNTAX_SHELL_FILES` / `py_compile` lists), `tests/gate-plan.json`:

- `tests/test-skill-pull-contract.sh`
- `tests/test-skill-pull-scripts.py`
- `tests/test-superpowers-upstream-fidelity.sh`
- `tests/test-ownership-inventory.py`
- `ownership-inventory` gate step

Rewrite or confirm `CHANGELOG.md`, `.gitleaks.toml`, and `.gitignore` still describe Team-only ownership. Do not leave changelog text that says this repo installs Superpowers/Anthropic.
- Base-only rule-runtime evaluator tests (`tests/test-rule-runtime-eval-contracts.*`, `tests/test-rule-runtime-eval-runner.sh`) if they still import deleted `shared/assistant.md` paths. Keep `docs/rule-runtime--team-readiness/` as historical evidence if inbound-referenced. Remove those docs from `tests/gate-plan.json` execution if they require the moved evaluator. Do not keep a Team test that reads `shared/assistant.md`.

- [ ] **Step 4: Run Team inventory, entry-doc, and `bash tests/run-all.sh --quick`**

Expected: inventory PASS; entry-doc PASS; quick gate rewritten to Team-only steps and PASS. A failing leftover reference to `community/SOURCES.yaml` or `shared/assistant.md` is a bug, not a skip.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: contract repository to team-skills ownership"
```

Inspect `git show --stat`: moved payload must be deletions, not copies into a backup directory.

---

### Task 5: Prune generated artifacts by inbound reference

**Files:**
- Create: `tools/split/prune_unreferenced_eval_results.py`
- Test: `tests/test-eval-result-inbound-refs.py`
- Delete: every tracked `.superpowers/` path (`git ls-files .superpowers`; observed 6 tracked files; ~185 ignored on-disk files stay untracked and are not copied). Delete darwin cards/TSV, unreferenced `tools/eval/results/**` after Plan 1 moved Base-owned inbound refs, plus `findings.md`, `progress.md`, `task_plan.md` if no inbound refs.
- Rewrite or delete `.claude/settings.local.json` if it still hard-codes `/Users/lijieli/org-claude-skills/shared/rules|reference|assistant.md`. After Base leaves Team, that permission is stale. Recreate only if a Team-owned local permission is still required; do not point at moved Base paths.

**Interfaces:**
- Consumes: current git-tracked files and references from tests/contracts/skill evals.
- Produces: HEAD without unreferenced generated blobs.

- [ ] **Step 1: Write failing inbound-ref tests**

```python
# tests/test-eval-result-inbound-refs.py
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tracked(prefix: str) -> set[str]:
    out = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", prefix], text=True)
    return {line for line in out.splitlines() if line}


class InboundRefTests(unittest.TestCase):
    def test_every_tracked_eval_result_is_referenced(self) -> None:
        results = tracked("tools/eval/results")
        text_roots = [
            ROOT / "tests",
            ROOT / "contracts",
            ROOT / "shared/skills",
            ROOT / "tools/eval/contracts",
            ROOT / "tools/eval/scenarios",
        ]
        corpus = []
        for root in text_roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.suffix in {".py", ".sh", ".json", ".md", ".yaml"} and path.is_file():
                    corpus.append(path.read_text(encoding="utf-8", errors="replace"))
        blob = "\n".join(corpus)
        unused = [rel for rel in sorted(results) if rel not in blob]
        self.assertEqual(unused, [])

    def test_generated_noise_gone(self) -> None:
        self.assertEqual(tracked(".superpowers"), set())
        self.assertEqual(tracked(".claude/skills/darwin-skill"), set())
        self.assertFalse((ROOT / "findings.md").exists())
        self.assertFalse((ROOT / "progress.md").exists())
        self.assertFalse((ROOT / "task_plan.md").exists())

    def test_local_settings_do_not_point_at_moved_base_paths(self) -> None:
        settings = ROOT / ".claude" / "settings.local.json"
        if not settings.exists():
            return
        text = settings.read_text(encoding="utf-8")
        self.assertNotIn("shared/assistant.md", text)
        self.assertNotIn("shared/rules/", text)
        self.assertNotIn("shared/reference/", text)
```

- [ ] **Step 2: Run to verify fail**

```bash
python3 tests/test-eval-result-inbound-refs.py
```

Expected: FAIL with unused eval results and tracked `.superpowers`.

- [ ] **Step 3: Prune**

Implementation: scan inbound refs; `git rm` unreferenced result files; keep referenced `summary.json` and any files those summaries need if tests read them. Delete tracked `.superpowers/` files (currently 6). Leave ignored on-disk `.superpowers/` alone; do not copy it. Delete darwin generated cards. For `findings.md`, `progress.md`, `task_plan.md`, search inbound refs; if none, `git rm`. Do not create `archive/` or `backup/`.

- [ ] **Step 4: Run tests and `git grep` for deleted paths in active tests/contracts**

```bash
python3 tests/test-eval-result-inbound-refs.py
git grep -n 'findings.md\|progress.md\|task_plan.md\|shared/assistant.md\|community/SOURCES.yaml' -- tests contracts AGENTS.md README.md ':!docs/superpowers/specs' ':!docs/superpowers/plans'
```

Expected: inbound-ref test PASS; grep only hits Plan/spec files or documented historical provenance, not active tests.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: drop unreferenced generated artifacts from Team HEAD"
```

---

### Task 6: Team full gate and push cutover commit

**Files:**
- Modify: `tests/run-all.sh`, `tests/gate-plan.json`, `.github/workflows/test.yml` as needed after Task 4/5.

**Interfaces:**
- Consumes: contracted tree.
- Produces: pushed Team commit and tag `team-skills-cutover`.

- [ ] **Step 1: Run `bash tests/run-all.sh --quick` then `bash tests/run-all.sh`**

Expected: both PASS on the contracted tree. CI workflow still runs `bash tests/run-all.sh` without Daily vendor trees. If CI needs ripgrep/pyyaml/jsonschema, keep those setup steps.

- [ ] **Step 2: Confirm Team CI may fetch pinned Base and Daily `systematic-debugging` only if tests need them**

If Task 3 tests already install Base from the sibling checkout, CI must either:

- vendor a tiny Base fixture, or
- `git clone --depth 1 --branch base-config-cutover-start` the confirmed Base remote in those tests.

Do not clone all of Daily. If the `fix` edge test needs `systematic-debugging`, clone that one Skill from the confirmed Daily tag into the temp HOME, not into Team source.

- [ ] **Step 3: Push**

```bash
git push origin main
git tag -a team-skills-cutover -m "Team contracted after Base/Daily/Personal extraction"
git push origin team-skills-cutover
git ls-remote origin team-skills-cutover
```

---

## Plan 4 acceptance

1. Destination proof passed before any deletion.
2. Team tree has Team Skills + hooks/agents/protocols/runtime; no Base payload, no `community/`, no `skill-pull`.
3. `lib` and workspace remain and are not installed.
4. Surface is Team-only; `qft-branch-management` gone.
5. Team install requires Base; `fix` edge is invocation-time only.
6. Active docs/tests/workflows resolve.
7. Tracked `.superpowers`, darwin cards, unreferenced eval results, and unreferenced planning ledgers are gone from HEAD.
8. `bash tests/run-all.sh --quick` and full `bash tests/run-all.sh` pass.
9. `team-skills-cutover` is pushed. Local runtime was not mutated.

## Handoff

- Plan 5 may build the one-time cleaner against this tag plus Base/Daily cutover-start tags.
- Do not install Team on this machine in Plan 5.
