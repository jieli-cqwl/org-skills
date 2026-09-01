# Impact Analysis

## Core Rule

Impact analysis starts from source atoms, builds a coverage denominator, and then projects upward into business impact, user paths, verification scope, coverage gaps, and decision risks. Do not start from a guessed business story and search downward for supporting evidence.

- Business impact is a projection result, not the starting point.
- Source evidence is the denominator; search hits and changed files are only clues.
- No atom coverage, no "no impact", no "closed", no "safe to skip regression".
- Preserve old behavior explicitly; compatibility is not implied by small code changes.
- Do not merge call sites during impact analysis. Grouping is display-only; every call site or runtime entry must keep a separate trace record and decision state.
- Supporting tables, reports, and matrices must not become a second source of truth.

## Source Atom Denominator

Build the denominator from actual code and runtime entry evidence before writing the final impact conclusion.

- Include the directly changed atoms.
- Include adjacent read, write, sync, export, cache, search-index, and derived-model atoms.
- Include old-logic protection paths that must keep existing behavior.
- Include real user entries when the system can be accessed.
- Include every discovered call site or runtime entry as its own trace record; repeat the same `source_atom_id` when one source atom fans out.
- For interface or shared-contract changes, include the contract owner, provider, every known consumer, error shape, tests, fixtures, and contract references.
- Include rejected candidates with the reason they are out of scope.
- Use LSP, IDE navigation, and type-aware search first; if they timeout or miss dynamic paths, continue with `rg`, file references, SQL/XML/route/API search, and manual call-chain tracing.
- Dynamic calls, generated code, config fields, table fields, async jobs, and external system entries are not safe just because code intelligence cannot see them.
- Do not collapse atoms, call sites, or runtime entries into one conclusion row. A grouped view may help reading, but it cannot replace the underlying trace records.

## Atom Record Contract

Every trace record should be recorded with stable English fields so downstream agents and humans can compare, filter, and audit results.

- `source_atom_id`: stable id for the underlying source atom; repeat it across records when the same atom reaches multiple call sites or runtime entries.
- `atom_type`: SQL/mapper, function/method, API endpoint, frontend route/page/component/service, job, ES/Canal, export, sync, config, state, enum, external entry, or real user entry.
- `denominator_status`: `ADMITTED` or `REJECTED_WITH_EVIDENCE`.
- `denominator_reason`: why this trace record is in the denominator or rejected from it.
- `evidence_anchor`: path:line, symbol, SQL/query condition, endpoint path, route, component, task entry, or runtime entry.
- `current_behavior`: current filter, data range, read/write semantics, call relation, side effect, permission, or invariant.
- `target_behavior`: required behavior after the change, including unchanged behavior when the atom must stay compatible.
- `target_action`: one of the decision states below.
- `trace_status`: `TRACE_COMPLETE`, `TRACE_PARTIAL`, `TRACE_BLOCKED`, or `NEEDS_TRACE`; incomplete traces cannot support closure.
- `business_entry`: terminal, task, page, API, external system, or user operation reached from the atom.
- `business_impact`: user-visible capability, business invariant, or explicitly no impact with evidence.
- `preserved_old_logic`: old behavior that must remain true, plus the regression object.
- `acceptance_assertion`: observable assertion for changed behavior, preserved behavior, or forbidden behavior.
- `runtime_status`: one of the runtime verification states below.
- `risk_or_decision`: remaining risk, coverage gap, or user decision required before closure.

## Trace Contract

Trace in this order: source_atom -> call_chain -> interface_task_or_page -> terminal_or_business_entry -> user_path -> business_impact -> acceptance_assertion.

- Each hop needs an evidence anchor or an explicit blocked reason.
- If the trace cannot reach a terminal entry, mark `trace_status=NEEDS_TRACE`; do not convert it to no impact.
- If a trace reaches only part of the chain, mark `trace_status=TRACE_PARTIAL`; if a dependency blocks tracing, mark `trace_status=TRACE_BLOCKED`.
- If a runtime entry is known but not executable, keep the atom and mark the runtime blocker.
- A broad function, shared helper, enum, config, SQL fragment, or generated route may fan out into multiple business entries; create separate trace records instead of hiding fan-out.
- A contract change that reaches clients, services, jobs, exports, permissions, or user-visible states needs a separate trace record for each provider or consumer path.
- A file-level diff is not a trace. A passing test is not a trace unless it exercises the same atom, entry, and assertion.

## Decision States

Every atom must end in exactly one decision state.

- `CHANGE`: target semantics require changing this atom.
- `KEEP_AS_IS`: this atom protects old logic or an adjacent path and must keep existing behavior.
- `REGRESSION_ONLY`: no code change is needed, but the user path, data range, side effect, or invariant needs verification.
- `NEEDS_TRACE`: the evidence chain has not reached a terminal entry or assertion.
- `NEEDS_DECISION`: business semantics, compatibility boundary, or acceptance wording needs user decision.
- `NOT_IMPACTED_WITH_EVIDENCE`: the atom is out of scope or unaffected, with checked dimensions and evidence.

## Business Impact Projection

Project source atoms into business language only after the denominator and trace state are visible.

- `functional_impact_items`: business capability, user-visible behavior, or business invariant affected by one or more trace records.
- `technical_touchpoints`: code, interface, config, data, contract, runtime entry, or external dependency that supports the impact item.
- `preserved_old_logic`: existing behavior that must not regress, including current data range and old user path.
- `regression_verification`: specific check proving changed behavior and preserved behavior at the right level.
- `coverage_gaps`: atoms, hops, environments, permissions, async paths, external dependencies, or data states not yet proven.
- `decision_risks`: decisions needed from the user before implementation or completion can be called closed.
- File names, function names, scripts, and search results are evidence anchors; they are not functional impact items.

## Runtime Verification

Runtime proof is required when the claim involves a user path, permission, environment data, async sync, cache, search index, external dependency, or frontend/backend integration.

- `STATIC_VERIFIED`: source evidence and trace are checked, but no runtime path was executed.
- `RUNTIME_VERIFIED`: real or representative runtime entry was executed and matched the acceptance assertion.
- `RUNTIME_UNVERIFIED`: runtime proof is still missing.
- `ACCOUNT_BLOCKED`: account, permission, or login blocks runtime proof.
- `ENV_BLOCKED`: environment, dependency, data, or service availability blocks runtime proof.
- If account and environment exist, log in from the real system entry and verify key paths.
- If runtime proof is blocked, report the blocker and residual risk; static review does not prove runtime closure.

## Closure Gate

Impact analysis is closed only when the denominator, trace, projection, and verification evidence all match the claim.

- The source atom denominator is listed and has admission/rejection reasons.
- Every discovered call site or runtime entry has a separate trace record with `target_action`, `trace_status`, `runtime_status`, and evidence anchor.
- Every functional impact item traces back to one or more source atoms.
- Every preserved old-logic path has a regression target.
- Every changed behavior and preserved behavior has an acceptance assertion.
- `NEEDS_TRACE`, `NEEDS_DECISION`, `RUNTIME_UNVERIFIED`, `ACCOUNT_BLOCKED`, and `ENV_BLOCKED` remain visible and block completion unless explicitly accepted as residual risk.
- No completion claim may be stronger than the evidence level: static evidence proves static trace; runtime evidence proves runtime behavior.
