#!/usr/bin/env python3
"""Contract tests for the repository validation workflow."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/test.yml"


class GitHubWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = yaml.load(
            WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
        )

    def test_push_validation_runs_only_on_main(self) -> None:
        triggers = self.workflow["on"]
        self.assertEqual(triggers["push"]["branches"], ["main"])
        self.assertIn("pull_request", triggers)

    def test_duplicate_runs_are_cancelled_per_pull_request(self) -> None:
        concurrency = self.workflow["concurrency"]
        self.assertIn("github.event.pull_request.number", concurrency["group"])
        self.assertEqual(concurrency["cancel-in-progress"], "true")

    def test_validation_installs_required_python_dependencies(self) -> None:
        steps = self.workflow["jobs"]["validate"]["steps"]
        install_step = next(step for step in steps if step.get("name") == "Install dependencies")
        install_command = install_step["run"]
        for dependency in ("pyyaml", "jsonschema", "defusedxml"):
            self.assertIn(dependency, install_command)

    def test_validation_installs_ripgrep(self) -> None:
        steps = self.workflow["jobs"]["validate"]["steps"]
        install_step = next(step for step in steps if step.get("name") == "Install dependencies")
        self.assertIn("ripgrep", install_step["run"])

    def test_validate_job_runs_full_gate(self) -> None:
        steps = self.workflow["jobs"]["validate"]["steps"]
        test_step = next(step for step in steps if step.get("name") == "Run tests")
        self.assertIn("bash tests/run-all.sh", test_step["run"])

    def _base_checkout_value(self) -> str:
        job = self.workflow["jobs"]["validate"]
        job_env = job.get("env") or {}
        test_step = next(step for step in job["steps"] if step.get("name") == "Run tests")
        step_env = test_step.get("env") or {}
        if isinstance(step_env, dict) and step_env.get("BASE_CHECKOUT"):
            return str(step_env["BASE_CHECKOUT"])
        if isinstance(job_env, dict) and job_env.get("BASE_CHECKOUT"):
            return str(job_env["BASE_CHECKOUT"])
        return ""

    def test_ci_uses_vendored_base_fixture_not_sibling_clone(self) -> None:
        checkout = self._base_checkout_value()
        self.assertIn("tests/fixtures/base-config-cutover-start", checkout)
        workflow_text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("git clone", workflow_text)
        self.assertNotIn("daily-skills", workflow_text)
        self.assertNotIn("community/", workflow_text)
        self.assertNotIn("/Users/lijieli/base-config", workflow_text)


if __name__ == "__main__":
    unittest.main()
