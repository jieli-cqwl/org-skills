"""Apply one-time runtime cutover removals. Journal metadata only; never restore baselines."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.install.tree_digest import canonical_tree_digest
from tools.migration.action_plan import ActionClass, ActionPlan, build_action_plan
from tools.migration.legacy_inventory import (
    EXPLICIT_DELETE_NAMES,
    PERSONAL_SKILLS,
    PRESERVE_SETTINGS_MARKERS,
    TEAM_CLAUDE_ONLY_SKILLS,
    TEAM_SKILLS,
    TEAM_SUPPORT_TREES,
)

_GIT_TIMEOUT_SEC = 30
_FS_WALK_TIMEOUT_SEC = 60
_VERIFY_CHILD_TIMEOUT_SEC = 180
_PHASES = ("remove", "verify", "retire-legacy-state")
_TARGETS = ("claude", "codex", "all")
_SKILL_REL = {
    "claude": Path(".claude") / "skills",
    "codex": Path(".agents") / "skills",
}
_HOOK_REL = {
    "claude": Path(".claude") / "hooks",
    "codex": Path(".codex") / "hooks",
}
_FORBIDDEN_SKILL_NAMES = TEAM_SKILLS | TEAM_CLAUDE_ONLY_SKILLS | PERSONAL_SKILLS | EXPLICIT_DELETE_NAMES

_REMOVE_CLASSES = frozenset(
    {
        ActionClass.REMOVE_OLD_ONLY.value,
        ActionClass.REMOVE_EXPLICIT_DELETE.value,
        ActionClass.REMOVE_FOR_FRESH_INSTALL.value,
    }
)
_SKIP_CLASSES = frozenset(
    {ActionClass.PRESERVE_EXTERNAL.value, ActionClass.DELETE_LEGACY_STATE.value}
)
_HOME_MARKERS = (".claude", ".codex", ".org-skills-state", ".agents")
_JOURNAL_STATUSES = frozenset({"pending", "done", "skipped", "failed"})

# Frozen old installer output for the five team Codex agent sections.
_TEAM_AGENT_MANAGED: dict[str, dict[str, str]] = {
    "agents.consistency-auditor": {
        "description": "仅 delivery-owner 标准链路 Task Packet 授权调度：跨工件一致性旁路审计，输出 advisory-only owner action",
        "config_file": "./agents/consistency-auditor.toml",
    },
    "agents.developer": {
        "description": "仅 delivery-owner 标准链路 Task Packet 授权调度：TDD驱动开发执行，完成任务并自验证",
        "config_file": "./agents/developer.toml",
    },
    "agents.fixer": {
        "description": "仅 delivery-owner 标准链路 Task Packet 授权调度：故障根因分析与最小修复",
        "config_file": "./agents/fixer.toml",
    },
    "agents.verifier": {
        "description": "仅 delivery-owner 标准链路 Task Packet 授权调度：Task级AC覆盖与代码质量验收",
        "config_file": "./agents/verifier.toml",
    },
    "agents.qa": {
        "description": "仅 delivery-owner 标准链路 Task Packet 授权调度：用户视角功能验收，独立给出PASS/FAIL",
        "config_file": "./agents/qa.toml",
    },
}
_TEAM_AGENT_ROLES = frozenset(name.split(".", 1)[1] for name in _TEAM_AGENT_MANAGED)

# Command-path identities emitted by the old Team hook registry, not preserve plugins.
_OLD_MANAGED_HOOK_MARKERS = frozenset(
    {
        "hooks/block_dangerous.sh",
        "hooks/code_quality_check.sh",
        "hooks/auto_format.sh",
        "hooks/post_compact.sh",
        "hooks/task_verify.sh",
        "hooks/managed/block_dangerous.sh",
        "hooks/managed/context_contract_validator.py",
        "hooks/managed/codex_user_prompt_submit.py",
        "hooks/managed/codex_subagent_dispatch_guard.py",
        "hooks/managed/codex_stop_dispatch.py",
    }
)


class ApplyBlockedError(Exception):
    """Raised when apply refuses a CONFLICT or blocked plan before any mutation."""


def _after_mutation(_entry: dict[str, Any]) -> None:
    """Test seam fired after a successful mutation is journaled as done."""
    raw = os.environ.get("ORG_CUTOVER_INTERRUPT_AFTER", "").strip()
    if not raw:
        return
    left = int(raw)
    if left <= 1:
        os.kill(os.getpid(), signal.SIGKILL)
    os.environ["ORG_CUTOVER_INTERRUPT_AFTER"] = str(left - 1)


def apply_action_plan(plan: ActionPlan, journal_path: Path | str) -> dict[str, Any]:
    if plan.status != "ready" or any(action.cls is ActionClass.CONFLICT for action in plan.actions):
        raise ApplyBlockedError("CONFLICT plan refused")

    journal_path = Path(journal_path)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    home = _infer_home(plan)
    # Bounded workspace only; never copy deleted bodies here as a backup.
    staging = Path(tempfile.mkdtemp(prefix="cutover-stage-"))
    try:
        entries = _merge_journal(plan, journal_path, home)
        _write_journal(journal_path, entries)
        for entry in entries:
            if entry.get("status") in {"done", "skipped"}:
                continue
            _apply_entry(entry, home)
            _write_journal(journal_path, entries)
            if entry.get("status") == "done":
                _after_mutation(entry)
        status = "partial" if any(row.get("status") == "failed" for row in entries) else "ok"
        return {"status": status, "journal_path": str(journal_path), "entries": entries}
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _infer_home(plan: ActionPlan) -> Path:
    for action in plan.actions:
        parts = Path(action.path).parts
        for marker in _HOME_MARKERS:
            if marker not in parts:
                continue
            idx = parts.index(marker)
            return Path(*parts[:idx]) if idx > 0 else Path(action.path).anchor
    raise ApplyBlockedError("cannot infer HOME from action plan")


def _merge_journal(plan: ActionPlan, journal_path: Path, home: Path) -> list[dict[str, Any]]:
    existing: dict[str, dict[str, Any]] = {}
    if journal_path.is_file():
        payload = json.loads(journal_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ApplyBlockedError("CONFLICT plan refused: journal is not a list")
        for row in payload:
            if isinstance(row, dict) and isinstance(row.get("path"), str):
                existing[str(row["path"])] = row

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()

    def take(path: str, cls: str, digest: str) -> None:
        if path in seen:
            return
        seen.add(path)
        if path in existing:
            entries.append(_normalize_entry(existing.pop(path), cls, digest))
            return
        entries.append(_entry(path, cls, digest, "pending"))

    for action in plan.actions:
        take(action.path, action.cls.value, _path_digest(Path(action.path)))
    for item in _structured_seed_entries(home):
        take(item["path"], item["cls"], item["pre_digest"])
    for leftover in existing.values():
        entries.append(_normalize_entry(leftover, str(leftover.get("cls") or ""), str(leftover.get("pre_digest") or "")))
    return entries


def _normalize_entry(row: dict[str, Any], cls: str, digest: str) -> dict[str, Any]:
    status = row.get("status")
    if status not in _JOURNAL_STATUSES:
        status = "pending"
    return _entry(
        str(row["path"]),
        str(row.get("cls") or cls),
        str(row.get("pre_digest") or digest),
        str(status),
        reason=row.get("reason") if isinstance(row.get("reason"), str) else None,
    )


def _entry(path: str, cls: str, pre_digest: str, status: str, reason: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "path": path,
        "cls": cls,
        "pre_digest": pre_digest,
        "status": status,
    }
    if reason:
        payload["reason"] = reason
    return payload


def _structured_seed_entries(home: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    config = home / ".codex" / "config.toml"
    if config.is_file():
        lines = _read_lines(config)
        for section in _TEAM_AGENT_MANAGED:
            start, end = _section_bounds(lines, section)
            if start is None or end is None:
                continue
            entries.append(
                _entry(
                    f"{config}#{section}",
                    ActionClass.REMOVE_OLD_ONLY.value,
                    _keys_digest(_section_keys(lines, start, end)),
                    "pending",
                )
            )
        start, end = _section_bounds(lines, "features")
        if start is not None and end is not None:
            idx = _key_index(lines, start, end, "multi_agent")
            if idx is not None:
                entries.append(
                    _entry(
                        f"{config}#features.multi_agent",
                        ActionClass.REMOVE_OLD_ONLY.value,
                        _text_digest(lines[idx]),
                        "pending",
                    )
                )
    settings = home / ".claude" / "settings.json"
    if settings.is_file():
        entries.append(
            _entry(
                f"{settings}#hooks",
                ActionClass.REMOVE_OLD_ONLY.value,
                _path_digest(settings),
                "pending",
            )
        )
    hooks = home / ".codex" / "hooks.json"
    if hooks.is_file():
        entries.append(
            _entry(
                f"{hooks}#hooks",
                ActionClass.REMOVE_OLD_ONLY.value,
                _path_digest(hooks),
                "pending",
            )
        )
    return entries


def _apply_entry(entry: dict[str, Any], home: Path) -> None:
    raw_path = str(entry["path"])
    selector = _structured_selector(raw_path)
    if selector is not None:
        file_path, name = selector
        if not _is_under(file_path, home):
            entry["status"] = "failed"
            entry["reason"] = "path escapes HOME"
            return
        _apply_structured(entry, file_path, name)
        return

    path = Path(raw_path)
    cls = entry.get("cls")
    if cls in _SKIP_CLASSES:
        entry["status"] = "skipped"
        return
    if cls not in _REMOVE_CLASSES:
        entry["status"] = "skipped"
        return
    if not path.exists() and not path.is_symlink():
        entry["status"] = "done"
        return
    if not _is_under(path, home):
        entry["status"] = "failed"
        entry["reason"] = "path escapes HOME"
        return
    current = _path_digest(path)
    if current != entry.get("pre_digest"):
        entry["status"] = "failed"
        entry["reason"] = "digest changed since preflight"
        return
    _remove_path(path)
    entry["status"] = "done"


def _apply_structured(entry: dict[str, Any], path: Path, selector: str) -> None:
    if selector.startswith("agents."):
        _apply_agent_section(entry, path, selector)
        return
    if selector == "features.multi_agent":
        _apply_multi_agent(entry, path)
        return
    if selector == "hooks":
        _apply_hook_file(entry, path)
        return
    entry["status"] = "skipped"


def _apply_agent_section(entry: dict[str, Any], path: Path, section: str) -> None:
    expected = _TEAM_AGENT_MANAGED.get(section)
    if expected is None:
        entry["status"] = "skipped"
        return
    if not path.is_file():
        entry["status"] = "done"
        return
    lines = _read_lines(path)
    start, end = _section_bounds(lines, section)
    if start is None or end is None:
        entry["status"] = "done"
        return
    actual = _section_keys(lines, start, end)
    current = _keys_digest(actual)
    if current != entry.get("pre_digest"):
        entry["status"] = "failed"
        entry["reason"] = "digest changed since preflight"
        return
    if actual != expected:
        entry["status"] = "failed"
        entry["reason"] = "structured drift"
        return
    del lines[start:end]
    if start < len(lines) and not lines[start].strip():
        del lines[start]
    if start > 0 and start <= len(lines) and not lines[start - 1].strip():
        del lines[start - 1]
    _write_lines(path, lines)
    entry["status"] = "done"


def _apply_multi_agent(entry: dict[str, Any], path: Path) -> None:
    if not path.is_file():
        entry["status"] = "done"
        return
    lines = _read_lines(path)
    start, end = _section_bounds(lines, "features")
    if start is None or end is None:
        entry["status"] = "done"
        return
    idx = _key_index(lines, start, end, "multi_agent")
    if idx is None:
        entry["status"] = "done"
        return
    current = _text_digest(lines[idx])
    if current != entry.get("pre_digest"):
        entry["status"] = "failed"
        entry["reason"] = "digest changed since preflight"
        return
    value = _parse_toml_assignment(lines[idx])
    if value is None or value[1] != "true":
        entry["status"] = "skipped"
        return
    if _non_team_agent_sections(lines):
        entry["status"] = "skipped"
        return
    del lines[idx]
    _write_lines(path, lines)
    entry["status"] = "done"


def _apply_hook_file(entry: dict[str, Any], path: Path) -> None:
    if not path.is_file():
        entry["status"] = "done"
        return
    current = _path_digest(path)
    if current != entry.get("pre_digest"):
        entry["status"] = "failed"
        entry["reason"] = "digest changed since preflight"
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        entry["status"] = "failed"
        entry["reason"] = "structured-corrupt"
        return
    if not isinstance(data, dict):
        entry["status"] = "failed"
        entry["reason"] = "structured-corrupt"
        return
    hooks = data.get("hooks")
    if isinstance(hooks, dict):
        for event, items in list(hooks.items()):
            if not isinstance(items, list):
                continue
            filtered = [item for item in items if not _is_old_managed_hook(item)]
            if filtered:
                hooks[event] = filtered
            else:
                hooks.pop(event, None)
        if hooks:
            data["hooks"] = hooks
        else:
            data.pop("hooks", None)
    data.pop("_org_skills", None)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    entry["status"] = "done"


def _is_old_managed_hook(item: Any) -> bool:
    blob = json.dumps(item, ensure_ascii=False)
    if any(marker in blob for marker in PRESERVE_SETTINGS_MARKERS):
        return False
    return any(marker in blob for marker in _OLD_MANAGED_HOOK_MARKERS)


def _non_team_agent_sections(lines: list[str]) -> list[str]:
    found: list[str] = []
    for line in lines:
        header = line.strip()
        if not header.startswith("[") or not header.endswith("]") or header.startswith("[["):
            continue
        name = header[1:-1].strip()
        if not name.startswith("agents.") or "." in name[len("agents.") :]:
            continue
        role = name.split(".", 1)[1]
        if role not in _TEAM_AGENT_ROLES:
            found.append(name)
    return found


def _section_bounds(lines: list[str], name: str) -> tuple[int | None, int | None]:
    start = None
    needle = f"[{name}]"
    for idx, line in enumerate(lines):
        if line.strip() == needle:
            start = idx
            break
    if start is None:
        return None, None
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        stripped = lines[idx].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            end = idx
            break
    return start, end


def _key_index(lines: list[str], start: int, end: int, key: str) -> int | None:
    for idx in range(start + 1, end):
        parsed = _parse_toml_assignment(lines[idx])
        if parsed is not None and parsed[0] == key:
            return idx
    return None


def _section_keys(lines: list[str], start: int, end: int) -> dict[str, str]:
    values: dict[str, str] = {}
    for idx in range(start + 1, end):
        parsed = _parse_toml_assignment(lines[idx])
        if parsed is None:
            continue
        values[parsed[0]] = parsed[1]
    return values


def _parse_toml_assignment(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, raw = stripped.split("=", 1)
    key = key.strip()
    raw = raw.strip()
    if not key:
        return None
    if raw.startswith('"'):
        try:
            value, _ = json.JSONDecoder().raw_decode(raw)
        except json.JSONDecodeError:
            return key, raw.strip('"')
        return key, str(value)
    return key, raw.split("#", 1)[0].strip()


def _structured_selector(path_str: str) -> tuple[Path, str] | None:
    if "#" not in path_str:
        return None
    file_part, selector = path_str.rsplit("#", 1)
    if not selector:
        return None
    return Path(file_part), selector


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if path.is_dir():
        shutil.rmtree(path)


def _is_under(path: Path, home: Path) -> bool:
    try:
        path.resolve().relative_to(home.resolve())
    except ValueError:
        return False
    return True


def _path_digest(path: Path) -> str:
    if not path.exists() and not path.is_symlink():
        return ""
    return canonical_tree_digest(path)


def _text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _keys_digest(values: dict[str, str]) -> str:
    return _text_digest(json.dumps(values, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _write_lines(path: Path, lines: list[str]) -> None:
    text = ("\n".join(lines).rstrip() + "\n") if lines else ""
    path.write_text(text, encoding="utf-8")


def _write_journal(path: Path, entries: Iterable[dict[str, Any]]) -> None:
    serialized = json.dumps(list(entries), ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(serialized, encoding="utf-8")
    tmp.replace(path)


class CutoverError(Exception):
    def __init__(
        self,
        code: str,
        *,
        resource: str = "-",
        detail: str = "",
        next_step: str = "",
    ) -> None:
        super().__init__(code)
        self.code = code
        self.resource = resource
        self.detail = detail
        self.next_step = next_step

    def format(self) -> str:
        return "\n".join(
            [
                f"error: {self.code}",
                f"resource: {self.resource}",
                f"detail: {self.detail or '-'}",
                f"safe_next_step: {self.next_step or '-'}",
            ]
        )


def _work_dir(home: Path) -> Path:
    return home / ".local" / "state" / "org-runtime-cutover"


def _journal_file(home: Path) -> Path:
    return _work_dir(home) / "journal.json"


def _plan_meta_path(home: Path) -> Path:
    return _work_dir(home) / "plan.json"


def _verify_ok_path(home: Path) -> Path:
    return _work_dir(home) / "verify-ok.json"


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One-time runtime cleaner. Never installs Base or Daily."
    )
    parser.add_argument("--home", default=None)
    parser.add_argument("--base", default=None)
    parser.add_argument("--daily", default=None)
    parser.add_argument("--target", choices=_TARGETS, default="all")
    parser.add_argument("--phase", choices=_PHASES)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--accept-plan", default=None)
    return parser.parse_args(argv)


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("ORG_STATE_ROOT", None)
    return env


def _run_git(checkout: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(checkout), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SEC,
            env=_subprocess_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise CutoverError(
            "timeout",
            resource=str(checkout),
            detail=f"git {' '.join(args)} timed out",
            next_step="inspect the checkout filesystem and rerun",
        ) from exc
    if proc.returncode != 0:
        raise CutoverError(
            "git",
            resource=str(checkout),
            detail=(proc.stderr or proc.stdout or "git failed").strip()[:2000],
            next_step="pass a real Base/Daily git checkout",
        )
    return proc.stdout.strip()


def _assert_checkout(path: Path, label: str) -> None:
    if not path.is_dir():
        raise CutoverError(
            "missing-checkout",
            resource=str(path),
            detail=f"{label} checkout is not a directory",
            next_step=f"pass --{label} at a sibling checkout",
        )
    if not (path / "install.sh").is_file():
        raise CutoverError(
            "missing-checkout",
            resource=str(path / "install.sh"),
            detail=f"{label} checkout is missing install.sh",
            next_step=f"pass --{label} at a sibling checkout",
        )
    inside = _run_git(path, "rev-parse", "--is-inside-work-tree")
    if inside != "true":
        raise CutoverError(
            "missing-checkout",
            resource=str(path),
            detail=f"{label} checkout is not a git work tree",
            next_step=f"pass --{label} at a sibling checkout",
        )


def _selected_targets(value: str) -> tuple[str, ...]:
    if value == "all":
        return ("claude", "codex")
    return (value,)


def _in_target(path_str: str, home: Path, target: str) -> bool:
    if target == "all":
        return True
    raw = path_str.split("#", 1)[0]
    path = Path(raw)
    roots: list[Path]
    if target == "claude":
        roots = [home / ".claude"]
    else:
        roots = [home / ".codex", home / ".agents"]
    for root in roots:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def _filter_plan(plan: ActionPlan, home: Path, target: str) -> ActionPlan:
    if target == "all":
        return plan
    actions = tuple(
        action
        for action in plan.actions
        if action.cls is ActionClass.DELETE_LEGACY_STATE or _in_target(action.path, home, target)
    )
    preserve = {
        path: digest
        for path, digest in plan.preserve_digests.items()
        if _in_target(path, home, target)
    }
    return ActionPlan(
        actions=actions,
        status=plan.status,
        preflight_hash=plan.preflight_hash,
        preserve_digests=preserve,
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(serialized, encoding="utf-8")
    tmp.replace(path)


def _plan_payload(plan: ActionPlan) -> dict[str, Any]:
    return {
        "preflight_hash": plan.preflight_hash,
        "status": plan.status,
        "preserve_digests": dict(plan.preserve_digests),
        "actions": [
            {"path": action.path, "cls": action.cls.value, "reason": action.reason}
            for action in plan.actions
        ],
    }


def _persist_remove_preflight(plan: ActionPlan, home: Path) -> Path:
    # Freeze per-path pre_digest before mutation so apply re-hash matches preflight.
    meta = _plan_meta_path(home)
    journal = _journal_file(home)
    _write_json(meta, _plan_payload(plan))
    journal.parent.mkdir(parents=True, exist_ok=True)
    entries = _merge_journal(plan, journal, home)
    _write_journal(journal, entries)
    return journal


def _accepted_hash(value: str) -> str:
    path = Path(value)
    if path.is_file():
        text = path.read_text(encoding="utf-8").strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return text
        if isinstance(payload, dict) and isinstance(payload.get("preflight_hash"), str):
            return payload["preflight_hash"]
        return text
    return value


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _phase_remove(
    *,
    home: Path,
    target: str,
    apply: bool,
    accept_plan: str | None,
) -> int:
    plan = _filter_plan(build_action_plan(home), home, target)
    if plan.status != "ready" or any(action.cls is ActionClass.CONFLICT for action in plan.actions):
        conflicts = [action.path for action in plan.actions if action.cls is ActionClass.CONFLICT]
        _emit(
            {
                "phase": "remove",
                "status": "blocked",
                "preflight_hash": plan.preflight_hash,
                "conflicts": conflicts,
            }
        )
        raise CutoverError(
            "conflict",
            resource=conflicts[0] if conflicts else "-",
            detail="CONFLICT plan refused",
            next_step="resolve the listed paths, then rerun --phase remove --dry-run",
        )
    if accept_plan:
        expected = _accepted_hash(accept_plan)
        if expected != plan.preflight_hash:
            raise CutoverError(
                "accept-plan",
                resource=accept_plan,
                detail=f"expected {expected} actual {plan.preflight_hash}",
                next_step="rerun --dry-run and pass that preflight_hash to --accept-plan",
            )
    journal = _persist_remove_preflight(plan, home)
    if not apply:
        _emit(
            {
                "phase": "remove",
                "status": "ready",
                "preflight_hash": plan.preflight_hash,
                "journal_path": str(journal),
                "actions": _plan_payload(plan)["actions"],
            }
        )
        return 0
    result = apply_action_plan(plan, journal)
    status = str(result.get("status") or "partial")
    _emit(
        {
            "phase": "remove",
            "status": status,
            "preflight_hash": plan.preflight_hash,
            "journal_path": str(journal),
        }
    )
    if status != "ok":
        raise CutoverError(
            "remove-partial",
            resource=str(journal),
            detail="one or more remove actions failed",
            next_step="inspect the journal, fix the failed path, then rerun --phase remove --apply",
        )
    return 0


def _load_plan_meta(home: Path) -> dict[str, Any] | None:
    path = _plan_meta_path(home)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CutoverError(
            "journal",
            resource=str(path),
            detail=str(exc),
            next_step="rerun --phase remove --dry-run",
        ) from exc
    if not isinstance(payload, dict):
        raise CutoverError(
            "journal",
            resource=str(path),
            detail="plan metadata is not an object",
            next_step="rerun --phase remove --dry-run",
        )
    return payload


def _verify_preserve(home: Path) -> None:
    meta = _load_plan_meta(home)
    if meta is None:
        return
    preserve = meta.get("preserve_digests")
    if not isinstance(preserve, dict):
        return
    for raw_path, expected in preserve.items():
        path = Path(str(raw_path))
        if not path.exists():
            raise CutoverError(
                "preserve-missing",
                resource=str(path),
                detail="preserved external path missing",
                next_step="restore the preserved plugin path from Git, then rerun --phase verify",
            )
        actual = canonical_tree_digest(path)
        if actual != expected:
            raise CutoverError(
                "preserve-drift",
                resource=str(path),
                detail=f"expected {expected} actual {actual}",
                next_step="restore the preserved plugin bytes, then rerun --phase verify",
            )


_EXPECTED_DIGEST_CHILD = r"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

checkout = Path(sys.argv[1])
target = sys.argv[2]
sys.path.insert(0, str(checkout))
from tools.install.repo_install import build_plan

staging = Path(tempfile.mkdtemp(prefix="cutover-verify-child-"))
try:
    plan = build_plan(target, staging)
    print(
        json.dumps(
            [
                {"resource_id": resource.resource_id, "tree_sha256": resource.tree_sha256}
                for resource in plan.resources
            ],
            ensure_ascii=False,
        )
    )
finally:
    shutil.rmtree(staging, ignore_errors=True)
"""


