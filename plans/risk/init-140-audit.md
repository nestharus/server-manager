# INIT-140 / BL-020 - Audit risk gate

**Verdict:** LOW

Scope: audit Proposal 35, "INIT-140: Web host rate-limit binding fix",
for KIC namespace resolution correctness, duplicate namespaced
`KongPlugin` behavior, and the `rate-limiting` plugin's `policy:
local` implications.

Source proposal:
`proposals/35-init-140-web-host-rate-limit-fix.md`.
Source RCA:
`.tmp/init-140-bl-020/phase0/rca.md`.
Primary local manifests:
`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml` and
`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`.

## A1 - KIC namespace resolution is correctly represented

The proposal's root-cause claim is technically correct:
`Ingress/auth-system/web-public-intake` annotates
`konghq.com/plugins: public-intake-rate-limit`, and a name-only
plugin reference resolves in the referer's namespace, not by searching
other namespaces.

Evidence:

- The local web Ingress is in namespace `auth-system` and references
  `public-intake-rate-limit` by name only
  (`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml:4-13`).
- The existing local `KongPlugin/public-intake-rate-limit` is in
  namespace `server-manager`, not `auth-system`
  (`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:1-10`).
- The RCA's live event confirms KIC failed translation on the
  `auth-system` Ingress with
  `referenced KongPlugin or KongClusterPlugin "public-intake-rate-limit" does not exist`
  (`.tmp/init-140-bl-020/phase0/rca.md:73-82`).
- KIC annotation docs define `konghq.com/plugins` as associating named
  `KongPlugin` resources with Ingress rules:
  https://developer.konghq.com/kubernetes-ingress-controller/reference/annotations/#konghqcomplugins
- KIC source at commit `e7b3048` parses annotation values as either
  `namespace:name` or name-only strings. Name-only strings leave
  `plugin.Namespace` empty.
  https://github.com/Kong/kubernetes-ingress-controller/blob/e7b3048dfa2b311009efb8dd3035cbec41f87b8a/internal/annotations/annotations.go#L161-L184
- KIC relation building defaults to `referer.GetNamespace()` and only
  switches namespace when a remote namespace was explicitly specified
  and permitted by `ReferenceGrant`. For Ingress route plugins it builds
  a virtual Ingress with `Namespace: ingress.Namespace`.
  https://github.com/Kong/kubernetes-ingress-controller/blob/e7b3048dfa2b311009efb8dd3035cbec41f87b8a/internal/dataplane/kongstate/kongstate.go#L342-L405
- KIC later fetches the plugin by the computed `namespace:name` key and
  skips plugin creation when lookup fails.
  https://github.com/Kong/kubernetes-ingress-controller/blob/e7b3048dfa2b311009efb8dd3035cbec41f87b8a/internal/dataplane/kongstate/kongstate.go#L482-L495

The proposal's Option A, adding
`KongPlugin/auth-system/public-intake-rate-limit`, directly fixes the
actual lookup path. Audit risk LOW for A1.

## A2 - Duplicate KongPlugin names in two namespaces produce independent route associations

The proposal's duplicate-resource plan is technically clean:

- `Ingress/server-manager/server-manager-public-intake-api` resolves
  its name-only annotation against
  `KongPlugin/server-manager/public-intake-rate-limit`
  (`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:17-26`).
- `Ingress/auth-system/web-public-intake` will resolve the same
  name-only annotation against the proposed
  `KongPlugin/auth-system/public-intake-rate-limit`
  (`proposals/35-init-140-web-host-rate-limit-fix.md:39-48`).

KIC keys plugin relations by `namespace:name`, so the two resources are
not collapsed into one association bucket. During plugin build, KIC
loads each `namespace:name` entry separately, then emits one Kong plugin
entity for each relation combination. Route relations receive a
specific Kong route ID.

Relevant KIC source:

- Relation key: `pluginKey := namespace + ":" + plugin.Name`.
  https://github.com/Kong/kubernetes-ingress-controller/blob/e7b3048dfa2b311009efb8dd3035cbec41f87b8a/internal/dataplane/kongstate/kongstate.go#L380-L405
- Build loop fetches the plugin for that namespace/name, iterates
  `relations.GetCombinations()`, deep-copies the plugin, and assigns
  `plugin.Route = &kong.Route{ID: ...}` for route relations.
  https://github.com/Kong/kubernetes-ingress-controller/blob/e7b3048dfa2b311009efb8dd3035cbec41f87b8a/internal/dataplane/kongstate/kongstate.go#L482-L548

That means the fix should create one route-scoped `rate-limiting`
plugin for the API-host route and one route-scoped `rate-limiting`
plugin for the web-host route. It should not double-bind both plugins
to either route, and it should not create a shared KIC relation state
between the namespaces.

Audit risk LOW for A2.

## A3 - `policy: local` does not create per-namespace divergence, but it preserves per-node local counters

The proposal pins the `auth-system` plugin config to the local
`server-manager` config: `minute: 5`, `hour: 50`, `policy: local`,
`fault_tolerant: true`, and `hide_client_headers: false`
(`proposals/35-init-140-web-host-rate-limit-fix.md:91-112`).
This matches the local canonical manifest
(`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:6-12`).

Kong's documented `local` strategy stores counters in memory on the
Kong node, has minimal performance impact, and is less accurate when
traffic is distributed across multiple nodes without consistent hashing:
https://developer.konghq.com/plugins/rate-limiting/

Kong's KIC rate-limiting example states the same operational behavior:
with `policy: local`, request counters are stored in each Pod's local
memory separately and each Kong node applies the policy independently:
https://docs.konghq.com/kubernetes-ingress-controller/latest/plugins/rate-limiting/

Audit conclusion:

- There is no Kubernetes namespace-level counter divergence introduced
  by duplicating the `KongPlugin`; namespaces only affect KIC lookup and
  relation construction before Kong config is generated.
- There is existing Kong runtime divergence from `policy: local`: each
  Kong node/pod counts independently.
- The fix also creates independent route-scoped plugin entities for the
  API-host and web-host routes. This is consistent with the proposal's
  route-scoped validator acceptance (`proposals/35-init-140-web-host-rate-limit-fix.md:156-166`),
  but it is not a shared global public-intake quota across both hostnames.

This is not an F-level blocker because INIT-140 is scoped to restoring
the missing route-scoped plugin association and explicitly anti-scopes
request-burst behavior testing (`proposals/35-init-140-web-host-rate-limit-fix.md:193-196`).
Audit risk LOW for A3.

## Findings

No F1/F2 findings.

## Gate

The proposal is technically correct for KIC namespace resolution and
for the duplicate namespaced `KongPlugin` fix. Proceed to the next gate.

GATE_AUDIT_DONE: plans/risk/init-140-audit.md
