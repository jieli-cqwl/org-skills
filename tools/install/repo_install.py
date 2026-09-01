from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.install.tree_digest import (  # noqa: E402
    FileRecord,
    canonical_tree_digest,
    canonical_tree_files,
)

REPO_ID = "team-skills"
BASE_REPO_ID = "base-config"
SCHEMA_VERSION = 1
TARGETS = ("claude", "codex")
TargetName = Literal["claude", "codex"]
RESOURCE_KIND = Literal["file", "tree", "symlink"]
_CHUNK_SIZE = 1024 * 1024
_MODE_BITS = {"0644": 0o644, "0755": 0o755}
_SURFACE_APPLY_TIMEOUT_SEC = 120
_TOOL_TIMEOUT_SEC = 60
_COPY_IGNORE_NAMES = {".DS_Store", "__pycache__"}
_PRUNE_DIR_NAMES = {"evals", "fixtures", "examples", "selves"}
CLAUDE_ONLY = {"code-review-fix", "doc-review-fix"}
SKILLS_REL = {
    "claude": Path(".claude") / "skills",
    "codex": Path(".agents") / "skills",
}
TARGET_DIRNAME = {"claude": ".claude", "codex": ".codex"}
BASE_ASSISTANT_NAME = {"claude": "CLAUDE.md", "codex": "AGENTS.md"}


@dataclass(frozen=True)
class Require:
    repo_id: str
    target: Literal["same"]
    resource_ids: tuple[str, ...]


@dataclass
class ResourcePlan:
    resource_id: str
    resource_root: Path
    kind: RESOURCE_KIND
    source_path: Path
    staged_path: Path
    files: list[FileRecord]
    tree_sha256: str


@dataclass
class InstallPlan:
    repo_id: str
    repo_version: str
    target: TargetName
    requires: list[Require]
    resources: list[ResourcePlan]
    structured_entries: list[dict[str, Any]] = field(default_factory=list)
    staging_dir: Path | None = None


class InstallError(Exception):
    def __init__(
        self,
        code: str,
        *,
        resource_id: str = "-",
        expected_digest: str = "-",
        actual_digest: str = "-",
        owner: str = REPO_ID,
        completed_targets: Sequence[str] = (),
        next_step: str,
        detail: str = "",
        target: str = "-",
    ) -> None:
        super().__init__(code)
        self.code = code
        self.resource_id = resource_id
        self.expected_digest = expected_digest
        self.actual_digest = actual_digest
        self.owner = owner
        self.completed_targets = tuple(completed_targets)
        self.next_step = next_step
        self.detail = detail
        self.target = target

    def with_completed(self, completed: Sequence[str]) -> InstallError:
        return InstallError(
            self.code,
            resource_id=self.resource_id,
            expected_digest=self.expected_digest,
            actual_digest=self.actual_digest,
            owner=self.owner,
            completed_targets=completed,
            next_step=self.next_step,
            detail=self.detail,
            target=self.target,
        )

    def format(self) -> str:
        completed = ",".join(self.completed_targets) if self.completed_targets else "-"
        lines = [
            f"error: {self.code}",
            f"resource_id: {self.resource_id}",
            f"expected_digest: {self.expected_digest}",
            f"actual_digest: {self.actual_digest}",
            f"owner: {self.owner}",
            f"target: {self.target}",
            f"completed_targets: {completed}",
            f"safe_next_step: {self.next_step}",
        ]
        if self.detail:
            lines.append(f"detail: {self.detail}")
        return "\n".join(lines)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install Team Skills, hooks, agents, and protocols.")
    parser.add_argument("--target", choices=(*TARGETS, "all"), required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    return parser.parse_args(argv)


def selected_targets(value: str) -> tuple[TargetName, ...]:
    if value == "all":
        return ("claude", "codex")
    if value == "claude":
        return ("claude",)
    if value == "codex":
        return ("codex",)
    raise InstallError(
        "usage",
        next_step="rerun with --target claude|codex|all",
        detail=f"unknown target {value}",
    )


def repo_version() -> str:
    path = REPO_ROOT / "VERSION"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise InstallError(
            "missing-version",
            next_step="restore VERSION in the Team checkout and rerun",
            detail=str(exc),
        ) from exc


def state_root() -> Path:
    env = os.environ.get("SKILL_REPO_STATE_ROOT")
    if env:
        return Path(env)
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg) / "skill-repos"
    return Path.home() / ".local" / "state" / "skill-repos"


def home_dir() -> Path:
    return Path.home()


def target_root(target: TargetName) -> Path:
    return home_dir() / TARGET_DIRNAME[target]


def skill_dest(name: str, target: TargetName) -> Path:
    return home_dir() / SKILLS_REL[target] / name


def python_launcher() -> str:
    found = shutil.which("python3")
    return found or sys.executable


def manifest_path(root: Path, target: TargetName) -> Path:
    return root / REPO_ID / target / "installed.json"


def journal_path(root: Path, target: TargetName) -> Path:
    return root / REPO_ID / target / ".in-progress.json"


def feature_state_path(root: Path) -> Path:
    return root / REPO_ID / "codex" / "codex-hooks-feature-state.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def lexists(path: Path) -> bool:
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False


def file_record_dict(rec: FileRecord) -> dict[str, Any]:
    return {
        "path": rec.path,
        "kind": rec.kind,
        "mode": rec.mode,
        "sha256": rec.sha256,
        "link_target": rec.link_target,
    }


def plan_to_manifest(plan: InstallPlan) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "repo_id": plan.repo_id,
        "repo_version": plan.repo_version,
        "target": plan.target,
        "requires": [
            {
                "repo_id": req.repo_id,
                "target": req.target,
                "resource_ids": list(req.resource_ids),
            }
            for req in plan.requires
        ],
        "resources": [
            {
                "resource_id": resource.resource_id,
                "resource_root": str(resource.resource_root),
                "kind": resource.kind,
                "tree_sha256": resource.tree_sha256,
                "files": [file_record_dict(rec) for rec in resource.files],
            }
            for resource in plan.resources
        ],
        "structured_entries": list(plan.structured_entries),
    }


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def atomic_replace(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dest)