def _expected_resource_digests(checkout: Path, target: str, home: Path) -> list[dict[str, str]]:
    env = _subprocess_env()
    env["HOME"] = str(home)
    env["PYTHONPATH"] = str(checkout)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _EXPECTED_DIGEST_CHILD, str(checkout), target],
            check=False,
            capture_output=True,
            text=True,
            timeout=_VERIFY_CHILD_TIMEOUT_SEC,
            env=env,
            cwd=str(checkout),
        )
    except subprocess.TimeoutExpired as exc:
        raise CutoverError(
            "timeout",
            resource=str(checkout),
            detail=f"verify staging timed out for {target}",
            next_step="inspect the checkout and rerun --phase verify",
        ) from exc
    if proc.returncode != 0:
        raise CutoverError(
            "verify-stage",
            resource=str(checkout),
            detail=(proc.stderr or proc.stdout or "staging failed").strip()[:2000],
            next_step="restore the checkout installer payload and rerun --phase verify",
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise CutoverError(
            "verify-stage",
            resource=str(checkout),
            detail="installer staging did not print JSON",
            next_step="restore the checkout installer and rerun --phase verify",
        ) from exc
    if not isinstance(payload, list):
        raise CutoverError(
            "verify-stage",
            resource=str(checkout),
            detail="installer staging JSON must be a list",
            next_step="restore the checkout installer and rerun --phase verify",
        )
    rows: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict) or "resource_id" not in item or "tree_sha256" not in item:
            raise CutoverError(
                "verify-stage",
                resource=str(checkout),
                detail="installer staging row missing resource_id/tree_sha256",
                next_step="restore the checkout installer and rerun --phase verify",
            )
        rows.append(
            {"resource_id": str(item["resource_id"]), "tree_sha256": str(item["tree_sha256"])}
        )
    return rows


