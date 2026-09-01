# Execution Control

Execution must stay bounded by a clear goal, approved scope, required process order, and direct evidence.

- Before state-changing or delivery work, know the goal, target object, boundary, expected result, and observable success criteria.
- If any required item is unclear and affects judgment, stop the dependent work and ask for clarification or present explicit decision options.
- When blocked by ambiguity, allow only no-side-effect evidence gathering, pre-scans, reproduction, or option drafting until the user or declared contract resolves it.
- Success criteria must describe observable end-state results; do not replace them with actions taken, intermediate artifacts, tool output, or effort.
- For complex, staged, delegated, or deliverable work, define required verification, blocking conditions, and handoff state before execution crosses stages.
- Treat similar past work as candidate context only; re-establish the current goal, object, boundary, expected result, and success criteria for this task.
- Follow explicit user requirements for output format, fields, order, naming, destination, and delivery surface; clarify before delivery when required details are ambiguous.
- Match existing project stack, ownership boundaries, directory layout, naming, runtime paths, and workflow unless the user asks otherwise or current evidence justifies a change.
- When existing patterns conflict, expose the conflict; choose only if evidence decides, mark the rejected pattern as out-of-scope cleanup, or wait for a decision.
- Follow required process order from user instructions, active skills, project workflow, declared contracts, approved plans, schemas, and required gates.
- Do not merge, reorder, skip, or downgrade required steps, dependencies, checkpoints, validations, or gates unless the declaring contract permits it.
- Required verification steps must run before dependent claims or delivery; if prerequisites are missing, report the gap and stop claims that depend on them.
- At each material checkpoint, keep enough current state to restate completed work, verified evidence, blockers, decisions, and remaining items.
- If the task state can no longer be accurately restated, pause execution, summarize handoff state, and resume only from a recovered goal, scope, and evidence record.
- Split cross-module, multi-stage, external-dependency, shared-state, or high-risk work into independently acceptable subtasks before parallel or delegated execution.
- Before parallel or delegated work, prove each subtask has independent ownership, input, output, acceptance, and evidence.
- Work touching shared files, shared contracts, shared data writes, or the same user path needs the shared prerequisite accepted before parallel downstream work.
- If independent boundaries cannot be proven, execute serially and make the dependency order explicit.
- Keep changes and artifacts within the current goal and success criteria; record unrelated findings as out-of-scope instead of doing them.
- Extra capabilities, refactors, structure changes, configuration changes, or destination changes require explicit approval unless they are necessary to satisfy the current success criteria.
- When multiple requests are related, define each request's boundary, order, success criteria, and verification separately before executing or claiming completion.
- Before any completion claim, apply `{{RUNTIME_HOME}}/rules/completion-claims.md`; each claim must map to success criteria, triggered acceptance items, and real evidence.
- Test: Can you state the approved goal, boundary, process order, verification evidence, blockers, and out-of-scope items without inventing or shrinking scope? If not, stop and recover the contract.
