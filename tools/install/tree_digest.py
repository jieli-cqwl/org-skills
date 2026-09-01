from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Literal

_CHUNK_SIZE = 1024 * 1024
_EXEC_BITS = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


@dataclass(frozen=True)
class FileRecord:
    path: str
    kind: Literal["file", "symlink"]
    mode: Literal["0644", "0755"]
    sha256: str | None
    link_target: str | None


def canonical_tree_files(root: Path) -> list[FileRecord]:
    root = Path(root)
    if _is_plain_directory(root):
        records = [_record_for(path, root) for path in _iter_tree_entries(root)]
        records.sort(key=lambda rec: rec.path)
        return records
    return [_record_for(root, root.parent)]


def canonical_tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for rec in canonical_tree_files(root):
        digest.update(_record_line(rec))
    return digest.hexdigest()


def _record_line(rec: FileRecord) -> bytes:
    return (
        "\0".join(
            [rec.path, rec.kind, rec.mode, rec.sha256 or "", rec.link_target or ""]
        )
        + "\n"
    ).encode("utf-8")


def _is_plain_directory(path: Path) -> bool:
    return stat.S_ISDIR(path.lstat().st_mode)


def _iter_tree_entries(root: Path) -> Iterator[Path]:
    stack = [root]
    while stack:
        current = stack.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                path = Path(entry.path)
                if entry.is_symlink():
                    yield path
                    continue
                if entry.is_dir(follow_symlinks=False):
                    stack.append(path)
                    continue
                if entry.is_file(follow_symlinks=False):
                    yield path
                    continue
                raise ValueError(f"unsupported path kind: {path}")


def _record_for(path: Path, walk_root: Path) -> FileRecord:
    rel = _relative_posix(path, walk_root)
    st = path.lstat()
    if stat.S_ISLNK(st.st_mode):
        link_target = os.readlink(path)
        _reject_unsafe_link_target(link_target)
        return FileRecord(
            path=rel,
            kind="symlink",
            mode="0644",
            sha256=None,
            link_target=link_target,
        )
    if not stat.S_ISREG(st.st_mode):
        raise ValueError(f"unsupported path kind: {path}")
    return FileRecord(
        path=rel,
        kind="file",
        mode="0755" if st.st_mode & _EXEC_BITS else "0644",
        sha256=_sha256_bytes(path),
        link_target=None,
    )


def _relative_posix(path: Path, walk_root: Path) -> str:
    rel = path.relative_to(walk_root)
    if any(part == ".." for part in rel.parts) or rel.is_absolute():
        raise ValueError(f"path escapes resource root: {path}")
    posix = rel.as_posix()
    if posix in {"", "."}:
        raise ValueError(f"path is not a tree entry: {path}")
    return posix


def _reject_unsafe_link_target(link_target: str) -> None:
    # Fail closed: absolute targets and any '..' hop can leave the resource root.
    target = Path(link_target)
    if target.is_absolute() or any(part == ".." for part in target.parts):
        raise ValueError(f"unsafe symlink target: {link_target}")


def _sha256_bytes(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
