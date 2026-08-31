# Repository Split and Clean Runtime Migration Design

**Status:** Written spec approved for implementation planning on 2026-08-31. Five ordered plans live under `docs/superpowers/plans/2026-08-31--repository-split--01` through `--05`. Runtime mutation remains unauthorized until Plan 5 cutover gates pass and all four remotes have pushed cutover commits.

**Authority:** This document is the single design source for the repository split and the one-time local runtime migration. It does not replace standard-chain canonical artifacts or enter `contracts/active-doc-scope.yaml`.

## Goal

Split the current monolithic repository into one base-configuration repository and three Skill repositories with different maintenance purposes. A user or LLM chooses what to install for the current environment; the repositories do not encode Profiles or silently install sibling repositories.

After the split, this machine must contain a fresh installation of only:

- `base-config`;
- `daily-skills`.

The old monolithic installation must be removed completely. Recovery relies on pushed Git commits, tags, locked upstream refs, and provenance—not on persistent local content backups.

## Design Principle

Repository ownership and runtime composition are different decisions:

- A repository answers **who maintains this resource**.
- An installation command answers **what this environment needs now**.
- A dependency is declared only when source evidence proves the caller cannot fulfill its contract without that resource.
- A dependency declaration identifies the smallest required unit; it does not justify a Profile, a central orchestrator, or a shared package-manager library. A whole-repository dependency is allowed only when source evidence requires that repository's complete contract.

This is the minimum architecture that preserves clean ownership without replacing the monorepo with a more complicated distributed monorepo.

## Confirmed Decisions

1. There are four logical repositories: `base-config`, `daily-skills`, `team-skills`, and `personal-skills`.
2. The current repository remains `team-skills` and retains its full Git history. The other three repositories start from snapshot commits with provenance.
3. `base-config` contains the global assistant entry, rules, and references. It contains no Skills, hooks, agents, protocols, source locks, or standard-chain runtime.
4. All repository-managed `hooks/`, `agents/`, and `protocols/` belong to `team-skills`, including `block_dangerous` and the current Claude engineering hooks.
5. `daily-skills` owns Superpowers, Anthropic, Vercel, `skill-pull`, `mermaid-diagrams`, `prompt-optimizer`, the Obsidian pair, and the four Grill Skills.
6. `personal-skills` owns architecture-, PRD-, visualization-, and personal-workflow Skills.
7. Seven rejected external Skills are deleted completely. Grill stays daily. Only the Obsidian pair remains from the previously reviewed group of nine external Skills.
8. The local cutover installs Base and Daily only. This is an explicit one-time composition choice, not a reusable Profile.
9. Git is the recovery source. The migration creates no persistent content backup and deletes the legacy backup/state tree after successful verification.
10. Installers install only their own repository. Missing hard Skill dependencies are reported by exact Skill name and owner; installers do not clone or install sibling repositories.

## Acceptance Scope

The split is accepted only when all of the following are directly proven:

1. Every current source resource is mapped to exactly one repository, explicit deletion, or explicit out-of-scope preservation.
2. Base contains only assistant/rules/reference payload plus its own minimal install, test, release, and provenance files.
3. Daily and Personal contain Skills and their source-maintenance assets, but no hooks, agents, protocols, standard-chain runtime, or copied common installer library.
4. Team contains every standard-chain hook, agent, protocol, runtime catalog, team Skill, contract, validator, and team-only test it needs.
5. The three Skill inventories are disjoint. `lib/` and `*-workspace/` directories are not misclassified as installable Skills.
6. Every declared hard dependency has a source anchor. Every cross-repository reference that is not a hard dependency is explicitly classified as optional, test-only, or documentation-only.
7. Each repository can install, upgrade, dry-run, and uninstall only its own resources without a central orchestrator. A dependent installer checks preconditions but never mutates the dependency owner.
8. The one-time migration removes all legacy org-managed runtime resources before freshly installing Base and Daily; it does not adopt old files in place.
9. Plugin- and user-owned resources are byte-for-byte preserved.
10. The old `~/.org-skills-state` tree, including its content backups and archives, is absent after success.
11. New persistent installer state contains ownership and integrity metadata only, never copies of installed content.
12. Local Claude and Codex contain Base and Daily resources only, plus preserved external/plugin resources; Team, Personal, rejected, stale, and retired org-managed resources are absent.
13. Generated workspaces, review diffs, local result cards, stale planning ledgers, and unreferenced raw evaluation output are not copied into new repositories or retained as active Team source.

## Evidence From the Current Repository and Runtime

Observed on 2026-08-31 from source baseline `b00f1ff6` and the installed Claude/Codex runtimes:

