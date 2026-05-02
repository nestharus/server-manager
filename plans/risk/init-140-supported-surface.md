# INIT-140 — Supported-surface risk gate

**Gate role:** supported-surface

**Verdict:** LOW

INIT-140 fixes BL-020 by adding a same-namespace
`KongPlugin/public-intake-rate-limit` next to each
`Ingress/auth-system/web-public-intake` that already carries
`konghq.com/plugins: public-intake-rate-limit` (`proposals/35-init-140-web-host-rate-limit-fix.md:39-48`,
`:118-133`). The target surface is supported by KIC: `KongPlugin` is
the documented custom resource for plugin configuration, and
`konghq.com/plugins` is the documented annotation for associating those
named resources with Ingress rules (`proposals/35-init-140-web-host-rate-limit-fix.md:26-33`).

The proposal changes only GitOps manifests and tests, and explicitly
excludes Pomerium route changes, request-burst testing,
`KongClusterPlugin` migration, cross-namespace reference adoption, and
Discord-visible actions (`proposals/35-init-140-web-host-rate-limit-fix.md:186-198`).

## Required inputs read

- `proposals/35-init-140-web-host-rate-limit-fix.md`
- `.tmp/init-140-bl-020/phase0/rca.md`
- `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`
- `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
- Supporting current KIC docs, accessed May 2, 2026:
  - <https://developer.konghq.com/kubernetes-ingress-controller/reference/annotations/#konghqcomplugins>
  - <https://developer.konghq.com/kubernetes-ingress-controller/custom-resources/#kongplugin>
  - <https://developer.konghq.com/kubernetes-ingress-controller/rate-limiting/>
  - <https://developer.konghq.com/kubernetes-ingress-controller/routing/cross-namespace/>

## Question 1 — Is per-namespace KongPlugin the documented KIC pattern?

**Yes.**

KIC documents `konghq.com/plugins` as the annotation for associating
named `KongPlugin` custom resources with an Ingress, Service,
HTTPRoute, KongConsumer, or KongConsumerGroup. The annotation reference
states that the annotation values are the names of `KongPlugin`
resources applied to the Ingress rules on the annotated Ingress. The
custom-resource docs show `KongPlugin` linked to an Ingress through
`konghq.com/plugins`, and the rate-limiting guide creates a namespaced
`KongPlugin` in the same namespace as the target Service before
annotating that Service.

This matches the local working path:

| Surface | Current state | Result |
|---|---|---|
| API host | `KongPlugin/public-intake-rate-limit` exists in `server-manager` (`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:1-12`) and `Ingress/server-manager-public-intake-api` in `server-manager` references it (`:14-50`) | KIC attaches route-scoped `rate-limiting` for API-host public-intake routes (`.tmp/init-140-bl-020/phase0/rca.md:13-16`) |
| Web host | `Ingress/auth-system/web-public-intake` references `public-intake-rate-limit` (`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml:1-44`) but no matching `KongPlugin` exists in `auth-system` (`.tmp/init-140-bl-020/phase0/rca.md:56-62`) | KIC emits `KongConfigurationTranslationFailed` and the route has `plugins=[]` (`.tmp/init-140-bl-020/phase0/rca.md:17-20`, `:73-82`) |

The RCA's root cause is therefore consistent with documented KIC
behavior: the web Ingress is asking for a named plugin resource that is
absent from the Ingress namespace (`.tmp/init-140-bl-020/phase0/rca.md:99-103`).
Adding the same named `KongPlugin` in `auth-system` is directly on the
supported KIC surface.

## Question 2 — Is duplicating a KongPlugin across namespaces idiomatic?

**Yes for this slice, with an explicit scale boundary.**

KIC docs distinguish the two supported shapes:

- `KongPlugin`: namespaced plugin configuration linked from Kubernetes
  resources through `konghq.com/plugins`.
- `KongClusterPlugin`: cluster-level equivalent, documented for cases
  where plugin configuration should be centralized and controlled by a
  different persona; the docs also state that a namespaced
  `KongPlugin` takes priority over a `KongClusterPlugin` with the same
  name.

That distinction makes the proposal's choice coherent. The policy is
still channel-specific and bound to two concrete namespace-local
Ingresses, so keeping the plugin definition local to each referencing
namespace is a normal Kubernetes/KIC use of a namespaced custom
resource. It avoids a cluster-scoped object whose accidental reuse
would be broader than BL-020 needs (`proposals/35-init-140-web-host-rate-limit-fix.md:52-66`).

This is not the same as saying docs specifically recommend copy/paste
duplication for large fleets. They do not. They provide
`KongClusterPlugin` for centralized shared configuration and Gateway API
/ operator cross-namespace mechanisms for explicitly authorized
cross-namespace references. For INIT-140's two-namespace local/dev
surface, a duplicate namespaced `KongPlugin` is supported and
idiomatic. If the same plugin must be kept identical across many
namespaces or teams, the idiomatic pressure shifts toward an explicit
centralized policy decision, not unbounded manual copies.

## Question 3 — Are there channel templates where this pattern scales poorly?

**Yes, but not enough to block INIT-140.**

Current public-intake channel materialization already has four relevant
files:

| Channel | API-side plugin | Web-side reference |
|---|---|---|
| `local` | `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:1-12` | `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml:1-44` |
| `dev` | `gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml:1-11` | `gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml:1-36` |

INIT-140 would add one `auth-system` plugin copy to the local web file
and one to the dev web file (`proposals/35-init-140-web-host-rate-limit-fix.md:118-133`).
That is acceptable at the current size, especially because the proposal
keeps each plugin beside the Ingress that references it
(`proposals/35-init-140-web-host-rate-limit-fix.md:70-78`).

The scaling limit is config drift. The proposal requires the
`auth-system` copy to match the canonical `server-manager` config
exactly (`minute: 5`, `hour: 50`, `policy: local`,
`fault_tolerant: true`, `hide_client_headers: false`)
(`proposals/35-init-140-web-host-rate-limit-fix.md:91-112`). The local
API-side manifest already matches that (`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:6-12`),
but the current dev API-side manifest lacks `policy: local`
(`gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml:6-11`).
The proposal notices this and says the dev API-side manifest should be
checked during implementation (`proposals/35-init-140-web-host-rate-limit-fix.md:109-112`).

The proposed static anti-orphan test is necessary but not sufficient for
long-term template scaling: it catches missing same-namespace plugins
(`proposals/35-init-140-web-host-rate-limit-fix.md:135-144`,
`:168-177`), but by itself it does not prove all duplicated
`public-intake-rate-limit` plugins have identical config across
`server-manager` and `auth-system` in each channel. That is acceptable
for this supported-surface gate because Q4 makes config parity a
contract and the runtime validator remains the live local proof
(`proposals/35-init-140-web-host-rate-limit-fix.md:148-166`,
`:179-184`). It should be carried into implementation as a test-quality
observation.

## Supported-surface evaluation

| Check | Verdict | Reason |
|---|---|---|
| KIC supports `KongPlugin` on Ingress via `konghq.com/plugins` | PASS | Official annotation and CRD docs describe this exact surface; rate-limiting guide uses namespaced `KongPlugin` + annotation. |
| Same-namespace fix addresses the RCA root cause | PASS | The failing Ingress is in `auth-system` and lacks a same-namespace plugin; working API Ingress has plugin and reference in `server-manager`. |
| Duplicating plugin across current channel namespaces is acceptable | PASS | Namespaced resources are the documented non-cluster-scoped KIC path; `KongClusterPlugin` is explicitly deferred until centralization is worth the blast radius. |
| Channel-template scaling | PASS with observation | Two channels / two namespaces is manageable; more channels need stronger parity tests or a deliberate `KongClusterPlugin` decision. |
| Adjacent surfaces | PASS | No Pomerium route, API contract, Cedar/OPAL, Authentik, DB, web app, or Discord-visible surface changes. |

## Findings

### F1 — Config parity test should be stronger than anti-orphan detection

Severity: LOW.

The same-namespace anti-orphan test catches the exact BL-020 failure
class, but duplicated `KongPlugin` resources can still drift in config.
That risk is already visible because the current dev API-side
`KongPlugin` omits `policy: local`, while the proposal's canonical
config includes it (`gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml:6-11`,
`proposals/35-init-140-web-host-rate-limit-fix.md:96-112`).

This does not block the supported-surface gate: per-namespace
`KongPlugin` is supported and Q4 already specifies exact parity. It
does mean implementation should either extend the new pytest guard to
assert exact config equality for all `public-intake-rate-limit`
`KongPlugin` resources in a channel, or otherwise prove that the copied
`auth-system` plugins and existing `server-manager` plugins cannot drift
silently.

### F2 — Revisit centralization only after the copy count grows

Severity: LOW.

The proposal's deferral of `KongClusterPlugin` is appropriate for
INIT-140 because the public-intake policy remains channel-specific and
the failing reference is fixed by adding a local resource beside the
referencing Ingress (`proposals/35-init-140-web-host-rate-limit-fix.md:52-66`).
If future channel templates add more public-intake namespaces or more
shared plugin policies, the KIC docs point to `KongClusterPlugin` as the
centralized configuration mechanism. That should be a separate design
decision, not a hidden migration inside this bug fix.

## Verdict

**LOW.** The target surface is supported by current KIC docs, the fix is
faithful to the RCA, and the immediate local/dev namespace-copy pattern
is acceptable. The only material caveat is config drift as duplicated
plugins multiply; that is a test-strengthening observation, not a gate
failure for INIT-140.

GATE_SUPPORTED-SURFACE_DONE: plans/risk/init-140-supported-surface.md
