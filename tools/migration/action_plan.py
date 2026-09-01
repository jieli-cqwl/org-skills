"""Classify one-time runtime cutover actions. Classification only; no HOME mutation."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Iterable, Literal, Mapping

from tools.install.tree_digest import canonical_tree_digest
from tools.migration import legacy_inventory as inventory


class ActionClass(str, Enum):
    REMOVE_FOR_FRESH_INSTALL = "REMOVE_FOR_FRESH_INSTALL"
    REMOVE_OLD_ONLY = "REMOVE_OLD_ONLY"
    REMOVE_EXPLICIT_DELETE = "REMOVE_EXPLICIT_DELETE"
    PRESERVE_EXTERNAL = "PRESERVE_EXTERNAL"
    DELETE_LEGACY_STATE = "DELETE_LEGACY_STATE"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class Action:
    path: str
    cls: ActionClass
    reason: str = ""


@dataclass(frozen=True)
class ActionPlan:
    actions: tuple[Action, ...]
    status: Literal["ready", "blocked"]
    preflight_hash: str
    preserve_digests: dict[str, str]


def build_action_plan(
    home: Path,
    legacy_tag_root: Path | str | None = None,
    *,
    pre_split_tag: str | None = None,
    expected_bytes: Mapping[str, bytes] | None = None,
) -> ActionPlan:
    home = Path(home)
    tag = pre_split_tag or (
        legacy_tag_root
        if isinstance(legacy_tag_root, str)
        else inventory.PRE_SPLIT_TAG
    )
    expected = dict(expected_bytes or {})
    if isinstance(legacy_tag_root, Path):
        expected = {**_expected_from_tag_root(home, legacy_tag_root), **expected}

    actions = _classify_runtime(home)
    actions = _apply_unexplained_drift(actions, expected)
    actions = tuple(sorted(actions, key=lambda item: item.path))
    preserve_digests = {
        action.path: canonical_tree_digest(Path(action.path))
        for action in actions
        if action.cls is ActionClass.PRESERVE_EXTERNAL and Path(action.path).exists()
    }
    status: Literal["ready", "blocked"] = (
        "blocked" if any(action.cls is ActionClass.CONFLICT for action in actions) else "ready"
    )
    preflight_hash = _preflight_hash(tag, actions, preserve_digests)
    return ActionPlan(
        actions=actions,
        status=status,
        preflight_hash=preflight_hash,
        preserve_digests=preserve_digests,
    )


def _classify_runtime(home: Path) -> list[Action]:
    claimed = {str(path) for path in _legacy_manifest_paths(home)}
    actions: dict[str, Action] = {}

    def record(path: Path, cls: ActionClass, reason: str) -> None:
        actions[str(path)] = Action(path=str(path), cls=cls, reason=reason)

    for rel_root in inventory.SKILL_ROOTS:
        root = home / rel_root
        if not root.is_dir():
            continue
        for child in _iter_dir_children(root):
            relative = child.relative_to(home)
            if inventory.is_preserve_relative(relative):
                record(child, ActionClass.PRESERVE_EXTERNAL, "hard-coded preserve set")
                continue
            named = inventory.classify_skill_name(child.name)
            if named is not None:
                record(child, ActionClass(named), f"skill inventory:{child.name}")
                continue
            if str(child) in claimed:
                record(child, ActionClass.CONFLICT, "unmapped legacy-manifest path")
                continue
            record(child, ActionClass.PRESERVE_EXTERNAL, "unowned runtime path")

    for rel_root in inventory.HOOK_ROOTS:
        root = home / rel_root
        if not root.exists():
            continue
        for child in _iter_dir_children(root):
            relative = child.relative_to(home)
            if inventory.is_preserve_relative(relative):
                record(child, ActionClass.PRESERVE_EXTERNAL, "hard-coded preserve set")
            else:
                record(child, ActionClass.REMOVE_OLD_ONLY, "team-managed hook")

    for rel in inventory.BASE_RUNTIME_PATHS:
        path = home / rel
        if path.exists():
            record(path, ActionClass.REMOVE_FOR_FRESH_INSTALL, "base destination")

    state_root = home / inventory.STATE_DIRNAME
    if state_root.exists():
        for path in _iter_files(state_root):
            relative = path.relative_to(state_root)
            if inventory.is_known_legacy_state(relative):
                record(path, ActionClass.DELETE_LEGACY_STATE, "known legacy state")
            else:
                record(path, ActionClass.CONFLICT, "unexpected legacy state")
    return list(actions.values())


def _apply_unexplained_drift(
    actions: Iterable[Action], expected_bytes: Mapping[str, bytes]
) -> list[Action]:
    # Legacy manifests are ownership clues, not content proof. Dirty fingerprint is not an exception.
    drifted: list[str] = []
    for path_str, expected in expected_bytes.items():
        path = Path(path_str)
        actual = path.read_bytes() if path.is_file() else None
        if actual != expected:
            drifted.append(path_str)
    if not drifted:
        return list(actions)

    updated: list[Action] = []
    seen: set[str] = set()
    for action in actions:
        if _covers_any(action.path, drifted):
            updated.append(replace(action, cls=ActionClass.CONFLICT, reason="unexplained drift"))
        else:
            updated.append(action)
        seen.add(action.path)
    for path_str in drifted:
        if path_str not in seen:
            updated.append(Action(path=path_str, cls=ActionClass.CONFLICT, reason="unexplained drift"))
            seen.add(path_str)
    return updated


def _covers_any(action_path: str, drifted: Iterable[str]) -> bool:
    prefix = action_path.rstrip("/") + "/"
    for path_str in drifted:
        if path_str == action_path or path_str.startswith(prefix):
            return True
        drifted_prefix = path_str.rstrip("/") + "/"
        if action_path.startswith(drifted_prefix):
            return True
    return False


def _legacy_manifest_paths(home: Path) -> set[Path]:
    claimed: set[Path] = set()
    state_root = home / inventory.STATE_DIRNAME
    if not state_root.exists():
        return claimed
    for path in _iter_files(state_root):
        if path.name != "installed-manifest":
            continue
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            raw = line.strip()
            if not raw:
                continue
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = home / candidate
            claimed.add(candidate)
    return claimed


def _expected_from_tag_root(home: Path, tag_root: Path) -> dict[str, bytes]:
    expected: dict[str, bytes] = {}
    if not tag_root.is_dir():
        return expected
    for path in _iter_files(tag_root):
        relative = path.relative_to(tag_root)
        expected[str(home / relative)] = path.read_bytes()
    return expected


def _iter_dir_children(root: Path) -> list[Path]:
    children: list[Path] = []
    with os.scandir(root) as entries:
        for entry in entries:
            children.append(Path(entry.path))
    return sorted(children)


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            files.append(Path(dirpath) / name)
    return files


def _preflight_hash(
    tag: str, actions: tuple[Action, ...] | list[Action], preserve_digests: Mapping[str, str]
) -> str:
    payload = {
        "pre_split_tag": tag,
        "actions": [{"path": action.path, "cls": action.cls.value, "reason": action.reason} for action in actions],
        "preserve_digests": dict(sorted(preserve_digests.items())),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
