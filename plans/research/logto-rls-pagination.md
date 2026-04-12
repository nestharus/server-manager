# Logto RLS Pagination Research

Researched on 2026-04-11.

## Executive summary

I did not find evidence that Logto has a first-class product feature specifically for "RLS pagination" or "paginated row filtering" as a distinct capability. The closest Logto features are:

1. `Custom JWT` / custom access token claims via `getCustomJwtClaims`, which lets Logto mint access tokens containing additional authorization-relevant claims.
2. `Organization-level API resources` / organization tokens, which let Logto issue tokens scoped to a specific `organization_id` and API audience, with scopes derived from organization roles.

Those features can reduce or eliminate per-page calls to an external authorization system because the filter context can be embedded in the token once, then reused across multiple paginated API requests until the token expires. But Logto is not itself the thing that performs row filtering in PostgreSQL. PostgreSQL RLS still does that work, and the application still has to bridge Logto claims into the database session or a downstream DB JWT.

So the user's claim is directionally plausible, but the precise interpretation matters: Logto can help you avoid re-fetching authorization context on every page request by putting stable authz context into a JWT. I did not find a Logto feature that creates a pagination snapshot, holds a server-side authorization cursor, or directly integrates with PostgreSQL RLS in a way that is unique to pagination.

## 1. What Logto actually provides

The feature name most relevant to this question is `Custom JWT` / `custom access token claims`. Logto's docs say it can "add custom claims within access tokens" and that JWT access tokens are the default when a client requests authorization for a specific resource or organization. The implementation surface is a JavaScript callback named `getCustomJwtClaims`, whose return value is merged into the token payload and signed by Logto. Logto also documents that the callback receives token context plus user and organization membership data for user tokens, and can optionally fetch external data before issuing the token. Sources:

- [Custom access token](https://docs.logto.io/developers/custom-token-claims)
- [Create a custom access token script](https://docs.logto.io/developers/custom-token-claims/create-script)
- [Custom JWT blog post](https://blog.logto.io/glance-on-custom-jwt-access-token-claims)

Separately, Logto has `organization-level API resources`. This is its organization-aware authorization model for multi-tenant APIs. When the client requests a token with both `resource` and `organization_id`, Logto issues a JWT that includes organization context and scopes filtered by the user's organization role assignments. That is an authorization feature, not just identity/OIDC plumbing. Sources:

- [Protect organization-level API resources](https://docs.logto.io/authorization/organization-level-api-resources)
- [Authorization overview](https://docs.logto.io/authorization)

What I did not find in Logto docs, product pages, or changelogs:

- No feature named "RLS pagination"
- No feature named "data filtering for paginated results"
- No built-in Postgres policy compiler
- No documented mechanism that creates a stable authorization snapshot across pages
- No documented query rewrite layer that pushes filters into SQL for you

There is one possible source of confusion: Logto's own platform uses PostgreSQL and applies RLS internally for tenant isolation, and Logto publishes articles about implementing multi-tenancy with PostgreSQL RLS. But those are examples of how to build with PostgreSQL, not a user-facing Logto product feature that directly manages your application's RLS. Sources:

- [Multi-tenancy implementation with PostgreSQL](https://blog.logto.io/implement-multi-tenancy)
- [July 2025 changelog snippet about Logto's own RLS usage](https://blog.logto.io/ru/changelogs/2025-july)

My conclusion on question 1 is therefore:

`Inference:` the relevant Logto feature is `Custom JWT`, optionally combined with `organization-level API resources`. There does not appear to be a distinct Logto-branded RLS pagination product.

## 2. How this works with paginated API responses

Logto does not appear to do anything pagination-specific. The pattern is more general:

1. User signs in.
2. Logto issues an access token for a resource, optionally scoped to an organization.
3. The token includes built-in claims like `sub`, `aud`, `scope`, and possibly `organization_id`.
4. If `Custom JWT` is configured, Logto also adds custom claims such as tenant IDs, project IDs, subscription tier, or other bounded authorization metadata.
5. Your API validates the token and uses those claims to shape the database session or downstream query context.
6. PostgreSQL RLS filters rows.
7. `ORDER BY`, `LIMIT`, cursor logic, or `OFFSET` paginate the already-authorized result set.

The reason this can avoid "re-querying auth on each page" is that the access token is self-contained. Logto's docs explicitly note that JWTs allow consumers to access claims directly, and its blog says custom claims can improve service-provider performance by reducing repeated external API calls. The same blog also warns that once a JWT is issued it does not change during its validity period, which is exactly the tradeoff here: fewer repeated authorization lookups, but more risk of stale authorization if claims change mid-session. Sources:

- [Custom access token](https://docs.logto.io/developers/custom-token-claims)
- [Custom JWT blog post](https://blog.logto.io/glance-on-custom-jwt-access-token-claims)

For pagination specifically, the important behavior is on the PostgreSQL side. PostgreSQL says RLS policy expressions are evaluated for each row "prior to any conditions or functions coming from the user's query." That means the visible row set is filtered before user query predicates are fully applied. PostgreSQL also says `LIMIT`/`OFFSET` pagination is unstable without an explicit `ORDER BY`, and large offsets are inefficient. Sources:

- [PostgreSQL row security policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [PostgreSQL LIMIT and OFFSET](https://www.postgresql.org/docs/current/queries-limit.html)

So, in practical terms:

- Yes, Logto can help you reuse the same authorization context across page 1, page 2, page 3, and so on.
- No, Logto does not create a special protected-pagination mechanism.
- The correctness of paginated results still depends on your SQL ordering and your RLS design.
- If claims change during token lifetime, later pages may reflect stale authorization until token refresh.

That last point is the main architectural limit. Logto's model is strongest when the page-shaping claims are relatively stable for the token lifetime: tenant membership, organization ID, bounded project list, coarse role set, or subscription tier. It is weaker for rapidly changing relationship-based entitlements.

## 3. How it integrates with PostgreSQL RLS

I did not find a native "Logto to PostgreSQL RLS" integration outside the Supabase quick start, but the integration pattern is clear.

Logto's official Supabase guide shows this flow:

1. Validate the Logto access token in your backend.
2. Extract the authoritative user ID from the Logto token, typically `payload.sub`.
3. Mint a downstream JWT for Supabase containing `userId`.
4. In the database, read that claim via `request.jwt.claims`.
5. Write RLS policies against the extracted claim.

Source:

- [Add authentication to your Supabase application](https://docs.logto.io/quick-starts/supabase)

That is not limited to Supabase. For raw PostgreSQL, the same idea can be adapted in two common ways:

1. Backend validates the Logto token, then sets session variables or custom GUCs on the DB connection, and RLS policies read them via `current_setting(...)`.
2. Backend validates the Logto token, then mints an internal DB-facing JWT or session token whose claims are consumed by a PostgREST/Supabase-style access layer.

The RLS policy itself remains PostgreSQL-native. Logto is the upstream token issuer and claim shaper, not the RLS engine.

If you combine organization tokens with PostgreSQL RLS, the cleanest mapping is:

- `sub` -> acting principal
- `organization_id` -> tenant boundary
- `scope` -> coarse action allowlist
- custom claims -> bounded data partitions, such as project, region, chapter, queue, or account set

Then the API enforces resource audience and scopes, while PostgreSQL RLS enforces row visibility using the org and partition claims.

## 4. Cloud, self-hosted, or both

For `Custom JWT`, Logto is explicit:

- available to Logto OSS users
- available to Logto Cloud tenants with development environment
- available to paid Logto Cloud production tenants, including Pro and Enterprise

Logto also documents an execution-model difference:

- in Logto Cloud, custom JWT code runs in an isolated serverless environment
- in Logto OSS, the script runs with the same privileges as the Logto server process

Sources:

- [Create a custom access token script](https://docs.logto.io/developers/custom-token-claims/create-script)
- [May 2024 product update](https://blog.logto.io/changelogs/2024-may)

For organization-scoped API authorization, I found docs describing the feature as part of Logto authorization, and Logto pricing shows `Role-based access control` and `Organizations` as Cloud paid-plan capabilities. I did not find a separate document saying this feature is Cloud-only, and because Logto OSS exists as the open-source product, the safer reading is:

`Inference:` the core feature exists in OSS and Cloud, but Cloud plan gating affects production availability and quotas. There is no evidence of a separate Cloud-only RLS pagination feature.

## 5. How this fits alongside Authentik and OPAL/Cedar

This can coexist, but only if the responsibilities stay clean.

Authentik can remain the primary IdP. Logto supports enterprise OIDC federation, so Logto can sit downstream of Authentik and use Authentik as the upstream identity provider. Sources:

- [Logto OIDC enterprise SSO](https://docs.logto.io/integrations/oidc-sso)
- [Logto enterprise connectors](https://docs.logto.io/connectors/enterprise-connectors)
- [authentik OAuth2/OIDC provider docs](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/)

In that setup:

- Authentik authenticates the user.
- Logto becomes the token issuer for your application/API surface.
- Logto adds organization context, scopes, and possibly custom claims.
- OPAL/Cedar remains the dynamic authorization engine.

This split makes sense because OPAL is an administration layer that keeps policy and policy data in sync with policy agents, and Cedar is designed for request-time authorization decisions over principal, action, resource, context, and entity data. Sources:

- [OPAL intro](https://docs.opal.ac/getting-started/intro)
- [OPAL TL;DR](https://docs.opal.ac/getting-started/tldr)
- [Cedar authorization concepts](https://docs.cedarpolicy.com/auth/authorization.html)

The main design rule is:

- put stable, page-shaping context into Logto tokens
- keep volatile or relationship-heavy decisions in OPAL/Cedar

Examples of good things to embed in a Logto token:

- tenant or organization ID
- static role set
- bounded project IDs if the list is small and changes rarely
- subscription tier

Examples of bad things to embed:

- large dynamic ACL expansions
- rapidly changing per-document permissions
- highly volatile relationship graphs

Why: Logto's own docs warn that `getCustomJwtClaims` runs during token issuance, external fetching adds latency, and token contents remain fixed during the token lifetime. That makes Logto a good coarse-grained authorization carrier, but not a replacement for live policy evaluation.

## 6. Alternatives that achieve the same goal without Logto specifically

Yes. Several patterns can provide the same "don't re-query authorization for every page" outcome.

### A. Token-embedded claims from Authentik or another STS

If Authentik is already the main IdP, you can mint API tokens directly from Authentik or from a thin token-exchange service. Embed tenant/org/role/project claims there and let the API plus PostgreSQL RLS consume them. This removes Logto entirely.

### B. Backend-issued internal DB token

Validate the upstream IdP token once, then mint a short-lived internal database-facing JWT containing only the claims your RLS policies need. This is effectively the pattern in Logto's Supabase guide, but it works with any IdP.

### C. Session variables plus PostgreSQL RLS

Instead of JWT propagation, validate once at the API layer and `SET LOCAL` session variables on the DB connection. RLS reads `current_setting(...)`. This avoids token bloat and is often simpler in service-to-database architectures.

### D. Materialized entitlement tables or access projections

Precompute allowed partitions or relationships in PostgreSQL and have RLS join against those tables. OPAL data sync can feed these tables. This works well when the authorization model is complex but query-time performance must stay predictable.

### E. Cursor or snapshot caching

On the first page request, compute the effective authorization filter or authorized ID set, store a snapshot key, and have later page cursors reference that snapshot. This is the closest thing to a real "protected pagination" feature, but it is application code, not a standard Logto feature.

### F. Keyset pagination instead of offset pagination

Even with token-based claims, keyset pagination is usually better than `OFFSET` for protected result sets. PostgreSQL explicitly warns that `LIMIT`/`OFFSET` without stable ordering is inconsistent, and large offsets are inefficient. Keyset pagination reduces drift and query cost.

## Bottom line

As of 2026-04-11, the best-supported answer is:

- Logto does not appear to offer a dedicated RLS-pagination product feature.
- The relevant Logto capabilities are `Custom JWT` and organization-scoped API tokens.
- Those capabilities can avoid repeated per-page authorization lookups by embedding stable authz context in tokens.
- PostgreSQL RLS still performs the actual row filtering.
- In an Authentik + OPAL/Cedar stack, Logto is most defensible as a token-shaping and coarse-grained authorization layer, not as the authoritative live PDP.
- If you want the same effect without Logto, the strongest alternatives are token-embedded claims, DB session claims, entitlement/materialized-view projections, and cursor/snapshot caching.