- The installed version fingerprint is `1.2.4-20dbfa45-dirty-f57e224e`; current runtime bytes therefore cannot be assumed to equal a clean Git commit.
- Legacy installed manifests are path lists. They prove that the old installer claimed paths, but do not prove that current content still equals installed content.
- The legacy uninstaller restores whole-file Claude settings and Codex hook baselines, can resurrect backup content, and does not reliably remove structured Codex Agent configuration. It is unsafe for this cutover.
- `~/.org-skills-state/archive/` currently contains a `dot-claude-git.tar.gz` backup and related retirement records. Keeping or moving that archive would violate the no-local-backup decision.
- Codex configuration contains `[features] multi_agent = true` and five team Agent sections. The actual key identity is `features.multi_agent`, not a top-level `multi_agent` key.
- `features.hooks` cannot be blindly restored to its old false state because surviving Superset/user hook entries still need hooks enabled.
- External resources currently include Claude `learned/`, Claude plugin root `superset/`, Codex `superset-*`, and Superset/worktree/read-pages hook files and entries. They are not owned by this repository.
- Grill Skills exist in both runtimes but are absent from Git. Their upstream bodies match `mattpocock/skills@bb1c760d559872044e76d18216c87165fa69908a` apart from declared runtime-surface fields.
- Obsidian Skills exist in Codex but are absent from Git. The selected upstream ref is `kepano/obsidian-skills@a1dc48e68138490d522c04cbf5822214c6eb1202`.
- `shared/skills/lib/` has no `SKILL.md` and is a team library. `shared/skills/qft-branch-flow-workspace/` is an evaluation workspace and must never be installed as a Skill.
- `contracts/skill-runtime-surface.json` contains stale `qft-branch-management`; no corresponding source or runtime Skill exists.
- `claude/skills/code-review-fix` and `doc-review-fix` are team-only Claude Skills and were missing from the first inventory draft.
- Source inspection proves three current hard Skill edges:
  - `grill-me` calls `grilling`;
  - `grill-with-docs` calls `grilling` and `domain-modeling`;
  - team `fix` requires daily `systematic-debugging` before diagnosis or code changes.
- Team `qa` mentions `webapp-testing`, but also accepts Playwright or an equivalent project browser tool. That is an optional integration, not a hard dependency.
- Other hits such as `brainstorming` in evaluation evidence are test/document references, not runtime dependencies.
- Team runtime content has a real Base dependency: Team Skills directly read six Base paths (`rules/code-changes.md`, `rules/completion-claims.md`, `reference/code-structure-reuse.md`, `reference/impact-analysis.md`, `reference/技术方案设计.md`, and `reference/测试规范.md`), while `claude/hooks/post_compact.sh` instructs the runtime to reload all Claude rules after compaction.
- Root `AGENTS.md`, `README.md`, install tests, rule-runtime evaluators, fixtures, and probes still reference `shared/assistant.md`, `shared/rules/`, or `shared/reference/`. Moving only the payload would leave broken source paths; these consumers must move or be rewritten with their owner.
- Although `.gitignore` already ignores `.superpowers/`, 185 files remain tracked there and occupy about 42 MB in the working tree. They are generated brainstorm/SDD workspaces and review packages, not canonical source.
- `tools/eval/results/` contains about 3,142 files and 36 MB. Some summaries are active test fixtures, so blanket deletion is unsafe; unreferenced raw output must be pruned while referenced baselines move with their capability owner.
- Tracked `.claude/skills/darwin-skill/` cards/results are generated Personal-Skill output, not the canonical Darwin source under `community/alchaincyf/`. `.claude/settings.local.json` also contains a hard-coded permission for the old repository path.

## Repository Boundaries

| Logical repository | Purpose | Installed locally after cutover | History policy |
|---|---|---:|---|
| `base-config` | Global assistant entry, rules, references | Yes | New snapshot repository with provenance |
| `daily-skills` | General daily Skills and external Skill maintenance | Yes | New snapshot repository with provenance |
| `team-skills` | Standard-chain and team delivery capabilities | No | Current repository, full history retained |
| `personal-skills` | Architecture, PRD, visualization, personal workflow | No | New snapshot repository with provenance |

Logical IDs are installer identities. Physical remote URLs do not change runtime ownership. Before implementation creates or pushes the three new repositories, the user must provide or approve their remote URLs; local runtime mutation is blocked until all required commits and tags are pushed.

### Base Configuration Repository

Initial payload:

```text
assistant.md
rules/code-changes.md
rules/completion-claims.md
rules/document-governance.md
rules/execution-control.md
reference/authentication-and-authorization.md
reference/code-comments.md
reference/code-structure-reuse.md
reference/constants-and-configuration.md
reference/error-handling.md
reference/impact-analysis.md
reference/performance-and-efficiency.md
reference/协作判断.md
reference/技术方案设计.md
reference/测试规范.md
```

These files are copied from current `shared/assistant.md`, `shared/rules/`, and `shared/reference/`.

Repository support files are limited to what Base itself needs:

```text
install.sh
tools/install/
tests/
VERSION
README.md
AGENTS.md
CLAUDE.md
PROVENANCE.md
```