def load_json_object(path: Path, *, owner: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(
            "manifest-unreadable",
            owner=owner,
            next_step=f"repair or remove {path} then rerun",
            detail=str(exc),
        ) from exc
    if not isinstance(payload, dict):
        raise InstallError(
            "manifest-unreadable",
            owner=owner,
            next_step=f"repair or remove {path} then rerun",
            detail="manifest is not a JSON object",
        )
    return payload


def load_own_manifest(root: Path, target: TargetName) -> dict[str, Any] | None:
    path = manifest_path(root, target)
    if not path.is_file():
        return None
    payload = load_json_object(path, owner=REPO_ID)
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise InstallError(
            "schema",
            owner=REPO_ID,
            target=target,
            next_step="export or remove the incompatible installed.json then rerun",
            detail=f"unsupported schema_version {payload.get('schema_version')!r}",
        )
    if payload.get("repo_id") != REPO_ID:
        raise InstallError(
            "owner-mismatch",
            owner=str(payload.get("repo_id") or "unknown"),
            target=target,
            next_step="do not reuse another repo's manifest path",
        )
    if payload.get("target") != target:
        raise InstallError(
            "target-mismatch",
            owner=REPO_ID,
            target=target,
            next_step="remove the mismatched installed.json then rerun",
        )
    resources = payload.get("resources")
    if not isinstance(resources, list):
        raise InstallError(
            "manifest-unreadable",
            owner=REPO_ID,
            target=target,
            next_step="repair installed.json then rerun",
            detail="resources must be a list",
        )
    return payload


def dest_for_record(resource: dict[str, Any], rec: dict[str, Any]) -> Path:
    root = Path(str(resource["resource_root"]))
    if resource.get("kind") == "file":
        return root
    return root / str(rec["path"])


def record_drift(resource: dict[str, Any]) -> tuple[str, str, str] | None:
    files = resource.get("files") or []
    if not isinstance(files, list) or not files:
        return (
            str(resource.get("resource_id") or "-"),
            str(resource.get("tree_sha256") or "-"),
            "missing-files",
        )
    for rec in files:
        if not isinstance(rec, dict):
            return str(resource.get("resource_id") or "-"), "-", "invalid-file-record"
        dest = dest_for_record(resource, rec)
        expected = str(rec.get("sha256") or rec.get("link_target") or "-")
        if not lexists(dest):
            return str(resource.get("resource_id") or "-"), expected, "missing"
        kind = rec.get("kind")
        if kind == "symlink":
            actual = os.readlink(dest)
            if actual != rec.get("link_target"):
                return str(resource.get("resource_id") or "-"), expected, actual
            continue
        if dest.is_symlink() or not dest.is_file():
            return str(resource.get("resource_id") or "-"), expected, "not-a-file"
        actual = sha256_file(dest)
        if actual != rec.get("sha256"):
            return str(resource.get("resource_id") or "-"), expected, actual
    return None


def owned_resources(manifest: dict[str, Any] | None) -> dict[Path, dict[str, Any]]:
    if not manifest:
        return {}
    owned: dict[Path, dict[str, Any]] = {}
    for resource in manifest.get("resources") or []:
        if not isinstance(resource, dict) or "resource_root" not in resource:
            raise InstallError(
                "manifest-unreadable",
                owner=REPO_ID,
                next_step="repair installed.json then rerun",
                detail="resource is missing resource_root",
            )
        owned[Path(str(resource["resource_root"]))] = resource
    return owned


def existing_digest(path: Path) -> str:
    if path.is_symlink():
        return os.readlink(path)
    if path.is_file():
        return sha256_file(path)
    if path.is_dir():
        try:
            return canonical_tree_digest(path)
        except (OSError, ValueError):
            return "exists"
    return "exists"


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    ignored = set()
    for name in names:
        if name in _COPY_IGNORE_NAMES or name.endswith(".pyc"):
            ignored.add(name)
    return ignored


def _parse_scalar(value: str) -> Any:
    if value in {"[]", ""}:
        return []
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        return value[1:-1]
    if value.isdigit():
        return int(value)
    return value


def parse_dependencies_yaml(text: str) -> dict[str, Any]:
    # Isolated HOME tests do not have PyYAML; keep a bounded parser for this contract.
    payload: dict[str, Any] = {}
    current_list: list[Any] | None = None
    current_item: dict[str, Any] | None = None
    nested_list_key: str | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if nested_list_key and current_item is not None and line.startswith("      - "):
            current_item.setdefault(nested_list_key, []).append(
                _parse_scalar(line.strip()[2:].strip())
            )
            continue
        if line.startswith("    ") and current_item is not None and ":" in line:
            key, value = line.strip().split(":", 1)
            key = key.strip()
            value = value.strip()
            if value == "":
                nested_list_key = key
                current_item[key] = []
            else:
                nested_list_key = None
                current_item[key] = _parse_scalar(value)
            continue
        if line.startswith("  - "):
            if current_list is None:
                raise InstallError(
                    "missing-dependencies",
                    owner=REPO_ID,
                    next_step="repair contracts/dependencies.yaml and rerun",
                    detail=f"list item without a list key: {line}",
                )
            current_item = {}
            current_list.append(current_item)
            nested_list_key = None
            rest = line[4:]
            if ":" in rest:
                key, value = rest.split(":", 1)
                current_item[key.strip()] = _parse_scalar(value.strip())
            continue
        if line.startswith(" ") or ":" not in line:
            raise InstallError(
                "missing-dependencies",
                owner=REPO_ID,
                next_step="repair contracts/dependencies.yaml and rerun",
                detail=f"unsupported dependencies.yaml line: {line}",
            )
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        nested_list_key = None
        current_item = None
        if value == "":
            current_list = []
            payload[key] = current_list
            continue
        current_list = None
        payload[key] = _parse_scalar(value)
    payload.setdefault("repo_requires", [])
    payload.setdefault("edges", [])
    payload.setdefault("optional_edges", [])
    return payload


def load_dependencies() -> dict[str, Any]:
    path = REPO_ROOT / "contracts" / "dependencies.yaml"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InstallError(
            "missing-dependencies",
            owner=REPO_ID,
            next_step="restore contracts/dependencies.yaml and rerun",
            detail=str(exc),
        ) from exc
    payload = parse_dependencies_yaml(text)
    if not isinstance(payload, dict):
        raise InstallError(
            "missing-dependencies",
            owner=REPO_ID,
            next_step="repair contracts/dependencies.yaml and rerun",
            detail="dependencies.yaml must be a mapping",
        )
    return payload


def base_requires() -> Require:
    data = load_dependencies()
    requires = data.get("repo_requires") or []
    if not isinstance(requires, list) or not requires:
        raise InstallError(
            "missing-dependencies",
            owner=REPO_ID,
            next_step="restore Team repo_requires for base-config and rerun",
        )
    first = requires[0]
    if not isinstance(first, dict) or first.get("repo_id") != BASE_REPO_ID:
        raise InstallError(
            "missing-dependencies",
            owner=BASE_REPO_ID,
            next_step="restore contracts/dependencies.yaml repo_requires[0] as base-config",
        )
    ids = first.get("resource_ids") or []
    if not isinstance(ids, list) or not ids:
        raise InstallError(
            "missing-dependencies",
            owner=BASE_REPO_ID,
            next_step="restore Base resource_ids in contracts/dependencies.yaml",
        )
    return Require(
        repo_id=BASE_REPO_ID,
        target="same",
        resource_ids=tuple(str(item) for item in ids),
    )


def check_skill_edge(caller: str, *, target: TargetName = "claude") -> None:
    data = load_dependencies()
    edges = data.get("edges") or []
    if not isinstance(edges, list):
        raise InstallError(
            "missing-dependencies",
            owner=REPO_ID,
            next_step="repair contracts/dependencies.yaml edges and rerun",
        )
    matched = False
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        if str(edge.get("caller") or "") != caller:
            continue
        matched = True
        required = str(edge.get("required_unit") or "")
        owner = str(edge.get("owner") or "")
        dest = skill_dest(required, target) / "SKILL.md"
        if dest.is_file():
            continue
        raise InstallError(
            "missing-skill-edge",
            resource_id=required,
            owner=owner,
            target=target,
            next_step=f"install {required} from {owner}; do not clone {owner} from Team",
            detail=f"{caller} requires {required}",
        )
    if not matched:
        raise InstallError(
            "missing-skill-edge",
            resource_id=caller,
            owner=REPO_ID,
            target=target,
            next_step="repair contracts/dependencies.yaml edges and rerun",
            detail=f"no runtime-invocation edge for {caller}",
        )


def load_surface_skills() -> dict[str, Any]:
    path = REPO_ROOT / "contracts" / "skill-runtime-surface.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(
            "missing-surface",
            owner=REPO_ID,
            next_step="restore contracts/skill-runtime-surface.json and rerun",
            detail=str(exc),
        ) from exc
    skills = payload.get("skills")
    if not isinstance(skills, dict) or not skills:
        raise InstallError(
            "missing-surface",
            owner=REPO_ID,
            next_step="restore Team skill-runtime-surface.json keys and rerun",
        )
    return skills


