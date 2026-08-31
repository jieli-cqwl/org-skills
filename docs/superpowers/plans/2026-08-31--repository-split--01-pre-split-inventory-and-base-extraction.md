# Repository Split Plan 1: Pre-split Inventory And Base Extraction

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze the ownership denominator, push the pre-split recovery tag, create the `base-config` snapshot repository, and prove Base can install, upgrade, drift-stop, and uninstall only its own assistant/rules/reference payload.

**Architecture:** Keep the current monolith untouched as payload source until Plan 4. Generate a machine-readable inventory from live source roots and fail on unmapped or duplicate ownership. Copy Base payload and Base-owned evaluators into a sibling snapshot repo with provenance. Give Base its own installer that implements the shared behavioral contract; do not extract a shared installer library.

**Tech Stack:** Git snapshot repo, bash `install.sh` wrapper, Python installer (`tools/install/repo_install.py`), JSON manifests, unittest + isolated-HOME bash tests.

**Spec:** `docs/superpowers/specs/2026-08-31--repository-split-and-clean-runtime-migration--design.md`

**Depends on:** Written spec at `a6e5e2a1` plus this plan set committed.

**Unblocks:** Plan 2/3 vendor copy after Task 1 inventory is green and Task 2 tag is pushed. Plan 2/3 installer tasks after Task 4 `tree_digest.py` exists (copy bytes; do not import the Base checkout). Plan 4 after this repo's cutover commit is pushed.

**Forbidden:** `git push`, `gh repo create`, and annotated-tag push until remotes.yaml has `confirmed: true`. Mutating `~/.claude`, `~/.codex`, `~/.agents`, or `~/.org-skills-state` on this machine. Calling current `install.sh --uninstall`. Installing Team or Personal. Adding a new `--quick` gate step (quick is capped at 36 by `tests/test-run-all-runner-contract.sh`).

## Global Constraints

- Logical repo IDs: `base-config`, `daily-skills`, `team-skills`, `personal-skills`.
- Current GitHub remote `https://github.com/jieli-cqwl/org-claude-skills.git` remains `team-skills`. Do not rename it.
- Installer CLI for every repo: `install.sh [--target claude|codex|all] [--dry-run] [--uninstall]`.
- State root: `${SKILL_REPO_STATE_ROOT:-${XDG_STATE_HOME:-$HOME/.local/state}/skill-repos}`.
- Manifest path: `<state-root>/<repo-id>/<target>/installed.json`.
- Common lock: `<state-root>/.lock` via `fcntl.flock`. Every installer must acquire it before read or mutate.
- Manifest `schema_version` is `1`. Path-only manifests are forbidden.
- Tree digest: sorted relative paths plus kind, executable mode (`0644` or `0755`), content sha256, symlink target. Exclude timestamps and host ownership.
- Reject absolute paths, `..` traversal, and symlinks that escape the resource root.
- New destination must be absent. Existing content without this repo's matching manifest is a conflict even when bytes match.
- Drift (digest mismatch) stops upgrade and uninstall. Never overwrite or delete modified content.
- `--target all` validates both targets first, then records each target outcome. Concurrent external write that stops one target is visible partial success, never all-target success. A lifecycle test must cover that path.
- No Profiles, no central orchestrator, no shared installer library, no persistent content backup. Copy `tree_digest.py` bytes into each repo; never `sys.path` to a sibling checkout.
- Tests must not lock Skill / Rule / Reference / Agent Markdown prose with `assert_present` / `assert_absent` / `grep` / `rg`. Assert paths, inventories, JSON contracts, and digests.
- Python tests that import `tools.*` MUST `sys.path.insert(0, str(ROOT))` where ROOT is the repo root, or run as `cd "$ROOT" && PYTHONPATH="$ROOT" python3 tests/...`. Bare `python3 tests/foo.py` puts `tests/` on `sys.path[0]` and cannot import `tools.split` / `tools.install`.
- Base `tests/lib/install-test-env.sh` is a **new** helper. It may define `install_test_run` / `install_test_run_allow_failure`. Do not assume monolith `install_test_run_install*` names exist here. Set `SKILL_REPO_STATE_ROOT="$home/.local/state/skill-repos"`; never `ORG_STATE_ROOT`.
- Sibling checkout root: parent of this monolith (`/Users/lijieli/base-config`, `/Users/lijieli/daily-skills`, `/Users/lijieli/personal-skills`).
- Recovery tag name: `pre-split-2026-08-31`.
- Base contains no Skills, hooks, agents, protocols, source locks, or standard-chain runtime.

## File Structure

Create in sibling `/Users/lijieli/base-config/` (empty git repo, no copied `.git` from the monolith):

```text
assistant.md
rules/code-changes.md
rules/completion-claims.md
rules/document-governance.md
rules/execution-control.md
reference/authentication-and-authorization.md
reference/code-comments.md
reference/code-structure-reuse.md
reference/constants-and-configuration.md
reference/error-handling.md
reference/impact-analysis.md
reference/performance-and-efficiency.md
reference/协作判断.md
reference/技术方案设计.md
reference/测试规范.md
install.sh
tools/install/tree_digest.py
tools/install/repo_install.py
tests/lib/install-test-env.sh
tests/test-tree-digest.py
tests/test-install-lifecycle.sh
tests/test-rule-runtime-eval-contracts.py
tests/test-rule-runtime-eval-contracts.sh
tests/run-all.sh
tools/eval/contracts/rule-runtime-eval.json
tools/eval/scripts/run_rule_runtime_eval.py
tools/eval/scenarios/assistant-entry/
tools/eval/scenarios/sql-schema-comments/
VERSION
README.md
AGENTS.md
CLAUDE.md
PROVENANCE.md
.github/workflows/test.yml
.gitignore
```

