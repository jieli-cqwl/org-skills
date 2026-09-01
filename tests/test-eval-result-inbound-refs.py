# tests/test-eval-result-inbound-refs.py
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tracked(prefix: str) -> set[str]:
    out = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", prefix], text=True)
    return {line for line in out.splitlines() if line}


class InboundRefTests(unittest.TestCase):
    def test_every_tracked_eval_result_is_referenced(self) -> None:
        results = tracked("tools/eval/results")
        text_roots = [
            ROOT / "tests",
            ROOT / "contracts",
            ROOT / "shared/skills",
            ROOT / "tools/eval/contracts",
            ROOT / "tools/eval/scenarios",
        ]
        corpus = []
        for root in text_roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.suffix in {".py", ".sh", ".json", ".md", ".yaml"} and path.is_file():
                    corpus.append(path.read_text(encoding="utf-8", errors="replace"))
        blob = "\n".join(corpus)
        unused = [rel for rel in sorted(results) if rel not in blob]
        self.assertEqual(unused, [])

    def test_generated_noise_gone(self) -> None:
        self.assertEqual(tracked(".superpowers"), set())
        self.assertEqual(tracked(".claude/skills/darwin-skill"), set())
        self.assertFalse((ROOT / "findings.md").exists())
        self.assertFalse((ROOT / "progress.md").exists())
        self.assertFalse((ROOT / "task_plan.md").exists())

    def test_local_settings_do_not_point_at_moved_base_paths(self) -> None:
        settings = ROOT / ".claude" / "settings.local.json"
        if not settings.exists():
            return
        text = settings.read_text(encoding="utf-8")
        self.assertNotIn("shared/assistant.md", text)
        self.assertNotIn("shared/rules/", text)
        self.assertNotIn("shared/reference/", text)


if __name__ == "__main__":
    unittest.main()
