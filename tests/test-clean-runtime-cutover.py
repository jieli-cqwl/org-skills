# tests/test-clean-runtime-cutover.py
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURE_HOME = ROOT / "tests/fixtures/runtime-cutover/preflight-home"

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

    def test_explained_drift_keeps_preserve_and_explicit_delete(self) -> None:
        home = self._home()
        learned = home / ".claude/skills/learned/x.md"
        rejected = home / ".claude/skills/resume-tailor/SKILL.md"
        plan = build_action_plan(
            home,
            pre_split_tag="pre-split-2026-08-31",
            expected_bytes={str(learned): b"other\n", str(rejected): b"old\n"},
        )
        by_path = {a.path: a.cls for a in plan.actions}
        self.assertEqual(by_path[str(home / ".claude/skills/learned")], ActionClass.PRESERVE_EXTERNAL)
        self.assertEqual(by_path[str(home / ".claude/skills/resume-tailor")], ActionClass.REMOVE_EXPLICIT_DELETE)
        self.assertFalse(any(a.cls == ActionClass.CONFLICT and "learned" in a.path for a in plan.actions))
        self.assertFalse(any(a.cls == ActionClass.CONFLICT and "resume-tailor" in a.path for a in plan.actions))

    def test_fixture_preflight_home_preserve_hooks_and_decoy_state(self) -> None:
        home = FIXTURE_HOME
        plan = build_action_plan(home, pre_split_tag="pre-split-2026-08-31")
        by_path = {a.path: a.cls for a in plan.actions}
        self.assertEqual(
            by_path[str(home / ".org-skills-state/external-runtime-skills/codex.txt")],
            ActionClass.DELETE_LEGACY_STATE,
        )
        for name in (
            "superset_notify.sh",
            "read_pages_context.py",
            "worktree_create.sh",
            "worktree_remove.sh",
        ):
            self.assertEqual(
                by_path[str(home / ".claude/hooks" / name)],
                ActionClass.PRESERVE_EXTERNAL,
            )

    def test_codex_hook_tree_non_preserve_is_remove_old_only(self) -> None:
        home = self._home()
        hook = home / ".codex/hooks/team_hook.sh"
        hook.parent.mkdir(parents=True)
        hook.write_text("team\n", encoding="utf-8")
        plan = build_action_plan(home, pre_split_tag="pre-split-2026-08-31")
        by_path = {a.path: a.cls for a in plan.actions}
        self.assertEqual(by_path[str(hook)], ActionClass.REMOVE_OLD_ONLY)

    def test_team_shared_skills_trees_are_remove_old_only(self) -> None:
        home = self._home()
        for rel in (".claude/shared/skills/lib", ".codex/shared/skills/lib"):
            lib = home / rel
            lib.mkdir(parents=True)
            (lib / "note.md").write_text("team-lib\n", encoding="utf-8")
        plan = build_action_plan(home, pre_split_tag="pre-split-2026-08-31")
        by_path = {a.path: a.cls for a in plan.actions}
        self.assertEqual(by_path[str(home / ".claude/shared/skills")], ActionClass.REMOVE_OLD_ONLY)
        self.assertEqual(by_path[str(home / ".codex/shared/skills")], ActionClass.REMOVE_OLD_ONLY)
        self.assertNotIn(str(home / ".claude/skills/lib"), by_path)
        self.assertNotIn(str(home / ".codex/skills/lib"), by_path)


if __name__ == "__main__":
    unittest.main()
