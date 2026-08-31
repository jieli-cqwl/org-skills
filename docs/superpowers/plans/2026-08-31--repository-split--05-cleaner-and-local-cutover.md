# Repository Split Plan 5: Cleaner And Local Cutover

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove a one-time cleaner against fixtures, run isolated Base+Daily E2E, then on this machine remove the old org-managed installation, fresh-install Base and Daily, and delete `~/.org-skills-state`.

**Architecture:** The cleaner is not a fifth installer. It lives in Team at `tools/migration/clean_runtime_cutover.py`, takes explicit Base and Daily checkout paths, never calls legacy `install.sh --uninstall`, and never adopts old files into new manifests. Removal plus fresh install is the clean-state proof. Git is the only recovery source.

**Tech Stack:** Python cleaner, captured runtime fixtures, isolated HOME E2E, then a reviewed dry-run against the real machine.

**Spec:** `docs/superpowers/specs/2026-08-31--repository-split-and-clean-runtime-migration--design.md`

**Depends on:** Plan 4 `team-skills-cutover` pushed; Plan 1 Base and Plan 2 Daily cutover-start tags pushed. Plan 3 Personal exists but is not installed.

**Forbidden:** Runtime mutation before all four remotes have pushed cutover commits. Calling legacy uninstall. Persistent content backup. Installing Team or Personal on this machine. Restoring `claude-settings-baseline.json` or `codex-hooks-baseline.json`. Trusting `external-runtime-skills/*.txt` as the preserve list.

## Global Constraints

- Cleaner CLI: `python3 tools/migration/clean_runtime_cutover.py --base <path> --daily <path> --phase remove|verify|retire-legacy-state [--target claude|codex|all] [--dry-run] [--apply]`
- The cleaner never installs Base or Daily. Installers are always explicit subprocesses of the E2E/cutover operator, not `--phase` of the cleaner.
- `--apply` requires `--dry-run` output from the same preflight hash, or a `--accept-plan <plan.json>` pointing at that hash.
- Python tests that import `tools.migration` must `sys.path.insert(0, str(ROOT))` or run with `PYTHONPATH="$ROOT"`. Plan 5 E2E sources the **Team** helper `tests/lib/install-test-env.sh` and uses `install_test_new_home` / `install_test_assert_*` only — not Base's `install_test_run`.
- Action classes: `REMOVE_FOR_FRESH_INSTALL`, `REMOVE_OLD_ONLY`, `REMOVE_EXPLICIT_DELETE`, `PRESERVE_EXTERNAL`, `DELETE_LEGACY_STATE`, `CONFLICT`.
- Unexplained drift is `CONFLICT` and stops before mutation.
- Dirty installed fingerprint `1.2.4-20dbfa45-dirty-f57e224e` is not an exception.
- `features.multi_agent` is the Codex TOML identity. `features.hooks` stays `true` if any preserved external hook remains.
- Grill and Obsidian currently installed trees are `REMOVE_FOR_FRESH_INSTALL` after source/digest checks.
- Legacy state root `~/.org-skills-state` is deleted only after final verification, including `archive/dot-claude-git.tar.gz`.
- New state root is `skill-repos`. No content copies in manifests.
- Partial success is never reported as success.
- Tests must not grep Skill Markdown prose.

## File Structure

Create in Team (this repo):

```text
tools/migration/clean_runtime_cutover.py
tools/migration/action_plan.py
tools/migration/legacy_inventory.py
tests/fixtures/runtime-cutover/
tests/test-clean-runtime-cutover.py
tests/test-clean-runtime-cutover-e2e.sh
```

Do not add a permanent compositor, Profile, or fifth repo.

## Frozen identities

Rejected / stale / retired runtime names to classify `REMOVE_EXPLICIT_DELETE`:

```text
architecture-blueprint-generator
job-description-analyzer
resume-ats-optimizer
resume-bullet-writer
resume-tailor
tailored-resume-generator
tech-resume-optimizer
qft-branch-management
review-fix-loop
codex-doc-review
_retired-qft-chat-analysis-user-copy
qft-chat-analysis
qft-chat-analysis-workspace
```

Preserve-external minimum set:

```text
~/.claude/skills/learned/
~/.claude/skills/superset/
~/.agents/skills/superset-*
~/.claude/hooks/superset_notify.sh
~/.claude/hooks/read_pages_context.py
~/.claude/hooks/worktree_create.sh
~/.claude/hooks/worktree_remove.sh
```

Plus the matching Claude settings.json and Codex `hooks.json` entries, including `SUPERSET_HOME_DIR` notify commands.

Five team Codex `[agents.*]` sections to remove when managed fields match the pre-split installer output, frozen from `shared/agents/codex/*.toml` at `pre-split-2026-08-31`:

```text
agents.consistency-auditor
agents.developer
agents.fixer
agents.qa
agents.verifier
```

---

### Task 1: Action-plan model and fixture preflight

**Files:**
- Create: `tools/migration/action_plan.py`
- Create: `tools/migration/legacy_inventory.py`
- Create: `tests/fixtures/runtime-cutover/preflight-home/`
- Test: `tests/test-clean-runtime-cutover.py`

**Interfaces:**
- Consumes: a fake HOME with legacy manifests, preserved plugin files, drift files, and unknown state files.
- Produces: `build_action_plan(home: Path, legacy_tag_root: Path) -> ActionPlan` with one action per path.

- [ ] **Step 1: Write failing classification tests**

```python
# tests/test-clean-runtime-cutover.py
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.migration.action_plan import ActionClass, build_action_plan


class ActionPlanTests(unittest.TestCase):
    def _home(self) -> Path:
        td = Path(tempfile.mkdtemp(prefix="cutover-"))
        claude = td / ".claude"
        (claude / "skills" / "product-director").mkdir(parents=True)
        (claude / "skills" / "product-director" / "SKILL.md").write_text("team\n", encoding="utf-8")
        (claude / "skills" / "learned").mkdir()
        (claude / "skills" / "learned" / "x.md").write_text("keep\n", encoding="utf-8")
        (claude / "skills" / "superset").mkdir()
        (claude / "skills" / "superset" / "SKILL.md").write_text("plugin\n", encoding="utf-8")
        (claude / "hooks").mkdir()
        (claude / "hooks" / "superset_notify.sh").write_text("notify\n", encoding="utf-8")
        (claude / "skills" / "resume-tailor").mkdir()
        (claude / "skills" / "resume-tailor" / "SKILL.md").write_text("gone\n", encoding="utf-8")
        state = td / ".org-skills-state"
        (state / "claude").mkdir(parents=True)
        (state / "claude" / "installed-manifest").write_text(
            str(claude / "skills" / "product-director") + "\n", encoding="utf-8"
        )
        (state / "archive").mkdir()
        (state / "archive" / "dot-claude-git.tar.gz").write_bytes(b"backup")
        (state / "mystery.txt").write_text("unknown\n", encoding="utf-8")
        return td

    def test_classifies_preserve_remove_and_legacy_state(self) -> None:
        home = self._home()
        plan = build_action_plan(home, pre_split_tag="pre-split-2026-08-31")
        by_path = {a.path: a.cls for a in plan.actions}
        self.assertEqual(by_path[str(home / ".claude/skills/learned")], ActionClass.PRESERVE_EXTERNAL)
        self.assertEqual(by_path[str(home / ".claude/skills/superset")], ActionClass.PRESERVE_EXTERNAL)
        self.assertEqual(by_path[str(home / ".claude/hooks/superset_notify.sh")], ActionClass.PRESERVE_EXTERNAL)
        self.assertEqual(by_path[str(home / ".claude/skills/product-director")], ActionClass.REMOVE_OLD_ONLY)
        self.assertEqual(by_path[str(home / ".claude/skills/resume-tailor")], ActionClass.REMOVE_EXPLICIT_DELETE)
        self.assertEqual(by_path[str(home / ".org-skills-state/archive/dot-claude-git.tar.gz")], ActionClass.DELETE_LEGACY_STATE)
        self.assertEqual(plan.status, "blocked")
        self.assertTrue(any(a.cls == ActionClass.CONFLICT for a in plan.actions))

    def test_unexplained_drift_is_conflict(self) -> None:
        home = self._home()
        skill = home / ".claude/skills/product-director/SKILL.md"
        skill.write_text("mutated locally\n", encoding="utf-8")
        plan = build_action_plan(home, pre_split_tag="pre-split-2026-08-31", expected_bytes={str(skill): b"team\n"})
        self.assertTrue(any(a.cls == ActionClass.CONFLICT and "product-director" in a.path for a in plan.actions))

    def test_unknown_legacy_state_blocks(self) -> None:
        home = self._home()
        plan = build_action_plan(home, pre_split_tag="pre-split-2026-08-31")
        mystery = str(home / ".org-skills-state/mystery.txt")
        self.assertTrue(any(a.path == mystery and a.cls == ActionClass.CONFLICT for a in plan.actions))
```