def _base_dest_rel(resource_id: str, target: str) -> Path:
    root = Path(".claude" if target == "claude" else ".codex")
    if resource_id == "assistant":
        return root / ("CLAUDE.md" if target == "claude" else "AGENTS.md")
    return root / resource_id


def _verify_base(home: Path, checkout: Path, targets: tuple[str, ...]) -> None:
    for target in targets:
        rows = _expected_resource_digests(checkout, target, home)
        if len(rows) != 15:
            raise CutoverError(
                "resource-count",
                resource=str(checkout),
                detail=f"base staged {len(rows)} expected 15",
                next_step="restore the 15-file Base payload and rerun --phase verify",
            )
        for row in rows:
            dest = home / _base_dest_rel(row["resource_id"], target)
            if not dest.exists():
                raise CutoverError(
                    "missing-resource",
                    resource=str(dest),
                    detail="Base payload is missing",
                    next_step="run Base install.sh --target all, then rerun --phase verify",
                )
            actual = canonical_tree_digest(dest)
            if actual != row["tree_sha256"]:
                raise CutoverError(
                    "digest-mismatch",
                    resource=str(dest),
                    detail=f"expected {row['tree_sha256']} actual {actual}",
                    next_step="reinstall Base from the pinned checkout, then rerun --phase verify",
                )


