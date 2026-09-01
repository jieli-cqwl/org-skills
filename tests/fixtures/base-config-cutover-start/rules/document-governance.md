# Document Governance

Documents must preserve one current source of truth for active work, handoff, archive, and recoverable state.

- Use `--` between managed path semantic segments and `-` inside a segment; do not keep same-meaning sibling directories with different separator styles.
- Rename a managed path only when required for the current outcome; synchronize project-declared scope registries, entry refs, tests, fixtures, validation refs, and recovery paths.
- Put active project state in the project-declared active-doc location, canonical artifact, or source-of-truth contract; do not create a second source of truth.
- When behavior, rules, contracts, tools, tests, or validation entrypoints change the same constraint, update the affected docs in the same change or state exactly why they are out of scope.
- A stale doc is any doc that conflicts with current code, contracts, scope registries, accepted decisions, canonical artifacts, or validation output.
- Fix or archive stale docs that are in scope, block verification, remain referenced by active paths, or would mislead current delivery; report out-of-scope stale docs without expanding work.
- Completion for behavior, constraint, or document-governance changes requires current evidence that in-scope docs, refs, fixtures, and validation references are synchronized.
- Archive docs no longer used as current facts under the project-declared archive location.
- Do not use archived docs as default handoff input unless the user explicitly asks for historical audit, archive recovery, or provenance.
- Before archiving or renaming, clear or update active-doc, test, fixture, runtime, and validator references; move validation-consumed material to a stable fixture or reference location.
- When a managed feature or task is completed and has no active inbound refs, archive the whole directory or keep it active with explicit current ownership and scope.
- When archiving a managed registry entry, record archive metadata and preserve a recoverable handoff pointer.
- Resume active work from project-declared active scope registries or active handoff contracts; unmanaged docs are not active handoff candidates by default.
- Use worklogs or handoff docs only for navigation and contract-required status pointers; do not copy full PRDs, designs, task lists, acceptance details, or canonical state into them.
- If a project defines canonical artifacts, registry pointers, or workflow state contracts, those contracts define active truth; human projections, chat notes, worklog text, and legacy Markdown are background only.
- If the registry, handoff docs, archive, and canonical artifacts disagree, stop and report the source-of-truth conflict; do not choose the convenient source.
- Prove handoff, archive recovery, and reference reachability with the project-declared validators or targeted tests.
- Test: Would a downstream agent recover the same active scope, source of truth, artifact refs, and archive boundary from current validated docs? If not, fix the docs or report blocked.
