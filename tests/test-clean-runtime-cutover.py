# tests/test-clean-runtime-cutover.py
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURE_HOME = ROOT / "tests/fixtures/runtime-cutover/preflight-home"

from tools.install.tree_digest import canonical_tree_digest
from tools.migration.action_plan import ActionClass, build_action_plan
from tools.migration.clean_runtime_cutover import _persist_remove_preflight, apply_action_plan

TEAM_AGENT_SECTIONS = (
    (
        "consistency-auditor",
        "仅 delivery-owner 标准链路 Task Packet 授权调度：跨工件一致性旁路审计，输出 advisory-only owner action",
        "./agents/consistency-auditor.toml",
    ),
    (
        "developer",
        "仅 delivery-owner 标准链路 Task Packet 授权调度：TDD驱动开发执行，完成任务并自验证",
        "./agents/developer.toml",
    ),
    (
        "fixer",
        "仅 delivery-owner 标准链路 Task Packet 授权调度：故障根因分析与最小修复",
        "./agents/fixer.toml",
    ),
    (
        "qa",
        "仅 delivery-owner 标准链路 Task Packet 授权调度：用户视角功能验收，独立给出PASS/FAIL",
        "./agents/qa.toml",
    ),
    (
        "verifier",
        "仅 delivery-owner 标准链路 Task Packet 授权调度：Task级AC覆盖与代码质量验收",
        "./agents/verifier.toml",
    ),
)


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

    def test_agent_tuning_migration_sentinel_is_delete_legacy_state(self) -> None:
        home = self._home()
        sentinel = home / ".org-skills-state/codex/agent-tuning-migration-v1"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_bytes(b"")
        plan = build_action_plan(home, pre_split_tag="pre-split-2026-08-31")
        by_path = {a.path: a.cls for a in plan.actions}
        self.assertEqual(by_path[str(sentinel)], ActionClass.DELETE_LEGACY_STATE)
        mystery = str(home / ".org-skills-state/mystery.txt")
        self.assertEqual(by_path[mystery], ActionClass.CONFLICT)
        self.assertEqual(plan.status, "blocked")

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
        self.assertEqual(
            by_path[str(home / ".org-skills-state/codex/agent-tuning-migration-v1")],
            ActionClass.DELETE_LEGACY_STATE,
        )
        self.assertEqual(
            by_path[str(home / ".org-skills-state/mystery.txt")],
            ActionClass.CONFLICT,
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

    def test_skill_root_lib_is_remove_old_only_not_preserve(self) -> None:
        home = self._home()
        for rel in (".claude/skills/lib", ".agents/skills/lib"):
            lib = home / rel
            lib.mkdir(parents=True)
            (lib / "script-common.sh").write_text("old-team-lib\n", encoding="utf-8")
        plan = build_action_plan(home, pre_split_tag="pre-split-2026-08-31")
        by_path = {a.path: a.cls for a in plan.actions}
        self.assertEqual(by_path[str(home / ".claude/skills/lib")], ActionClass.REMOVE_OLD_ONLY)
        self.assertEqual(by_path[str(home / ".agents/skills/lib")], ActionClass.REMOVE_OLD_ONLY)


class ApplyActionPlanTests(unittest.TestCase):
    def _ready_home(self) -> Path:
        td = Path(tempfile.mkdtemp(prefix="cutover-ready-"))
        self.addCleanup(shutil.rmtree, td, ignore_errors=True)
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
        return td

    def _journal(self) -> Path:
        td = Path(tempfile.mkdtemp(prefix="cutover-journal-"))
        self.addCleanup(shutil.rmtree, td, ignore_errors=True)
        return td / "journal.json"

    def _plan(self, home: Path):
        return build_action_plan(home, pre_split_tag="pre-split-2026-08-31")

    def _write_codex_config(
        self,
        home: Path,
        *,
        extra_field_role: str | None = None,
        extra_agent: str | None = None,
        multi_agent: str = "true",
        hooks: str = "true",
    ) -> Path:
        lines = ["[features]", f"multi_agent = {multi_agent}", f"hooks = {hooks}", ""]
        for role, description, config_file in TEAM_AGENT_SECTIONS:
            lines.append(f"[agents.{role}]")
            lines.append(f'description = "{description}"')
            lines.append(f'config_file = "{config_file}"')
            if extra_field_role == role:
                lines.append('model = "gpt-5"')
            lines.append("")
        if extra_agent:
            lines.append(f"[agents.{extra_agent}]")
            lines.append('description = "user-owned agent"')
            lines.append("")
        path = home / ".codex" / "config.toml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return path

    def _journal_entries(self, journal: Path) -> list[dict]:
        payload = json.loads(journal.read_text(encoding="utf-8"))
        self.assertIsInstance(payload, list)
        return payload

    def test_apply_remove_old_only_preserves_external_bytes(self) -> None:
        home = self._ready_home()
        learned = home / ".claude/skills/learned/x.md"
        superset = home / ".claude/skills/superset/SKILL.md"
        learned_bytes = learned.read_bytes()
        superset_bytes = superset.read_bytes()
        plan = self._plan(home)
        self.assertEqual(plan.status, "ready")
        apply_action_plan(plan, self._journal())
        self.assertFalse((home / ".claude/skills/product-director").exists())
        self.assertEqual(learned.read_bytes(), learned_bytes)
        self.assertEqual(superset.read_bytes(), superset_bytes)
        self.assertTrue((home / ".claude/hooks/superset_notify.sh").is_file())

    def test_apply_refuses_conflict_plan_without_mutation(self) -> None:
        home = self._ready_home()
        mystery = home / ".org-skills-state/mystery.txt"
        mystery.write_text("unknown\n", encoding="utf-8")
        target = home / ".claude/skills/product-director/SKILL.md"
        before = target.read_bytes()
        plan = self._plan(home)
        self.assertEqual(plan.status, "blocked")
        journal = self._journal()
        with self.assertRaises(Exception) as ctx:
            apply_action_plan(plan, journal)
        self.assertIn("CONFLICT", str(ctx.exception).upper())
        self.assertEqual(target.read_bytes(), before)
        self.assertTrue(mystery.is_file())
        self.assertTrue((home / ".claude/skills/product-director").exists())

    def test_rehash_before_mutation_stops_changed_path(self) -> None:
        home = self._ready_home()
        target = home / ".claude/skills/product-director"
        plan = self._plan(home)
        journal = self._journal()
        journal.write_text(
            json.dumps(
                [
                    {
                        "path": str(target),
                        "cls": ActionClass.REMOVE_OLD_ONLY.value,
                        "pre_digest": canonical_tree_digest(target),
                        "status": "pending",
                    }
                ],
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (target / "SKILL.md").write_text("changed-after-preflight\n", encoding="utf-8")
        apply_action_plan(plan, journal)
        self.assertTrue(target.exists())
        self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "changed-after-preflight\n")
        entries = [row for row in self._journal_entries(journal) if row["path"] == str(target)]
        self.assertTrue(any(row["status"] == "failed" for row in entries))

    def test_interrupt_resume_does_not_restore_from_journal(self) -> None:
        home = self._ready_home()
        first = home / ".claude/skills/product-director"
        second = home / ".claude/skills/resume-tailor"
        plan = self._plan(home)
        journal = self._journal()
        import tools.migration.clean_runtime_cutover as cutover

        state = {"count": 0}

        def boom(_entry: dict) -> None:
            state["count"] += 1
            if state["count"] >= 1:
                raise RuntimeError("interrupted after first deletion")

        with patch.object(cutover, "_after_mutation", boom):
            with self.assertRaises(RuntimeError):
                apply_action_plan(plan, journal)
        gone = [path for path in (first, second) if not path.exists()]
        remaining = [path for path in (first, second) if path.exists()]
        self.assertEqual(len(gone), 1, "interrupt must stop after the first deletion")
        self.assertEqual(len(remaining), 1)
        entries = self._journal_entries(journal)
        self.assertTrue(any(row["path"] == str(gone[0]) and row["status"] == "done" for row in entries))
        self.assertTrue(any(row["path"] == str(remaining[0]) and row["status"] == "pending" for row in entries))
        journal_text = journal.read_text(encoding="utf-8")
        self.assertNotIn("team\n", journal_text)
        self.assertNotIn("gone\n", journal_text)
        apply_action_plan(plan, journal)
        self.assertFalse(first.exists())
        self.assertFalse(second.exists())
        self.assertNotIn("team\n", journal.read_text(encoding="utf-8"))

    def test_matching_team_agent_sections_removed_drift_stops_that_section(self) -> None:
        home = self._ready_home()
        config = self._write_codex_config(home, extra_field_role="qa")
        apply_action_plan(self._plan(home), self._journal())
        text = config.read_text(encoding="utf-8")
        for role, _, _ in TEAM_AGENT_SECTIONS:
            if role == "qa":
                self.assertIn(f"[agents.{role}]", text)
                self.assertIn("model = \"gpt-5\"", text)
            else:
                self.assertNotIn(f"[agents.{role}]", text)

    def test_multi_agent_removed_only_without_non_team_agent(self) -> None:
        home = self._ready_home()
        config = self._write_codex_config(home)
        apply_action_plan(self._plan(home), self._journal())
        text = config.read_text(encoding="utf-8")
        self.assertNotIn("multi_agent", text)
        for role, _, _ in TEAM_AGENT_SECTIONS:
            self.assertNotIn(f"[agents.{role}]", text)

        kept = self._ready_home()
        kept_config = self._write_codex_config(kept, extra_agent="my-bot")
        apply_action_plan(self._plan(kept), self._journal())
        kept_text = kept_config.read_text(encoding="utf-8")
        self.assertIn("multi_agent = true", kept_text)
        self.assertIn("[agents.my-bot]", kept_text)
        for role, _, _ in TEAM_AGENT_SECTIONS:
            self.assertNotIn(f"[agents.{role}]", kept_text)

    def test_preserved_external_hook_keeps_features_hooks_ignores_snapshot(self) -> None:
        home = self._ready_home()
        config = self._write_codex_config(home)
        hooks_path = home / ".codex" / "hooks.json"
        hooks_path.parent.mkdir(parents=True, exist_ok=True)
        hooks_path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": (
                                            '[ -n "$SUPERSET_HOME_DIR" ] && '
                                            '[ -x "$SUPERSET_HOME_DIR/hooks/notify.sh" ] && '
                                            'SUPERSET_AGENT_ID=codex "$SUPERSET_HOME_DIR/hooks/notify.sh" || true'
                                        ),
                                    }
                                ]
                            }
                        ]
                    }
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        snapshot = home / ".org-skills-state/codex/codex-hooks-feature-state.json"
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(
            json.dumps({"had_file": True, "had_features_section": True, "had_codex_hooks": False})
            + "\n",
            encoding="utf-8",
        )
        apply_action_plan(self._plan(home), self._journal())
        hooks_data = json.loads(hooks_path.read_text(encoding="utf-8"))
        self.assertIn("SUPERSET_HOME_DIR", json.dumps(hooks_data))
        self.assertIn("hooks = true", config.read_text(encoding="utf-8"))

    def test_claude_settings_removes_only_old_managed_hook_identities(self) -> None:
        home = self._ready_home()
        settings_path = home / ".claude" / "settings.json"
        old_managed = {
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": "bash $HOME/.claude/hooks/block_dangerous.sh"}],
        }
        unrelated = {
            "hooks": [{"type": "command", "command": "bash /opt/custom/user_hook.sh"}],
        }
        preserved = {
            "hooks": [{"type": "command", "command": "python3 $HOME/.claude/hooks/read_pages_context.py"}],
        }
        settings_path.write_text(
            json.dumps(
                {
                    "hooks": {"PreToolUse": [old_managed, unrelated, preserved]},
                    "unrelated_key": True,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        baseline = home / ".org-skills-state/claude/claude-settings-baseline.json"
        baseline.write_text("{}\n", encoding="utf-8")
        apply_action_plan(self._plan(home), self._journal())
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        entries = data["hooks"]["PreToolUse"]
        self.assertEqual(entries, [unrelated, preserved])
        self.assertTrue(data["unrelated_key"])
        self.assertNotIn("block_dangerous.sh", json.dumps(data))

    def test_grill_obsidian_removed_for_fresh_install(self) -> None:
        home = self._ready_home()
        future_bytes = b"future-daily-bytes\n"
        grill = home / ".claude/skills/grill-me"
        obsidian = home / ".claude/skills/obsidian-markdown"
        grill.mkdir()
        obsidian.mkdir()
        (grill / "SKILL.md").write_bytes(future_bytes)
        (obsidian / "SKILL.md").write_bytes(future_bytes)
        plan = self._plan(home)
        by_path = {action.path: action.cls for action in plan.actions}
        self.assertEqual(by_path[str(grill)], ActionClass.REMOVE_FOR_FRESH_INSTALL)
        self.assertEqual(by_path[str(obsidian)], ActionClass.REMOVE_FOR_FRESH_INSTALL)
        apply_action_plan(plan, self._journal())
        self.assertFalse(grill.exists())
        self.assertFalse(obsidian.exists())

    def test_cleaner_does_not_write_installed_json(self) -> None:
        home = self._ready_home()
        apply_action_plan(self._plan(home), self._journal())
        self.assertEqual(list(home.rglob("installed.json")), [])

    def test_cleaner_never_calls_install_uninstall(self) -> None:
        home = self._ready_home()
        source = (ROOT / "tools/migration/clean_runtime_cutover.py").read_text(encoding="utf-8")
        self.assertNotIn("--uninstall", source)
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("os.system") as system,
        ):
            apply_action_plan(self._plan(home), self._journal())
        self.assertEqual(run.call_args_list, [])
        self.assertEqual(popen.call_args_list, [])
        self.assertEqual(system.call_args_list, [])

    def test_journal_is_metadata_not_content_backup(self) -> None:
        home = self._ready_home()
        skill_body = (home / ".claude/skills/product-director/SKILL.md").read_text(encoding="utf-8")
        journal = self._journal()
        apply_action_plan(self._plan(home), journal)
        self.assertTrue(journal.is_file())
        leftover = [path for path in journal.parent.iterdir() if path != journal]
        self.assertEqual(leftover, [])
        entries = self._journal_entries(journal)
        self.assertGreater(len(entries), 0)
        text = journal.read_text(encoding="utf-8")
        self.assertNotIn(skill_body, text)
        for row in entries:
            self.assertIn("path", row)
            self.assertIn("cls", row)
            self.assertIn("pre_digest", row)
            self.assertIn("status", row)
            self.assertNotIn("body", row)
            self.assertNotIn("content", row)
            self.assertIn(row["status"], {"pending", "done", "skipped", "failed"})

    def test_persist_preflight_digests_archive_parent_relative_symlink(self) -> None:
        home = self._ready_home()
        link = (
            home
            / ".org-skills-state/archive/dot-claude-retirement-20260326022826"
            / "runtime-files/skills/design/references/review-iteration-protocol.md"
        )
        link.parent.mkdir(parents=True)
        link.symlink_to("../../product/references/review-iteration-protocol.md")
        plan = self._plan(home)
        by_path = {action.path: action.cls for action in plan.actions}
        self.assertEqual(by_path[str(link)], ActionClass.DELETE_LEGACY_STATE)
        self.assertEqual(plan.status, "ready")
        journal = _persist_remove_preflight(plan, home)
        self.assertTrue(journal.is_file())
        entries = self._journal_entries(journal)
        row = next(item for item in entries if item["path"] == str(link))
        self.assertEqual(row["cls"], ActionClass.DELETE_LEGACY_STATE.value)
        self.assertTrue(row["pre_digest"])

    def test_apply_deletes_team_support_trees(self) -> None:
        home = self._ready_home()
        for rel in (".claude/shared/skills/lib", ".codex/shared/skills/lib"):
            lib = home / rel
            lib.mkdir(parents=True)
            (lib / "note.md").write_text("team-lib\n", encoding="utf-8")
        apply_action_plan(self._plan(home), self._journal())
        self.assertFalse((home / ".claude/shared/skills").exists())
        self.assertFalse((home / ".codex/shared/skills").exists())


class RetireDotClaudeDisabledTests(unittest.TestCase):
    def test_retire_dot_claude_exits_nonzero_without_mutating_fake_home(self) -> None:
        home = Path(tempfile.mkdtemp(prefix="cutover-retire-"))
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        claude = home / ".claude"
        claude.mkdir()
        keep = claude / "keep.txt"
        keep.write_text("stay\n", encoding="utf-8")
        git_dir = claude / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        env = {**os.environ, "HOME": str(home)}
        proc = subprocess.run(
            [str(ROOT / "tools/migration/retire-dot-claude.sh"), "--claude-dir", str(claude)],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
            cwd=str(home),
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("clean_runtime_cutover.py", proc.stderr)
        self.assertTrue(keep.is_file())
        self.assertEqual(keep.read_text(encoding="utf-8"), "stay\n")
        self.assertTrue(git_dir.exists())


if __name__ == "__main__":
    unittest.main()