def _verify_daily(home: Path, checkout: Path, targets: tuple[str, ...]) -> None:
    for target in targets:
        rows = _expected_resource_digests(checkout, target, home)
        if len(rows) != 42:
            raise CutoverError(
                "resource-count",
                resource=str(checkout),
                detail=f"daily staged {len(rows)} expected 42",
                next_step="restore the 42 Daily Skill trees and rerun --phase verify",
            )
        for row in rows:
            dest = home / _SKILL_REL[target] / row["resource_id"]
            if not dest.exists():
                raise CutoverError(
                    "missing-resource",
                    resource=str(dest),
                    detail="Daily Skill is missing",
                    next_step="run Daily install.sh --target all, then rerun --phase verify",
                )
            actual = canonical_tree_digest(dest)
            if actual != row["tree_sha256"]:
                raise CutoverError(
                    "digest-mismatch",
                    resource=str(dest),
                    detail=f"expected {row['tree_sha256']} actual {actual}",
                    next_step="reinstall Daily from the pinned checkout, then rerun --phase verify",
                )


def _verify_absent_old(home: Path, targets: tuple[str, ...]) -> None:
    for target in targets:
        skills = home / _SKILL_REL[target]
        if skills.is_dir():
            for child in _iter_dir_children(skills):
                if child.name in _FORBIDDEN_SKILL_NAMES:
                    raise CutoverError(
                        "residue",
                        resource=str(child),
                        detail="old org-managed skill still present",
                        next_step="rerun --phase remove --apply, then Base and Daily install.sh",
                    )
        hook = home / _HOOK_REL[target] / "post_compact.sh"
        if hook.exists() or hook.is_symlink():
            raise CutoverError(
                "residue",
                resource=str(hook),
                detail="old org-managed hook still present",
                next_step="rerun --phase remove --apply, then Base and Daily install.sh",
            )
    for rel in TEAM_SUPPORT_TREES:
        path = home / rel
        if path.exists() or path.is_symlink():
            raise CutoverError(
                "residue",
                resource=str(path),
                detail="team support tree still present",
                next_step="rerun --phase remove --apply",
            )


