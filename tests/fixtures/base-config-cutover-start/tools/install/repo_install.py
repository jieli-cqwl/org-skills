from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Literal, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.install.tree_digest import (  # noqa: E402
    FileRecord,
    canonical_tree_digest,
    canonical_tree_files,
)

REPO_ID = "base-config"
SCHEMA_VERSION = 1
TARGETS = ("claude", "codex")
TargetName = Literal["claude", "codex"]
RESOURCE_KIND = Literal["file", "tree", "symlink"]

RESOURCE_IDS: tuple[str, ...] = (
    "assistant",
    "rules/code-changes.md",
    "rules/completion-claims.md",
    "rules/document-governance.md",
    "rules/execution-control.md",
    "reference/authentication-and-authorization.md",
    "reference/code-comments.md",
    "reference/code-structure-reuse.md",
    "reference/constants-and-configuration.md",
    "reference/error-handling.md",
    "reference/impact-analysis.md",
    "reference/performance-and-efficiency.md",
    "reference/协作判断.md",
    "reference/技术方案设计.md",
    "reference/测试规范.md",
)

TARGET_DIRNAME = {"claude": ".claude", "codex": ".codex"}
ASSISTANT_NAME = {"claude": "CLAUDE.md", "codex": "AGENTS.md"}
ENTRY_DOC = {"claude": "CLAUDE.md", "codex": "AGENTS.md"}
RUNTIME_HOME = {"claude": "$HOME/.claude", "codex": "$HOME/.codex"}
_CHUNK_SIZE = 1024 * 1024
_MODE_BITS = {"0644": 0o644, "0755": 0o755}


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
    parser = argparse.ArgumentParser(description="Install Base assistant, rules, and references.")
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
            next_step="restore VERSION in the Base checkout and rerun",
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


def dest_for(resource_id: str, target: TargetName) -> Path:
    root = target_root(target)
    if resource_id == "assistant":
        return root / ASSISTANT_NAME[target]
    return root / resource_id


def source_for(resource_id: str) -> Path:
    if resource_id == "assistant":
        return REPO_ROOT / "assistant.md"
    return REPO_ROOT / resource_id


def manifest_path(root: Path, target: TargetName) -> Path:
    return root / REPO_ID / target / "installed.json"


def journal_path(root: Path, target: TargetName) -> Path:
    return root / REPO_ID / target / ".in-progress.json"


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


def render_text(text: str, target: TargetName) -> str:
    rendered = text.replace("{{RUNTIME_HOME}}", RUNTIME_HOME[target]).replace(
        "{{ENTRY_DOC}}", ENTRY_DOC[target]
    )
    if "{{" in rendered:
        raise InstallError(
            "unrendered-placeholder",
            resource_id="assistant",
            owner=REPO_ID,
            next_step="remove unsupported placeholders from the Base payload and rerun",
        )
    return rendered


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


def iter_target_manifests(
    root: Path, target: TargetName
) -> Iterator[tuple[str, Path, dict[str, Any]]]:
    if not root.is_dir():
        return
    for entry in sorted(root.iterdir(), key=lambda path: path.name):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        path = entry / target / "installed.json"
        if not path.is_file():
            continue
        yield entry.name, path, load_json_object(path, owner=entry.name)


def dependents_on_base(
    root: Path, target: TargetName
) -> list[tuple[str, tuple[str, ...]]]:
    found: list[tuple[str, tuple[str, ...]]] = []
    for repo_id, _path, payload in iter_target_manifests(root, target):
        if repo_id == REPO_ID:
            continue
        requires = payload.get("requires") or []
        if not isinstance(requires, list):
            raise InstallError(
                "manifest-unreadable",
                owner=repo_id,
                target=target,
                next_step=f"repair {repo_id}'s installed.json then rerun",
            )
        required: list[str] = []
        depends = False
        for req in requires:
            if not isinstance(req, dict):
                raise InstallError(
                    "manifest-unreadable",
                    owner=repo_id,
                    target=target,
                    next_step=f"repair {repo_id}'s requires list then rerun",
                )
            if req.get("repo_id") != REPO_ID:
                continue
            depends = True
            ids = req.get("resource_ids") or []
            if not isinstance(ids, list):
                raise InstallError(
                    "manifest-unreadable",
                    owner=repo_id,
                    target=target,
                    next_step=f"repair {repo_id}'s resource_ids then rerun",
                )
            required.extend(str(item) for item in ids)
        if depends:
            found.append((repo_id, tuple(required)))
    return found


def dest_for_record(resource: dict[str, Any], rec: dict[str, Any]) -> Path:
    root = Path(str(resource["resource_root"]))
    if resource.get("kind") == "file":
        return root
    return root / str(rec["path"])


def record_drift(resource: dict[str, Any]) -> tuple[str, str, str] | None:
    # Compare live bytes to recorded files[].sha256, not a recomputed tree
    # digest: planted manifests may store content sha256 as tree_sha256.
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


def stage_resource(
    resource_id: str, target: TargetName, staging_dir: Path
) -> ResourcePlan:
    source = source_for(resource_id)
    dest = dest_for(resource_id, target)
    if not source.is_file():
        raise InstallError(
            "missing-source",
            resource_id=resource_id,
            owner=REPO_ID,
            target=target,
            next_step="restore the Base payload file and rerun",
            detail=str(source),
        )
    if resource_id == "assistant":
        staged_path = staging_dir / "assistant" / ASSISTANT_NAME[target]
    else:
        staged_path = staging_dir / resource_id
    staged_path.parent.mkdir(parents=True, exist_ok=True)
    staged_path.write_text(render_text(source.read_text(encoding="utf-8"), target), encoding="utf-8")
    os.chmod(staged_path, 0o644)
    records = canonical_tree_files(staged_path)
    if not records:
        raise InstallError(
            "empty-resource",
            resource_id=resource_id,
            owner=REPO_ID,
            target=target,
            next_step="restore the Base payload file and rerun",
        )
    return ResourcePlan(
        resource_id=resource_id,
        resource_root=dest,
        kind="file",
        source_path=source,
        staged_path=staged_path,
        files=records,
        tree_sha256=canonical_tree_digest(staged_path),
    )