- [ ] **Step 2: Run to verify fail**

```bash
python3 tests/test-clean-runtime-cutover.py
```

Expected: FAIL missing module.

- [ ] **Step 3: Implement classification**

`ActionPlan` fields: `actions`, `status` (`ready|blocked`), `preflight_hash`, `preserve_digests`. Known `~/.org-skills-state` children (manifests, baselines, backups, `archive/dot-claude-retirement-*`, `external-runtime-skills`) are `DELETE_LEGACY_STATE`. Any other file there is `CONFLICT`. Legacy path manifests are ownership clues, not content proof: compare current digest to the pre-split expected tree. Dirty fingerprint requires every diff to be overlay, approved deletion, or preserved external.

Do not read `external-runtime-skills/*.txt` as the preserve list. Hard-code the spec preserve set plus exact settings/hooks identities discovered from the fixture.

- [ ] **Step 4: Run tests**

```bash
python3 tests/test-clean-runtime-cutover.py
```

Expected: PASS classification cases. Mutation tests come in Task 2.

- [ ] **Step 5: Commit**

```bash
git add tools/migration tests/test-clean-runtime-cutover.py tests/fixtures/runtime-cutover
git commit -m "feat: classify runtime cutover actions fail-closed"
```

---

### Task 2: Removal, interruption/resume, and structured-config rules

**Files:**
- Create: `tools/migration/clean_runtime_cutover.py`
- Extend: `tests/test-clean-runtime-cutover.py`

**Interfaces:**
- Consumes: an `ActionPlan` with `status=ready`.
- Produces: `apply_action_plan(plan, journal_path)` that removes old resources, never restores baselines, resumes from journal metadata only.

- [ ] **Step 1: Write failing apply/resume tests**

Cases:

1. Apply `REMOVE_OLD_ONLY` on `product-director` deletes it; preserve `learned/` and `superset/` bytes unchanged.
2. Apply refuses `CONFLICT` plan; no path mutated.
3. Immediately before each mutation, re-hash; if changed since preflight, stop that action and leave failure visible.
4. Interrupt after first deletion: journal records completed actions. Rerun resumes remaining actions and does not restore deleted content from journal.
5. Codex fixture with five team `[agents.*]` sections whose managed fields match: those sections are removed. A user-added field in one section is drift and stops that section.
6. `features.multi_agent = true` is removed only when it matches old emitted value and no non-team agent section remains.
7. Preserved external hook remains and `features.hooks` stays true. Old `had_codex_hooks: false` snapshot is not applied.
8. Claude settings.json: remove only exact old-managed hook identities; preserve unrelated entries and order as far as the parser permits.
9. Grill/Obsidian destinations are `REMOVE_FOR_FRESH_INSTALL` even if bytes match future Daily content. After apply they are absent, so Daily install writes fresh.
10. Cleaner does not write `installed.json` for Base/Daily; that is the installer.
11. Cleaner never calls `install.sh --uninstall`.
12. Journal and staging live under a temp dir; they are not content backups.

