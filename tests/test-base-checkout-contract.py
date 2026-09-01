#!/usr/bin/env python3
"""Team install tests honor BASE_CHECKOUT and a test-only Base fixture."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tests/lib/install-test-env.sh"
FIXTURE = ROOT / "tests/fixtures/base-config-cutover-start"
DEFAULT_BASE = "/Users/lijieli/base-config"
PINNED_SHA = "bb314976b162eb22d51bfcfbc9b4d024543ca9fe"
REQUIRED_RELATIVE_PATHS = (
    "install.sh",
    "VERSION",
    "assistant.md",
    "tools/install/repo_install.py",
    "tools/install/tree_digest.py",
    "rules/code-changes.md",
    "reference/测试规范.md",
    "SOURCE.txt",
)


def resolved_base_checkout(extra_env: dict[str, str] | None = None) -> str:
    env = os.environ.copy()
    env.pop("BASE_CHECKOUT", None)
    env.pop("BASE_REPO", None)
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [
            "bash",
            "-c",
            'set -euo pipefail; . "$1"; printf "%s\\n" "$BASE_CHECKOUT"',
            "bash",
            str(HELPER),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout.strip()


class BaseCheckoutContractTests(unittest.TestCase):
    def test_helper_defaults_to_sibling_base_checkout(self) -> None:
        helper = HELPER.read_text(encoding="utf-8")
        self.assertRegex(
            helper,
            r'(?m)^BASE_CHECKOUT="\$\{BASE_CHECKOUT:-/Users/lijieli/base-config\}"$',
        )
        self.assertEqual(resolved_base_checkout(), DEFAULT_BASE)

    def test_helper_honors_base_checkout_override(self) -> None:
        helper = HELPER.read_text(encoding="utf-8")
        self.assertIn('"$BASE_CHECKOUT/install.sh"', helper)
        override = "/tmp/team-ci-base-fixture"
        self.assertEqual(
            resolved_base_checkout({"BASE_CHECKOUT": override}),
            override,
        )

    def test_fixture_is_test_only_cutover_start_payload(self) -> None:
        self.assertTrue(FIXTURE.is_dir(), f"missing Base fixture at {FIXTURE}")
        for relative in REQUIRED_RELATIVE_PATHS:
            path = FIXTURE / relative
            self.assertTrue(path.is_file(), f"missing fixture file {relative}")
        self.assertTrue(os.access(FIXTURE / "install.sh", os.X_OK))
        source = (FIXTURE / "SOURCE.txt").read_text(encoding="utf-8")
        self.assertIn("base-config-cutover-start", source)
        self.assertIn(PINNED_SHA, source)
        self.assertIn("test-only", source)
        self.assertFalse((FIXTURE / "community").exists())
        self.assertFalse((FIXTURE / "skills" / "systematic-debugging").exists())
        self.assertFalse((ROOT / "shared" / "assistant.md").exists())
        self.assertFalse((ROOT / "shared" / "rules").exists())
        self.assertFalse((ROOT / "community").exists())
        install_wrapper = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertNotIn("tests/fixtures/base-config-cutover-start", install_wrapper)

    def test_fixture_base_installs_into_isolated_home(self) -> None:
        with tempfile.TemporaryDirectory(prefix="team-base-fixture-") as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            state = home / ".local" / "state" / "skill-repos"
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["SKILL_REPO_STATE_ROOT"] = str(state)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env.pop("ORG_STATE_ROOT", None)
            result = subprocess.run(
                ["bash", str(FIXTURE / "install.sh"), "--target", "claude"],
                cwd=str(FIXTURE),
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest_path = state / "base-config" / "claude" / "installed.json"
            self.assertTrue(manifest_path.is_file(), result.stdout + result.stderr)
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("repo_id"), "base-config")
            ids = {
                str(resource.get("resource_id"))
                for resource in payload.get("resources") or []
                if isinstance(resource, dict)
            }
            self.assertIn("assistant", ids)
            self.assertIn("rules/code-changes.md", ids)
            self.assertTrue((home / ".claude" / "CLAUDE.md").is_file())
            self.assertFalse((home / ".claude" / "skills" / "product-director").exists())


if __name__ == "__main__":
    unittest.main()