Base does not provide a shared installer implementation or generic compatibility protocol. Installing Base is not a precondition for Daily or Personal; Team checks Base only because Team source contains the concrete dependency documented below.

Runtime destinations remain the current global entry/rule/reference locations for the selected Claude or Codex target.

### Daily Skill Repository

Initial installable Skill inventory:

```text
agent-browser
algorithmic-art
brainstorming
brand-guidelines
canvas-design
claude-api
dispatching-parallel-agents
doc-coauthoring
docx
domain-modeling
executing-plans
find-skills
finishing-a-development-branch
frontend-design
grill-me
grill-with-docs
grilling
internal-comms
mcp-builder
mermaid-diagrams
obsidian-cli
obsidian-markdown
pdf
pptx
prompt-optimizer
receiving-code-review
requesting-code-review
skill-creator
skill-pull
slack-gif-creator
subagent-driven-development
systematic-debugging
test-driven-development
theme-factory
using-git-worktrees
using-superpowers
verification-before-completion
web-artifacts-builder
webapp-testing
writing-plans
writing-skills
xlsx
```

Source ownership:

- locked Anthropic Skills;
- locked Superpowers Skills, kept as a pure upstream mirror;
- Vercel `agent-browser` and `find-skills`;
- first-party `skill-pull`;
- `mermaid-diagrams`;
- `prompt-optimizer`;
- `obsidian-cli` and `obsidian-markdown`;
- `grill-me`, `grilling`, `grill-with-docs`, and `domain-modeling`.

Grill initially locks `mattpocock/skills@bb1c760d559872044e76d18216c87165fa69908a`. Obsidian initially locks `kepano/obsidian-skills@a1dc48e68138490d522c04cbf5822214c6eb1202`. Existing Anthropic, Superpowers, Vercel, Mermaid, and prompt-optimizer refs are copied unchanged from the current source lock.

The installer target controls where supported Skills are installed. Obsidian is not frozen as Codex-only merely because the current local copy happens to exist only in Codex. The local `--target all` cutover installs the Daily inventory to both Claude and Codex unless a Skill's own source/surface contract explicitly forbids a target.

Daily contains no hooks. Current `claude/hooks/*` files do not move here.

Recommended source layout:

```text
first-party/skills/skill-pull/
vendor/anthropic/
vendor/superpowers/
vendor/vercel/
vendor/awesome-copilot/prompt-optimizer/
vendor/softaworks/mermaid-diagrams/
vendor/obsidian/
vendor/mattpocock/
adapters/codex/
sources/SOURCES.yaml
contracts/dependencies.yaml
contracts/skill-runtime-surface.json
contracts/superpowers-boundary.yaml
tools/source-sync/
tools/install/
tests/
install.sh
VERSION
README.md
AGENTS.md
CLAUDE.md
PROVENANCE.md
```

Vendor directories remain source-pure. Runtime visibility/frontmatter and Codex adapters live outside vendor trees.

### Team Skill Repository

The current repository becomes `team-skills` without history rewriting.

It owns:

- all current `shared/skills/*` except `skill-pull`;
- `shared/skills/lib/` as a non-installable library;
- `shared/skills/qft-branch-flow-workspace/` as a non-installable evaluation workspace;
- `claude/skills/code-review-fix` and `claude/skills/doc-review-fix`;
- every current `shared/hooks/` and `claude/hooks/` resource;
- `shared/agents/`;
- `shared/protocols/`;
- `shared/runtime/`;
- standard-chain contracts, canonical schemas, validators, tools, tests, fixtures, docs, and examples;
- the team installer and its structured configuration logic.

First-party installable Skills:

```text
cli-updater
commit
consistency-audit
deep-research
delivery-estimator
delivery-owner
design
developer
feishu-docs
fix
github-repo-radar
overview
product-director
product-manager
project-memory
prompt
qa
qft-branch-flow
qft-group-chat-export
refactor
research
review
rules-manager
scan
security
skill-quality-audit
tech-lead
test-design
ux
verify
worktree
```

Claude-only installable Skills:

```text
code-review-fix
doc-review-fix
```

Team installs its own standard-chain hooks, agents, protocols, and runtime data. It does not copy Base configuration, but it requires Base on the same runtime target because Team Skills and `post_compact` consume Base rules/references. Team's other current cross-repository hard dependency is `fix -> daily-skills/systematic-debugging`.

### Personal Skill Repository

Initial installable Skill inventory:

```text
agent-reach
architecture
baoyu-markdown-to-html
bb-browser
code-to-prd
darwin-skill
graphify
humanizer-zh
notebooklm
planning-with-files
prd
self-improving-agent
to-prd
ui-ux-pro-max
```

Personal owns its own vendor trees, source lock, Codex adapters, `contracts/dependencies.yaml`, runtime-surface policy, source-specific update adapters, installer, and tests. It contains no hooks, agents, protocols, or standard-chain runtime.

It is extracted and verified but is not installed on this machine during the cutover.