- [ ] **Step 2: Run to verify fail**

```bash
python3 tests/test-clean-runtime-cutover.py
```

Expected: FAIL missing `apply_action_plan`.

- [ ] **Step 3: Implement apply/resume**

Journal schema: list of `{path, cls, pre_digest, status: pending|done|skipped|failed}`. No file bodies. Timeouts on all subprocesses. Bounded temp dirs cleaned on success. On failure, leave journal for diagnosis.

- [ ] **Step 4: Run tests**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/migration tests/test-clean-runtime-cutover.py
git commit -m "feat: apply cutover removals with journal resume"
```

---

### Task 3: Isolated Base+Daily end-to-end

**Files:**
- Test: `tests/test-clean-runtime-cutover-e2e.sh`

**Interfaces:**
- Consumes: pinned Base and Daily checkouts; cleaner; temp HOME.
- Produces: proof that after cleaner + Base install + Daily install, only Base+Daily org resources exist and plugins are preserved.

- [ ] **Step 1: Write failing E2E**

```bash
# tests/test-clean-runtime-cutover-e2e.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
. "$ROOT/tests/lib/install-test-env.sh"
install_test_init
home="$(install_test_new_home cutover-e2e)"
export HOME="$home"
export SKILL_REPO_STATE_ROOT="$home/.local/state/skill-repos"
export PYTHONPATH="$ROOT"

mkdir -p "$home/.claude/skills/product-director" "$home/.claude/skills/learned" "$home/.claude/skills/resume-tailor"
printf 'old-team\n' > "$home/.claude/skills/product-director/SKILL.md"
printf 'keep\n' > "$home/.claude/skills/learned/note.md"
printf 'reject\n' > "$home/.claude/skills/resume-tailor/SKILL.md"
mkdir -p "$home/.org-skills-state/archive" "$home/.org-skills-state/claude"
printf 'backup\n' > "$home/.org-skills-state/archive/dot-claude-git.tar.gz"
printf '%s\n' "$home/.claude/skills/product-director" > "$home/.org-skills-state/claude/installed-manifest"

python3 "$ROOT/tools/migration/clean_runtime_cutover.py" \
  --home "$home" --base /Users/lijieli/base-config --daily /Users/lijieli/daily-skills \
  --target all --phase remove --apply
install_test_assert_path_absent "$home/.claude/skills/product-director"
install_test_assert_path_absent "$home/.claude/skills/resume-tailor"
install_test_assert_file_exists "$home/.claude/skills/learned/note.md"
test -d "$home/.org-skills-state"

bash /Users/lijieli/base-config/install.sh --target all
bash /Users/lijieli/daily-skills/install.sh --target all

python3 "$ROOT/tools/migration/clean_runtime_cutover.py" \
  --home "$home" --base /Users/lijieli/base-config --daily /Users/lijieli/daily-skills \
  --target all --phase verify --apply
python3 "$ROOT/tools/migration/clean_runtime_cutover.py" \
  --home "$home" --phase retire-legacy-state --apply