Create in the current monolith (split machinery only; inventory may land before the tag, remotes.yaml only after user confirmation):

```text
tools/split/__init__.py
tools/split/ownership_allowlists.py
tools/split/generate_ownership_inventory.py
tests/test-ownership-inventory.py
docs/superpowers/specs/2026-08-31--repository-split-and-clean-runtime-migration--remotes.yaml
```

Register `tests/test-ownership-inventory.py` in `tests/gate-plan.json` as **full** tier, not quick. Do not raise the 36-step quick cap. Plan 1 proving command is `cd "$ROOT" && PYTHONPATH="$ROOT" python3 tests/test-ownership-inventory.py` plus unchanged `bash tests/run-all.sh --quick`.

Do not copy `shared/hooks`, `shared/agents`, `shared/protocols`, `shared/skills`, `community/`, or `contracts/standard-chain.yaml` into Base.

## Shared Types (frozen for Plans 2–5)

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

REPO_IDS = ("base-config", "daily-skills", "team-skills", "personal-skills")
TARGETS = ("claude", "codex")
FILE_KINDS = ("file", "symlink")
RESOURCE_KINDS = ("file", "tree", "symlink")
SCHEMA_VERSION = 1

@dataclass(frozen=True)
class FileRecord:
    path: str
    kind: Literal["file", "symlink"]
    mode: Literal["0644", "0755"]
    sha256: str | None
    link_target: str | None

@dataclass(frozen=True)
class Require:
    repo_id: str
    target: Literal["same"]
    resource_ids: tuple[str, ...]

@dataclass
class ResourcePlan:
    resource_id: str
    resource_root: Path
    kind: Literal["file", "tree", "symlink"]
    source_path: Path
    files: list[FileRecord]
    tree_sha256: str

@dataclass
class InstallPlan:
    repo_id: str
    repo_version: str
    target: Literal["claude", "codex"]
    requires: list[Require]
    resources: list[ResourcePlan]
    structured_entries: list[dict] = field(default_factory=list)
```

Base `resource_id` values:

```text
assistant
rules/code-changes.md
rules/completion-claims.md
rules/document-governance.md
rules/execution-control.md
reference/authentication-and-authorization.md
reference/code-comments.md
reference/code-structure-reuse.md
reference/constants-and-configuration.md
reference/error-handling.md
reference/impact-analysis.md
reference/performance-and-efficiency.md
reference/协作判断.md
reference/技术方案设计.md
reference/测试规范.md
```

Runtime destinations:

| resource_id | claude | codex |
|---|---|---|
| `assistant` | `$HOME/.claude/CLAUDE.md` | `$HOME/.codex/AGENTS.md` |
| `rules/<file>` | `$HOME/.claude/rules/<file>` | `$HOME/.codex/rules/<file>` |
| `reference/<file>` | `$HOME/.claude/reference/<file>` | `$HOME/.codex/reference/<file>` |

Base `requires` is empty. Team is the only repo that later records a Base requirement.

---

### Task 1: Confirm remotes and freeze the ownership inventory

**Files:**
- Create: `docs/superpowers/specs/2026-08-31--repository-split-and-clean-runtime-migration--remotes.yaml`
- Create: `tools/split/ownership_allowlists.py`
- Create: `tools/split/generate_ownership_inventory.py`
- Test: `tests/test-ownership-inventory.py`

**Interfaces:**
- Consumes: spec ownership table and Skill inventories.
- Produces: `scan_ownership(repo_root: Path) -> Inventory`; `assert_complete(inventory)` raises `OwnershipError` on unmapped or duplicate atoms; remotes file with `confirmed: true`.

- [ ] **Step 1: Stop if remotes are unconfirmed**

Do not create GitHub repositories yet. Write this file only after the user confirms URLs. Recommended defaults matching origin owner `jieli-cqwl`:

```yaml
schema_version: 1
confirmed: true
visibility: private
repos:
  base-config: https://github.com/jieli-cqwl/base-config.git
  daily-skills: https://github.com/jieli-cqwl/daily-skills.git
  personal-skills: https://github.com/jieli-cqwl/personal-skills.git
  team-skills: https://github.com/jieli-cqwl/org-claude-skills.git
```

If the user supplies different URLs, write those instead. If `confirmed` is not `true`, every later task that runs `git remote add` or `git push` must fail closed.

- [ ] **Step 2: Write the failing inventory test**

```python
# tests/test-ownership-inventory.py
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.split.generate_ownership_inventory import (
    OwnershipError,
    assert_complete,
    scan_ownership,
)
from tools.split.ownership_allowlists import (
    BASE_FILES,
    DAILY_SKILLS,
    PERSONAL_SKILLS,
    REJECTED_SKILLS,
    TEAM_SKILLS,
    TEAM_CLAUDE_ONLY_SKILLS,
)


