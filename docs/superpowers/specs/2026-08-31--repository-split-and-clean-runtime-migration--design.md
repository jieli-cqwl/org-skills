# Repository Split and Clean Runtime Migration Design

**Status:** Approved in conversation on 2026-08-31; written-spec review pending.

**Authority:** This document is the design source for the repository split and one-time local runtime migration. It does not enter `contracts/active-doc-scope.yaml`, replace standard-chain canonical artifacts, or authorize implementation before written-spec review.

## Goal

Split the current monolithic repository into one base-configuration repository and three scenario-specific Skill repositories, while leaving the local Claude and Codex runtimes with only the base and daily repositories installed.

The result must have explicit ownership, independent installation and removal, Git-based recovery, no persistent content backups, and no residue from the old monolithic installation.

## Acceptance Scope

The change is accepted only when all of the following are true:

1. Four repository boundaries exist: base configuration, daily Skills, team Skills, and personal Skills.
2. The current repository remains the team repository and retains its Git history.
3. The three new repositories start from cutover snapshots with provenance, without copying the current repository's full object history.
4. Every current managed resource has exactly one destination repository or an explicit delete decision.
5. `hooks/`, `agents/`, `protocols/`, standard-chain runtime files, and standard-chain contracts remain team-only.
6. Base and daily repositories remain free of team and personal resources.
7. The local runtime installs only base and daily repositories after migration.
8. Plugin-owned and user-owned resources remain untouched.
9. The seven rejected external Skills and all of their source-lock and runtime traces are removed.
10. Persistent installer state contains only ownership and integrity metadata, never copies of installed content.

## Observed Starting Facts

- The Git worktree is clean at commit `20dbfa45`.
- Both managed runtime targets report `1.2.4-20dbfa45-dirty-f57e224e`; the installed state is therefore not reproducible from the clean commit alone.
- The managed runtime contains `grill-me`, `grilling`, `grill-with-docs`, and `domain-modeling`, while the current repository does not contain their sources.
- The old installer writes Codex `[agents.*]` sections and `multi_agent = true`, but its uninstall path does not remove those structured settings.
- The old uninstall path restores whole-file Claude settings and Codex hooks baselines. Those baselines predate the current files and can erase unrelated changes.
- The old uninstall path restores content backups and can resurrect resources that the migration intends to remove.
- Current tools, tests, installers, and contracts contain broad `shared/`, `community/`, and `tools/community/` path coupling. The split is a contract and tool separation, not a directory-only move.

These facts make the existing `install.sh --uninstall` unsuitable for this cutover.

## Repository Model

Logical repository IDs are stable installer identities and do not depend on Git remote names.

| Logical repository ID | Role | Local installation after cutover | History policy |
|---|---|---:|---|
| `base-config` | Runtime entry, rules, and references | Yes | Snapshot repository with provenance |
| `daily-skills` | General daily Skills and external source management | Yes | Snapshot repository with provenance |
| `team-skills` | Standard-chain and team delivery capabilities | No | Current repository with full history |
| `personal-skills` | Architecture, PRD, visualization, and personal workflow Skills | No | Snapshot repository with provenance |

Remote names and visibility do not participate in runtime identity. Repository publication must preserve these four logical IDs even if remote names differ.

### Base Configuration Repository

The base repository owns configuration required before any Skill repository is installed:

- `assistant.md`, rendered to the Claude and Codex global runtime entry files;
- `rules/`;
- `reference/`;
- a base-only installer, uninstaller, contracts, and tests;
- a machine-readable compatibility marker consumed by Skill repositories.

The initial base payload is exactly:

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

It must not contain Skills, hooks, agents, protocols, standard-chain runtime catalogs, external source locks, or source-sync tools.

Canonical source layout:

```text
assistant.md
rules/
reference/
contracts/
tools/installer/
tests/
install.sh
VERSION
```

### Daily Skill Repository

The daily repository owns general-purpose Skills used in normal sessions. It contains no standard-chain runtime machinery.

Daily inventory:

- all locked Anthropic Skills;
- all locked Superpowers Skills;
- Vercel `agent-browser` and `find-skills`;
- first-party `skill-pull`;
- `mermaid-diagrams`;
- `prompt-optimizer`;
- `obsidian-cli`;
- `obsidian-markdown`;
- `grill-me`;
- `grilling`;
- `grill-with-docs`;
- `domain-modeling`.

The exact initial Skill names are:

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

The four Grill Skills are one dependency unit. `grill-with-docs` must never be installed without `domain-modeling`.

