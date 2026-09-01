#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InstallScriptContractTests(unittest.TestCase):
    def test_wrapper_execs_team_repo_install(self) -> None:
        script = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn('exec python3 "$ROOT/tools/install/repo_install.py"', script)
        self.assertIn("PYTHONPATH", script)
        self.assertNotIn("community/", script)
        self.assertNotIn("shared/assistant.md", script)
        self.assertNotIn("community/SOURCES.yaml", script)

    def test_repo_install_is_team_only(self) -> None:
        source = (ROOT / "tools/install/repo_install.py").read_text(encoding="utf-8")
        self.assertIn('REPO_ID = "team-skills"', source)
        self.assertIn('BASE_REPO_ID = "base-config"', source)
        self.assertNotIn("community/SOURCES.yaml", source)
        self.assertNotIn("shared/assistant.md", source)
        self.assertNotIn("shared/rules/", source)

    def test_repo_install_renders_runtime_placeholders(self) -> None:
        source = (ROOT / "tools/install/repo_install.py").read_text(encoding="utf-8")
        self.assertIn("render_runtime_placeholders.py", source)
        self.assertIn("render_skill_placeholders", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