### Explicit Deletions

The following seven rejected external Skills must be absent from every new source lock, repository, runtime-surface contract, installer manifest, Claude runtime, and Codex runtime:

```text
architecture-blueprint-generator
job-description-analyzer
resume-ats-optimizer
resume-bullet-writer
resume-tailor
tailored-resume-generator
tech-resume-optimizer
```

Also remove stale or retired org-managed runtime traces:

```text
qft-branch-management
review-fix-loop
codex-doc-review
_retired-qft-chat-analysis-user-copy
qft-chat-analysis
qft-chat-analysis-workspace
```

No tombstone or local content copy is retained. Historical recovery uses Git history or the recorded upstream source.

## Ownership Denominator

Every current top-level source group has one terminal decision:

| Current source atom | Target action | Owner / reason |
|---|---|---|
| `shared/assistant.md` | MOVE | Base |
| `shared/rules/` | MOVE | Base |
| `shared/reference/` | MOVE | Base |
| active tests, fixtures, probes, and evaluator code whose primary subject is assistant/rules/reference behavior | MOVE/SPLIT | Base owns Base behavior; Team keeps only tests of Team consumption |
| root `AGENTS.md`, `README.md`, and other active refs to moved `shared/*` paths | REWRITE | Team must not retain dead source-path references |
| `shared/skills/skill-pull/` | MOVE | Daily |
| `community/anthropic/` | MOVE/RELAYOUT | Daily |
| `community/superpowers/` | MOVE/RELAYOUT | Daily |
| `community/vercel/` | MOVE/RELAYOUT | Daily |
| `community/open-skills/.../mermaid-diagrams` | MOVE/RELAYOUT | Daily |
| `community/open-skills/.../prompt-optimizer` | MOVE/RELAYOUT | Daily |
| Grill and Obsidian locked upstream subtrees | FETCH | Daily; absent from current Git |
| `contracts/superpowers-boundary.yaml` and its active validators/tests | MOVE/REWRITE | Daily owns Superpowers mirror purity |
| remaining current `community/*` Skill sources and adapters | MOVE/RELAYOUT | Personal, as listed in its inventory |
| `community/SOURCES.yaml` | SPLIT | Daily and Personal keep only their own sources |
| `shared/skills/*` except `skill-pull` | KEEP | Team; `lib` and workspace stay non-installable |
| `claude/skills/code-review-fix`, `doc-review-fix` | KEEP | Team, Claude-only |
| all `shared/hooks/` and `claude/hooks/` | KEEP | Team |
| `shared/agents/`, `shared/protocols/`, `shared/runtime/` | KEEP | Team |
| standard-chain/canonical contracts, tools, tests, fixtures, docs, examples | KEEP | Team |
| mixed runtime-surface and source-lock contracts | SPLIT | Each Skill repo gets only its own keys; Team keeps team keys |
| tracked `.superpowers/` workspaces, review diffs, and stale PID files | DELETE FROM ACTIVE HEAD | Generated artifacts already ignored; Git history is recovery |
| tracked `.claude/skills/darwin-skill/` result cards/TSV | DELETE FROM ACTIVE HEAD | Generated output, not Personal source truth |
| `.claude/settings.local.json` hard-coded old-path permission | DELETE/RECREATE ONLY IF NEEDED | The referenced Base paths leave Team |
| `.github/workflows/` | SPLIT/REWRITE | Team keeps Team gates; each new repo creates only its own minimal workflow |
| root `.gitignore`, `.gitleaks.toml`, `AGENTS.md`, `CLAUDE.md`, `README.md`, `CHANGELOG.md`, `VERSION`, installers | KEEP/REWRITE | Team keeps its lineage; new repos create fresh owner-specific files rather than copy mixed roots |
| root `findings.md`, `progress.md`, `task_plan.md` | DELETE AFTER INBOUND-REF CHECK | Stale planning ledgers; do not copy to any snapshot repo |
| `tools/eval/results/` | KEEP/MOVE/PRUNE BY INBOUND REF | Retain only active test baselines; move Base-owned evidence; drop unreferenced raw output from active HEAD |
| seven rejected Skills and stale/retired traces | DELETE | Explicit user decision or no live source |
| `claude-code-engineering/`, absent `qft-cc-core/` | KEEP OUT OF SCOPE | Ignored nested checkouts, not managed split payload |

Implementation must generate a machine-readable inventory from actual source roots and fail if any current Skill root, source-lock entry, runtime-surface key, hook, agent, protocol, or installer destination is unmapped or mapped more than once. The table is the design denominator; the generated inventory is verification evidence, not a second source of truth.

Active-tree cleanup is conservative: a tracked result or report with an active test/contract inbound reference stays or moves with its owner; an unreferenced generated artifact is deleted from active HEAD. Nothing is copied into a backup directory because its prior bytes remain in Git history.