def _iter_dir_children(root: Path) -> list[Path]:
    deadline = time.monotonic() + _FS_WALK_TIMEOUT_SEC
    children: list[Path] = []
    with os.scandir(root) as entries:
        for entry in entries:
            if time.monotonic() > deadline:
                raise TimeoutError(f"fs walk timed out: {root}")
            children.append(Path(entry.path))
    return sorted(children)


def _verify_structured(home: Path) -> None:
    config = home / ".codex" / "config.toml"
    if config.is_file():
        text = config.read_text(encoding="utf-8")
        for section in _TEAM_AGENT_MANAGED:
            if f"[{section}]" in text:
                raise CutoverError(
                    "residue",
                    resource=f"{config}#{section}",
                    detail="team Codex agent section still present",
                    next_step="rerun --phase remove --apply",
                )
    for rel in (Path(".claude") / "settings.json", Path(".codex") / "hooks.json"):
        path = home / rel
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CutoverError(
                "structured-corrupt",
                resource=str(path),
                detail=str(exc),
                next_step="repair the structured config then rerun --phase verify",
            ) from exc
        hooks = data.get("hooks") if isinstance(data, dict) else None
        if not isinstance(hooks, dict):
            continue
        for event, items in hooks.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if _is_old_managed_hook(item):
                    raise CutoverError(
                        "residue",
                        resource=f"{path}#{event}",
                        detail="old-managed hook identity still present",
                        next_step="rerun --phase remove --apply",
                    )


