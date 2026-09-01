# tests/test-split-destination-proof.py
from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REMOTES = ROOT / "docs/superpowers/specs/2026-08-31--repository-split-and-clean-runtime-migration--remotes.yaml"
SIBLING_ROOT = Path("/Users/lijieli")


def git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)
    return proc.stdout.strip()


def sibling_checkouts_available() -> bool:
    data = yaml.safe_load(REMOTES.read_text())
    for repo_id in data["repos"]:
        if repo_id == "team-skills":
            continue
        if not (SIBLING_ROOT / repo_id / ".git").exists():
            return False
    return True


def assert_destinations_pushed() -> None:
    """Fail closed unless remotes.yaml is confirmed and Base/Daily/Personal HEAD match origin."""
    data = yaml.safe_load(REMOTES.read_text())
    if not data.get("confirmed"):
        raise AssertionError("remotes.yaml confirmed is not true; stop Plan 4 contraction")
    if not sibling_checkouts_available():
        if os.environ.get("GITHUB_ACTIONS") == "true":
            raise unittest.SkipTest(
                "live sibling destination proof is host-local; Team CI vendors the Base fixture instead"
            )
        raise AssertionError("missing local sibling checkout for destination proof")
    for repo_id, _url in data["repos"].items():
        if repo_id == "team-skills":
            continue
        local = SIBLING_ROOT / repo_id
        if not (local / ".git").exists():
            raise AssertionError(f"missing local checkout for {repo_id}: {local}")
        remote = git(local, "ls-remote", "origin", "HEAD").split()[0]
        head = git(local, "rev-parse", "HEAD")
        if remote != head:
            raise AssertionError(f"{repo_id}: origin HEAD {remote} != local HEAD {head}")


class RemotesYamlTests(unittest.TestCase):
    def test_team_remote_is_org_skills(self) -> None:
        data = yaml.safe_load(REMOTES.read_text())
        self.assertEqual(
            data["repos"]["team-skills"],
            "https://github.com/jieli-cqwl/org-skills.git",
        )


class DestinationProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not sibling_checkouts_available() and os.environ.get("GITHUB_ACTIONS") == "true":
            raise unittest.SkipTest(
                "live sibling destination proof is host-local; Team CI vendors the Base fixture instead"
            )

    def test_remotes_confirmed_and_pushed(self) -> None:
        assert_destinations_pushed()

    def test_base_payload_still_in_base(self) -> None:
        assert_destinations_pushed()
        base = Path("/Users/lijieli/base-config")
        self.assertTrue((base / "assistant.md").is_file())
        self.assertTrue((base / "rules" / "code-changes.md").is_file())

    def test_daily_has_42_and_personal_has_14(self) -> None:
        assert_destinations_pushed()
        daily = {p.parent.name for p in Path("/Users/lijieli/daily-skills").glob("**/SKILL.md")}
        personal = {p.parent.name for p in Path("/Users/lijieli/personal-skills").glob("**/SKILL.md")}
        self.assertEqual(len(daily), 42)
        self.assertEqual(len(personal), 14)
        self.assertIn("skill-pull", daily)
        self.assertIn("darwin-skill", personal)
        self.assertNotIn("skill-pull", personal)


if __name__ == "__main__":
    unittest.main()
