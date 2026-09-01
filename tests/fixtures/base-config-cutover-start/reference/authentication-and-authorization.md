# Authentication And Authorization

Authentication proves an identity or credential. Authorization decides whether that identity may perform an operation on a resource. Identify both boundaries before applying mechanism-specific checks.

## Mechanism And Trust Boundary

- Name the credential or session mechanism, issuer or producer, validator, protected resource, capability owner, and every trust-boundary transition.
- Do not infer guarantees from a mechanism it does not provide. Local signature checks do not validate opaque tokens; token validity does not prove resource permission; client-side visibility does not enforce authorization.
- Keep credential parsing and authentication separate from tenant, scope, role, and object-level authorization decisions when their ownership or failure semantics differ.

## Applicable Validation

- Server-side sessions: verify identifier confidentiality, lookup and rotation, expiry and revocation, transport and storage attributes, and shared-state or load-balancing behavior. Check CSRF, CORS, proxy, and browser cookie behavior only when those boundaries exist.
- JWTs: verify the allowed algorithm and key source plus applicable signature, issuer, audience, time, claim, key-rotation, and revocation semantics. Do not require claims the contract does not define.
- Opaque access tokens: use the owning lookup or introspection contract and verify applicable active, expiry, client, audience, tenant, and scope semantics. Define behavior when validation is unavailable.
- API keys: protect storage and transport; define identifier handling, hashing where supported, rotation, revocation, scope, tenant isolation, rate limits, and audit ownership.

## Authorization And Evidence

- Enforce authorization at every protected backend or service boundary; frontend visibility and upstream checks are not substitutes.
- Distinguish unauthenticated, unauthorized, expired, revoked, unavailable-validation, and malformed-input outcomes without leaking credentials or internal validation detail.
- Derive positive, negative, boundary, and legacy regression cases from the chosen mechanism and protected resources. Include only applicable cases, and prove tenant or object isolation whenever the resource model requires it.