To separate migration from upstream upgrade, the Grill unit initially locks `https://github.com/mattpocock/skills` at `bb1c760d559872044e76d18216c87165fa69908a`, the exact upstream commit matching the four currently installed Skill bodies. The Obsidian unit initially locks `https://github.com/kepano/obsidian-skills` at `a1dc48e68138490d522c04cbf5822214c6eb1202`. Existing Anthropic, Superpowers, Vercel, prompt-optimizer, and mermaid-diagrams refs are copied unchanged from the current source lock at extraction time.

Canonical source layout:

```text
first-party/skills/skill-pull/
vendor/anthropic/
vendor/superpowers/
vendor/vercel/
vendor/awesome-copilot/
vendor/softaworks/
vendor/obsidian/
vendor/mattpocock/
adapters/codex/
sources/SOURCES.yaml
contracts/
tools/
tests/
install.sh
VERSION
```

Vendor directories remain source-pure. Runtime frontmatter, visibility policy, and Codex adapters live outside vendor trees and are applied by the installer from an explicit runtime-surface contract.

### Team Skill Repository

The current `org-claude-skills` repository becomes `team-skills` without rewriting its Git history.

It owns:

- every current `shared/skills/*` Skill except `skill-pull`;
- all `shared/agents/` content;
- all `shared/hooks/` content;
- all `shared/protocols/` content;
- all `shared/runtime/` standard-chain catalogs and profiles;
- standard-chain contracts, canonical schemas, tools, tests, fixtures, and active documentation;
- team-only Claude and Codex adapters;
- a team-only installer and uninstaller.

The exact first-party Skill inventory is:

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
lib
overview
product-director
product-manager
project-memory
prompt
qa
qft-branch-flow
qft-branch-flow-workspace
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

The team repository depends on an installed compatible `base-config`; it must not carry copies of `assistant.md`, base rules, or base references.

The team repository may retain the current `shared/` naming for standard-chain assets because those paths are deeply embedded in current contracts. Removing the base and daily/personal assets is required; renaming all team paths is not.

### Personal Skill Repository

The personal repository owns the following locked external Skills:

```text
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
agent-reach
```

It has its own source lock, adapters, runtime-surface contract, installer, and tests. It does not contain `mermaid-diagrams` or `prompt-optimizer`; those are daily Skills.

### Explicit Deletions

The following external Skills are removed from source locks, repository content, Claude runtime, Codex runtime, migration allowlists, and generated manifests:

```text
architecture-blueprint-generator
job-description-analyzer
resume-ats-optimizer
resume-bullet-writer
resume-tailor
tailored-resume-generator
tech-resume-optimizer
```

No tombstone copy or content backup is retained. Recovery, if ever required, uses the pre-split Git tag and upstream provenance.

## Cross-Repository Contracts

Each Skill repository declares a base compatibility contract with:

- `schema_version`;
- required logical repository ID `base-config`;
- supported base contract-version range;
- installer protocol version;
- target runtime surfaces: Claude, Codex, or both.

Installation stops before mutation when the base marker is missing or incompatible. No Skill repository reads files from a sibling checkout at runtime.

Each repository owns its own source lock and update cadence. When two repositories consume the same upstream repository, each locks the exact subtree and commit independently. An updater may mutate only the repository whose source lock it reads.

## Installer Ownership Protocol

