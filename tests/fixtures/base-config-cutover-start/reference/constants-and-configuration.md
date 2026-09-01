# Constants And Configuration

Constants and configuration belong to the owner that can change them safely: secrets stay outside the repository, environment differences stay configurable, stable public semantics can be shared, and local implementation details stay local.

## Value Classification

- Secrets, tokens, passwords, private keys, private certificates, production accounts, and credentials must use environment variables or secret storage and be never committed.
- Environment addresses, ports, deployment differences, runtime credentials, deployment paths, and host-specific paths belong in configuration or environment variables, not business logic.
- Missing or invalid required configuration must produce an explicit failure; do not hide drift with a hidden default, string concatenation, copied test configuration, or sample credentials.
- External dependency selection, credentials, and enable or disable switches must be explicit, validated configuration with an owner; never encode backup credentials or fake-success defaults in application code. Runtime failure, fallback, retry, and terminal-state semantics belong to error handling.
- User-visible messages belong to the existing message or i18n system.
- Business constants, enums, and statuses belong to the owning domain, concept module, enum, or type system.

## Layering Decision

- Used only in one file: keep it near that file.
- Shared within one module: place it in the module owner.
- Shared across modules: export it only when the value is a stable public contract.
- Do not import another module's private constants across ownership boundaries; adjust dependency direction or keep duplicated local values when no public contract exists.
- Changing or removing shared constants, enums, statuses, serialized values, or configuration keys requires checking consumers, stored data, compatibility, migration needs, and rollback or regression evidence.

## Naming And Splitting

- Global constants need a domain prefix that communicates the public contract.
- Module constants need a module or concept prefix that prevents cross-boundary misuse.
- Prefer enums or literal union types for finite sets; bare strings or numbers are acceptable only for local, stable, low-risk values.
- Split growing constant files by domain, ownership, stability, and dependency direction.
- Promote values to global scope only when the semantics are stable and public.