class OwnershipInventoryTests(unittest.TestCase):
    def test_current_monolith_is_fully_mapped(self) -> None:
        inventory = scan_ownership(ROOT)
        assert_complete(inventory)
        self.assertEqual(inventory.unmapped, [])
        self.assertEqual(inventory.duplicates, [])
        self.assertEqual(set(inventory.by_repo["daily-skills"]["skills"]), set(DAILY_SKILLS))
        self.assertEqual(set(inventory.by_repo["personal-skills"]["skills"]), set(PERSONAL_SKILLS))
        self.assertEqual(set(inventory.by_repo["team-skills"]["skills"]), set(TEAM_SKILLS) | set(TEAM_CLAUDE_ONLY_SKILLS))
        self.assertTrue(set(REJECTED_SKILLS).isdisjoint(inventory.present_skill_names))
        # Acceptance 1: DELETE / prune / out-of-scope atoms are mapped, not ignored.
        self.assertIn(".superpowers/", inventory.delete_from_active_head)
        self.assertIn(".claude/skills/darwin-skill/cards/", inventory.delete_from_active_head)
        self.assertIn("findings.md", inventory.delete_from_active_head)
        self.assertIn("tools/eval/results/", inventory.prune_by_inbound_ref)
        self.assertIn("claude-code-engineering/", inventory.out_of_scope)
        self.assertEqual(
            inventory.non_hard_edges[("qa", "webapp-testing")],
            "optional",
        )

    def test_unmapped_skill_root_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skill = root / "shared" / "skills" / "ghost" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("---\nname: ghost\n---\n", encoding="utf-8")
            inventory = scan_ownership(root)
            with self.assertRaises(OwnershipError) as ctx:
                assert_complete(inventory)
            self.assertIn("ghost", str(ctx.exception))
            self.assertIn("unmapped", str(ctx.exception).lower())

    def test_duplicate_mapping_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "shared" / "skills" / "skill-pull").mkdir(parents=True)
            (root / "shared" / "skills" / "skill-pull" / "SKILL.md").write_text(
                "---\nname: skill-pull\n---\n", encoding="utf-8"
            )
            (root / "community" / "open-skills" / "skills" / "skill-pull").mkdir(parents=True)
            (root / "community" / "open-skills" / "skills" / "skill-pull" / "SKILL.md").write_text(
                "---\nname: skill-pull\n---\n", encoding="utf-8"
            )
            inventory = scan_ownership(root)
            with self.assertRaises(OwnershipError) as ctx:
                assert_complete(inventory)
            self.assertIn("duplicate", str(ctx.exception).lower())

    def test_lib_and_workspace_are_not_installable_skills(self) -> None:
        inventory = scan_ownership(ROOT)
        self.assertIn("shared/skills/lib", inventory.non_installable)
        self.assertIn("shared/skills/qft-branch-flow-workspace", inventory.non_installable)
        self.assertNotIn("lib", inventory.present_skill_names)
        self.assertNotIn("qft-branch-flow-workspace", inventory.by_repo["team-skills"]["skills"])

    def test_allowlists_match_spec_counts(self) -> None:
        self.assertEqual(len(DAILY_SKILLS), 42)
        self.assertEqual(len(PERSONAL_SKILLS), 14)
        self.assertEqual(len(TEAM_SKILLS), 31)
        self.assertEqual(len(TEAM_CLAUDE_ONLY_SKILLS), 2)
        self.assertEqual(len(BASE_FILES), 15)
        self.assertEqual(len(set(DAILY_SKILLS) & set(PERSONAL_SKILLS) & set(TEAM_SKILLS)), 0)
        self.assertTrue(set(DAILY_SKILLS).isdisjoint(PERSONAL_SKILLS))
        self.assertTrue(set(DAILY_SKILLS).isdisjoint(TEAM_SKILLS))
        self.assertTrue(set(PERSONAL_SKILLS).isdisjoint(TEAM_SKILLS))
        self.assertTrue(set(DAILY_SKILLS).isdisjoint(TEAM_CLAUDE_ONLY_SKILLS))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