install_test_assert_file_exists "$home/.claude/CLAUDE.md"
install_test_assert_file_exists "$home/.claude/rules/code-changes.md"
install_test_assert_file_exists "$home/.codex/AGENTS.md"
install_test_assert_file_exists "$home/.codex/rules/code-changes.md"
install_test_assert_file_exists "$home/.claude/skills/brainstorming/SKILL.md"
install_test_assert_file_exists "$home/.claude/skills/grilling/SKILL.md"
install_test_assert_file_exists "$home/.claude/skills/obsidian-markdown/SKILL.md"
install_test_assert_file_exists "$home/.agents/skills/skill-pull/SKILL.md"
install_test_assert_file_exists "$home/.agents/skills/grilling/SKILL.md"
install_test_assert_path_absent "$home/.claude/skills/product-director"
install_test_assert_path_absent "$home/.claude/skills/darwin-skill"
install_test_assert_path_absent "$home/.claude/hooks/post_compact.sh"
install_test_assert_path_absent "$home/.org-skills-state"
install_test_assert_file_exists "$home/.local/state/skill-repos/base-config/claude/installed.json"
install_test_assert_file_exists "$home/.local/state/skill-repos/daily-skills/codex/installed.json"
install_test_assert_path_absent "$home/.local/state/skill-repos/team-skills"
cmp -s "$home/.claude/skills/learned/note.md" <(printf 'keep\n')
```

This is the only allowed E2E control flow: `remove` → Base `install.sh` → Daily `install.sh` → `verify` → `retire-legacy-state`. `--apply` without `--phase` is forbidden. After `remove`, `~/.org-skills-state` still exists. After `retire-legacy-state`, it is absent. The cleaner does not invoke installers.

- [ ] **Step 2: Run to verify fail**

```bash
bash tests/test-clean-runtime-cutover-e2e.sh
```

Expected: FAIL until phased CLI exists.

- [ ] **Step 3: Implement the three cleaner phases only**

The E2E script, not the cleaner, runs Base/Daily `install.sh` with `HOME` and `SKILL_REPO_STATE_ROOT`. Cleaner subprocesses need timeouts on any git/fs walks. Never pass `ORG_STATE_ROOT`. On verify failure, do not delete legacy state; do not create a new backup.

- [ ] **Step 4: Run E2E twice (resume after kill in the middle of remove)**

Expected: PASS both.

- [ ] **Step 5: Commit**

```bash
git add tools/migration tests/test-clean-runtime-cutover-e2e.sh
git commit -m "test: isolated Base+Daily cutover"
```

---

### Task 4: Real-machine dry-run review gate

**Files:** none committed except the dry-run report if the user supplies `--output`.

**Interfaces:**
- Consumes: real `$HOME` Claude/Codex/org-skills-state.
- Produces: printed action plan. No mutation.

- [ ] **Step 1: Stop unless four remotes are pushed**

```bash
python3 tests/test-split-destination-proof.py
git ls-remote origin team-skills-cutover
git -C /Users/lijieli/base-config ls-remote origin HEAD
git -C /Users/lijieli/daily-skills ls-remote origin HEAD
git -C /Users/lijieli/personal-skills ls-remote origin HEAD
```

All four must resolve. Personal is not installed but must be pushed.

- [ ] **Step 2: Capture preflight digests of preserve-external paths on the real machine**

Record learned/superset/hooks hashes in the dry-run output. Do not write them under `~/.org-skills-state`.

- [ ] **Step 3: Dry-run**

```bash
python3 tools/migration/clean_runtime_cutover.py \
  --base /Users/lijieli/base-config \
  --daily /Users/lijieli/daily-skills \
  --target all \
  --dry-run
```

Expected: exit 0 with `status=ready` **or** exit non-zero with `CONFLICT` list. If conflicts exist, stop and give the user the exact paths. The cleaner does not decide to discard.

- [ ] **Step 4: Human review**

Paste the action summary: counts per class, every `CONFLICT`, every `REMOVE_EXPLICIT_DELETE`, every preserved plugin path. Do not apply in the same turn as the first dry-run unless the user already approved this plan's apply step and the dry-run is `ready` with zero conflicts.

- [ ] **Step 5: No commit unless cleaner bugfixes were needed.** If dry-run reveals a classifier bug, fix with a failing fixture first (Task 1/2), do not special-case this machine.

---

### Task 5: Real apply, fresh install, retire legacy state

**Files:** none in git besides any bugfix from Task 4.

**Interfaces:**
- Consumes: approved dry-run plan hash.
- Produces: this machine running Base+Daily only.

- [ ] **Step 1: Apply remove phase**

```bash
python3 tools/migration/clean_runtime_cutover.py \
  --base /Users/lijieli/base-config \
  --daily /Users/lijieli/daily-skills \
  --target all \
  --accept-plan <dry-run-hash> \
  --phase remove \
  --apply