Historical designs and result summaries may retain old monolith paths as dated provenance when they are not active handoff inputs. Active instructions, contracts, tests, fixtures, workflows, and README links must resolve in their new owner repository; history is not an excuse for a broken active reference.

## Dependency Model: Evidence, Then On-Demand Acquisition

There is one proven repository-level dependency, four proven runtime Skill edges, and one maintenance-only edge. They are declared next to the caller in `contracts/dependencies.yaml`:

| Caller | Scope | Required unit | Owner | Evidence |
|---|---|---|---|---|
| `team-skills` | runtime install | Base installed on the same target | Base | Team consumes six named Base rule/reference paths; `post_compact` consumes the Base rules directory |
| `daily/grill-me` | runtime invocation | `grilling` | Daily | `grill-me/SKILL.md` calls the Skill tool with `grilling` |
| `daily/grill-with-docs` | runtime invocation | `grilling` | Daily | `grill-with-docs/SKILL.md` calls it |
| `daily/grill-with-docs` | runtime invocation | `domain-modeling` | Daily | `grill-with-docs/SKILL.md` calls it |
| `team/fix` | runtime invocation | `systematic-debugging` | Daily | `fix/SKILL.md` marks it REQUIRED and sole owner of diagnosis |
| Personal source update | maintenance only | `skill-pull` | Daily | Personal owns external source locks but the user assigned the generic updater to Daily |

Rules:

1. A repository installer installs only that repository's payload for the selected target.
2. Base, Daily, and Personal have no repository prerequisite.
3. Team requires Base on the same target. It checks Base's installed manifest and the required resource paths; it does not install or update Base.
4. Internal dependencies must be present in the same install plan; the default full-repository Daily install satisfies the Grill edges.
5. A missing cross-repository Skill prerequisite stops that capability when it is checked or invoked; it does not block installation of unrelated Team capabilities. The error names the exact owner and Skill path and never triggers an implicit clone or whole-Daily installation.
6. The user or LLM may acquire that exact Skill using the runtime's existing Skill installation mechanism, then rerun the check. This design does not build a dependency resolver.
7. Optional/tool-substitutable references do not enter the hard dependency contract.
8. Upstream Superpowers dependency instructions remain upstream truth; this repository does not duplicate them into a second graph.
9. Install-time tools are checked by the owning installer. Skill-specific executables, authentication, and services such as Obsidian CLI, browser state, Bun/npm, or NotebookLM are acquired only when that Skill is invoked; they are not preinstalled merely because the repository is installed.
10. Personal installation does not require Daily. Only a Personal source-update run requires `skill-pull`, which is acquired on demand like any other maintenance Skill.
11. CI validates repo-local behavior and only the real dependency edges owned by that repository. There is no permanent all-combinations composition matrix.

This model admits the necessary `Team -> Base` relationship and the actual `fix -> systematic-debugging` edge without turning Team into a dependency on all 42 Daily Skills.

## `skill-pull` Ownership and Source Updates

`skill-pull` moves to Daily and becomes checkout-scoped:

1. It runs in the repository the user wants to update.
2. It reads only that checkout's `sources/SOURCES.yaml` and declared source-specific adapters.
3. It changes only paths owned by those source entries.
4. It verifies locked ref, subtree fidelity, license/provenance metadata, adapters, surfaces, and the target repository's tests.
5. It shows the diff and validation result. Commit and push remain explicit user actions.

The generic orchestration code stays inside the Daily `skill-pull` Skill. Daily- and Personal-specific extraction adapters stay in their respective repositories. No generic source-sync library is vendored between repositories, Team has no external Skill source lock after contraction, and Base has no source lock.

## Minimal Installer Contract

Each repository owns its installer implementation. There is no canonical installer library in Base and no runtime import from sibling checkouts.

All installers follow the same small behavioral contract because they share runtime directories:

```text
install.sh [--target claude|codex|all] [--dry-run] [--uninstall]
```

### Resource Ownership State

Persistent state root:

```text
${SKILL_REPO_STATE_ROOT:-${XDG_STATE_HOME:-$HOME/.local/state}/skill-repos}
```

Per target:

```text
<state-root>/<repo-id>/<target>/installed.json
```

The manifest records metadata only:

```json
{
  "schema_version": 1,
  "repo_id": "base-config|daily-skills|team-skills|personal-skills",
  "repo_version": "<VERSION>",
  "target": "claude|codex",
  "requires": [
    {
      "repo_id": "<required repo id>",
      "target": "same",
      "resource_ids": ["<required resource id>"]
    }
  ],
  "resources": [
    {
      "resource_id": "<stable repo-local id>",
      "resource_root": "<absolute file or directory>",
      "kind": "file|tree|symlink",
      "tree_sha256": "<canonical digest>",
      "files": [
        {
          "path": "<relative path>",
          "kind": "file|symlink",
          "mode": "0644|0755",
          "sha256": "<hex>",
          "link_target": "<symlink only>"
        }
      ]
    }
  ],
  "structured_entries": []
}
```