def discover_skills(target: TargetName) -> dict[str, Path]:
    expected = set(load_surface_skills())
    if target == "codex":
        expected -= CLAUDE_ONLY
    found: dict[str, Path] = {}
    for name in sorted(expected):
        if name in CLAUDE_ONLY:
            source = REPO_ROOT / "claude" / "skills" / name
        else:
            source = REPO_ROOT / "shared" / "skills" / name
        if not (source / "SKILL.md").is_file():
            raise InstallError(
                "missing-source",
                resource_id=name,
                owner=REPO_ID,
                target=target,
                next_step="restore the Team Skill tree and rerun",
                detail=str(source),
            )
        found[name] = source
    return found


def prune_internal_skill_roots(skills_dir: Path) -> None:
    if not skills_dir.is_dir():
        return
    for skill_dir in list(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        if skill_dir.name.endswith("-workspace"):
            shutil.rmtree(skill_dir)
            continue
        for dirpath, dirnames, _filenames in os.walk(skill_dir, topdown=True):
            remove = [name for name in dirnames if name in _PRUNE_DIR_NAMES]
            for name in remove:
                shutil.rmtree(Path(dirpath) / name, ignore_errors=True)
            dirnames[:] = [name for name in dirnames if name not in _PRUNE_DIR_NAMES]


def run_python_script(
    script: Path,
    args: Sequence[str],
    *,
    timeout: int,
    resource_id: str,
    target: TargetName,
    next_step: str,
    cwd: Path | None = None,
) -> str:
    if not script.is_file():
        raise InstallError(
            "missing-source",
            resource_id=resource_id,
            owner=REPO_ID,
            target=target,
            next_step=f"restore {script} and rerun",
        )
    cmd = [sys.executable, str(script), *args]
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd or script.parent),
        )
    except subprocess.TimeoutExpired as exc:
        raise InstallError(
            "timeout",
            resource_id=resource_id,
            owner=REPO_ID,
            target=target,
            next_step=next_step,
            detail=f"{script.name} timed out",
        ) from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "command failed").strip()[:2000]
        raise InstallError(
            "structured-apply",
            resource_id=resource_id,
            owner=REPO_ID,
            target=target,
            next_step=next_step,
            detail=detail,
        )
    return proc.stdout


def apply_runtime_surface(staging_dir: Path, target: TargetName) -> None:
    run_python_script(
        REPO_ROOT / "tools" / "skills" / "apply_skill_runtime_surface.py",
        [
            "--contract",
            str(REPO_ROOT / "contracts" / "skill-runtime-surface.json"),
            "--skills-dir",
            str(staging_dir),
            "--runtime",
            target,
        ],
        timeout=_SURFACE_APPLY_TIMEOUT_SEC,
        resource_id="runtime-surface",
        target=target,
        next_step="fix contracts/skill-runtime-surface.json or staged Skill trees and rerun",
        cwd=REPO_ROOT,
    )


def inject_claude_skill_hooks(skills_dir: Path, target: TargetName) -> None:
    run_python_script(
        REPO_ROOT / "tools" / "community" / "render_hook_registry.py",
        [
            "inject-claude-skill-hooks",
            "--registry",
            str(REPO_ROOT / "shared" / "hooks" / "registry.json"),
            "--skills-dir",
            str(skills_dir),
            "--runtime-home",
            "$HOME/.claude",
            "--python-launcher",
            python_launcher(),
        ],
        timeout=_TOOL_TIMEOUT_SEC,
        resource_id="hooks",
        target=target,
        next_step="inspect shared/hooks/registry.json and rerun",
    )