def _verify_manifests(home: Path, targets: tuple[str, ...]) -> None:
    state = Path(os.environ.get("SKILL_REPO_STATE_ROOT") or (home / ".local" / "state" / "skill-repos"))
    team = state / "team-skills"
    if team.exists() or team.is_symlink():
        raise CutoverError(
            "residue",
            resource=str(team),
            detail="team-skills state is present",
            next_step="do not install Team; remove the team-skills state root and rerun verify",
        )
    for repo_id in ("base-config", "daily-skills"):
        for target in targets:
            path = state / repo_id / target / "installed.json"
            if not path.is_file():
                raise CutoverError(
                    "missing-manifest",
                    resource=str(path),
                    detail=f"{repo_id} {target} manifest missing",
                    next_step=f"run {repo_id} install.sh --target {target}, then rerun --phase verify",
                )
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise CutoverError(
                    "manifest-unreadable",
                    resource=str(path),
                    detail=str(exc),
                    next_step="repair installed.json then rerun --phase verify",
                ) from exc
            if not isinstance(payload, dict) or payload.get("repo_id") != repo_id:
                raise CutoverError(
                    "owner-mismatch",
                    resource=str(path),
                    detail=f"expected repo_id {repo_id}",
                    next_step="remove the mismatched installed.json and reinstall",
                )


