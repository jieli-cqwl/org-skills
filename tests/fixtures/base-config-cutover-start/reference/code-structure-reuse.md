# Code Structure And Reuse

Code structure should preserve existing behavior first, and introduce abstraction only when a separate boundary decision earns its cost.

## Existing Path Reuse

- Existing path reuse is the default for iterative work in existing projects; start from the existing implementation path instead of creating a parallel path.
- Trace callers, state branches, side effects, source of truth, data sources, UI entries, runtime entrypoints, tests, fixtures, and historical compatibility cases.
- Before adding behavior, identify the existing capability owner, callers, contracts, extension points, and compatibility constraints.
- Prefer to compatibly extend the existing path when it owns the same capability; a different scenario does not justify a new path if old callers keep identical behavior and verification remains clear.
- Add a new path only as an exception when the existing path cannot carry the required behavior or would break an existing contract.
- When adding a path, name the boundary, retained legacy behavior, affected callers, migration or removal condition, and regression evidence.
- Completion needs regression evidence for affected legacy behavior, not just proof that the new behavior works.
- A proposed shortcut, compatibility path, or shared-contract change must make the owner, consumers, preserved behavior, failure boundary, and required integration evidence explicit; include migration, removal, and rollback conditions when they apply.
- Shared business rules, derived values, statuses, permissions, and data semantics need a source-of-truth owner; secondary derivations must define their non-authoritative scope, freshness or consistency semantics, invalidation, verification, and removal or rollback condition.

## Complexity Signals

- Treat high cyclomatic complexity, long parameter lists, deep nesting, and oversized files as signals to inspect responsibility boundaries, not as automatic refactor triggers.
- When a complexity signal appears, first check whether responsibilities are mixed; split by responsibility, boundary, or data flow only when it clarifies ownership, failure handling, or verification.
- When parameters grow, prefer a domain parameter object over loose argument lists if it makes required inputs, defaults, and invariants clearer.
- Keep framework signatures, public API compatibility, generated files, pure configuration maps, and stable data tables intact when splitting would add risk or obscure intent.
- Record the reason, risk, and verification method when a high-complexity shape is intentionally retained.

## Abstraction Boundaries

- Abstraction is a structural boundary, not the default form of existing-path reuse or a cosmetic way to share similar code.
- Introduce a boundary as a function, component, service, interface, template, or configuration structure only when it removes real duplication, expresses a stable invariant, or isolates an identified change boundary.
- A valid abstraction must expose a stable contract, make call relationships clearer, reduce maintenance cost, or clarify verification responsibility.
- For reuse abstractions, call sites need aligned change direction; surface similarity, naming symmetry, single use, or future speculation is not enough.
- For invariant or change-boundary abstractions, name the source fact, protected invariant, consumers, and failure mode it prevents.
- Keep concrete code when abstraction increases dependency direction complexity, hidden state, parameter complexity, or test difficulty.
- An abstraction created only to satisfy a metric or make code look uniform is a complexity regression.

## Compatibility Code

- Compatibility layers must name the retained callers, reason, removal condition, and deletion path.
- Compatibility logic must not swallow new errors, change business semantics, or hide migration failure.
- Shared contract changes must identify the owner, single source of truth, dependent consumers, preserved behavior, compatible rollout sequence, and integration evidence before providers and consumers diverge; define migration or removal when persisted data or temporary compatibility is involved.