`resource_root`, desired file set, and tree digest are mandatory. A path-only manifest is forbidden because it cannot detect stale files left inside a Skill directory after upgrade. Tree digests use sorted relative paths plus kind, executable mode, content digest, and symlink target; timestamps and host ownership are excluded. Absolute paths, `..` traversal, and symlinks escaping the resource root are rejected.

Only repository-level install prerequisites enter `requires`; initially that is Team→Base. Invocation-time Skill prerequisites and Personal's maintenance-only `skill-pull` edge stay in `contracts/dependencies.yaml` and do not turn the whole repository into an installed dependent.

### Install, Upgrade, and Uninstall Rules

1. Acquire the common state lock before reading or mutating runtime ownership.
2. Render/stage the complete selected target plan in a bounded temporary directory.
3. Validate all target paths and structured entries before the first mutation.
4. Validate declared dependencies before the first mutation. Team reads Base's metadata manifest and required installed paths; it does not import Base installer code.
5. A new destination must be absent. Existing content without this repo's matching manifest is a conflict even when bytes happen to match.
6. Upgrade is allowed only when every currently owned resource matches its recorded digest. It reconciles the complete desired file set, including removal of files no longer present.
7. Drift stops upgrade or uninstall. The installer reports the resource and expected/actual digest; it does not overwrite or delete modified content.
8. Uninstall removes only resources whose current digest matches the manifest and only structured entries whose exact identity/value still matches.
9. Before uninstalling or removing required resource IDs, scan the metadata manifests for reverse repository dependencies. Base uninstall or an incompatible Base resource removal stops while Team is installed on that target and names the dependent; Team must be removed first.
10. Shared parent directories are containers, not owned resources. Base records each assistant/rule/reference file; Skill repositories record each Skill tree; Team records each hook/agent/protocol resource at its real ownership root.
11. Installers never own an entire shared settings/config file and never restore a whole-file baseline.
12. `--target all` validates both targets first, then records the outcome of each target. If an external concurrent write causes one target to stop, the command reports visible partial success and a safe rerun path; it never claims all-target success.
13. Temporary staging and an in-progress metadata journal may exist only during the operation. Both are cleaned after success. They contain no backup copy outside the bounded staging tree and are not retained as recovery artifacts.

Team alone needs structured configuration handling for hook identities and Codex Agent sections. Base, Daily, and Personal do not inherit that machinery merely for uniformity.

## One-Time Clean Migration

The cutover uses a one-time cleaner from a pinned Team commit. It is not a fifth installer and does not become a permanent orchestration layer.

The cleaner receives explicit paths to the prepared Base and Daily checkouts. It never calls the legacy uninstaller.

### Phase 1: Preflight and Drift Audit

Build one action plan covering every legacy manifest path, known old resource root, structured configuration entry, external preserved path, and old state file.

Classifications:

```text
REMOVE_FOR_FRESH_INSTALL
REMOVE_OLD_ONLY
REMOVE_EXPLICIT_DELETE
PRESERVE_EXTERNAL
DELETE_LEGACY_STATE
CONFLICT
```

Requirements:

- Render the expected old runtime from the exact pre-split Git tag and compare current old-managed resources by resource root/tree digest.
- The dirty installed fingerprint is not an exception. Every diff must be explained by a declared runtime overlay, an approved deletion, or an explicit preserved external owner.
- Unexplained drift is `CONFLICT` and stops before mutation. The user may commit/recover the content or explicitly authorize discard; the cleaner does not decide.
- Legacy path manifests are ownership clues, not content proof.
- The prepared Base and Daily commits, source locks, provenance, and pre-split recovery tag must exist and be pushed.
- Daily vendor trees must match their locked upstream refs, allowing only declared runtime-surface differences in installed copies.
- Any unexpected file inside `~/.org-skills-state` stops preflight. Known manifests, baselines, backups, and the current `archive/dot-claude-retirement-*` tree are classified `DELETE_LEGACY_STATE`; they are not moved elsewhere.
- Existing runtime resources outside legacy manifests default to `PRESERVE_EXTERNAL`. The only exceptions are the user-approved deletion list and the Grill/Obsidian destinations selected for remove-then-fresh-install. An unowned path that collides with any other planned destination is `CONFLICT`.

`PRESERVE_EXTERNAL` includes at least:

```text
~/.claude/skills/learned/
~/.claude/skills/superset/
~/.agents/skills/superset-*
~/.claude/hooks/superset_notify.sh
~/.claude/hooks/read_pages_context.py
~/.claude/hooks/worktree_create.sh
~/.claude/hooks/worktree_remove.sh
```

The exact matching Claude settings and Codex `hooks.json` entries, including `SUPERSET_HOME_DIR` notify commands, are preserved. `external-runtime-skills/*.txt` is not trusted as a preserve list.

### Phase 2: Remove the Old Installation