def render_json_tool(command: str, runtime_home: str, target: TargetName) -> dict[str, Any]:
    stdout = run_python_script(
        REPO_ROOT / "tools" / "community" / "render_hook_registry.py",
        [
            command,
            "--registry",
            str(REPO_ROOT / "shared" / "hooks" / "registry.json"),
            "--runtime-home",
            runtime_home,
            "--python-launcher",
            python_launcher(),
        ],
        timeout=_TOOL_TIMEOUT_SEC,
        resource_id="hooks",
        target=target,
        next_step="inspect shared/hooks/registry.json and rerun",
    )
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise InstallError(
            "structured-apply",
            resource_id="hooks",
            owner=REPO_ID,
            target=target,
            next_step="inspect render_hook_registry.py output and rerun",
            detail=str(exc),
        ) from exc
    if not isinstance(payload, dict):
        raise InstallError(
            "structured-apply",
            resource_id="hooks",
            owner=REPO_ID,
            target=target,
            next_step="inspect render_hook_registry.py output and rerun",
            detail="hook renderer returned a non-object",
        )
    return payload


def managed_agent_roles() -> list[tuple[str, str, str]]:
    community = str(REPO_ROOT / "tools" / "community")
    if community not in sys.path:
        sys.path.insert(0, community)
    from codex_runtime_agents import MANAGED_AGENT_ROLES

    return list(MANAGED_AGENT_ROLES)


def tree_plan(
    resource_id: str,
    source: Path,
    staged: Path,
    dest: Path,
    target: TargetName,
) -> ResourcePlan:
    try:
        records = canonical_tree_files(staged)
        digest = canonical_tree_digest(staged)
    except ValueError as exc:
        raise InstallError(
            "unsafe-tree",
            resource_id=resource_id,
            owner=REPO_ID,
            target=target,
            next_step="remove escaping symlinks from the resource tree and rerun",
            detail=str(exc),
        ) from exc
    if not records:
        raise InstallError(
            "empty-resource",
            resource_id=resource_id,
            owner=REPO_ID,
            target=target,
            next_step="restore the Team payload and rerun",
        )
    return ResourcePlan(
        resource_id=resource_id,
        resource_root=dest,
        kind="tree",
        source_path=source,
        staged_path=staged,
        files=records,
        tree_sha256=digest,
    )


def copy_tree(source: Path, staged: Path) -> None:
    if staged.exists():
        shutil.copytree(
            source,
            staged,
            dirs_exist_ok=True,
            ignore=_copy_ignore,
            symlinks=True,
        )
        return
    shutil.copytree(source, staged, ignore=_copy_ignore, symlinks=True)


def stage_skills(target: TargetName, staging_dir: Path) -> dict[str, Path]:
    sources = discover_skills(target)
    skills_stage = staging_dir / "skills"
    skills_stage.mkdir(parents=True, exist_ok=True)
    for name, source in sorted(sources.items()):
        copy_tree(source, skills_stage / name)
    prune_internal_skill_roots(skills_stage)
    if target == "claude":
        for skill_dir in skills_stage.iterdir():
            agents_dir = skill_dir / "agents"
            if agents_dir.is_dir():
                shutil.rmtree(agents_dir)
    apply_runtime_surface(skills_stage, target)
    if target == "claude":
        inject_claude_skill_hooks(skills_stage, target)
    remaining = {
        path.name
        for path in skills_stage.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }
    if remaining != set(sources):
        raise InstallError(
            "resource-count",
            owner=REPO_ID,
            target=target,
            next_step="restore the Team Skill trees and rerun",
            detail=f"staged {sorted(remaining)} from {sorted(sources)}",
        )
    return sources


def stage_support_trees(target: TargetName, staging_dir: Path) -> list[ResourcePlan]:
    dest_root = target_root(target)
    resources: list[ResourcePlan] = []

    hooks_stage = staging_dir / "hooks"
    copy_tree(REPO_ROOT / "shared" / "hooks", hooks_stage)
    if target == "claude":
        copy_tree(REPO_ROOT / "claude" / "hooks", hooks_stage)
    resources.append(
        tree_plan("hooks", REPO_ROOT / "shared" / "hooks", hooks_stage, dest_root / "hooks", target)
    )

    agents_source = REPO_ROOT / "shared" / "agents" / target
    agents_stage = staging_dir / "agents"
    copy_tree(agents_source, agents_stage)
    resources.append(tree_plan("agents", agents_source, agents_stage, dest_root / "agents", target))

    protocols_source = REPO_ROOT / "shared" / "protocols"
    protocols_stage = staging_dir / "protocols"
    copy_tree(protocols_source, protocols_stage)
    resources.append(
        tree_plan("protocols", protocols_source, protocols_stage, dest_root / "protocols", target)
    )

    runtime_source = REPO_ROOT / "shared" / "runtime"
    runtime_stage = staging_dir / "runtime"
    copy_tree(runtime_source, runtime_stage)
    resources.append(
        tree_plan(
            "runtime",
            runtime_source,
            runtime_stage,
            dest_root / "shared" / "runtime",
            target,
        )
    )

    tools_source = REPO_ROOT / "tools" / "community"
    tools_stage = staging_dir / "tools-community"
    copy_tree(tools_source, tools_stage)
    resources.append(
        tree_plan(
            "tools/community",
            tools_source,
            tools_stage,
            dest_root / "tools" / "community",
            target,
        )
    )

    contracts_stage = staging_dir / "contracts"
    contracts_stage.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "contracts" / "product-artifacts.yaml", contracts_stage / "product-artifacts.yaml")
    copy_tree(REPO_ROOT / "contracts" / "canonical", contracts_stage / "canonical")
    resources.append(
        tree_plan(
            "contracts",
            REPO_ROOT / "contracts",
            contracts_stage,
            dest_root / "contracts",
            target,
        )
    )

    shared_skills_stage = staging_dir / "shared-skills"
    shared_skills_stage.mkdir(parents=True, exist_ok=True)
    lib_source = REPO_ROOT / "shared" / "skills" / "lib"
    if lib_source.is_dir():
        copy_tree(lib_source, shared_skills_stage / "lib")
    for skill_dir in sorted((REPO_ROOT / "shared" / "skills").iterdir()):
        if not skill_dir.is_dir() or skill_dir.name in {"lib", "skill-pull"}:
            continue
        if skill_dir.name.endswith("-workspace"):
            continue
        for extra in ("contracts", "templates"):
            extra_dir = skill_dir / extra
            if extra_dir.is_dir():
                copy_tree(extra_dir, shared_skills_stage / skill_dir.name / extra)
    if any(shared_skills_stage.iterdir()):
        resources.append(
            tree_plan(
                "shared-skills",
                REPO_ROOT / "shared" / "skills",
                shared_skills_stage,
                dest_root / "shared" / "skills",
                target,
            )
        )
    return resources