def _phase_verify(
    *,
    home: Path,
    base: Path,
    daily: Path,
    target: str,
    apply: bool,
) -> int:
    targets = _selected_targets(target)
    _verify_manifests(home, targets)
    _verify_base(home, base, targets)
    _verify_daily(home, daily, targets)
    _verify_absent_old(home, targets)
    _verify_structured(home)
    _verify_preserve(home)
    if apply:
        _write_json(
            _verify_ok_path(home),
            {"status": "ok", "home": str(home), "targets": list(targets)},
        )
    _emit({"phase": "verify", "status": "ok", "legacy_state": str(home / ".org-skills-state")})
    return 0


def _phase_retire(*, home: Path, apply: bool) -> int:
    state = home / ".org-skills-state"
    meta = _work_dir(home)
    sentinel = _verify_ok_path(home)
    if not sentinel.is_file():
        raise CutoverError(
            "verify-required",
            resource=str(sentinel),
            detail="retire-legacy-state requires a successful --phase verify --apply",
            next_step="run --phase verify --apply, then rerun --phase retire-legacy-state --apply",
        )
    if not apply:
        _emit(
            {
                "phase": "retire-legacy-state",
                "status": "ready",
                "would_delete": [str(state), str(meta)],
            }
        )
        return 0
    if state.exists() or state.is_symlink():
        if state.is_symlink() or state.is_file():
            state.unlink()
        else:
            shutil.rmtree(state)
    if meta.exists():
        shutil.rmtree(meta)
    _emit({"phase": "retire-legacy-state", "status": "ok"})
    return 0


