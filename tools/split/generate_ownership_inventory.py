#!/usr/bin/env python3
"""Scan live source roots and freeze repository-split ownership."""

from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from tools.split.ownership_allowlists import (
    ACTION_DELETE,
    BASE_FILES,
    GRILL_OBSIDIAN_SKILLS,
    MISSING_FROM_GIT_FETCH_IN_PLAN_2,
    OUT_OF_SCOPE_PATHS,
    REJECTED_SKILLS,
    REPO_BASE,
    REPO_DAILY,
    REPO_PERSONAL,
    REPO_TEAM,
    STALE_RUNTIME_TRACES,
    is_rejected,
    is_stale_trace,
    skill_repo,
)

EDGE_HARD = "hard"
EDGE_OPTIONAL = "optional"
EDGE_TEST_ONLY = "test-only"
EDGE_DOCUMENTATION_ONLY = "documentation-only"
EDGE_DELETE = "delete"
NON_HARD_EDGE_KINDS = {
    EDGE_OPTIONAL,
    EDGE_TEST_ONLY,
    EDGE_DOCUMENTATION_ONLY,
    EDGE_DELETE,
}

# Classification for live cross-repo Skill name hits. Scanner still has to find the hit.
KNOWN_CROSS_REPO_EDGES: dict[tuple[str, str], str] = {
    ("fix", "systematic-debugging"): EDGE_HARD,
    ("grill-me", "grilling"): EDGE_HARD,
    ("grill-with-docs", "grilling"): EDGE_HARD,
    ("grill-with-docs", "domain-modeling"): EDGE_HARD,
    ("qa", "webapp-testing"): EDGE_OPTIONAL,
    ("skill-quality-audit", "brainstorming"): EDGE_DOCUMENTATION_ONLY,
}

LEDGER_FILES = ("findings.md", "progress.md", "task_plan.md")
INBOUND_REF_SUFFIXES = {".py", ".sh", ".json", ".yaml", ".yml", ".md"}
SKIP_CROSS_REPO_PARTS = {
    "vendor",
    "node_modules",
    ".git",
    "__pycache__",
}
PRINTF_NAME_RE = re.compile(r'"([a-z0-9][a-z0-9_-]*)"', re.IGNORECASE)
SOURCE_KEY_RE = re.compile(r"^  ([A-Za-z0-9_]+):\s*$", re.MULTILINE)


class OwnershipError(Exception):
    """Raised when scanned atoms are unmapped, duplicated, or unclassified."""


@dataclass
class Inventory:
    by_repo: dict[str, dict[str, list[str]]]
    present_skill_names: set[str]
    unmapped: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    delete_from_active_head: list[str] = field(default_factory=list)
    prune_by_inbound_ref: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    non_installable: list[str] = field(default_factory=list)
    non_hard_edges: dict[tuple[str, str], str] = field(default_factory=dict)
    missing_from_git: list[str] = field(default_factory=list)
    missing_status: dict[str, str] = field(default_factory=dict)
    hard_edges: dict[tuple[str, str], str] = field(default_factory=dict)
    unclassified_edges: list[str] = field(default_factory=list)


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _is_git_worktree(root: Path) -> bool:
    return (root / ".git").exists()


def _git_ls_files(root: Path, *paths: str) -> list[str]:
    if not _is_git_worktree(root):
        return []
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--", *paths],
        capture_output=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        return []
    return [item for item in completed.stdout.decode("utf-8").split("\0") if item]


def _record(bucket: dict[str, list[str]], atom: str, owner: str) -> None:
    bucket.setdefault(atom, []).append(owner)


def _skill_name_pattern(names: Iterable[str]) -> re.Pattern[str] | None:
    distinctive = [name for name in names if "-" in name or name in {"brainstorming", "grilling"}]
    if not distinctive:
        return None
    distinctive = sorted(set(distinctive), key=len, reverse=True)
    return re.compile(r"(?<![A-Za-z0-9_-])(" + "|".join(re.escape(n) for n in distinctive) + r")(?![A-Za-z0-9_-])")


def _iter_files(base: Path) -> list[Path]:
    if not base.exists():
        return []
    files: list[Path] = []
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix == ".log":
            continue
        files.append(path)
    return files