def build_plan(target: TargetName, staging_dir: Path) -> InstallPlan:
    resources = [stage_resource(resource_id, target, staging_dir) for resource_id in RESOURCE_IDS]
    if len(resources) != 15:
        raise InstallError(
            "resource-count",
            owner=REPO_ID,
            target=target,
            next_step="restore the 15-file Base payload and rerun",
            detail=f"planned {len(resources)} resources",
        )
    return InstallPlan(
        repo_id=REPO_ID,
        repo_version=repo_version(),
        target=target,
        requires=[],
        resources=resources,
        structured_entries=[],
        staging_dir=staging_dir,
    )


def reverse_dep_error(
    target: TargetName,
    dependents: Sequence[tuple[str, tuple[str, ...]]],
    *,
    dropping: Sequence[str],
    uninstall: bool,
) -> InstallError:
    names = ",".join(repo for repo, _ids in dependents)
    dropped = ",".join(dropping) if dropping else "all"
    action = "uninstall" if uninstall else "upgrade"
    return InstallError(
        "reverse-dep",
        resource_id=dropping[0] if dropping else "assistant",
        owner=names,
        target=target,
        next_step=f"uninstall {names} for target {target}, then rerun Base {action}",
        detail=f"{names} requires base-config resource_ids that {action} would drop ({dropped})",
    )


def validate_reverse_deps(
    root: Path,
    plan: InstallPlan,
    *,
    uninstall: bool,
) -> None:
    dependents = dependents_on_base(root, plan.target)
    if not dependents:
        return
    if uninstall:
        raise reverse_dep_error(plan.target, dependents, dropping=(), uninstall=True)
    desired = {resource.resource_id for resource in plan.resources}
    for repo_id, required_ids in dependents:
        missing = [resource_id for resource_id in required_ids if resource_id not in desired]
        if missing:
            raise reverse_dep_error(
                plan.target,
                ((repo_id, required_ids),),
                dropping=missing,
                uninstall=False,
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


def validate_conflicts(
    plan: InstallPlan, manifest: dict[str, Any] | None
) -> None:
    owned = owned_resources(manifest)
    for resource in plan.resources:
        dest = resource.resource_root
        if not lexists(dest):
            continue
        if dest in owned:
            continue
        # Existing dest without this repo's matching resource is a conflict
        # even when the current bytes happen to match the desired payload.
        actual = sha256_file(dest) if dest.is_file() and not dest.is_symlink() else "exists"
        raise InstallError(
            "conflict",
            resource_id=resource.resource_id,
            expected_digest=resource.tree_sha256,
            actual_digest=actual,
            owner="unowned",
            target=plan.target,
            next_step=(
                f"move or remove the existing file at {dest}, then rerun "
                f"install.sh --target {plan.target}"
            ),
        )


def validate_target(
    root: Path,
    plan: InstallPlan,
    *,
    uninstall: bool,
) -> None:
    manifest = load_own_manifest(root, plan.target)
    validate_reverse_deps(root, plan, uninstall=uninstall)
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
    validate_drift(manifest, target=plan.target, action="upgrade" if manifest else "install")
    validate_conflicts(plan, manifest)


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


def copy_staged_file(resource: ResourcePlan) -> None:
    dest = resource.resource_root
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = resource.staged_path.read_bytes()
    dest.write_bytes(data)
    mode = _MODE_BITS.get(resource.files[0].mode, 0o644)
    os.chmod(dest, mode)
    if dest.is_symlink() or not dest.is_file():
        raise InstallError(
            "write-failed",
            resource_id=resource.resource_id,
            owner=REPO_ID,
            next_step=f"inspect {dest} and rerun",
        )
    actual = sha256_file(dest)
    expected = resource.files[0].sha256 or "-"
    if actual != expected:
        raise InstallError(
            "write-failed",
            resource_id=resource.resource_id,
            expected_digest=expected,
            actual_digest=actual,
            owner=REPO_ID,
            next_step=f"inspect {dest} and rerun",
        )


def remove_empty_parents(path: Path, stop_at: Path) -> None:
    current = path
    while current != stop_at and stop_at in current.parents:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def apply_install(root: Path, plan: InstallPlan) -> None:
    validate_target(root, plan, uninstall=False)
    manifest = load_own_manifest(root, plan.target)
    owned = owned_resources(manifest)
    desired = {resource.resource_root: resource for resource in plan.resources}
    journal = write_journal(root, plan.target, "install")
    for resource in plan.resources:
        copy_staged_file(resource)
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
        dest.unlink()
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
    for resource in manifest.get("resources") or []:
        if not isinstance(resource, dict):
            raise InstallError(
                "manifest-unreadable",
                owner=REPO_ID,
                target=plan.target,
                next_step="repair installed.json then rerun",
            )
        files = resource.get("files") or []
        if not isinstance(files, list):
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
        for rec in files:
            if not isinstance(rec, dict):
                continue
            dest_for_record(resource, rec).unlink()
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
                staging = Path(tempfile.mkdtemp(prefix="base-config-stage-"))
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
