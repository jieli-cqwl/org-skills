"""Spec ownership inventories for the repository split.

Lists are copied verbatim from
docs/superpowers/specs/2026-08-31--repository-split-and-clean-runtime-migration--design.md.
"""

from __future__ import annotations

DAILY_SKILLS: tuple[str, ...] = (
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
)

PERSONAL_SKILLS: tuple[str, ...] = (
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
)

TEAM_SKILLS: tuple[str, ...] = (
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
)

TEAM_CLAUDE_ONLY_SKILLS: tuple[str, ...] = (
    "code-review-fix",
    "doc-review-fix",
)

BASE_FILES: tuple[str, ...] = (
    "assistant.md",
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

REJECTED_SKILLS: tuple[str, ...] = (
    "architecture-blueprint-generator",
    "job-description-analyzer",
    "resume-ats-optimizer",
    "resume-bullet-writer",
    "resume-tailor",
    "tailored-resume-generator",
    "tech-resume-optimizer",
)

# Daily names absent from Git; fetch in Plan 2. Status must stay MISSING_FROM_GIT_FETCH_IN_PLAN_2.
GRILL_OBSIDIAN_SKILLS: tuple[str, ...] = (
    "domain-modeling",
    "grill-me",
    "grill-with-docs",
    "grilling",
    "obsidian-cli",
    "obsidian-markdown",
)

STALE_RUNTIME_TRACES: tuple[str, ...] = (
    "qft-branch-management",
    "review-fix-loop",
    "codex-doc-review",
    "_retired-qft-chat-analysis-user-copy",
    "qft-chat-analysis",
    "qft-chat-analysis-workspace",
)

OUT_OF_SCOPE_PATHS: tuple[str, ...] = (
    "claude-code-engineering/",
    "qft-cc-core/",
)

REPO_DAILY = "daily-skills"
REPO_PERSONAL = "personal-skills"
REPO_TEAM = "team-skills"
REPO_BASE = "base-config"
ACTION_DELETE = "DELETE"

MISSING_FROM_GIT_FETCH_IN_PLAN_2 = "MISSING_FROM_GIT_FETCH_IN_PLAN_2"

_SKILL_REPO: dict[str, str] = {}
_SKILL_REPO.update({name: REPO_DAILY for name in DAILY_SKILLS})
_SKILL_REPO.update({name: REPO_PERSONAL for name in PERSONAL_SKILLS})
_SKILL_REPO.update({name: REPO_TEAM for name in TEAM_SKILLS})
_SKILL_REPO.update({name: REPO_TEAM for name in TEAM_CLAUDE_ONLY_SKILLS})


def skill_repo(name: str) -> str | None:
    return _SKILL_REPO.get(name)


def is_rejected(name: str) -> bool:
    return name in REJECTED_SKILLS


def is_stale_trace(name: str) -> bool:
    return name in STALE_RUNTIME_TRACES
