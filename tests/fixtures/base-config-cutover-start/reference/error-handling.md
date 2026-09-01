# Error Handling

Error handling must make failure visible, diagnosable, and recoverable; it must not package failure as success.

## Failure Decision

- Every failure path must choose one outcome: propagate the error, return an explicit failure result, expose visible partial failure, or enter manual intervention.
- Silent failure, hidden fallback, empty catches, bare except blocks, and default returns without an error signal are forbidden.
- Catch only expected error types; unexpected errors must keep an observable failure path.
- Fallback, downgrade, and defaults need a valid condition, unchanged business semantics, and an observable failure or degraded state.
- Retry, queue, async resend, fallback, and compensation paths must define the applicable owner and trigger, bounded lifetime, idempotency or duplicate-effect protection, observable terminal state, and recovery, disable, or manual-intervention path.
- Multi-provider and deferred-recovery paths must define the stop condition and resulting user and system state when every continuation path fails.

## Allowed Continuation

- Continue after failure only when the success criteria remain true and the failure stays visible.
- Valid cases include noncritical side effects, cleanup, rollback collection, batch partial success, and documented degraded mode.
- Exhausted retries, failed side effects, and partial work must expose affected objects, reasons, and recovery or manual intervention paths.

## External Dependencies

- External API, network, database, filesystem, shell, and third-party CLI calls need timeouts and visible failure states.
- Failure logs should identify request ID, dependency, operation, retry state, and affected object without secrets or user-sensitive data.
- Files, connections, locks, temporary resources, and subscriptions must be cleaned up on failure paths.

## User-Visible Errors

- User-facing errors must be understandable and actionable.
- Do not expose stack traces, SQL, keys, internal paths, service names, or implementation details.
- Permission, input, dependency outage, rate limit, timeout, and conflict failures should have distinct error semantics.

## State Changes And Partial Success

- State changes, batch work, async jobs, and partial success must expose the resulting failure state.
- Define rollback, retry, compensation, or manual intervention paths.
- Do not return fake success after side-effect failure unless the success criteria explicitly allow partial success and the result is visible.