```

Expected: old org-managed Team/Personal/rejected/stale resources gone. Plugins remain. Grill/Obsidian destinations empty.

- [ ] **Step 2: Fresh Base then Daily**

```bash
env SKILL_REPO_STATE_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/skill-repos" \
  bash /Users/lijieli/base-config/install.sh --target all
env SKILL_REPO_STATE_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/skill-repos" \
  bash /Users/lijieli/daily-skills/install.sh --target all
```

Expected: both succeed. Manifests exist only for `base-config` and `daily-skills`.

- [ ] **Step 3: Verify then retire legacy state**

```bash
python3 tools/migration/clean_runtime_cutover.py \
  --base /Users/lijieli/base-config \
  --daily /Users/lijieli/daily-skills \
  --target all \
  --phase verify \
  --apply
python3 tools/migration/clean_runtime_cutover.py --phase retire-legacy-state --apply
```

Verify must check, with current digests:

- Base assistant/rules/reference match Base source.
- All 42 Daily Skills including Grill/Obsidian match Daily rendered digests for both targets.
- Team Skills, Personal Skills, Claude-only review-fix Skills, hooks, agents, protocols, runtime catalogs absent.
- Rejected/stale names absent.
- Five team Codex agent sections absent.
- Surviving `features.multi_agent` / `features.hooks` have non-team evidence.
- Claude settings.json and Codex hooks.json/agent sections contain no command/path pointing at a removed org-managed file.
- Preserve-external digests match preflight.
- `~/.org-skills-state` absent after retire.
- No new backup/archive/report file unless `--output` was given.
- `git status --porcelain` is empty (or only the approved split paths) in `/Users/lijieli/base-config`, `/Users/lijieli/daily-skills`, `/Users/lijieli/personal-skills`, and this Team checkout at the pinned tags.

- [ ] **Step 4: Run owner gates**

```bash
bash /Users/lijieli/base-config/tests/run-all.sh
bash /Users/lijieli/daily-skills/tests/run-all.sh
bash /Users/lijieli/org-claude-skills/tests/run-all.sh --quick
```

Team quick gate must not reinstall Team onto this machine.

- [ ] **Step 5: Commit only if Team cleaner code changed after apply.** Cutover itself is an operation, not a git commit. Tag Team `runtime-cutover-2026-08-31` only if the user wants a marker; it is optional and not recovery evidence for payload.

---

## Plan 5 acceptance

Pass only with current, same-boundary evidence:

1. Isolated E2E passed, including interrupt/resume and plugin preservation.
2. Real dry-run was reviewed; conflicts were resolved by the user, not discarded by the cleaner.
3. Real apply removed old org-managed resources then fresh-installed Base+Daily.
4. New manifests exist only for `base-config` and `daily-skills`.
5. Team/Personal/rejected/stale/retired org resources are absent from Claude and Codex.
6. Preserve-external plugin files and hook entries keep preflight digests.
7. `~/.org-skills-state` does not exist.
8. No persistent migration backup or automatic report file.
9. Base and Daily gates pass; Team quick gate passes without installing Team locally.
10. Legacy `install.sh --uninstall` was never invoked.

## Failure policy

Stop on unmapped ownership, path collision, unexplained drift, missing hard dependency, malformed structured config, concurrent change, unavailable locked source, missing pushed recovery tag, or unexpected legacy state file. Errors name the resource, expected vs actual, owner, completed actions, and the exact safe next step. Reinstalling the pre-split tag is an explicit emergency choice, not automatic rollback.