Immediately before each mutation, compare the current digest with the preflight action. A changed path stops that action and leaves the failure visible.

Remove:

- all old org-managed Base/Daily/Team/Personal Skill and configuration resources (`REMOVE_FOR_FRESH_INSTALL` for Base/Daily destinations, `REMOVE_OLD_ONLY` for Team/Personal);
- the currently installed Grill and Obsidian trees after their source/digest checks, so their new Daily manifests start from a fresh write;
- all current repository-managed hooks, agents, protocols, runtime catalogs, and team Agent files;
- all `REMOVE_EXPLICIT_DELETE` rejected, stale, and retired runtime resources;
- exact old-managed hook entries and the five team Codex Agent sections when their current values match the old installer output.

Structured configuration rules:

- Never restore `claude-settings-baseline.json` or `codex-hooks-baseline.json`.
- Remove only exact old-managed JSON hook identities; preserve unrelated entries and ordering/fields as far as the parser permits.
- Remove the five exact team `[agents.*]` sections when their managed fields match. User-added or changed fields are drift and stop that section's removal.
- Treat `features.multi_agent` as the correct TOML identity. Remove it only when it matches the old emitted value, no non-team Agent section remains, and the action plan attributes it to the old install.
- Keep `features.hooks = true` when any preserved external hook entry remains. Do not apply the old `had_codex_hooks: false` snapshot over live external hooks.

The operation does not adopt matching old content into new manifests. Removal followed by fresh installation is the proof that stale files and old ownership state did not leak across the boundary.

### Phase 3: Fresh Base and Daily Installation

After old-managed resources are absent:

1. Run Base install for Claude and Codex from its pinned checkout.
2. Run Daily install for Claude and Codex from its pinned checkout.
3. Verify target manifests and actual resource tree digests.
4. Verify preserved external/plugin resources against preflight digests.

The cleaner keeps only a metadata action journal until final verification. On interruption, rerun compares current state with completed action records and the pinned desired state. It resumes idempotently; it never restores content from a journal or backup.

### Phase 4: Retire Legacy State

Only after final runtime verification:

- delete all of `~/.org-skills-state`, including manifests, whole-file baselines, backups, archives, external-runtime lists, and feature-state files;
- delete the temporary migration journal and staging directory;
- retain only the new Base and Daily metadata manifests;
- print a final action/hash report. Persisting that report requires an explicit output path from the user.

If any verification fails, legacy state and the metadata journal remain temporarily for diagnosis, but no new content backup is created. The supported recovery path is to fix the cause and rerun. Reinstalling the pre-split Git tag is an explicit emergency choice, not an automatic rollback.

## Git History and Provenance

Before any extraction or Team contraction:

1. Commit the final approved split design.
2. Create and push an annotated pre-split tag on the last monolithic source commit.
3. Record that tag and commit in every new repository's `PROVENANCE.md`.

History policy:

- Team keeps the current repository and full object history.
- Base, Daily, and Personal begin with snapshot commits; they do not copy the current `.git` object graph.
- Each new repository records source URL, source commit/tag, extraction date, resource mapping, and third-party locked refs.
- Extraction first copies and verifies new repositories. Team deletes moved assets only after their destination commits are pushed and independently pass tests.
- Before local mutation, push cutover commits/tags for all four repositories. A local-only commit is not accepted recovery evidence.

## Verification Boundaries

Each repository proves only what it owns:

| Repository | Required evidence |
|---|---|
| Base | exact payload allowlist; no Skills/hooks/agents/protocols; Claude/Codex install, upgrade, drift, uninstall |
| Daily | exact Skill inventory; source-lock fidelity; vendor purity; adapter/surface checks; Grill dependency edges; generic `skill-pull` checkout isolation; install lifecycle |
| Team | exact team inventory; all hooks/agents/protocols retained; Base/Daily/Personal payload absent; library/workspace not installed; real Team→Base and `fix`→`systematic-debugging` dependency checks; structured-config lifecycle; existing standard-chain gates |
| Personal | exact Skill inventory; source-lock fidelity; adapters/surfaces; no hooks/agents/protocols; install lifecycle in a temporary home |
| One-time migration | current-runtime dry-run; drift rejection; external preservation; interruption/resume; old-state deletion; fresh Base+Daily end-to-end result |

There is no permanent cross-repository composition matrix or Team-hosted integration center. Team CI may fetch pinned Base and the exact Daily `systematic-debugging` Skill solely to test Team's two real dependency boundaries. The cutover separately runs a temporary Base+Daily install in an isolated home followed by the real local migration.

Tests must include the failure paths that matter:

- unmapped or duplicate ownership;
- existing unowned destination;
- modified owned resource;
- stale file removed during upgrade;
- missing hard dependency;
- malformed or concurrently changed structured config;
- interruption after partial target application;
- preserved plugin resource changed or deleted;
- unknown legacy state file;
- final old-state or rejected-Skill residue;
- active test or contract reference pointing at a deleted/moved source or evidence path;
- tracked transient workspace or unreferenced raw evaluation output surviving Team contraction.

