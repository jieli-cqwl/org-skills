# tests/test-team-inventory.py
from __future__ import annotations

import importlib.util
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


def _load_assert_destinations_pushed():
    path = ROOT / "tests" / "test-split-destination-proof.py"
    spec = importlib.util.spec_from_file_location("test_split_destination_proof", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.assert_destinations_pushed


assert_destinations_pushed = _load_assert_destinations_pushed()


def first_party_skill_roots() -> set[str]:
    return {p.parent.name for p in (ROOT / "shared/skills").glob("*/SKILL.md")}


class TeamInventoryTests(unittest.TestCase):
    def test_first_party_skill_roots(self) -> None:
        roots = first_party_skill_roots()
        self.assertEqual(TEAM - roots, set())
        for name in sorted(NON_INSTALLABLE):
            self.assertTrue((ROOT / "shared/skills" / name).is_dir())
        self.assertFalse((ROOT / "shared/skills/lib/SKILL.md").exists())

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

    def test_contracted_tree(self) -> None:
        assert_destinations_pushed()
        roots = first_party_skill_roots()
        self.assertEqual(roots, TEAM)
        self.assertFalse((ROOT / "shared/skills/skill-pull").exists())
        self.assertFalse((ROOT / "community").exists())
        self.assertFalse((ROOT / "shared/assistant.md").exists())
        self.assertFalse((ROOT / "shared/rules").exists())
        self.assertFalse((ROOT / "shared/reference").exists())
        self.assertTrue((ROOT / "shared/skills/lib").is_dir())
        self.assertTrue((ROOT / "shared/skills/qft-branch-flow-workspace").is_dir())

    def test_active_docs_do_not_point_at_moved_shared_payload(self) -> None:
        assert_destinations_pushed()
        agents = (ROOT / "AGENTS.md").read_text()
        self.assertNotIn("shared/assistant.md", agents)
        self.assertNotIn("shared/rules/*.md", agents)
        self.assertNotIn("community/superpowers/skills", agents)
        self.assertIn("team-skills", agents)


if __name__ == "__main__":
    unittest.main()
