# Performance And Efficiency

Performance work starts from an observable bottleneck and closes with baseline metrics, capacity limits, failure paths, and before and after evidence from the same scenario. Performance changes must preserve existing behavior, correctness, and contracts unless the requested outcome explicitly changes them.

## Decision Order

1. Locate the bottleneck with profiling, logs, traces, or benchmarks; record the baseline.
2. Identify constraints: latency, throughput, memory, cost, dependency capacity, and failure cost.
3. Choose the smallest effective strategy: incremental work, streaming, pagination, indexes, batching, bounded concurrency, or local deduplication.
4. Define limits and failure behavior: attempt limits, intervals, timeouts, exit conditions, cleanup, backpressure, rollback, and visible failure states.
5. Compare before and after on the same scenario: latency, throughput, memory, hit rate, correctness, contract behavior, and failure behavior.

## Bounded Work

- Temporary files must use unique paths and must be cleaned up; fixed shared paths and unbounded accumulation are forbidden.
- Long-running jobs, polling, retries, batch work, and async jobs need attempt limits, intervals, timeouts, exit conditions, and cleanup.
- Large files, large result sets, queues, and in-memory collections need memory, response-size, or batch-size limits.
- Batch work must define concurrency limits, failure strategy, retry boundary, and recovery path.
- Shared async job state needs timeout, idempotency key, visible failure state, and resume strategy.
- Workers and background work must not wait forever, grow queues forever, retry forever, fail only in logs, or mark failed work as success.

## Database And IO

- Large-table queries must be paginated.
- New query paths on user paths, batch jobs, or high-frequency queries must evaluate indexes and query plans when data size can grow.
- Queries, network requests, or file IO inside loops must be checked for N+1 or repeated IO risk.
- CPU-intensive paths must check algorithmic complexity and data size before adding parallelism or task splitting.

## Cache Strategy

- Shared, persistent, cross-request, cross-process, or freshness-affecting cache requires explicit user approval.
- Cache design must define cached object, invalidation strategy, bypass path, rollback path, capacity limit, cost limit, consistency risk, and target hit rate.
- Verify cache hit, miss, invalidation, stale data, dependency failure, and rollback scenarios.
- Single-run local deduplication or intermediate result reuse is not a shared cache.