## Cutover Sequence

1. Approve, commit, and push this design; create and push the pre-split tag.
2. Create Base, Daily, and Personal snapshot repositories with provenance; fetch Grill and Obsidian at their locked refs.
3. Verify each new repository independently.
4. Contract the current repository into Team only; repair Team tests and installer around its retained ownership.
5. Push and tag the four exact cutover commits.
6. Build and verify the one-time cleaner against captured fixtures and temporary homes.
7. Run a temporary Base+Daily end-to-end install from the pinned commits.
8. Run the real cleaner in dry-run mode and review every action/classification.
9. Apply removal, fresh Base+Daily install, and final verification.
10. Delete legacy state and temporary migration metadata.

The legacy `install.sh --uninstall` path is never invoked.

## Final Local Acceptance

The local cutover passes only when direct evidence shows:

- new installer manifests exist only for `base-config` and `daily-skills`;
- Base assistant, rules, and references exactly match Base source digests;
- all Daily Skills, including Grill and Obsidian, match Daily source/rendered digests for the selected targets;
- every current org-managed hook, agent, protocol, runtime catalog, team Skill, personal Skill, and Claude-only review-fix Skill is absent;
- the seven rejected Skills and all stale/retired runtime traces are absent;
- the five team Codex Agent sections are absent and no managed command points to a removed file;
- surviving `features.multi_agent` or `features.hooks` values, if any, have explicit non-team ownership evidence; otherwise old-managed values are removed;
- Claude `learned/`, Claude `superset/`, Codex `superset-*`, and preserved external hook files/entries have their preflight digests;
- `~/.org-skills-state` does not exist;
- no persistent migration backup, archive copy, or automatic report file was created;
- Base and Daily quick/full gates pass against isolated installs and the actual local runtime;
- all four repository worktrees contain only the approved split changes.

## Rejected Alternatives

### Profiles and a Team-hosted composition center

Rejected because install scenarios are user choices, not repository identities. Profiles, a central matrix, and a Team integration center would create a new coordination product that this split does not need.

### Base-owned installer protocol and vendored copies

Rejected because Base is configuration, not infrastructure. Copying one installer library into three repositories creates version coupling and duplicated maintenance while solving no current cross-repository runtime call.

### No dependency declarations

Rejected because Team consumes Base runtime configuration, while `grill-me`, `grill-with-docs`, and Team `fix` contain proven hard calls. Ignoring them would make a clean-looking split with broken runtime behavior. The chosen design records only these evidence-backed edges and uses existing on-demand Skill acquisition.

### In-place adoption of the old runtime

Rejected because legacy manifests are path-only and the installed fingerprint is dirty. Adoption can silently preserve stale or modified bytes. Explicit removal plus fresh install provides a stronger and simpler clean-state proof.

### Persistent local rollback backup

Rejected by user decision. It duplicates Git recovery, accumulates unmaintained archives, consumes local storage, and obscures which copy is authoritative.

## Non-Goals

- A Profile system, dependency resolver, central package registry, fifth repository, or permanent compositor.
- Automatic network fetch of sibling repositories during install.
- A shared installer codebase or Base compatibility protocol.
- Installing Team or Personal on this machine during the cutover.
- Updating retained third-party Skills beyond the selected locked refs.
- Renaming every surviving Team `shared/` path.
- Deleting ignored nested checkouts such as `claude-code-engineering/`.
- Shrinking the historical Git object pack.
- Reconstructing the previous runtime automatically after a successful cutover.

## Implementation Decomposition

This specification is one architectural decision. Implementation is five ordered plans with separate review gates:

1. `docs/superpowers/plans/2026-08-31--repository-split--01-pre-split-inventory-and-base-extraction.md`
2. `docs/superpowers/plans/2026-08-31--repository-split--02-daily-extraction.md`
3. `docs/superpowers/plans/2026-08-31--repository-split--03-personal-extraction.md`
4. `docs/superpowers/plans/2026-08-31--repository-split--04-team-contraction-and-active-tree-cleanup.md`
5. `docs/superpowers/plans/2026-08-31--repository-split--05-cleaner-and-local-cutover.md`

Plans 1–3 copy and verify destinations before Plan 4 deletes source paths. Plan 5 cannot mutate the local runtime until all four repositories have pushed cutover commits and their owner gates pass. Physical remote URLs are a Plan 1 hard gate and do not change runtime ownership.

## Failure Policy

The migration and every installer fail closed on unmapped ownership, path collision, unexplained drift, missing hard dependency, malformed structured configuration, concurrent change, unavailable locked source, missing pushed recovery tag, or unexpected legacy state.

Partial success is never reported as success. Errors identify the resource, expected and actual state, owner evidence, completed target/actions, and the exact safe next step. Warnings do not substitute for decisions involving potential data loss.
