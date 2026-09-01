#!/usr/bin/env python3
"""Remove git-tracked eval result files that have no inbound reference."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULT_PREFIX = "tools/eval/results"
CORPUS_ROOTS = (
    "tests",
    "contracts",
    "shared/skills",
    "tools/eval/contracts",
    "tools/eval/scenarios",
)
TEXT_SUFFIXES = {".py", ".sh", ".json", ".md", ".yaml"}
COMPANION_REF_PATH = Path("tests/fixtures/eval-result-test-read-refs.json")

# product-eval-contract.sh names this directory then finds 36 of each basename.
ITERATION_1_PREFIX = "tools/eval/results/product-split-benchmark-20260415/iteration-1/"
ITERATION_1_NAMES = {"response.md", "grading.json", "timing.json", "eval_metadata.json"}

# product-split-benchmark-contract.sh names this directory then reads top-level files.
ITERATION_4_PREFIX = "tools/eval/results/product-split-benchmark-20260415/iteration-4/"
ITERATION_4_TOP_NAMES = {
    "benchmark.json",
    "benchmark.md",
    "benchmark-analysis.json",
    "review.html",
    "comparison-0.json",
    "comparison-1.json",
    "comparison-2.json",
    "comparison-3.json",
    "comparison-4.json",
    "comparison-5.json",
}


def git(*args: str, stdin: str | None = None) -> str:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        input=stdin,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout


def tracked(prefix: str) -> list[str]:
    return [line for line in git("ls-files", prefix).splitlines() if line]


def load_corpus(*, exclude: set[str]) -> str:
    chunks: list[str] = []
    for rel_root in CORPUS_ROOTS:
        root = ROOT / rel_root
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix not in TEXT_SUFFIXES or not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel in exclude:
                continue
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def exact_referenced(results: list[str], blob: str) -> set[str]:
    return {rel for rel in results if rel in blob}


def test_read_companions(results: list[str]) -> set[str]:
    keep: set[str] = set()
    for rel in results:
        name = Path(rel).name
        if rel.startswith(ITERATION_1_PREFIX) and name in ITERATION_1_NAMES:
            keep.add(rel)
            continue
        if (
            rel.startswith(ITERATION_4_PREFIX)
            and Path(rel).parent.name == "iteration-4"
            and name in ITERATION_4_TOP_NAMES
        ):
            keep.add(rel)
    return keep


def write_companion_refs(companions: set[str]) -> None:
    path = ROOT / COMPANION_REF_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "description": (
            "Eval result files tests read via directory roots rather than exact path literals."
        ),
        "files": sorted(companions),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def git_rm(paths: list[str]) -> None:
    if not paths:
        return
    git("rm", "-q", "--pathspec-from-file=-", stdin="\n".join(paths) + "\n")


def classify() -> tuple[list[str], set[str], set[str], list[str]]:
    results = tracked(RESULT_PREFIX)
    blob = load_corpus(exclude={COMPANION_REF_PATH.as_posix()})
    exact = exact_referenced(results, blob)
    companions = test_read_companions(results)
    keep = exact | companions
    unused = [rel for rel in results if rel not in keep]
    return results, exact, companions, unused


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="git rm unreferenced result files and write companion inbound refs",
    )
    args = parser.parse_args()
    results, exact, companions, unused = classify()
    print(
        f"tracked={len(results)} exact={len(exact)} "
        f"companions={len(companions)} unused={len(unused)}"
    )
    if not args.apply:
        for rel in unused[:20]:
            print(rel)
        if len(unused) > 20:
            print(f"... {len(unused) - 20} more")
        return 0
    write_companion_refs(companions)
    git_rm(unused)
    print(f"removed {len(unused)} unreferenced eval result files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
