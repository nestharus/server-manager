# Phase 1 scope risk assessment

Assessed against: `plans/proposals/phase1-foundation.md`

## Overall verdict: LOW

Phase 1 is appropriately narrow for a foundation bootstrap. It covers
the infrastructure substrate, GitOps reconciler, minimal secrets,
baseline ingress, and provider object storage without pulling in
identity, authorization, access proxy, database, eventing, or
application services. The deferred items are correct deferrals. The
in-scope items are proportionate to a bootstrap phase.

No findings warrant blocking the proposal. Five findings are recorded
below for tracking.

---

## Findings

### F-1. Buildkite boundary is one-sided — LOW

The proposal defines the CI/CD boundary clearly: Buildkite validates
changes, Flux reconciles cluster state, and Buildkite must not perform
out-of-band cluster mutation. However, Phase 1 only deploys the Flux
side. Buildkite agent placement is listed as an open question (section
6), and Buildkite is explicitly absent from the in-scope items.

**Risk**: the boundary is a stated intent rather than a validated
integration. Phase 1 will prove that Flux is the sole reconciler, but
it will not prove that Buildkite can participate correctly in the
delivery path.

**Assessment**: acceptable for bootstrap. The principle matters more
than bilateral deployment in the first phase. The boundary becomes
testable once Buildkite agents are placed in a later phase. No scope
change needed, but the exit criterion about the CI/GitOps boundary
(section 7, bullet 7) should be understood as a policy assertion rather
than an integration test.

### F-2. Minimal observability is entirely deferred — LOW

The proposal defers "broad observability" (section 5) and does not
mention any minimum cluster health or monitoring capability for the
foundation. `kube-hetzner` may ship default health tooling, but the
proposal does not rely on that or specify any minimum.

**Risk**: blind debugging during the most operationally fragile phase of
the platform. If a node, pod, or Flux reconciliation fails during
bootstrap validation, operators have no agreed-upon observability
baseline to diagnose it.

**Assessment**: this is a minor gap, not a scope violation. The proposal
should not pull in a full observability stack, but acknowledging that
some minimal health surface (node status, pod health, Flux
reconciliation status) is part of bootstrap validation would strengthen
the exit criteria.

### F-3. Object storage automation crosses a provider boundary — LOW

The proposal correctly notes (section 3, "Infrastructure control plane")
that Hetzner Object Storage automation may cross a provider boundary
because S3-style object storage is not covered by the `hcloud` resource
set. The OpenTofu research confirms this: Hetzner's own object-storage
docs point to the MinIO provider for bucket management.

**Risk**: the "reproducible from a clean environment" exit criterion
(section 7, bullet 1) depends on a secondary provider path that is not
yet finalized. That is a small seam in an otherwise clean OpenTofu
entrypoint story.

**Assessment**: acceptable. The proposal explicitly acknowledges this
and treats it as a known implementation detail. No scope change needed.

### F-4. TLS provisioning strategy is implicit — LOW

Kong is installed as the baseline ingress layer, and the exit criteria
require it to serve traffic through the Hetzner networking and
load-balancer path. For a "production-capable" foundation, TLS
termination is a reasonable baseline expectation, but the proposal does
not mention a certificate provisioning strategy (cert-manager, manual
certificates, or Hetzner managed certificates on the load balancer).

**Risk**: the ingress exit criterion may be met with HTTP-only traffic,
which would be technically correct but would leave the next phase
responsible for retrofitting TLS into an already-running ingress path.

**Assessment**: minor gap. The proposal does not need to solve the full
certificate lifecycle, but noting whether Phase 1 ingress is TLS-capable
or HTTP-only would reduce ambiguity.

### F-5. Platform-decisions-overlay is stale — INFO

The platform-decisions-overlay (`plans/platform-decisions-overlay.md`,
"Still open after this overlay") lists "Hosting decision: Hetzner vs
Vultr" as open. The Phase 1 proposal treats Hetzner as a locked
decision. This is a documentation gap, not a scope risk.

The Hetzner-vs-Vultr research recommends Vultr as the stronger platform
host, and the OpenTofu research notes Vultr has cleaner first-party
provider coverage. The Phase 1 proposal's commitment to Hetzner is
internally consistent and architecturally sound regardless of the
research recommendation, but the overlay should be updated to reflect
the lock so downstream documents do not reopen a decided question.

---

## Assessment against criteria

### 1. Is Phase 1 appropriately narrow for a foundation bootstrap?

**Yes.** The scope is substrate, reconciler, secrets, ingress, and
object storage. No application services, no identity, no authorization,
no access proxy, no database, no eventing. The exit criteria are
concrete and testable. The proposal explicitly names its own biggest
failure mode as scope creep (section 6) and constrains against it.

### 2. Does it defer anything that should be in the bootstrap path?

**Mostly no.** The two minor gaps are observability (F-2) and TLS (F-4),
both of which are reasonable to address as implementation-level
decisions rather than proposal-level scope changes. Nothing critical is
deferred that would block a working foundation.

### 3. Does it pull in later-phase work too early?

**No.** Every in-scope item is directly required for the bootstrap
substrate. Kong is kept to north-south ingress. SOPS + age is kept to
GitOps-compatible bootstrap secrets. Object storage is kept to one
provider bucket. Pomerium, Authentik, OPAL/Cedar, Postgres, Smallstep,
SeaweedFS, and application services are all explicitly out of scope.

### 4. Is the Buildkite / Flux / ingress / secrets split proportionate?

**Yes, with one caveat.** Flux is correctly positioned as the sole
reconciler and is deployed in Phase 1. Kong is correctly scoped to
north-south baseline ingress. SOPS + age is correctly scoped to
GitOps-native bootstrap secrets. The Buildkite side of the CI/CD
boundary is stated but not deployed (F-1), which is acceptable for
bootstrap but means the split is a policy assertion, not a validated
integration, until a later phase.