def planned_structured_entries(target: TargetName) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if target == "claude":
        fragment = render_json_tool("claude-settings-fragment", "$HOME/.claude", target)
        settings = target_root(target) / "settings.json"
        for event, items in (fragment.get("hooks") or {}).items():
            if not isinstance(items, list):
                continue
            for item in items:
                entries.append(
                    {
                        "kind": "claude-hook",
                        "path": str(settings),
                        "event": event,
                        "value": item,
                    }
                )
        return entries

    hooks_file = target_root(target) / "hooks.json"
    config = target_root(target) / "config.toml"
    payload = render_json_tool("codex-hooks", str(target_root(target)), target)
    for event, items in (payload.get("hooks") or {}).items():
        if not isinstance(items, list):
            continue
        for item in items:
            entries.append(
                {
                    "kind": "codex-hook",
                    "path": str(hooks_file),
                    "event": event,
                    "value": item,
                }
            )
    for role, description, config_file in managed_agent_roles():
        entries.append(
            {
                "kind": "codex-agent",
                "path": str(config),
                "section": f"agents.{role}",
                "value": {"description": description, "config_file": config_file},
            }
        )
    entries.append(
        {
            "kind": "codex-feature",
            "path": str(config),
            "section": "features",
            "key": "hooks",
            "value": "true",
        }
    )
    return entries


def build_plan(target: TargetName, staging_dir: Path) -> InstallPlan:
    sources = stage_skills(target, staging_dir)
    skills_stage = staging_dir / "skills"
    resources: list[ResourcePlan] = []
    for name in sorted(sources):
        staged_path = skills_stage / name
        resources.append(
            tree_plan(name, sources[name], staged_path, skill_dest(name, target), target)
        )
    resources.extend(stage_support_trees(target, staging_dir))
    return InstallPlan(
        repo_id=REPO_ID,
        repo_version=repo_version(),
        target=target,
        requires=[base_requires()],
        resources=resources,
        structured_entries=planned_structured_entries(target),
        staging_dir=staging_dir,
    )


def validate_base_requires(root: Path, plan: InstallPlan) -> None:
    req = plan.requires[0]
    missing = list(req.resource_ids)
    base_path = root / BASE_REPO_ID / plan.target / "installed.json"
    if not base_path.is_file():
        raise InstallError(
            "missing-dependency",
            resource_id=missing[0],
            owner=BASE_REPO_ID,
            target=plan.target,
            next_step=f"install base-config for target {plan.target}, then rerun Team install",
            detail="missing resource_ids: " + ",".join(missing),
        )
    payload = load_json_object(base_path, owner=BASE_REPO_ID)
    if payload.get("repo_id") != BASE_REPO_ID or payload.get("target") != plan.target:
        raise InstallError(
            "missing-dependency",
            resource_id=missing[0],
            owner=BASE_REPO_ID,
            target=plan.target,
            next_step=f"repair base-config installed.json for {plan.target} and rerun",
            detail="base-config manifest repo_id/target mismatch",
        )
    present = {
        str(resource.get("resource_id"))
        for resource in payload.get("resources") or []
        if isinstance(resource, dict)
    }
    absent = [resource_id for resource_id in req.resource_ids if resource_id not in present]
    if absent:
        raise InstallError(
            "missing-dependency",
            resource_id=absent[0],
            owner=BASE_REPO_ID,
            target=plan.target,
            next_step=f"install base-config resources for target {plan.target}, then rerun",
            detail="missing resource_ids: " + ",".join(absent),
        )
    by_id = {
        str(resource.get("resource_id")): resource
        for resource in payload.get("resources") or []
        if isinstance(resource, dict)
    }
    for resource_id in req.resource_ids:
        resource = by_id[resource_id]
        drifted = record_drift(resource)
        if drifted is None:
            continue
        _rid, expected, actual = drifted
        raise InstallError(
            "missing-dependency",
            resource_id=resource_id,
            expected_digest=expected,
            actual_digest=actual,
            owner=BASE_REPO_ID,
            target=plan.target,
            next_step=f"restore base-config {resource_id} on target {plan.target}, then rerun",
            detail=f"live Base file does not match installed.json for {resource_id}",
        )


def validate_drift(
    manifest: dict[str, Any] | None, *, target: TargetName, action: str
) -> None:
    if not manifest:
        return
    for resource in manifest.get("resources") or []:
        if not isinstance(resource, dict):
            raise InstallError(
                "manifest-unreadable",
                owner=REPO_ID,
                target=target,
                next_step="repair installed.json then rerun",
            )
        drifted = record_drift(resource)
        if drifted is None:
            continue
        resource_id, expected, actual = drifted
        raise InstallError(
            "drift",
            resource_id=resource_id,
            expected_digest=expected,
            actual_digest=actual,
            owner=REPO_ID,
            target=target,
            next_step=(
                f"restore {resource_id} to the recorded digest, then rerun {action}; "
                "do not overwrite or delete the drifted file"
            ),
        )


def validate_conflicts(plan: InstallPlan, manifest: dict[str, Any] | None) -> None:
    owned = owned_resources(manifest)
    for resource in plan.resources:
        dest = resource.resource_root
        if not lexists(dest):
            continue
        if dest in owned:
            continue
        raise InstallError(
            "conflict",
            resource_id=resource.resource_id,
            expected_digest=resource.tree_sha256,
            actual_digest=existing_digest(dest),
            owner="unowned",
            target=plan.target,
            next_step=(
                f"move or remove the existing path at {dest}, then rerun "
                f"install.sh --target {plan.target}"
            ),
        )