def run(argv: Sequence[str] | None = None) -> int:
    args = parse_args(list(argv if argv is not None else sys.argv[1:]))
    os.environ.pop("ORG_STATE_ROOT", None)
    if args.apply and args.phase is None:
        raise CutoverError(
            "apply-without-phase",
            detail="--apply without --phase is forbidden",
            next_step="rerun with --phase remove|verify|retire-legacy-state",
        )
    if args.apply and args.dry_run:
        raise CutoverError(
            "usage",
            detail="pass only one of --dry-run or --apply",
            next_step="rerun with either --dry-run or --apply",
        )
    if not args.apply and not args.dry_run:
        raise CutoverError(
            "usage",
            detail="pass --dry-run or --apply",
            next_step="rerun with --dry-run or --apply",
        )
    home = Path(args.home or os.environ.get("HOME") or str(Path.home())).expanduser()
    if not home.is_absolute():
        home = home.resolve()
    os.environ["HOME"] = str(home)
    os.environ["SKILL_REPO_STATE_ROOT"] = str(home / ".local" / "state" / "skill-repos")
    phase = args.phase or "remove"
    base = Path(args.base).expanduser().resolve() if args.base else None
    daily = Path(args.daily).expanduser().resolve() if args.daily else None
    if phase in {"remove", "verify"}:
        if base is None or daily is None:
            raise CutoverError(
                "usage",
                detail="--base and --daily are required for remove/verify",
                next_step="pass --base and --daily checkout paths",
            )
        _assert_checkout(base, "base")
        _assert_checkout(daily, "daily")
    if phase == "remove":
        return _phase_remove(
            home=home,
            target=args.target,
            apply=bool(args.apply),
            accept_plan=args.accept_plan,
        )
    if phase == "verify":
        if base is None or daily is None:
            raise CutoverError(
                "usage",
                detail="--base and --daily are required for verify",
                next_step="pass --base and --daily checkout paths",
            )
        return _phase_verify(
            home=home,
            base=base,
            daily=daily,
            target=args.target,
            apply=bool(args.apply),
        )
    return _phase_retire(home=home, apply=bool(args.apply))


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(argv)
    except CutoverError as exc:
        print(exc.format(), file=sys.stderr)
        return 1
    except ApplyBlockedError as exc:
        print(
            CutoverError(
                "conflict",
                detail=str(exc),
                next_step="resolve CONFLICT then rerun --phase remove --dry-run",
            ).format(),
            file=sys.stderr,
        )
        return 1
    except TimeoutError as exc:
        print(
            CutoverError(
                "timeout",
                detail=str(exc),
                next_step="inspect the filesystem and rerun",
            ).format(),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
