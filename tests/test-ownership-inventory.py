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