def _has_unclosed_quotes(text: str) -> bool:
    i = 0
    n = len(text)
    in_single = False
    in_double = False
    in_triple_single = False
    in_triple_double = False
    while i < n:
        if in_triple_double:
            if text.startswith('"""', i):
                in_triple_double = False
                i += 3
                continue
            i += 1
            continue
        if in_triple_single:
            if text.startswith("'''", i):
                in_triple_single = False
                i += 3
                continue
            i += 1
            continue
        if in_double:
            if text[i] == "\\" and i + 1 < n:
                i += 2
                continue
            if text[i] == '"':
                in_double = False
            i += 1
            continue
        if in_single:
            if text[i] == "'":
                in_single = False
            i += 1
            continue
        if text.startswith('"""', i):
            in_triple_double = True
            i += 3
            continue
        if text.startswith("'''", i):
            in_triple_single = True
            i += 3
            continue
        ch = text[i]
        if ch == '"':
            in_double = True
        elif ch == "'":
            in_single = True
        i += 1
    return in_single or in_double or in_triple_single or in_triple_double


def validate_structured_destinations(plan: InstallPlan) -> None:
    if plan.target == "claude":
        settings = target_root(plan.target) / "settings.json"
        if not settings.exists():
            return
        try:
            payload = json.loads(settings.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InstallError(
                "structured-corrupt",
                resource_id="settings.json",
                owner=REPO_ID,
                target=plan.target,
                next_step=f"repair {settings} then rerun",
                detail=str(exc),
            ) from exc
        if not isinstance(payload, dict):
            raise InstallError(
                "structured-corrupt",
                resource_id="settings.json",
                owner=REPO_ID,
                target=plan.target,
                next_step=f"repair {settings} then rerun",
                detail="settings.json must be a JSON object",
            )
        return

    hooks_file = target_root(plan.target) / "hooks.json"
    if hooks_file.exists():
        try:
            payload = json.loads(hooks_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InstallError(
                "structured-corrupt",
                resource_id="hooks.json",
                owner=REPO_ID,
                target=plan.target,
                next_step=f"repair {hooks_file} then rerun",
                detail=str(exc),
            ) from exc
        if not isinstance(payload, dict):
            raise InstallError(
                "structured-corrupt",
                resource_id="hooks.json",
                owner=REPO_ID,
                target=plan.target,
                next_step=f"repair {hooks_file} then rerun",
                detail="hooks.json must be a JSON object",
            )
    config = target_root(plan.target) / "config.toml"
    if not config.exists():
        return
    try:
        text = config.read_text(encoding="utf-8")
    except OSError as exc:
        raise InstallError(
            "structured-corrupt",
            resource_id="config.toml",
            owner=REPO_ID,
            target=plan.target,
            next_step=f"repair {config} then rerun",
            detail=str(exc),
        ) from exc
    if _has_unclosed_quotes(text):
        raise InstallError(
            "structured-corrupt",
            resource_id="config.toml",
            owner=REPO_ID,
            target=plan.target,
            next_step=f"repair the mid-write [agents.developer] section in {config} then rerun",
            detail="unclosed string in config.toml",
        )
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and "]" not in stripped:
            raise InstallError(
                "structured-corrupt",
                resource_id="config.toml",
                owner=REPO_ID,
                target=plan.target,
                next_step=f"repair truncated TOML table header in {config} then rerun",
                detail=stripped,
            )


def validate_target(
    root: Path,
    plan: InstallPlan,
    *,
    uninstall: bool,
) -> None:
    manifest = load_own_manifest(root, plan.target)
    if uninstall:
        if manifest is None:
            raise InstallError(
                "missing-manifest",
                owner=REPO_ID,
                target=plan.target,
                next_step=f"nothing is installed for {plan.target}; no uninstall is required",
            )
        validate_drift(manifest, target=plan.target, action="uninstall")
        return
    validate_base_requires(root, plan)
    validate_drift(manifest, target=plan.target, action="upgrade" if manifest else "install")
    validate_conflicts(plan, manifest)
    validate_structured_destinations(plan)


def write_journal(root: Path, target: TargetName, op: str) -> Path:
    path = journal_path(root, target)
    atomic_write_text(
        path,
        json.dumps({"op": op, "repo_id": REPO_ID, "target": target}, ensure_ascii=False)
        + "\n",
    )
    return path


def clear_journal(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def copy_staged_tree(resource: ResourcePlan) -> None:
    dest = resource.resource_root
    dest.mkdir(parents=True, exist_ok=True)
    for rec in resource.files:
        target = dest / rec.path
        source = resource.staged_path / rec.path
        target.parent.mkdir(parents=True, exist_ok=True)
        if rec.kind == "symlink":
            if lexists(target):
                target.unlink()
            os.symlink(rec.link_target or "", target)
            continue
        if not source.is_file():
            raise InstallError(
                "write-failed",
                resource_id=resource.resource_id,
                owner=REPO_ID,
                next_step=f"inspect staged file {source} and rerun",
                detail=f"missing staged file {rec.path}",
            )
        if lexists(target) and target.is_dir() and not target.is_symlink():
            raise InstallError(
                "write-failed",
                resource_id=resource.resource_id,
                owner=REPO_ID,
                next_step=f"inspect {target} and rerun",
                detail=f"{target} is a directory",
            )
        target.write_bytes(source.read_bytes())
        os.chmod(target, _MODE_BITS.get(rec.mode, 0o644))
        actual = sha256_file(target)
        expected = rec.sha256 or "-"
        if actual != expected:
            raise InstallError(
                "write-failed",
                resource_id=resource.resource_id,
                expected_digest=expected,
                actual_digest=actual,
                owner=REPO_ID,
                next_step=f"inspect {target} and rerun",
            )


def remove_empty_parents(path: Path, stop_at: Path) -> None:
    current = path
    while current != stop_at and stop_at in current.parents:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def remove_stale_tree_files(old_resource: dict[str, Any], new_resource: ResourcePlan) -> None:
    new_paths = {rec.path for rec in new_resource.files}
    root = Path(str(old_resource["resource_root"]))
    for rec in old_resource.get("files") or []:
        if not isinstance(rec, dict):
            continue
        rel = rec.get("path")
        if not rel or rel in new_paths:
            continue
        dest = dest_for_record(old_resource, rec)
        if lexists(dest) and not dest.is_dir():
            dest.unlink()
        elif lexists(dest) and dest.is_symlink():
            dest.unlink()
        remove_empty_parents(dest.parent, root)


def remove_resource_tree(resource: dict[str, Any]) -> None:
    root = Path(str(resource["resource_root"]))
    files = resource.get("files") or []
    if not isinstance(files, list):
        raise InstallError(
            "manifest-unreadable",
            owner=REPO_ID,
            next_step="repair installed.json then rerun",
            detail="files must be a list",
        )
    for rec in files:
        if not isinstance(rec, dict):
            continue
        dest = dest_for_record(resource, rec)
        if not lexists(dest):
            continue
        if dest.is_dir() and not dest.is_symlink():
            continue
        dest.unlink()
    if root.is_dir():
        for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            if path.is_dir() and not path.is_symlink():
                try:
                    path.rmdir()
                except OSError:
                    pass
        try:
            root.rmdir()
        except OSError:
            pass


def identity_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def merge_claude_settings(plan: InstallPlan) -> None:
    settings_path = target_root(plan.target) / "settings.json"
    fragment_hooks: dict[str, list[Any]] = {}
    for entry in plan.structured_entries:
        if entry.get("kind") != "claude-hook":
            continue
        fragment_hooks.setdefault(str(entry["event"]), []).append(entry["value"])
    if settings_path.is_file():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        if not isinstance(settings, dict):
            raise InstallError(
                "structured-corrupt",
                resource_id="settings.json",
                owner=REPO_ID,
                target=plan.target,
                next_step=f"repair {settings_path} then rerun",
            )
    else:
        settings = {}
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        settings["hooks"] = hooks
    for event, items in fragment_hooks.items():
        existing = hooks.get(event)
        if not isinstance(existing, list):
            existing = []
        managed = {identity_key(item) for item in items}
        kept = [item for item in existing if identity_key(item) not in managed]
        hooks[event] = items + kept
    atomic_write_text(settings_path, json.dumps(settings, ensure_ascii=False, indent=2) + "\n")


def remove_claude_settings_entries(entries: Sequence[dict[str, Any]]) -> None:
    by_path: dict[Path, list[dict[str, Any]]] = {}
    for entry in entries:
        if entry.get("kind") != "claude-hook":
            continue
        by_path.setdefault(Path(str(entry["path"])), []).append(entry)
    for path, path_entries in by_path.items():
        if not path.is_file():
            continue
        settings = json.loads(path.read_text(encoding="utf-8"))
        hooks = settings.get("hooks")
        if not isinstance(hooks, dict):
            continue
        managed = {identity_key(entry.get("value")) for entry in path_entries}
        for event, items in list(hooks.items()):
            if not isinstance(items, list):
                continue
            filtered = [item for item in items if identity_key(item) not in managed]
            if filtered:
                hooks[event] = filtered
            else:
                hooks.pop(event, None)
        if hooks:
            settings["hooks"] = hooks
        else:
            settings.pop("hooks", None)
        atomic_write_text(path, json.dumps(settings, ensure_ascii=False, indent=2) + "\n")


def apply_codex_structured(root: Path, plan: InstallPlan) -> None:
    manager = REPO_ROOT / "tools" / "community" / "manage_codex_runtime.py"
    config = target_root(plan.target) / "config.toml"
    hooks_file = target_root(plan.target) / "hooks.json"
    work = Path(tempfile.mkdtemp(prefix="team-codex-structured-"))
    try:
        work_config = work / "config.toml"
        if config.exists():
            shutil.copy2(config, work_config)
        else:
            work_config.write_text("", encoding="utf-8")
        run_python_script(
            manager,
            ["enable-feature", "--config", str(work_config), "--state", str(feature_state_path(root))],
            timeout=_TOOL_TIMEOUT_SEC,
            resource_id="config.toml",
            target=plan.target,
            next_step=f"repair {config} then rerun",
        )
        run_python_script(
            manager,
            ["configure-agents", "--config", str(work_config)],
            timeout=_TOOL_TIMEOUT_SEC,
            resource_id="config.toml",
            target=plan.target,
            next_step=f"repair {config} then rerun",
        )
        if _has_unclosed_quotes(work_config.read_text(encoding="utf-8")):
            raise InstallError(
                "structured-corrupt",
                resource_id="config.toml",
                owner=REPO_ID,
                target=plan.target,
                next_step=f"repair {config} then rerun",
                detail="agent config write produced an unclosed string",
            )
        atomic_replace(work_config, config)

        rendered = work / "managed-hooks.json"
        payload = render_json_tool("codex-hooks", str(target_root(plan.target)), plan.target)
        rendered.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        work_hooks = work / "hooks.json"
        if hooks_file.exists():
            shutil.copy2(hooks_file, work_hooks)
        else:
            work_hooks.write_text("{}\n", encoding="utf-8")
        run_python_script(
            manager,
            [
                "merge-hooks",
                "--hooks-file",
                str(work_hooks),
                "--managed-file",
                str(rendered),
                "--managed-root",
                str(target_root(plan.target) / "hooks" / "managed"),
            ],
            timeout=_TOOL_TIMEOUT_SEC,
            resource_id="hooks.json",
            target=plan.target,
            next_step=f"repair {hooks_file} then rerun",
        )
        atomic_replace(work_hooks, hooks_file)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def remove_codex_structured(root: Path, entries: Sequence[dict[str, Any]], target: TargetName) -> None:
    manager = REPO_ROOT / "tools" / "community" / "manage_codex_runtime.py"
    hooks_file = target_root(target) / "hooks.json"
    if hooks_file.exists():
        rendered = Path(tempfile.mkstemp(prefix="team-codex-hooks-", suffix=".json")[1])
        try:
            payload = render_json_tool("codex-hooks", str(target_root(target)), target)
            rendered.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            run_python_script(
                manager,
                [
                    "cleanup-hooks",
                    "--hooks-file",
                    str(hooks_file),
                    "--managed-root",
                    str(target_root(target) / "hooks" / "managed"),
                    "--managed-file",
                    str(rendered),
                ],
                timeout=_TOOL_TIMEOUT_SEC,
                resource_id="hooks.json",
                target=target,
                next_step=f"repair {hooks_file} then rerun uninstall",
            )
        finally:
            rendered.unlink(missing_ok=True)
    config = target_root(target) / "config.toml"
    if config.exists():
        text = config.read_text(encoding="utf-8")
        lines = text.splitlines()
        for entry in entries:
            if entry.get("kind") != "codex-agent":
                continue
            section = str(entry.get("section") or "")
            value = entry.get("value") or {}
            start = None
            for idx, line in enumerate(lines):
                if line.strip() == f"[{section}]":
                    start = idx
                    break
            if start is None:
                continue
            end = len(lines)
            for idx in range(start + 1, len(lines)):
                stripped = lines[idx].strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    end = idx
                    break
            block = lines[start + 1 : end]
            description = None
            config_file = None
            for line in block:
                stripped = line.strip()
                if stripped.startswith("description"):
                    description = stripped.split("=", 1)[1].strip().strip('"')
                if stripped.startswith("config_file"):
                    config_file = stripped.split("=", 1)[1].strip().strip('"')
            if description == value.get("description") and config_file == value.get("config_file"):
                del lines[start:end]
                if start < len(lines) and not lines[start].strip():
                    del lines[start]
                if start > 0 and start <= len(lines) and not lines[start - 1].strip():
                    del lines[start - 1]
        atomic_write_text(config, ("\n".join(lines).rstrip() + "\n") if lines else "")
    state = feature_state_path(root)
    if state.is_file() and config.exists():
        run_python_script(
            manager,
            ["restore-feature", "--config", str(config), "--state", str(state)],
            timeout=_TOOL_TIMEOUT_SEC,
            resource_id="config.toml",
            target=target,
            next_step=f"repair {config} then rerun uninstall",
        )
        state.unlink(missing_ok=True)


def apply_structured_entries(root: Path, plan: InstallPlan) -> None:
    if plan.target == "claude":
        merge_claude_settings(plan)
        return
    apply_codex_structured(root, plan)


def apply_install(root: Path, plan: InstallPlan) -> None:
    validate_target(root, plan, uninstall=False)
    manifest = load_own_manifest(root, plan.target)
    owned = owned_resources(manifest)
    desired = {resource.resource_root: resource for resource in plan.resources}
    journal = write_journal(root, plan.target, "install")
    for resource in plan.resources:
        copy_staged_tree(resource)
        old = owned.get(resource.resource_root)
        if old is not None:
            remove_stale_tree_files(old, resource)
    for dest, owned_resource in list(owned.items()):
        if dest in desired:
            continue
        drifted = record_drift(owned_resource)
        if drifted is not None:
            resource_id, expected, actual = drifted
            raise InstallError(
                "drift",
                resource_id=resource_id,
                expected_digest=expected,
                actual_digest=actual,
                owner=REPO_ID,
                target=plan.target,
                next_step=(
                    f"restore {resource_id} to the recorded digest, then rerun upgrade"
                ),
            )
        remove_resource_tree(owned_resource)
    apply_structured_entries(root, plan)
    atomic_write_text(
        manifest_path(root, plan.target),
        json.dumps(plan_to_manifest(plan), ensure_ascii=False, indent=2) + "\n",
    )
    clear_journal(journal)


def apply_uninstall(root: Path, plan: InstallPlan) -> None:
    validate_target(root, plan, uninstall=True)
    manifest = load_own_manifest(root, plan.target)
    if manifest is None:
        raise InstallError(
            "missing-manifest",
            owner=REPO_ID,
            target=plan.target,
            next_step=f"nothing is installed for {plan.target}; no uninstall is required",
        )
    journal = write_journal(root, plan.target, "uninstall")
    entries = manifest.get("structured_entries") or []
    if not isinstance(entries, list):
        entries = []
    if plan.target == "claude":
        remove_claude_settings_entries([entry for entry in entries if isinstance(entry, dict)])
    else:
        remove_codex_structured(
            root, [entry for entry in entries if isinstance(entry, dict)], plan.target
        )
    for resource in manifest.get("resources") or []:
        if not isinstance(resource, dict):
            raise InstallError(
                "manifest-unreadable",
                owner=REPO_ID,
                target=plan.target,
                next_step="repair installed.json then rerun",
            )
        drifted = record_drift(resource)
        if drifted is not None:
            resource_id, expected, actual = drifted
            raise InstallError(
                "drift",
                resource_id=resource_id,
                expected_digest=expected,
                actual_digest=actual,
                owner=REPO_ID,
                target=plan.target,
                next_step=(
                    f"restore {resource_id} to the recorded digest, then rerun uninstall"
                ),
            )
        remove_resource_tree(resource)
    path = manifest_path(root, plan.target)
    path.unlink()
    clear_journal(journal)
    remove_empty_parents(path.parent, root)


class _Lock:
    """Exclusive fcntl lock on <state-root>/.lock; held for the whole command."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.fd = -1

    def __enter__(self) -> _Lock:
        self.root.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.root / ".lock", os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_exc: object) -> None:
        if self.fd >= 0:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = -1


def emit_error(error: InstallError) -> None:
    print(error.format(), file=sys.stderr)


def emit_success(plan: InstallPlan, *, dry_run: bool, uninstall: bool) -> None:
    action = "dry-run" if dry_run else "uninstalled" if uninstall else "installed"
    print(
        f"{action} repo_id={plan.repo_id} target={plan.target} "
        f"resources={len(plan.resources)}",
        file=sys.stdout,
    )


def run(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    targets = selected_targets(args.target)
    root = state_root()
    staging_dirs: list[Path] = []
    try:
        with _Lock(root):
            plans: dict[TargetName, InstallPlan] = {}
            for target in targets:
                staging = Path(tempfile.mkdtemp(prefix="team-skills-stage-"))
                staging_dirs.append(staging)
                plans[target] = build_plan(target, staging)

            validations: dict[TargetName, InstallError | None] = {}
            for target in targets:
                try:
                    validate_target(root, plans[target], uninstall=args.uninstall)
                    validations[target] = None
                except InstallError as exc:
                    validations[target] = exc

            if args.dry_run:
                dry_failures = [error for error in validations.values() if error is not None]
                if dry_failures:
                    emit_error(dry_failures[0].with_completed(()))
                    return 1
                for target in targets:
                    emit_success(plans[target], dry_run=True, uninstall=args.uninstall)
                return 0

            completed: list[str] = []
            failures: list[InstallError] = []
            for target in targets:
                error = validations[target]
                if error is not None:
                    failures.append(error)
                    continue
                try:
                    if args.uninstall:
                        apply_uninstall(root, plans[target])
                    else:
                        apply_install(root, plans[target])
                except InstallError as exc:
                    failures.append(exc)
                    continue
                completed.append(target)
                emit_success(
                    plans[target], dry_run=False, uninstall=args.uninstall
                )

            if failures:
                first = failures[0].with_completed(completed)
                emit_error(first)
                return 1
            return 0
    except InstallError as exc:
        emit_error(exc)
        return 1
    finally:
        for staging in staging_dirs:
            shutil.rmtree(staging, ignore_errors=True)


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