All four installers implement protocol version 1 and use the same neutral state root:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/agent-repo-installer/v1/
```

Per-repository state lives under:

```text
<state-root>/<repo-id>/<target>/installed.json
```

`installed.json` records only:

- protocol version;
- repository ID and version;
- target runtime;
- installation timestamp;
- installed path, resource kind, and SHA-256 digest;
- structured-patch selector and installed digest;
- whether a scalar setting or structured entry was created by this installer.

It does not store copies of installed files or directories.

### Collision Rules

Before mutation, an installer obtains a state-root-wide lock, loads every repository manifest, and evaluates all target paths.

- A path owned by another repository is a hard conflict.
- An unowned existing path is a hard conflict, even when content is identical.
- Migration may explicitly adopt an identical old-managed path into a new owner.
- A reinstall is allowed only when the current digest matches the calling repository's installed digest.
- An uninstall removes a path only when its current digest matches the installed digest.
- Missing or drifted owned paths stop the operation and produce an actionable report.
- `--force` may not bypass ownership or drift checks. Intentional deletion requires a separately declared migration decision.

### Structured Configuration Rules

Claude settings, Codex config, and Codex hooks are shared structured files; no installer owns the whole file.

- JSON hooks are inserted and removed by exact normalized entry identity.
- TOML agent sections are inserted and removed by exact section identity and digest.
- An absent Boolean feature may be inserted as `true` and recorded as created.
- A pre-existing matching Boolean remains user-owned and is not removed later.
- A pre-existing conflicting Boolean stops installation instead of being overwritten.
- If a managed entry changes after installation, uninstall leaves it untouched and reports drift.
- Whole-file baselines are forbidden.

This prevents team uninstall from erasing unrelated settings and prevents dangling Agent sections after Agent files are removed.

### Transaction Rules

Installers validate the complete plan before writing. They may use one bounded `mktemp -d` transaction directory for rendered output and atomic file replacement. The transaction directory is removed on success or failure and is never registered as a backup location.

Persistent content backup directories are forbidden. Git commits, tags, source locks, and provenance records are the recovery source.

## `skill-pull` Redesign

`skill-pull` moves to `daily-skills` as a generic source-sync engine. It no longer knows the old monorepo layout and does not own another repository's content.

Its contract is:

1. Run from a target repository checkout.
2. Read that repository's `sources/SOURCES.yaml` and runtime-surface contract.
3. Update only paths declared by that source lock.
4. Validate vendor fidelity, license metadata, adapters, and target repository tests.
5. Show the diff and validation result.
6. Commit or push only when explicitly requested; never assume `main` or a remote.

The daily repository invokes it for daily sources. Team and personal repositories may install the daily `skill-pull` Skill, but each update run remains scoped to the checkout from which it is invoked. Base configuration has no external source lock and rejects `skill-pull` updates.

## One-Time Migration Cleaner

The migration cleaner is a one-time repository tool, not a fifth installer and not a runtime Skill. It is implemented and verified in the team repository after the pre-split source tag. Its verified commit receives a separate migration-tool tag; after successful cutover it is removed from the active team HEAD while remaining recoverable from that tag.

It accepts explicit paths to the prepared base and daily repositories and performs five phases.

### Phase 1: Preflight Inventory

Classify every affected path as one of:

- `REOWN_BASE`;
- `REOWN_DAILY`;
- `REMOVE_TEAM`;
- `REMOVE_PERSONAL`;
- `REMOVE_REJECTED`;
- `PRESERVE_EXTERNAL`;
- `CONFLICT`.

The report includes current digest, old ownership evidence, intended owner, and action. Any `CONFLICT` prevents mutation.

The preflight must identify and preserve plugin/user-owned resources, including `learned` and `superset-*`. It must remove old team-only QFT runtime residue, including `_retired-qft-chat-analysis-user-copy`, `qft-chat-analysis`, and `qft-chat-analysis-workspace`, because the team repository is not installed after cutover.

### Phase 2: Reproducibility Gate

- Verify the pre-split recovery tag resolves.
- Verify every retained dirty-only resource has been committed to base or daily.
- Verify the four Grill Skills and two Obsidian Skills have locked sources and runtime-surface entries.
- Verify no rejected Skill appears in any new source lock or install surface.
- Verify base and daily tests pass from fresh checkouts.

Failure stops before local mutation.

### Phase 3: Structured Cleanup Plan

- Remove exact old managed hook entries from the current Claude settings; never restore the old Claude baseline.
- Remove exact old managed entries from current Codex hooks; never restore the old Codex baseline.
- Remove the five exact standard-chain Codex Agent sections.
- Remove `multi_agent = true` only when the config contains no non-team Agent sections and the five team sections match the old managed contract; otherwise report a conflict.
- Restore the Codex hooks feature through its recorded feature-state contract when that contract is intact.
- Leave unrelated JSON and TOML fields unchanged.

The resulting structured files are parsed and validated before replacement.

### Phase 4: Apply and Install

1. Stage all base and daily outputs.
2. Remove old-managed team, personal, rejected, and retired runtime paths whose preflight digests still match.
3. Apply structured configuration cleanup.
4. Install `base-config`.
5. Install `daily-skills`.
6. Run target-level verification.

If any current digest differs from preflight, stop instead of applying a stale plan.

The cleaner maintains a metadata-only action journal until verification succeeds. The journal records action identity and status, never prior content. A failed run keeps the old installer state and the journal, and a rerun resumes from verified current state. Managed source recovery comes from the pre-split source tag and the prepared base and daily repositories.

### Phase 5: State Retirement

Only after successful verification:

- remove `~/.org-skills-state` manifests, external-runtime lists, baselines, and content backups;
- retain only the new base and daily ownership manifests;
- delete the transaction directory;
- emit a final machine-readable migration report containing actions and hashes, but no copied content.

The ignored nested repository `claude-code-engineering/` is outside migration scope and remains untouched.

## Git History and Provenance

Before extraction, create an annotated pre-split source tag on the clean source commit. The source tag is the content recovery anchor and must be pushed before destructive local migration. After the migration cleaner is implemented and verified, create and push a second annotated tag for the exact cleaner used during cutover.

History policy:

- `team-skills` keeps the current repository and full history;
- `base-config`, `daily-skills`, and `personal-skills` start from clean snapshot roots;
- each new repository records source repository URL, source commit, pre-split tag, extraction date, and resource mapping in `PROVENANCE.md`;
- no new repository imports the current repository's full object graph;
- repository deletion from the team HEAD does not claim to shrink historical objects.

This preserves traceability without multiplying the current `.git` storage across four repositories.

## CI and Release Boundaries

Each repository has independent quick and full gates, release versioning, and dry-run installation tests.

| Repository | Required independent evidence |
|---|---|
| Base | layout contract; render tests; Claude/Codex install, reinstall, drift, and uninstall tests |
| Daily | source-lock fidelity; adapter generation; runtime-surface validation; `skill-pull` target isolation; install lifecycle tests |
| Team | existing standard-chain quick/full gates; base compatibility; absence of base/daily/personal ownership; team install lifecycle tests |
| Personal | source-lock fidelity; adapter generation; runtime-surface validation; install lifecycle tests |

Cross-repository CI runs three compositions from clean temporary homes:

1. base plus daily;
2. base plus team;
3. base plus personal.

It also tests install order rejection, idempotent reinstall, cross-owner collision, local drift, structured-config preservation, failed-transaction cleanup, and uninstall isolation.

The local cutover acceptance run is base plus daily only. Team and personal composition tests run in isolated temporary homes, not the user's runtime.

## Cutover Order

1. Freeze current content and push the pre-split tag.
2. Create snapshot repositories and provenance records.
3. Commit retained Grill and Obsidian sources to daily; remove rejected source records.
4. Implement and verify protocol-v1 scoped installers.
5. Split tools, contracts, tests, and workflows by capability ownership.
6. Verify all four repositories independently and in the three supported compositions.
7. Tag and push the verified migration cleaner.
8. Run migration-cleaner dry-run and review its action report.
9. Run the one-time migration.
10. Verify the local runtime contains only base and daily managed resources plus preserved external resources.
11. Retire old state and content backups.

The old monolithic uninstaller is never invoked during this sequence.

## Final Local Acceptance

The cutover passes only when direct evidence shows:

- Claude and Codex ownership manifests exist only for `base-config` and `daily-skills`;
- global assistant entry, rules, and references match `base-config` digests;
- all daily Skills are present and owned by `daily-skills`;
- all team and personal Skills are absent from the user runtime;
- the seven rejected Skills are absent from repositories, source locks, generated surfaces, and runtime;
- standard-chain Agent files, Agent sections, hooks, protocols, runtime state, and QFT residue are absent locally;
- no managed hook command references a removed file;
- `learned`, `superset-*`, and any other preflight-classified external resources are unchanged;
- `~/.org-skills-state` no longer exists;
- no persistent content-backup directory was created;
- base plus daily quick and full gates pass against the actual installed runtime;
- `git diff` in all four repositories matches the approved extraction scope.

## Non-Goals

- Renaming every surviving `shared/` path in the team repository.
- Installing team or personal repositories on the user's machine during this cutover.
- Updating retained third-party sources beyond the content selected for the cutover.
- Creating a fifth orchestration repository or permanent global compositor.
- Deleting the ignored `claude-code-engineering/` nested repository.
- Shrinking the current repository's historical Git pack.

## Implementation Decomposition

This architecture is too broad for one implementation plan. Written-spec approval leads to six ordered plans, each producing an independently reviewable state:

1. protocol-v1 ownership library and `base-config` extraction;
2. `daily-skills` extraction, retained-source capture, and generic `skill-pull`;
3. `personal-skills` extraction and rejected-source removal;
4. `team-skills` contraction and standard-chain dependency repair;
5. one-time migration cleaner and dry-run evidence;
6. cross-repository integration, local cutover, and state retirement.

Plans 2 through 4 depend on the protocol and base compatibility marker from plan 1. Plan 5 depends on verified base and daily repositories. Plan 6 depends on all repository gates and the tagged migration cleaner.

## Failure Policy

The migration is fail-closed. Missing source locks, incompatible base versions, path collisions, local drift, malformed structured configuration, stale preflight digests, or missing recovery tag stop the operation before the affected mutation.

Warnings are not accepted for ownership ambiguity or potential data loss. The operator receives the exact path, current owner evidence, expected digest, actual digest, and safe next action.
