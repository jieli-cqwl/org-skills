# tests/test-team-inventory.py
from __future__ import annotations

import json
import sys
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


def consume_phase_arg(argv: list[str]) -> str:
    if "--phase" not in argv:
        return "surface"
    idx = argv.index("--phase")
    if idx + 1 >= len(argv):
        raise SystemExit("tests/test-team-inventory.py: --phase requires surface or tree")
    phase = argv[idx + 1]
    if phase not in {"surface", "tree"}:
        raise SystemExit(f"tests/test-team-inventory.py: unknown --phase {phase}")
    del argv[idx : idx + 2]
    return phase


PHASE = consume_phase_arg(sys.argv)


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

    @unittest.skipUnless(
        PHASE == "tree",
        "gated until Task 4 payload deletion; community/assistant still present",
    )
    def test_contracted_tree(self) -> None:
        roots = first_party_skill_roots()
        self.assertEqual(roots, TEAM)
        self.assertFalse((ROOT / "shared/skills/skill-pull").exists())
        self.assertFalse((ROOT / "community").exists())
        self.assertFalse((ROOT / "shared/assistant.md").exists())
        self.assertFalse((ROOT / "shared/rules").exists())
        self.assertFalse((ROOT / "shared/reference").exists())


if __name__ == "__main__":
    unittest.main()
