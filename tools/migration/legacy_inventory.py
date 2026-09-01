"""Hard-coded cutover inventories. Preserve lists are never read from state files."""

from __future__ import annotations

from pathlib import Path

PRE_SPLIT_TAG = "pre-split-2026-08-31"

TEAM_SKILLS = frozenset(
    {
        "cli-updater",
        "commit",
        "consistency-audit",
        "deep-research",
        "delivery-estimator",
        "delivery-owner",
        "design",
        "developer",
        "feishu-docs",
        "fix",
        "github-repo-radar",
        "overview",
        "product-director",
        "product-manager",
        "project-memory",
        "prompt",
        "qa",
        "qft-branch-flow",
        "qft-group-chat-export",
        "refactor",
        "research",
        "review",
        "rules-manager",
        "scan",
        "security",
        "skill-quality-audit",
        "tech-lead",
        "test-design",
        "ux",
        "verify",
        "worktree",
    }
)

TEAM_CLAUDE_ONLY_SKILLS = frozenset({"code-review-fix", "doc-review-fix"})

DAILY_SKILLS = frozenset(
    {
        "agent-browser",
        "algorithmic-art",
        "brainstorming",
        "brand-guidelines",
        "canvas-design",
        "claude-api",
        "dispatching-parallel-agents",
        "doc-coauthoring",
        "docx",
        "domain-modeling",
        "executing-plans",
        "find-skills",
        "finishing-a-development-branch",
        "frontend-design",
        "grill-me",
        "grill-with-docs",
        "grilling",
        "internal-comms",
        "mcp-builder",
        "mermaid-diagrams",
        "obsidian-cli",
        "obsidian-markdown",
        "pdf",
        "pptx",
        "prompt-optimizer",
        "receiving-code-review",
        "requesting-code-review",
        "skill-creator",
        "skill-pull",
        "slack-gif-creator",
        "subagent-driven-development",
        "systematic-debugging",
        "test-driven-development",
        "theme-factory",
        "using-git-worktrees",
        "using-superpowers",
        "verification-before-completion",
        "web-artifacts-builder",
        "webapp-testing",
        "writing-plans",
        "writing-skills",
        "xlsx",
    }
)

PERSONAL_SKILLS = frozenset(
    {
        "agent-reach",
        "architecture",
        "baoyu-markdown-to-html",
        "bb-browser",
        "code-to-prd",
        "darwin-skill",
        "graphify",
        "humanizer-zh",
        "notebooklm",
        "planning-with-files",
        "prd",
        "self-improving-agent",
        "to-prd",
        "ui-ux-pro-max",
    }
)

EXPLICIT_DELETE_NAMES = frozenset(
    {
        "architecture-blueprint-generator",
        "job-description-analyzer",
        "resume-ats-optimizer",
        "resume-bullet-writer",
        "resume-tailor",
        "tailored-resume-generator",
        "tech-resume-optimizer",
        "qft-branch-management",
        "review-fix-loop",
        "codex-doc-review",
        "_retired-qft-chat-analysis-user-copy",
        "qft-chat-analysis",
        "qft-chat-analysis-workspace",
    }
)

FRESH_INSTALL_SKILLS = DAILY_SKILLS
REMOVE_OLD_ONLY_SKILLS = TEAM_SKILLS | TEAM_CLAUDE_ONLY_SKILLS | PERSONAL_SKILLS

PRESERVE_RELATIVE_PATHS = frozenset(
    {
        Path(".claude/skills/learned"),
        Path(".claude/skills/superset"),
        Path(".claude/hooks/superset_notify.sh"),
        Path(".claude/hooks/read_pages_context.py"),
        Path(".claude/hooks/worktree_create.sh"),
        Path(".claude/hooks/worktree_remove.sh"),
    }
)

# Matching Claude settings.json / Codex hooks.json command identities, including SUPERSET_HOME_DIR notify.
PRESERVE_SETTINGS_MARKERS = frozenset(
    {
        "superset_notify.sh",
        "read_pages_context.py",
        "worktree_create.sh",
        "worktree_remove.sh",
        "SUPERSET_HOME_DIR",
    }
)

BASE_RUNTIME_PATHS = (
    Path(".claude/CLAUDE.md"),
    Path(".codex/AGENTS.md"),
    Path(".claude/rules"),
    Path(".codex/rules"),
    Path(".claude/reference"),
    Path(".codex/reference"),
)

SKILL_ROOTS = (Path(".claude/skills"), Path(".agents/skills"))
# Copied Team support that landed under skills/ instead of shared/skills/.
SKILL_ROOT_SUPPORT_NAMES = frozenset({"lib"})
HOOK_ROOTS = (Path(".claude/hooks"), Path(".codex/hooks"))
TEAM_SUPPORT_TREES = (Path(".claude/shared/skills"), Path(".codex/shared/skills"))
STATE_DIRNAME = ".org-skills-state"

_KNOWN_STATE_LEAF_NAMES = frozenset(
    {
        "installed-manifest",
        "installed-version",
        "backup-manifest",
        "pruned-manifest",
        # Old monolith install.sh 0-byte sentinel beside installed-manifest.
        "agent-tuning-migration-v1",
        "claude-settings-baseline.json",
        "codex-hooks-baseline.json",
        "codex-hooks-feature-state.json",
    }
)
_KNOWN_STATE_DIR_NAMES = frozenset(
    {
        "backups",
        "unexpected-artifacts",
        "manual-skill-refiner-backups",
    }
)


def _posix(relative: Path | str) -> str:
    posix = Path(relative).as_posix()
    while posix.startswith("./"):
        posix = posix[2:]
    return posix


def is_preserve_relative(relative: Path | str) -> bool:
    rel = Path(_posix(relative))
    if rel in PRESERVE_RELATIVE_PATHS:
        return True
    posix = rel.as_posix()
    if posix.startswith(".agents/skills/superset-"):
        return True
    return any(
        posix == marker.as_posix() or posix.startswith(marker.as_posix() + "/")
        for marker in PRESERVE_RELATIVE_PATHS
    )


def classify_skill_name(name: str) -> str | None:
    if name in EXPLICIT_DELETE_NAMES:
        return "REMOVE_EXPLICIT_DELETE"
    if name in FRESH_INSTALL_SKILLS:
        return "REMOVE_FOR_FRESH_INSTALL"
    if name in REMOVE_OLD_ONLY_SKILLS:
        return "REMOVE_OLD_ONLY"
    return None


def is_known_legacy_state(relative: Path | str) -> bool:
    """Known ~/.org-skills-state children are deleted after verify; anything else is CONFLICT."""
    parts = [part for part in _posix(relative).split("/") if part]
    if not parts:
        return False
    top = parts[0]
    if top == "external-runtime-skills":
        return True
    if top == "archive":
        if len(parts) == 2 and parts[1] == "dot-claude-git.tar.gz":
            return True
        return len(parts) >= 2 and parts[1].startswith("dot-claude-retirement-")
    if top not in {"claude", "codex"}:
        return False
    if len(parts) == 1:
        return False
    name = parts[1]
    if name in _KNOWN_STATE_LEAF_NAMES:
        return True
    if name.endswith("-baseline.json") or name.endswith("-feature-state.json"):
        return True
    return name in _KNOWN_STATE_DIR_NAMES
