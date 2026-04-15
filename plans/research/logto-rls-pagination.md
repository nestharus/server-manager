# Logto RLS pagination research

## 1. Executive summary

As of April 14, 2026, Logto is a credible identity server with solid support for OAuth/OIDC, RBAC, multi-tenant organizations, organization-scoped API tokens, custom token claims, webhooks, and standard API-side JWT validation. It is materially more capable than a bare authentication broker.

However, nothing in Logto's current feature set changes the core problem this platform cares about: protected result filtering over cursor pagination without constant re-querying. Logto can issue richer tokens, including organization context and scopes, and it can notify the app when auth state changes. It does not provide a first-class mechanism for stable authorized result sets, cursor snapshots, row-visibility evaluation inside the database, or policy-aware pagination semantics.

In practice, Logto still leaves the hard part in the application or data layer:

- deciding what a cursor means when authorization can change between page fetches
- deciding whether row visibility is evaluated against current policy or a snapshot
- enforcing row-level predicates inside SQL or an authorization engine on every page
- handling drift when the authorized set changes while a client is paginating

For this platform specifically, Logto is best understood as a lighter IdP and token issuer, not as a solution to the protected-pagination problem. Given the user's stated preference for the more robust `Authentik + Pomerium + OPAL/Cedar` direction, Logto should not change the platform recommendation.

## 2. Capability snapshot

### Identity and token issuance

Logto's current docs frame it as an auth server / identity provider that issues token-based authorization artifacts for apps and APIs. Its authorization model is explicitly token-centric: users, clients, and services receive permissions through RBAC, and backends validate those tokens and scopes on each request.

Relevant current capabilities:

- Global RBAC for users and machine-to-machine clients.
- Organization-aware RBAC for multi-tenant SaaS.
- Organization templates that define reusable organization roles and permissions across tenants.
- Global API resources and organization-level API resources.
- Organization permissions for non-API actions and UI/business-logic gating.
- Custom access-token claims through `getCustomJwtClaims`.
- Webhooks for changes to users, roles, permissions, organizations, organization roles, and organization permissions.
- Standard backend API protection guidance for FastAPI and other stacks via JWT validation, audience checks, scope checks, issuer checks, and organization-context checks.

The important shape of the model is:

- Logto decides identity and coarse permission claims.
- The application validates the token and enforces the claims.
- Multi-tenant isolation is expressed through org-aware tokens and scopes, not through a database-native visibility model.

### Organizations and API authorization

Logto's organization model is mature enough to matter for B2B SaaS:

- organizations represent tenants / workspaces / customers
- users and M2M apps can hold different roles in different organizations
- organization-level API tokens can include both API audience and `organization_id`
- docs explicitly position this for tenant-level isolation in SaaS

That is useful for clean tenant scoping. If the platform's authorization problem were mostly "which tenant is this user acting in?" plus coarse scopes, Logto would help.

### What it does not advertise as a first-class feature

I found no first-class Logto feature for:

- database row-level security authoring or execution
- query rewriting for authorization predicates
- result-set snapshotting for paginated reads
- stable-cursor semantics under changing authorization
- live policy-data synchronization into a policy engine or database
- protected list filtering beyond "validate token, then enforce in your app/API"

Custom token claims and webhooks are the closest features, but they are still infrastructure for passing claims and events, not for solving list/filter/cursor consistency.

## 3. Does Logto change the RLS-pagination problem?

Short answer: no, not materially.

### What Logto does help with

Logto can simplify the front edge of the problem:

- a request can arrive with a validated identity
- the token can already contain org context and scopes
- coarse tenant filters can often be derived directly from the token
- permission-change webhooks can help invalidate caches or trigger token refresh logic

That reduces some auth plumbing. It may eliminate repeated lookups like "which org is this request acting in?" or "which coarse scopes does this principal have?" if those are already in the token.

### Why the hard problem still remains

The platform's actual problem is not "how do I know who the user is?" It is "how do I page through a protected result set when visibility can change per row, across requests, without constantly re-running unstable queries?"

Logto does not change that because the protected result-set problem usually depends on data Logto does not own:

- row attributes
- row-to-subject relationships
- dynamic policy data
- joins across business tables
- mutable sharing state
- in-flight permission or membership changes

Even Logto's strongest multi-tenant authorization feature, organization-level API resources, still ends with "validate access tokens in your API, enforcing both organization context and permissions." The FastAPI guide shows the backend validating JWTs, checking `aud`, checking `organization_id`, and checking required scopes. That is request authorization, not result-set shaping.

### Stable cursor semantics are still your job

A stable cursor over an authorized list needs one of these patterns:

- a snapshot of the visible set
- a cursor keyed to a monotonic sort plus an authorization predicate that is re-evaluated consistently
- materialized authorization state that the query can join against
- explicit acceptance of drift and duplicates / gaps

Logto does not provide any of those.

At best, Logto can give the query more input:

- `sub`
- `organization_id`
- coarse scopes
- custom claims

But the database or authorization layer still has to answer the real question for every row: "is this row visible to this principal in this policy state?"

### Logto's own JWT model highlights the limitation

Logto's docs explicitly say permission updates only appear in newly issued tokens and never modify existing JWTs. Existing JWTs keep old scopes until expiry, and the docs recommend validating scopes on every call, using short token lifetimes, and optionally signaling clients to refresh.

That is reasonable token hygiene, but it is also evidence that Logto does not solve stable authorized pagination:

- if tokens are the carrier of auth state, older page requests can continue with stale scopes until expiry
- if you refresh aggressively, the visible set can change between pages
- if row visibility depends on business data beyond scopes, token refresh still does not solve it

### Narrow case where Logto helps a little

There is one narrow case where Logto meaningfully reduces complexity:

- visibility is mostly tenant scoping by `organization_id`
- permissions are coarse and role-based
- list results are already partitioned cleanly by tenant
- row-level authorization inside a tenant is not the primary challenge

In that case, Logto's organization tokens can cleanly drive predicates like `WHERE org_id = :organization_id`, and pagination becomes normal tenant-local cursor pagination.

That is not the problem described here. The problem here is protected filtering over a changing authorized set, which remains a data-layer concern.

## 4. Operational and architectural fit

### Relative fit of Logto itself

Logto is still operationally lighter than the heavier direction:

- one main identity service plus Postgres
- standard OIDC/OAuth integration pattern
- official backend integration docs
- good built-in story for organizations and app-facing RBAC

But "lighter" should be interpreted carefully in 2026. Logto's current OSS docs recommend `2` vCPU, `8 GiB` memory, and `256 GiB` disk as minimum hosting guidance. OSS also does not support multiple administrators, which is a real operational limit for a team-managed platform. For production multi-instance deployments, the docs also call out shared connector storage and single-instance DB alteration steps.

So Logto is lighter than a broader access-and-policy stack, but it is not magic "tiny auth sidecar" infrastructure anymore.

### Fit versus `Authentik + Pomerium + OPAL/Cedar`

Compared to the heavier direction:

- `Logto` gives you identity, login flows, tenant-aware RBAC, and token issuance.
- `Authentik` is a fuller workforce / SSO identity platform with broader provider and proxy-adjacent operational patterns.
- `Pomerium` adds identity-aware access mediation for human/operator entry points and continuous request-time policy at the gateway layer.
- `OPAL/Cedar` adds a dedicated authorization plane for fine-grained policy evaluation and fast policy/data propagation.

The key point is not that the heavier stack solves pagination automatically. It does not. Cursor stability still belongs to the app and data model.

The key point is that the heavier stack is aligned with the platform's actual needs:

- separate identity from authorization
- support richer, changing policy data
- avoid overloading token scopes as the whole authorization model
- give the system a real policy plane rather than only token claims

Cedar is explicitly designed as a separate authorization layer that answers "can this principal take this action on this resource in this context?" OPAL is explicitly designed to push policy and policy-data changes to policy agents in real time. That combination is much closer to a system that can support changing protected visibility than Logto alone, even though the final cursor semantics still need application design.

So operationally:

- Logto is simpler if the goal is mostly authn plus coarse RBAC.
- The heavier stack is more complex, but it matches a platform that already wants a robust, explicit authorization architecture.

## 5. Risks and caveats

- Do not mistake org-scoped tokens for row-level authorization. They help with tenant context, not with per-row visibility rules.
- Do not mistake custom claims for dynamic authorization. Claims are extra token data, not a live policy engine.
- Do not mistake webhooks for solved consistency. They can trigger invalidation or refresh, but they do not define stable page semantics.
- Logto's JWT model can worsen ambiguity if the system relies too heavily on token-contained scopes while business authorization changes mid-pagination.
- OSS operational limits matter: current docs say self-hosted OSS does not support configuring multiple administrators.
- The current OSS deployment guidance is less lightweight than older Logto impressions suggested.
- If the platform already prefers `Authentik + Pomerium + OPAL/Cedar`, switching to Logto for simplicity would save components while giving up architectural separation exactly where this platform seems to want more of it, not less.

## 6. Recommendation

Do not adopt Logto on the theory that it materially solves the RLS-pagination problem. It does not.

For this platform, the right conclusion is narrower:

- treat Logto as a viable lighter IdP and token issuer
- do not treat it as an authorization-system substitute
- do not let it change the platform recommendation toward a more robust stack

If the platform were optimizing for a simpler baseline of "ship app auth quickly with organizations and RBAC," Logto would remain a credible option.

Given the user's stated preference for the more robust 2026 direction, the recommendation is:

- keep the `Authentik + Pomerium + OPAL/Cedar` trajectory
- regard Logto as insufficient leverage on the specific protected-pagination problem
- only reconsider Logto if the platform intentionally decides to collapse back to a simpler IdP-centric architecture and accept that authorization and pagination semantics stay in application code and SQL

## Sources

- Logto docs, "Authorization": https://docs.logto.io/authorization
- Logto docs, "Role-based access control (RBAC)": https://docs.logto.io/authorization/role-based-access-control
- Logto docs, "Protect organization-level API resources": https://docs.logto.io/authorization/organization-level-api-resources
- Logto docs, "Protect your FastAPI with RBAC and JWT validation": https://docs.logto.io/api-protection/python/fastapi
- Logto docs, "Organizations": https://docs.logto.io/organizations
- Logto docs, "Custom access token": https://docs.logto.io/developers/custom-token-claims
- Logto docs, "Webhooks": https://docs.logto.io/developers/webhooks
- Logto docs, "Get started with OSS": https://docs.logto.io/logto-oss/get-started-with-oss
- Logto docs, "Deployment and configuration": https://docs.logto.io/logto-oss/deployment-and-configuration
- authentik docs, "Providers": https://docs.goauthentik.io/docs/providers
- authentik docs, "Outposts": https://docs.goauthentik.io/add-secure-apps/outposts
- Pomerium docs, "Authorization and Policy Enforcement with Pomerium": https://www.pomerium.com/docs/capabilities/authorization
- Cedar Policy Language docs, "What is Cedar?": https://docs.cedarpolicy.com/
- Cedar Policy Language docs, "How Cedar authorization works": https://docs.cedarpolicy.com/auth/authorization.html
- OPAL docs, "Welcome to OPAL": https://docs.opal.ac/
- OPAL docs, "Architecture": https://docs.opal.ac/overview/architecture
- OPAL docs, "OPAL TL;DR": https://docs.opal.ac/getting-started/tldr/