def _load_yaml_mapping(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        yaml = None
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text) or {}
        if isinstance(data, dict):
            return data
        return {}
    sources: dict[str, dict] = {}
    for match in SOURCE_KEY_RE.finditer(text):
        sources[match.group(1)] = {}
    return {"sources": sources}


def _source_scope_owners(root: Path, entry: object) -> set[str]:
    if not isinstance(entry, dict):
        return set()
    scope = entry.get("scope") or []
    if not isinstance(scope, list):
        return set()
    owners: set[str] = set()
    for item in scope:
        if not isinstance(item, str) or not item.strip():
            continue
        rel = item.strip()
        path = root / rel
        name = Path(rel).name
        names: list[str] = []
        if name == "skills" or rel.endswith("/skills"):
            if path.is_dir():
                names.extend(
                    child.name
                    for child in path.iterdir()
                    if child.is_dir() and not child.name.startswith(".")
                )
        else:
            names.append(name)
            if path.is_dir() and not (path / "SKILL.md").is_file():
                names.extend(
                    child.name
                    for child in path.iterdir()
                    if child.is_dir() and (child / "SKILL.md").is_file()
                )
        for skill_name in names:
            owner = _owner_or_delete(skill_name)
            if owner is not None:
                owners.add(owner)
    return owners


