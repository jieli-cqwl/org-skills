"""Apply one-time runtime cutover removals. Journal metadata only; never restore baselines."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable

from tools.install.tree_digest import canonical_tree_digest
from tools.migration.action_plan import ActionClass, ActionPlan
from tools.migration.legacy_inventory import PRESERVE_SETTINGS_MARKERS

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
    return


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
