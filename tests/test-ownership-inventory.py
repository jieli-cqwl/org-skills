from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        self.assertIn("progress.md", inventory.delete_from_active_head)
        self.assertIn("task_plan.md", inventory.delete_from_active_head)
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

    def test_short_name_cross_repo_callee_is_not_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skill = root / "shared" / "skills" / "fix" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: fix\n---\nCall `prd` before writing.\n",
                encoding="utf-8",
            )
            inventory = scan_ownership(root)
            recorded = (
                ("fix", "prd") in inventory.hard_edges
                or ("fix", "prd") in inventory.non_hard_edges
                or any("prd" in item for item in inventory.unclassified_edges)
                or any("prd" in item for item in inventory.unmapped)
            )
            self.assertTrue(recorded, "short-name callee prd must be recorded")
            with self.assertRaises(OwnershipError) as ctx:
                assert_complete(inventory)
            self.assertIn("prd", str(ctx.exception).lower())

    def test_git_ls_files_failure_does_not_look_like_empty_tree(self) -> None:
        failed = subprocess.CompletedProcess(
            args=["git", "ls-files"],
            returncode=128,
            stdout=b"",
            stderr=b"fatal: not a git repository",
        )
        with mock.patch(
            "tools.split.generate_ownership_inventory.subprocess.run",
            return_value=failed,
        ):
            with self.assertRaises(OwnershipError) as ctx:
                scan_ownership(ROOT)
        self.assertIn("git ls-files", str(ctx.exception).lower())

    def test_ledger_inbound_ref_in_tools_or_docs_is_classified(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "findings.md").write_text("stale ledger\n", encoding="utf-8")
            docs = root / "docs" / "usage.md"
            docs.parent.mkdir(parents=True)
            docs.write_text("Read findings.md before changing inventory.\n", encoding="utf-8")
            inventory = scan_ownership(root)
            self.assertNotIn("findings.md", inventory.delete_from_active_head)
            self.assertIn("findings.md", inventory.keep_for_inbound_ref)


if __name__ == "__main__":
    unittest.main()

