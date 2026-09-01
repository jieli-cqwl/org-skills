# Completion Claims

Completion means the requested outcome is proven at its acceptance scope, not that work was performed.

- Claim only what current, direct evidence proves.
- The claim must match the requested outcome, acceptance scope, changed artifacts, delivered artifacts, and observed behavior.
- If the target, success criteria, or acceptance scope is unclear, stop and state what cannot be proven; do not invent a smaller scope.
- Derive acceptance scope from the request, explicit acceptance requirements, affected paths, contracts, dependencies, risks, and required verification.
- User-specified verification adds evidence requirements; it does not shrink the requested outcome unless the user explicitly limits acceptance scope.
- Checks prove only what they exercise; they cannot define, shrink, or replace the requested outcome or acceptance scope.
- Completion evidence must distinguish the claimed outcome from in-scope failure modes; a check that would pass for the wrong behavior is not evidence.
- The strength of a claim must match the strength of evidence; partial, sampled, local, mock, stub, fake, or indirect evidence supports only the scope it proves.
- Claims about user paths, boundaries, runtimes, dependencies, contracts, integrations, environments, E2E behavior, or substituted paths require evidence at that same level.
- Interface, integration, or user-path completion cannot be claimed from isolated provider or consumer changes, mocks, planned validation, or unverified downstream work.
- If a change touches shared contracts, entrypoints, data formats, install/runtime paths, or consumers, verify representative real consumers or prove why they are outside scope.
- Evidence must be current to this task/run, reproducible, and tied to the requested outcome; manual evidence must record input, path, environment, expected result, and observed result.
- Historical output, cached impressions, report self-reference, log summaries, tool success, green checks outside scope, and substituted paths are not completion evidence.
- Do not make completion true by skipping, xfail-ing, deleting checks, loosening assertions, changing acceptance scope after failure, or replacing required real evidence with weaker evidence.
- Any in-scope item that is unrun, failed, blocked, missing evidence, waiting on a dependency, carrying unaccepted risk, or awaiting a decision blocks completion.
- Accepted residual risks and out-of-scope failures do not expand the completion claim; report proven facts, blocked items, unverified items, and out-of-scope failures separately.
- Test: Would a senior test engineer accept this evidence for the scope you are claiming? If not, do not call it complete.