def _parse_install_sh_selected(install_sh: Path) -> set[str]:
    if not install_sh.is_file():
        return set()
    text = install_sh.read_text(encoding="utf-8")
    selected: set[str] = set()
    for func in (
        "community_anthropic_selected",
        "community_anthropic_adapter_selected",
        "community_vercel_selected",
        "community_alchaincyf_selected",
        "community_nextlevelbuilder_selected",
        "community_panniantong_selected",
        "community_skills_sh_selected",
        "community_skills_sh_adapter_selected",
        "claude_only_skills",
    ):
        match = re.search(
            rf"^{re.escape(func)}\(\) \{{(.*?)^\}}",
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
        if not match:
            continue
        selected.update(PRINTF_NAME_RE.findall(match.group(1)))
    return selected


def _has_inbound_ref(root: Path, filename: str) -> bool:
    token = re.compile(
        rf"(^|[^A-Za-z0-9._-]){re.escape(filename)}([^A-Za-z0-9._-]|$)"
    )
    # Classification tests name the ledgers; they are not consumers of the files.
    skip_names = {"test-ownership-inventory.py", "generate_ownership_inventory.py"}
    for search in (root / "tests", root / "contracts"):
        if not search.exists():
            continue
        for path in search.rglob("*"):
            if not path.is_file() or path.suffix not in INBOUND_REF_SUFFIXES:
                continue
            if path.name in skip_names:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if token.search(text):
                return True
    return False


def _owner_or_delete(name: str) -> str | None:
    if is_rejected(name) or is_stale_trace(name):
        return ACTION_DELETE
    return skill_repo(name)


def _non_installable_dir(name: str) -> bool:
    return name == "lib" or name.endswith("-workspace")


def _cross_repo_kind_for_path(rel_path: str, caller: str, callee: str) -> str | None:
    known = KNOWN_CROSS_REPO_EDGES.get((caller, callee))
    if known:
        return known
    if is_rejected(callee) or is_stale_trace(callee):
        return EDGE_DELETE
    parts = Path(rel_path).parts
    if "evals" in parts or rel_path.startswith("tests/") or rel_path.startswith("tools/eval/"):
        return EDGE_TEST_ONLY
    if rel_path.startswith("docs/"):
        return EDGE_DOCUMENTATION_ONLY
    return None


def _scan_cross_repo_edges(
    root: Path,
    skill_dirs: list[tuple[str, Path]],
    present_names: set[str],
) -> tuple[dict[tuple[str, str], str], dict[tuple[str, str], str], list[str]]:
    scan_names = set(present_names) | set(GRILL_OBSIDIAN_SKILLS) | set(REJECTED_SKILLS)
    pattern = _skill_name_pattern(scan_names)
    hard: dict[tuple[str, str], str] = {}
    non_hard: dict[tuple[str, str], str] = {}
    unclassified: list[str] = []
    if pattern is None:
        return hard, non_hard, unclassified

    files: list[tuple[str, Path]] = []
    for caller, skill_dir in skill_dirs:
        for rel_dir in ("", "references", "projections", "evals"):
            base = skill_dir if rel_dir == "" else skill_dir / rel_dir
            if rel_dir == "":
                skill_md = skill_dir / "SKILL.md"
                if skill_md.is_file():
                    files.append((caller, skill_md))
                continue
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if path.is_file() and path.suffix in {".md", ".json"}:
                    files.append((caller, path))

    for caller, path in files:
        caller_repo = skill_repo(caller)
        if caller_repo is None:
            continue
        rel = _rel(root, path)
        if any(part in SKIP_CROSS_REPO_PARTS for part in Path(rel).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in pattern.finditer(text):
            callee = match.group(1)
            if callee == caller:
                continue
            callee_repo = skill_repo(callee)
            if callee_repo is None and not is_rejected(callee) and not is_stale_trace(callee):
                continue
            if callee_repo == caller_repo:
                continue
            key = (caller, callee)
            kind = _cross_repo_kind_for_path(rel, caller, callee)
            if kind is None:
                unclassified.append(f"{caller}->{callee} in {rel}")
                continue
            if kind == EDGE_HARD:
                hard[key] = kind
            elif kind in NON_HARD_EDGE_KINDS:
                non_hard[key] = kind
    return hard, non_hard, unclassified


def scan_ownership(repo_root: Path) -> Inventory:
    root = repo_root.resolve()
    mappings: dict[str, list[str]] = {}
    present: set[str] = set()
    skill_dirs: list[tuple[str, Path]] = []
    by_repo_skills: dict[str, set[str]] = {
        REPO_DAILY: set(),
        REPO_PERSONAL: set(),
        REPO_TEAM: set(),
    }
    non_installable: list[str] = []
    delete_from_active_head: list[str] = []
    prune_by_inbound_ref: list[str] = []
    out_of_scope: list[str] = []
    unmapped: list[str] = []

    shared_skills = root / "shared" / "skills"
    if shared_skills.is_dir():
        for entry in sorted(shared_skills.iterdir()):
            if not entry.is_dir():
                continue
            rel_dir = _rel(root, entry)
            if _non_installable_dir(entry.name):
                non_installable.append(rel_dir)
                _record(mappings, f"non-installable:{rel_dir}", REPO_TEAM)
                continue
            skill_md = entry / "SKILL.md"
            if skill_md.is_file():
                skill_dirs.append((entry.name, entry))

    for pattern in ("claude/skills/*/SKILL.md", "community/*/skills/*/SKILL.md"):
        for skill_md in sorted(root.glob(pattern)):
            skill_dirs.append((skill_md.parent.name, skill_md.parent))

    name_roots: dict[str, list[str]] = defaultdict(list)
    for name, skill_dir in skill_dirs:
        rel_root = _rel(root, skill_dir)
        name_roots[name].append(rel_root)
        present.add(name)
        owner = _owner_or_delete(name)
        atom = f"skill-name:{name}"
        if owner is None:
            unmapped.append(name)
            _record(mappings, atom, "unmapped")
            continue
        if is_rejected(name):
            unmapped.append(name)
            _record(mappings, atom, ACTION_DELETE)
            continue
        _record(mappings, atom, owner)
        _record(mappings, f"skill-root:{rel_root}", owner)
        if owner in by_repo_skills:
            by_repo_skills[owner].add(name)

    for name, roots in name_roots.items():
        if len(roots) > 1:
            for _rel_root in roots:
                _record(mappings, f"skill-name:{name}", "duplicate-root")

    for adapter in sorted(root.glob("community/*/codex/skills/*")):
        if not adapter.is_dir():
            continue
        rel_adapter = _rel(root, adapter)
        owner = _owner_or_delete(adapter.name)
        atom = f"codex-adapter:{rel_adapter}"
        if owner is None:
            unmapped.append(rel_adapter)
            _record(mappings, atom, "unmapped")
        else:
            _record(mappings, atom, owner)

    missing_from_git: list[str] = []
    missing_status: dict[str, str] = {}
    for name in GRILL_OBSIDIAN_SKILLS:
        if name in present:
            continue
        missing_from_git.append(name)
        missing_status[name] = MISSING_FROM_GIT_FETCH_IN_PLAN_2
        _record(mappings, f"skill-name:{name}", REPO_DAILY)
        by_repo_skills[REPO_DAILY].add(name)

    for name in REJECTED_SKILLS:
        _record(mappings, f"delete-skill:{name}", ACTION_DELETE)
    for name in STALE_RUNTIME_TRACES:
        _record(mappings, f"delete-trace:{name}", ACTION_DELETE)

    assistant = root / "shared" / "assistant.md"
    if assistant.is_file():
        if "assistant.md" in BASE_FILES:
            _record(mappings, "base-file:assistant.md", REPO_BASE)
        else:
            unmapped.append("shared/assistant.md")
            _record(mappings, "base-file:assistant.md", "unmapped")
    for folder, prefix in (("rules", "rules"), ("reference", "reference")):
        base = root / "shared" / folder
        if not base.is_dir():
            continue
        for path in sorted(base.glob("*.md")):
            spec_rel = f"{prefix}/{path.name}"
            atom = f"base-file:{spec_rel}"
            if spec_rel in BASE_FILES:
                _record(mappings, atom, REPO_BASE)
            else:
                unmapped.append(_rel(root, path))
                _record(mappings, atom, "unmapped")

    for hook_root in (root / "shared" / "hooks", root / "claude" / "hooks"):
        for path in _iter_files(hook_root):
            rel = _rel(root, path)
            _record(mappings, f"hook:{rel}", REPO_TEAM)

    agents_root = root / "shared" / "agents"
    for path in _iter_files(agents_root):
        rel = _rel(root, path)
        _record(mappings, f"agent:{rel}", REPO_TEAM)

    protocols_root = root / "shared" / "protocols"
    for path in _iter_files(protocols_root):
        rel = _rel(root, path)
        _record(mappings, f"protocol:{rel}", REPO_TEAM)

    sources_path = root / "community" / "SOURCES.yaml"
    if sources_path.is_file():
        data = _load_yaml_mapping(sources_path)
        sources = data.get("sources") or {}
        if isinstance(sources, dict):
            for key, entry in sources.items():
                atom = f"source-key:{key}"
                owners = _source_scope_owners(root, entry)
                if len(owners) == 1:
                    _record(mappings, atom, next(iter(owners)))
                elif not owners:
                    unmapped.append(f"source-key:{key}")
                    _record(mappings, atom, "unmapped")
                else:
                    for owner in sorted(owners):
                        _record(mappings, atom, owner)

    surface_path = root / "contracts" / "skill-runtime-surface.json"
    if surface_path.is_file():
        payload = json.loads(surface_path.read_text(encoding="utf-8"))
        skills = payload.get("skills") or {}
        if isinstance(skills, dict):
            for key in skills:
                atom = f"surface-key:{key}"
                owner = _owner_or_delete(key)
                if owner is None:
                    unmapped.append(f"surface-key:{key}")
                    _record(mappings, atom, "unmapped")
                else:
                    _record(mappings, atom, owner)

    selected = _parse_install_sh_selected(root / "install.sh")
    superpowers = root / "community" / "superpowers" / "skills"
    if superpowers.is_dir():
        selected.update(path.name for path in superpowers.iterdir() if path.is_dir())
    if shared_skills.is_dir():
        for entry in shared_skills.iterdir():
            if entry.is_dir() and (entry / "SKILL.md").is_file() and not _non_installable_dir(entry.name):
                selected.add(entry.name)
    claude_skills = root / "claude" / "skills"
    if claude_skills.is_dir():
        selected.update(
            entry.name
            for entry in claude_skills.iterdir()
            if entry.is_dir() and (entry / "SKILL.md").is_file()
        )
    for name in sorted(selected):
        atom = f"installer-name:{name}"
        owner = _owner_or_delete(name)
        if owner is None:
            unmapped.append(f"installer-name:{name}")
            _record(mappings, atom, "unmapped")
        else:
            _record(mappings, atom, owner)

    tracked_superpowers = _git_ls_files(root, ".superpowers")
    if tracked_superpowers:
        delete_from_active_head.append(".superpowers/")
        _record(mappings, "generated:.superpowers/", ACTION_DELETE)

    darwin_cards = ".claude/skills/darwin-skill/cards/"
    darwin_tsv = ".claude/skills/darwin-skill/results.tsv"
    tracked_darwin = _git_ls_files(root, ".claude/skills/darwin-skill")
    if tracked_darwin or (root / darwin_cards).exists() or (root / darwin_tsv).exists():
        delete_from_active_head.append(darwin_cards)
        _record(mappings, f"generated:{darwin_cards}", ACTION_DELETE)
        if any(path.endswith("results.tsv") for path in tracked_darwin) or (root / darwin_tsv).is_file():
            delete_from_active_head.append(darwin_tsv)
            _record(mappings, f"generated:{darwin_tsv}", ACTION_DELETE)

    for filename in LEDGER_FILES:
        path = root / filename
        if path.is_file() and not _has_inbound_ref(root, filename):
            delete_from_active_head.append(filename)
            _record(mappings, f"generated:{filename}", ACTION_DELETE)

    eval_results = root / "tools" / "eval" / "results"
    if eval_results.exists():
        prune_by_inbound_ref.append("tools/eval/results/")
        _record(mappings, "generated:tools/eval/results/", "PRUNE_BY_INBOUND_REF")

    gitignore = root / ".gitignore"
    gitignore_text = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    for rel_path in OUT_OF_SCOPE_PATHS:
        exists = (root / rel_path.rstrip("/")).exists()
        if exists or rel_path in gitignore_text:
            out_of_scope.append(rel_path)
            _record(mappings, f"out-of-scope:{rel_path}", "OUT_OF_SCOPE")

    hard_edges, non_hard_edges, unclassified = _scan_cross_repo_edges(root, skill_dirs, present)
    for key, kind in hard_edges.items():
        _record(mappings, f"edge:{key[0]}->{key[1]}", kind)
    for key, kind in non_hard_edges.items():
        _record(mappings, f"edge:{key[0]}->{key[1]}", kind)
    for item in unclassified:
        unmapped.append(item)
        _record(mappings, f"edge:{item}", "unmapped")

    duplicates = sorted(
        {
            atom.split(":", 1)[-1] if atom.startswith("skill-name:") else atom
            for atom, owners in mappings.items()
            if len(owners) > 1
        }
    )
    # Duplicate skill roots already force skill-name atoms to have extra owners.
    skill_dupes = sorted(name for name, roots in name_roots.items() if len(roots) > 1)
    if skill_dupes:
        duplicates = sorted(set(duplicates) | set(skill_dupes))

    unmapped = sorted(set(unmapped))
    return Inventory(
        by_repo={
            REPO_BASE: {"skills": [], "files": list(BASE_FILES)},
            REPO_DAILY: {"skills": sorted(by_repo_skills[REPO_DAILY])},
            REPO_PERSONAL: {"skills": sorted(by_repo_skills[REPO_PERSONAL])},
            REPO_TEAM: {"skills": sorted(by_repo_skills[REPO_TEAM])},
        },
        present_skill_names=present,
        unmapped=unmapped,
        duplicates=duplicates,
        delete_from_active_head=delete_from_active_head,
        prune_by_inbound_ref=prune_by_inbound_ref,
        out_of_scope=out_of_scope,
        non_installable=non_installable,
        non_hard_edges=non_hard_edges,
        missing_from_git=missing_from_git,
        missing_status=missing_status,
        hard_edges=hard_edges,
        unclassified_edges=unclassified,
    )


def _fmt_list(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def assert_complete(inventory: Inventory) -> None:
    if inventory.duplicates:
        raise OwnershipError(f"duplicate mapping: {inventory.duplicates}")
    if inventory.unmapped:
        raise OwnershipError(f"unmapped atoms: {inventory.unmapped}")
    if inventory.unclassified_edges:
        raise OwnershipError(f"unmapped unclassified cross-repo hits: {inventory.unclassified_edges}")
    present_rejected = sorted(set(REJECTED_SKILLS) & set(inventory.present_skill_names))
    if present_rejected:
        raise OwnershipError(f"rejected skills present: {present_rejected}")
    for name in GRILL_OBSIDIAN_SKILLS:
        if name in inventory.present_skill_names:
            continue
        if inventory.missing_status.get(name) != MISSING_FROM_GIT_FETCH_IN_PLAN_2:
            raise OwnershipError(
                f"unmapped missing skill {name} without {MISSING_FROM_GIT_FETCH_IN_PLAN_2}"
            )
    print(
        "unmapped="
        + _fmt_list(inventory.unmapped)
        + " duplicates="
        + _fmt_list(inventory.duplicates)
        + " missing_from_git="
        + _fmt_list(inventory.missing_from_git)
    )


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    inventory = scan_ownership(root)
    assert_complete(inventory)


if __name__ == "__main__":
    main()
