# Code Comments

Comments are for meaning the code cannot reveal. Prefer clearer code first: better naming, extraction, simpler control flow, or stronger types; add comments only when intent, invariants, boundaries, tradeoffs, failure modes, or non-obvious business rules still need to be preserved.

## Required Comments

- Public boundaries, cross-module contracts, complex business rules, non-obvious constraints, high-risk failure conditions, and decisions affecting data consistency, permission, audit, idempotency, rollback, or user-visible behavior.
- Compatibility logic, temporary bypasses, migration code, and retained old paths must name the caller or constraint being preserved plus the expiration or removal condition.
- Database schema changes must keep business semantics traceable at the authoritative schema layer. New or modified tables, columns, enum or status values, constraints, and non-obvious indexes must explain business meaning and, where applicable, amount units and precision, currency, time source or timezone, allowed values, nullable or default meaning, constraint semantics, index semantics, and the protected invariant.
- Schema comment carriers depend on the database dialect and migration tool: use MySQL `COMMENT`, PostgreSQL `COMMENT ON TABLE/COLUMN`, ORM or migration comment APIs, or an equivalent checked-in schema document when native comments are unavailable.
- New DDL or migration review must distinguish required schema semantics from dialect-specific comment syntax, check the project's existing migration/comment style, and fix the current change before merge.
- Historical schema-comment backfill is separate migration work. Current changes must cover new, modified, or directly touched schema; broad backfills require owner review, batching, rollback, lock/deploy risk assessment, and verification.
- Multi-table joins, aggregation/window logic, complex filters, sorting, pagination, data repair, and performance assumptions must explain business intent and key constraints.
- SQL comments must not translate syntax; they must explain why the query filters, joins, sorts, paginates, or repairs data that way.
- Concurrency, transactions, locks, retries, cache consistency, and idempotency logic must comment the invariant being protected and the failure conditions.
- State machines or state transitions must explain legal transitions, illegal transition protection, and failure recovery.
- Complex regex, parsing rules, protocol mappings, and format conversions must explain input/output semantics, boundaries, and unsupported cases.
- External protocol compatibility must name the version, caller, and removal condition.

## Forbidden Comments

- Do not write comments that only repeat obvious assignment, branching, or function calls.
- Do not write database comments that merely translate table or column names, restate SQL syntax, or expose secrets, bypass conditions, sensitive risk rules, or internal operational details in database metadata.
- Do not keep stale TODOs, resolved FIXMEs, or comments that disagree with implementation.