cd /Users/lijieli/org-claude-skills && PYTHONPATH="$PWD" python3 tests/test-ownership-inventory.py
```

Expected: FAIL with `ModuleNotFoundError` for `tools.split.generate_ownership_inventory`.

- [ ] **Step 4: Implement allowlists and scanner**

Copy the spec inventories verbatim into `tools/split/ownership_allowlists.py`. `DAILY_SKILLS` must include Grill/Obsidian names even though they are absent from current Git. Scanner roots:

```text
shared/assistant.md
shared/rules/*.md
shared/reference/*.md
shared/skills/*/SKILL.md
claude/skills/*/SKILL.md
community/*/skills/*/SKILL.md
community/*/codex/skills/*
shared/hooks/**
claude/hooks/**
shared/agents/**
shared/protocols/**
contracts/skill-runtime-surface.json keys
community/SOURCES.yaml source keys
```

Classification rules:

- `skill-pull` → Daily.
- `lib/` and `*-workspace/` → Team non-installable.
- `qft-branch-management` surface key → explicit delete, not a Skill owner.
- Grill/Obsidian names → Daily, status `MISSING_FROM_GIT_FETCH_IN_PLAN_2`.
- Rejected seven names → `DELETE`; fail if present.
- `claude-code-engineering/` and `qft-cc-core/` → `OUT_OF_SCOPE`.
- tracked `.superpowers/` → `DELETE_FROM_ACTIVE_HEAD` (current index has 6 files; ignore untracked on-disk trees).
- `.claude/skills/darwin-skill/cards/` and `results.tsv` → `DELETE_FROM_ACTIVE_HEAD`.
- `findings.md`, `progress.md`, `task_plan.md` → `DELETE_FROM_ACTIVE_HEAD` after inbound-ref check.
- `tools/eval/results/` → `PRUNE_BY_INBOUND_REF`; Base-owned inbound-referenced baselines MOVE with the evaluator in Task 6.
- `qa` → `webapp-testing` → `optional` (not a hard edge). Every other cross-repo Skill name hit must be hard, optional, test-only, documentation-only, or delete; unclassified hits fail `assert_complete`.

`assert_complete` fails if any scanned Skill root, source-lock key, runtime-surface key, hook file, agent file, protocol file, installer-selected name, tracked generated tree listed above, or unclassified cross-repo Skill mention is unmapped or mapped more than once. Missing Grill/Obsidian from Git is allowed only with status `MISSING_FROM_GIT_FETCH_IN_PLAN_2`.

- [ ] **Step 5: Run the test to verify it passes and wire it into the monolith full gate**

```bash
cd /Users/lijieli/org-claude-skills && PYTHONPATH="$PWD" python3 tests/test-ownership-inventory.py
```

Expected: PASS. Print `unmapped=[] duplicates=[] missing_from_git=[domain-modeling, grill-me, grill-with-docs, grilling, obsidian-cli, obsidian-markdown]`.

Add a `tests/gate-plan.json` step:

```json
{
  "id": "ownership-inventory",
  "command": ["python3", "tests/test-ownership-inventory.py"],
  "area": "install-runtime",
  "tier": "full",
  "tags": ["python", "split"],
  "parallel_safe": true,
  "timeout_sec": 60
}
```

Do **not** add it to quick. `tests/test-run-all-runner-contract.sh` fails if quick exceeds 36 steps. Prefix the python command's environment in `tests/run-all.sh` is not required if the test inserts `ROOT` onto `sys.path`. Keep `--quick` at 36 steps and still green.

- [ ] **Step 6: Commit**

```bash
git add tools/split tests/test-ownership-inventory.py \
  docs/superpowers/specs/2026-08-31--repository-split-and-clean-runtime-migration--remotes.yaml
git commit -m "$(cat <<'EOF'
feat(split): freeze ownership inventory and confirmed remotes

EOF
)"
```

Only include the remotes file in this commit if `confirmed: true`.

---

### Task 2: Push the design/plans and create the pre-split tag

**Files:**
- Modify: none besides git refs.
- Test: none. This is recovery-evidence setup.

**Interfaces:**
- Consumes: confirmed remotes; current `main` with design + plans + inventory.
- Produces: annotated tag `pre-split-2026-08-31` on the last monolithic source commit, pushed to `team-skills` remote.

- [ ] **Step 1: Verify working tree and commit remaining plan files if needed**

```bash
git status --short
git log --oneline origin/main..HEAD
```

Expected: only split-design/plan/inventory files. Commit any leftover plan files before tagging.

- [ ] **Step 2: Push `main` and create the annotated tag**

```bash
git push origin main
git tag -a pre-split-2026-08-31 -m "Monolithic source snapshot before repository split"
git push origin pre-split-2026-08-31
git ls-remote --tags origin 'pre-split-2026-08-31'
```

Expected: tag exists on origin. A local-only tag is not recovery evidence. Stop here if push is denied.

- [ ] **Step 3: Record the tag in a note used by later PROVENANCE.md files**

```bash
git rev-parse pre-split-2026-08-31^{}
git rev-parse origin/main
```

Keep both SHAs for Task 3 `PROVENANCE.md`. Do not mutate runtime.

---

### Task 3: Create the Base snapshot repository and copy payload

**Files:**
- Create: `/Users/lijieli/base-config/` as a new git repo.
- Copy payload from monolith `shared/assistant.md`, `shared/rules/`, `shared/reference/`.
- Create: `PROVENANCE.md`, `VERSION`, `README.md`, `AGENTS.md`, `CLAUDE.md`, `.gitignore`.

**Interfaces:**
- Consumes: tag `pre-split-2026-08-31`; `BASE_FILES`.
- Produces: Base worktree whose payload bytes match the tagged monolith files.

- [ ] **Step 1: Write a failing payload-identity test in the monolith that can run against the sibling repo**

Add to `tests/test-ownership-inventory.py`:

```python
    def test_base_checkout_payload_matches_tagged_source(self) -> None:
        base = Path("/Users/lijieli/base-config")
        self.assertTrue((base / ".git").exists(), "base-config repo missing")
        src_root = Path(__file__).resolve().parents[1]
        mapping = {
            "assistant.md": "shared/assistant.md",
            "rules/code-changes.md": "shared/rules/code-changes.md",
            "rules/completion-claims.md": "shared/rules/completion-claims.md",
            "rules/document-governance.md": "shared/rules/document-governance.md",
            "rules/execution-control.md": "shared/rules/execution-control.md",
            "reference/authentication-and-authorization.md": "shared/reference/authentication-and-authorization.md",
            "reference/code-comments.md": "shared/reference/code-comments.md",
            "reference/code-structure-reuse.md": "shared/reference/code-structure-reuse.md",
            "reference/constants-and-configuration.md": "shared/reference/constants-and-configuration.md",
            "reference/error-handling.md": "shared/reference/error-handling.md",
            "reference/impact-analysis.md": "shared/reference/impact-analysis.md",
            "reference/performance-and-efficiency.md": "shared/reference/performance-and-efficiency.md",
            "reference/协作判断.md": "shared/reference/协作判断.md",
            "reference/技术方案设计.md": "shared/reference/技术方案设计.md",
            "reference/测试规范.md": "shared/reference/测试规范.md",
        }
        for dst, src in mapping.items():
            left = (src_root / src).read_bytes()
            right = (base / dst).read_bytes()
            self.assertEqual(left, right, dst)
        forbidden = ["skills", "hooks", "agents", "protocols", "community", "shared"]
        for name in forbidden:
            self.assertFalse((base / name).exists(), name)
```

- [ ] **Step 2: Run it to verify it fails**

```bash
PYTHONPATH="$PWD" python3 tests/test-ownership-inventory.py TestOwnershipInventoryTests.test_base_checkout_payload_matches_tagged_source
```

Expected: FAIL `base-config repo missing`.

- [ ] **Step 3: Create the snapshot repo and copy payload**

```bash
mkdir -p /Users/lijieli/base-config
git -C /Users/lijieli/base-config init
# copy the 15 payload files with directories; do not copy monolith .git
cp shared/assistant.md /Users/lijieli/base-config/assistant.md
mkdir -p /Users/lijieli/base-config/rules /Users/lijieli/base-config/reference
cp shared/rules/*.md /Users/lijieli/base-config/rules/
cp shared/reference/*.md /Users/lijieli/base-config/reference/
```

`VERSION` starts at `0.1.0`. `CLAUDE.md` is only:

```markdown
# CLAUDE.md

@AGENTS.md
```

`AGENTS.md` must describe Base as assistant/rules/reference only, and must not mention `shared/assistant.md`.

`PROVENANCE.md` must record:

```text
source_url: https://github.com/jieli-cqwl/org-claude-skills.git
source_tag: pre-split-2026-08-31
source_commit: <sha from Task 2>
extracted_at: 2026-08-31
payload: assistant.md, rules/, reference/ copied from shared/
third_party_refs: none
```

`.gitignore`: `.DS_Store`, `__pycache__/`, `*.pyc`, `*.tmp`.

- [ ] **Step 4: Re-run payload identity test**

```bash
PYTHONPATH="$PWD" python3 tests/test-ownership-inventory.py TestOwnershipInventoryTests.test_base_checkout_payload_matches_tagged_source
```

Expected: PASS.

- [ ] **Step 5: Commit in the Base repo only**

```bash
git -C /Users/lijieli/base-config add assistant.md rules reference VERSION README.md AGENTS.md CLAUDE.md PROVENANCE.md .gitignore
git -C /Users/lijieli/base-config commit -m "feat: import Base payload from pre-split-2026-08-31"
```

Do not `git push` until Task 7. Do not delete `shared/assistant.md` from the monolith.

---

### Task 4: Tree digest and fail-closed path rules

**Files:**
- Create: `/Users/lijieli/base-config/tools/install/tree_digest.py`
- Test: `/Users/lijieli/base-config/tests/test-tree-digest.py`

**Interfaces:**
- Consumes: a directory or file.
- Produces: `canonical_tree_digest(root: Path) -> str`, `canonical_tree_files(root: Path) -> list[FileRecord]`. Raises `ValueError` on absolute/escaping symlinks or `..` paths.

- [ ] **Step 1: Write the failing digest tests**

```python
# tests/test-tree-digest.py
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.install.tree_digest import canonical_tree_digest, canonical_tree_files


class TreeDigestTests(unittest.TestCase):
    def test_sorted_paths_and_mode_and_content(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "b.txt").write_text("b\n", encoding="utf-8")
            (root / "a.txt").write_text("a\n", encoding="utf-8")
            os.chmod(root / "a.txt", 0o644)
            os.chmod(root / "b.txt", 0o755)
            files = canonical_tree_files(root)
            self.assertEqual([f.path for f in files], ["a.txt", "b.txt"])
            self.assertEqual(files[0].mode, "0644")
            self.assertEqual(files[1].mode, "0755")
            digest1 = canonical_tree_digest(root)
            (root / "a.txt").write_text("a2\n", encoding="utf-8")
            digest2 = canonical_tree_digest(root)
            self.assertNotEqual(digest1, digest2)

    def test_rejects_escaping_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "res"
            root.mkdir()
            outside = Path(td) / "outside.txt"
            outside.write_text("nope\n", encoding="utf-8")
            os.symlink(outside, root / "link")
            with self.assertRaises(ValueError):
                canonical_tree_files(root)

    def test_rejects_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            os.symlink("../x", root / "link")
            with self.assertRaises(ValueError):
                canonical_tree_files(root)

    def test_single_file_resource(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "CLAUDE.md"
            path.write_text("# x\n", encoding="utf-8")
            files = canonical_tree_files(path)
            self.assertEqual(files[0].path, path.name)
            self.assertEqual(files[0].kind, "file")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

```bash
PYTHONPATH=/Users/lijieli/base-config python3 /Users/lijieli/base-config/tests/test-tree-digest.py
```

Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement `tree_digest.py`**

Rules:

- Walk files and symlinks only; skip directories as records.
- Relative path is POSIX, sorted.
- Mode is `0755` if any execute bit is set, else `0644`. Symlinks record `0644`.
- File digest is sha256 of raw bytes.
- Canonical digest is sha256 over lines `path\0kind\0mode\0sha256_or_empty\0link_target_or_empty\n`.
- A file resource uses the file's parent as walk root and a single record.
- Reject `Path.is_absolute()` link targets and any `..` in link target parts.

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=/Users/lijieli/base-config python3 /Users/lijieli/base-config/tests/test-tree-digest.py
```

Expected: PASS.

- [ ] **Step 5: Commit in Base**

```bash
git -C /Users/lijieli/base-config add tools/install/tree_digest.py tests/test-tree-digest.py
git -C /Users/lijieli/base-config commit -m "feat: add canonical tree digest"
```

---

### Task 5: Base installer lifecycle

**Files:**
- Create: `/Users/lijieli/base-config/tools/install/repo_install.py`
- Create: `/Users/lijieli/base-config/install.sh`
- Create: `/Users/lijieli/base-config/tests/lib/install-test-env.sh`
- Test: `/Users/lijieli/base-config/tests/test-install-lifecycle.sh`

**Interfaces:**
- Consumes: `canonical_tree_digest`, Base payload, `SKILL_REPO_STATE_ROOT`, `HOME`.
- Produces: `install.sh` that writes `base-config/<target>/installed.json` and the 15 runtime files; no Skills/hooks.

- [ ] **Step 1: Write the failing lifecycle test**

```bash
# tests/test-install-lifecycle.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
. "$ROOT/tests/lib/install-test-env.sh"
install_test_init

install_test_case_start "dry-run writes nothing"
home="$(install_test_new_home base-dry)"
log="$(install_test_log_path base-dry)"
install_test_run "$home" "$log" --target all --dry-run
install_test_assert_path_absent "$home/.claude/CLAUDE.md" "dry-run claude assistant"
install_test_assert_path_absent "$home/.codex/AGENTS.md" "dry-run codex assistant"
install_test_assert_path_absent "$(install_test_state_root "$home")/base-config" "dry-run state"
install_test_case_pass "dry-run writes nothing"

install_test_case_start "install writes assistant rules reference only"
home="$(install_test_new_home base-install)"
log="$(install_test_log_path base-install)"
install_test_run "$home" "$log" --target all
install_test_assert_file_exists "$home/.claude/CLAUDE.md"
install_test_assert_file_exists "$home/.claude/rules/code-changes.md"
install_test_assert_file_exists "$home/.claude/reference/测试规范.md"
install_test_assert_file_exists "$home/.codex/AGENTS.md"
install_test_assert_file_exists "$home/.codex/rules/completion-claims.md"
install_test_assert_path_absent "$home/.claude/skills" "no claude skills"
install_test_assert_path_absent "$home/.agents" "no codex user skills"
install_test_assert_path_absent "$home/.claude/hooks" "no claude hooks"
install_test_assert_path_absent "$home/.org-skills-state" "legacy state unused"
manifest="$(install_test_state_root "$home")/base-config/claude/installed.json"
python3 - "$manifest" "$home/.claude/CLAUDE.md" <<'PY'
import json, sys
from pathlib import Path
manifest = json.loads(Path(sys.argv[1]).read_text())
assert manifest["schema_version"] == 1
assert manifest["repo_id"] == "base-config"
assert manifest["target"] == "claude"
assert manifest["requires"] == []
ids = {r["resource_id"] for r in manifest["resources"]}
assert "assistant" in ids
assert "rules/code-changes.md" in ids
assert all(r["tree_sha256"] for r in manifest["resources"])
assert all(r["files"] for r in manifest["resources"])
PY
install_test_case_pass "install writes assistant rules reference only"

install_test_case_start "unowned destination is conflict"
home="$(install_test_new_home base-conflict)"
mkdir -p "$home/.claude"
printf 'foreign\n' > "$home/.claude/CLAUDE.md"
log="$(install_test_log_path base-conflict)"
set +e
install_test_run_allow_failure "$home" "$log" --target claude
rc=$?
set -e
install_test_assert_failure "$rc" "conflict should fail"
install_test_assert_file_contains "$log" "conflict" "conflict message"
install_test_assert_file_contains "$home/.claude/CLAUDE.md" "foreign" "left untouched"
install_test_case_pass "unowned destination is conflict"

install_test_case_start "drift stops upgrade and uninstall"
home="$(install_test_new_home base-drift)"
install_test_run "$home" "$(install_test_log_path base-drift-install)" --target claude
printf '\nmutated\n' >> "$home/.claude/rules/code-changes.md"
set +e
install_test_run_allow_failure "$home" "$(install_test_log_path base-drift-upgrade)" --target claude
up_rc=$?
install_test_run_allow_failure "$home" "$(install_test_log_path base-drift-uninstall)" --target claude --uninstall
un_rc=$?
set -e
install_test_assert_failure "$up_rc" "drift upgrade"
install_test_assert_failure "$un_rc" "drift uninstall"
install_test_assert_file_exists "$home/.claude/rules/code-changes.md"
install_test_case_pass "drift stops upgrade and uninstall"

install_test_case_start "upgrade removes stale owned file"
home="$(install_test_new_home base-stale)"
install_test_run "$home" "$(install_test_log_path base-stale-1)" --target claude
# Plant a file that is recorded in the current manifest, then shrink the desired
# set so the next install must delete it. Do this by appending a fake owned file
# to installed.json and to disk, then running a helper that upgrades from the
# real desired 15-file plan.
stale="$home/.claude/rules/retired-extra.md"
printf 'stale\n' > "$stale"
python3 - "$home/.local/state/skill-repos/base-config/claude/installed.json" "$stale" <<'PY'
import hashlib, json, sys
from pathlib import Path
manifest_path = Path(sys.argv[1])
stale = Path(sys.argv[2])
manifest = json.loads(manifest_path.read_text())
digest = hashlib.sha256(stale.read_bytes()).hexdigest()
manifest["resources"].append({
    "resource_id": "rules/retired-extra.md",
    "resource_root": str(stale),
    "kind": "file",
    "tree_sha256": digest,
    "files": [{"path": "retired-extra.md", "kind": "file", "mode": "0644", "sha256": digest, "link_target": None}],
})
manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
PY
install_test_run "$home" "$(install_test_log_path base-stale-upgrade)" --target claude
install_test_assert_path_absent "$stale" "stale owned file removed on upgrade"
install_test_assert_file_exists "$home/.claude/rules/code-changes.md"
install_test_case_pass "upgrade removes stale owned file"

install_test_case_start "clean uninstall removes owned files"
home="$(install_test_new_home base-un)"
install_test_run "$home" "$(install_test_log_path base-un-1)" --target claude
install_test_run "$home" "$(install_test_log_path base-un-2)" --target claude --uninstall
install_test_assert_path_absent "$home/.claude/CLAUDE.md" "assistant removed"
install_test_assert_path_absent "$home/.claude/rules/code-changes.md" "rule removed"
install_test_assert_path_absent "$home/.local/state/skill-repos/base-config/claude/installed.json" "manifest removed"
install_test_case_pass "clean uninstall removes owned files"

install_test_case_start "target-all reports visible partial success"
home="$(install_test_new_home base-partial)"
mkdir -p "$home/.codex"
printf 'foreign\n' > "$home/.codex/AGENTS.md"
set +e
install_test_run_allow_failure "$home" "$(install_test_log_path base-partial)" --target all
rc=$?
set -e
install_test_assert_failure "$rc" "all-target must not claim success"
install_test_assert_file_exists "$home/.claude/CLAUDE.md"
install_test_assert_file_contains "$home/.codex/AGENTS.md" "foreign" "codex left untouched"
install_test_assert_file_contains "$(install_test_log_path base-partial)" "claude" "completed target named"
install_test_case_pass "target-all reports visible partial success"

install_test_case_start "reverse-dep blocks Base uninstall while Team is installed"
home="$(install_test_new_home base-revdep)"
install_test_run "$home" "$(install_test_log_path base-revdep-install)" --target claude
state="$(install_test_state_root "$home")"
mkdir -p "$state/team-skills/claude"
python3 - "$state/team-skills/claude/installed.json" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({
  "schema_version": 1,
  "repo_id": "team-skills",
  "repo_version": "0.0.0-test",
  "target": "claude",
  "requires": [{"repo_id": "base-config", "target": "same", "resource_ids": ["assistant"]}],
  "resources": [],
  "structured_entries": []
}), encoding="utf-8")
PY
set +e
install_test_run_allow_failure "$home" "$(install_test_log_path base-revdep-un)" --target claude --uninstall
rc=$?
set -e
install_test_assert_failure "$rc" "base uninstall blocked by team"
install_test_assert_file_contains "$(install_test_log_path base-revdep-un)" "team-skills" "names dependent"
install_test_assert_file_exists "$home/.claude/CLAUDE.md"
install_test_case_pass "reverse-dep blocks Base uninstall while Team is installed"
```

`tests/lib/install-test-env.sh` must set `HOME` and `SKILL_REPO_STATE_ROOT="$home/.local/state/skill-repos"` and must not set `ORG_STATE_ROOT`.

- [ ] **Step 2: Run to verify it fails**

```bash
bash /Users/lijieli/base-config/tests/test-install-lifecycle.sh
```

Expected: FAIL because `install.sh` is missing.

- [ ] **Step 3: Implement installer**

`install.sh` is a thin wrapper:

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$ROOT/tools/install/repo_install.py" "$@"
```

`repo_install.py` must:

1. Parse `--target`, `--dry-run`, `--uninstall`.
2. Acquire `<state-root>/.lock`.
3. For each selected target, render the 15-file plan into a bounded temp dir (`tempfile.mkdtemp(prefix="base-config-stage-")`).
4. Validate destinations and requires before the first mutation. Base requires is `[]`. Reverse-dep scan reads every `<state-root>/*/<target>/installed.json` and stops uninstall **or an upgrade that would drop a required `resource_id`** if any `requires.repo_id == base-config`. The error names `team-skills`.
5. On install: copy staged files; write `installed.json` atomically.
6. On upgrade: compare current bytes to manifest digests; fail on drift; reconcile desired file set.
7. On uninstall: delete only digest-matching files and matching structured entries; remove manifest; do not restore baselines.
8. Clean staging and any `.in-progress.json` after success.
9. Fail closed with: resource id, expected/actual digest, owner, completed targets, safe next step.
10. `--target all`: validate both, apply sequentially, report partial success if the second target hits an external concurrent change.

Do not read or write `~/.org-skills-state`. Do not copy `tools/community`. Do not install Skills.

- [ ] **Step 4: Run lifecycle tests**

```bash
bash /Users/lijieli/base-config/tests/test-install-lifecycle.sh
```

Expected: PASS all cases.

- [ ] **Step 5: Commit in Base**

```bash
git -C /Users/lijieli/base-config add install.sh tools/install/repo_install.py tests
git -C /Users/lijieli/base-config commit -m "feat: install Base assistant rules and references"
```

---

### Task 6: Move Base-owned rule-runtime evaluators

**Files:**
- Copy and rewrite into Base:
  - `tools/eval/contracts/rule-runtime-eval.json`
  - `tools/eval/scripts/run_rule_runtime_eval.py`
  - `tools/eval/scenarios/assistant-entry/`
  - `tools/eval/scenarios/sql-schema-comments/`
  - inbound-referenced `tools/eval/results/` paths whose only owner is the rule-runtime evaluator
  - `tests/test-rule-runtime-eval-contracts.py`
  - `tests/test-rule-runtime-eval-contracts.sh`
- Keep originals in the monolith until Plan 4. Plan 4 must not prune a result path that was moved to Base until the Base copy exists.

**Interfaces:**
- Consumes: Base payload paths `assistant.md`, `rules/`, `reference/`.
- Produces: Base evaluator whose `runtime_sources` no longer mention `shared/`.

- [ ] **Step 1: Write a failing Base contract test**

In Base `tests/test-rule-runtime-eval-contracts.py`, assert every `runtime_sources` entry exists at Base repo root (`assistant.md`, `rules/*.md`, `reference/*.md`) and that the list contains no `shared/` prefix. Copy the current contract test's structural assertions, replacing path prefixes.

- [ ] **Step 2: Run to verify it fails**

```bash
PYTHONPATH=/Users/lijieli/base-config python3 /Users/lijieli/base-config/tests/test-rule-runtime-eval-contracts.py
```

Expected: FAIL missing contract file.

- [ ] **Step 3: Copy evaluator files and rewrite paths**

Replace `shared/assistant.md` → `assistant.md`, `shared/rules/` → `rules/`, `shared/reference/` → `reference/`. Copy only `tools/eval/results/` files that the Base evaluator tests/contracts inbound-reference. Do not copy standard-chain eval contracts, `docs/rule-runtime--team-readiness/`, or Team skill evals. Team consumption tests stay in the monolith.

- [ ] **Step 4: Run Base contract tests**

```bash
bash /Users/lijieli/base-config/tests/test-rule-runtime-eval-contracts.sh
```

Expected: PASS.

- [ ] **Step 5: Commit in Base**

```bash
git -C /Users/lijieli/base-config add tools/eval tests/test-rule-runtime-eval-contracts.py tests/test-rule-runtime-eval-contracts.sh
git -C /Users/lijieli/base-config commit -m "feat: move Base rule-runtime evaluator"
```

---

### Task 7: Base gate, remote, and push

**Files:**
- Create: `/Users/lijieli/base-config/tests/run-all.sh`
- Create: `/Users/lijieli/base-config/.github/workflows/test.yml`

**Interfaces:**
- Consumes: confirmed `base-config` remote.
- Produces: pushed Base commit that Plan 4 may treat as extraction evidence.

- [ ] **Step 1: Add `tests/run-all.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
python3 tests/test-tree-digest.py
python3 tests/test-rule-runtime-eval-contracts.py
bash tests/test-rule-runtime-eval-contracts.sh
bash tests/test-install-lifecycle.sh
echo "[PASS] base-config gates"
```

CI workflow: checkout, Python 3.11, run `bash tests/run-all.sh`.

- [ ] **Step 2: Run the Base gate**

```bash
bash /Users/lijieli/base-config/tests/run-all.sh
```

Expected: PASS. Then run monolith `PYTHONPATH="$PWD" python3 tests/test-ownership-inventory.py` and `bash tests/run-all.sh --quick`. Quick stays at 36 steps and green. This plan must not break Team tests that still see the monolith payload.

- [ ] **Step 3: Add remote and push**

```bash
git -C /Users/lijieli/base-config remote add origin "$(python3 -c 'import yaml,pathlib; print(yaml.safe_load(pathlib.Path("docs/superpowers/specs/2026-08-31--repository-split-and-clean-runtime-migration--remotes.yaml").read_text())["repos"]["base-config"])')"
# run from monolith so the remotes file resolves, or pass the URL explicitly
git -C /Users/lijieli/base-config push -u origin HEAD:main
git -C /Users/lijieli/base-config tag -a base-config-cutover-start -m "Base snapshot from pre-split-2026-08-31"
git -C /Users/lijieli/base-config push origin base-config-cutover-start
```

If the GitHub repo does not exist, create it as private (`gh repo create ... --private --source=/Users/lijieli/base-config --remote=origin --push`) only using the confirmed URL. Stop if the confirmed remote is missing.

- [ ] **Step 4: Prove push with ls-remote, not a local-only commit**

```bash
git -C /Users/lijieli/base-config ls-remote origin HEAD
```

Expected: remote SHA equals local HEAD.

---

## Plan 1 acceptance

Pass only with current evidence of:

1. `scan_ownership` on the monolith is complete, including DELETE/PRUNE/OUT_OF_SCOPE atoms and `qa`→`webapp-testing` optional; Grill/Obsidian are the only allowed `MISSING_FROM_GIT` Daily names.
2. `pre-split-2026-08-31` exists on `origin` (Task 2; blocked until remotes confirmed).
3. Base payload bytes match tagged `shared/assistant.md|rules|reference`.
4. Base install, upgrade-stale-file, drift, uninstall, reverse-dep, and `--target all` partial-success tests pass in isolated `HOME`.
5. Base contains no Skills/hooks/agents/protocols.
6. Base uninstall is blocked by a Team reverse-dep manifest.
7. Base remote HEAD is pushed (Task 7; blocked until remotes confirmed).
8. Monolith `bash tests/run-all.sh --quick` still passes at 36 steps. Inventory is a full-tier proving command, not a quick step.
9. Local Claude/Codex/org-skills-state were not mutated.

## Handoff

- Plan 2/3 vendor copy may start after Task 1 inventory is green **and** Task 2 tag is pushed.
- Plan 2/3 installer tasks copy `tree_digest.py` **after Task 4**. They must not import `/Users/lijieli/base-config`.
- Plan 4 must not delete `shared/assistant.md`, `shared/rules/`, or `shared/reference/` until this Base remote SHA is recorded.
- Do not start Plan 5.
