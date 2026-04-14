# Phase 1 scope risk assessment

Assessed against: `plans/proposals/phase1-foundation.md`
Cross-referenced with: `plans/platform-decisions-overlay.md`,
`plans/research/hetzner-vs-vultr.md`, `plans/research/buildkite-capabilities.md`,
`plans/research/self-hosted-s3.md`, `plans/research/pomerium-smallstep.md`,
`plans/research/opentofu-providers.md`

## Overall verdict: LOW

Phase 1 is appropriately narrow for a foundation bootstrap. The
in-scope items — Hetzner substrate, k3s via kube-hetzner, Flux CD,
SOPS + age secrets, Kong ingress, and Hetzner Object Storage — are
exactly the components needed to produce a reproducible, GitOps-driven
cluster foundation. The deferred items (Authentik, OPAL/Cedar, Pomerium,
Postgres, Smallstep, SeaweedFS, Buildkite agents, eventing, application
services) are correct deferrals that would widen the blast radius of
the bootstrap without strengthening it.

Six findings are recorded below. None warrant blocking the proposal.

---

## Findings

### F-1. Hosting decision conflict with research — LOW

The platform-decisions-overlay (`plans/platform-decisions-overlay.md`,
"Still open after this overlay") lists "Hosting decision: Hetzner vs
Vultr" as open. The Phase 1 proposal treats Hetzner as locked. Meanwhile,
the Hetzner-vs-Vultr research recommends Vultr as the stronger platform
host, and the OpenTofu research notes Vultr has cleaner first-party
provider coverage (managed Kubernetes, object storage, and database
resources all native to the provider).

**Risk**: if the hosting decision has not been formally locked, Phase 1
builds on a foundation that the research recommends against. If it has
been locked, the overlay is stale and downstream readers may reopen a
decided question.

**Assessment**: this is a process/documentation concern, not a scope
defect in the proposal itself. The proposal is internally consistent
about Hetzner and architecturally sound on that assumption. The overlay
should be updated to reflect whichever decision was actually made.
No scope change needed.

### F-2. Buildkite boundary is stated but not validated — LOW

The proposal defines the CI/CD boundary clearly: Buildkite validates
changes, Flux reconciles cluster state, and Buildkite must not perform
out-of-band cluster mutation. However, Phase 1 only deploys the Flux
side. Buildkite agent placement is listed as an open question (section
6), and Buildkite is explicitly absent from the in-scope items.

The exit criterion in section 7 ("the CI/GitOps boundary is explicit
and enforced: Buildkite is not performing out-of-band cluster mutation")
is technically unfalsifiable in Phase 1 — Buildkite cannot mutate the
cluster if it is not present.

**Risk**: the boundary is a policy assertion, not a validated
integration. Phase 1 proves Flux is the sole reconciler, but cannot
prove the two systems interoperate correctly across the seam.

**Assessment**: acceptable for bootstrap. The principle matters more
than bilateral deployment in the first phase. The boundary becomes
testable when Buildkite agents arrive. The exit criterion should be
read as a design constraint, not an integration test.

### F-3. No observability baseline for bootstrap validation — LOW

The proposal defers "broad observability" (section 5) without specifying
any minimum cluster health or monitoring capability. kube-hetzner may
ship default health tooling, but the proposal does not rely on or
specify any minimum diagnostic surface.

**Risk**: blind debugging during the most operationally fragile phase
of the platform. If a node, Flux reconciliation, or Kong routing fails
during bootstrap validation, operators have no agreed-upon observability
baseline to diagnose it.

**Assessment**: minor gap, not a scope violation. The proposal should
not pull in a full observability stack, but acknowledging that some
minimum health surface (node status, pod health, Flux reconciliation
status, Kong request path) is part of bootstrap validation would
strengthen the exit criteria without expanding scope.

### F-4. Object storage automation crosses a provider boundary — LOW

The proposal correctly notes (section 3, "Infrastructure control plane")
that Hetzner Object Storage automation may cross a provider boundary
because S3-style object storage is not in the `hcloud` resource set.
The OpenTofu research confirms this: Hetzner's own docs point to the
MinIO provider for bucket management. The self-hosted S3 research
separately notes that Hetzner object storage is single-DC-per-bucket
and EU-only.

**Risk**: the "reproducible from a clean environment" exit criterion
(section 7, bullet 1) depends on a secondary provider path that is
not yet finalized. This is a small seam in an otherwise clean OpenTofu
entrypoint story.

**Assessment**: acceptable. The proposal explicitly acknowledges this
and treats it as a known implementation detail rather than hiding it.
No scope change needed.

### F-5. TLS provisioning strategy is implicit — LOW

Kong is installed as the baseline ingress layer and the exit criteria
require it to serve traffic through the Hetzner networking and
load-balancer path. For a "production-capable" foundation, TLS
termination is a reasonable baseline expectation, but the proposal
does not mention a certificate provisioning strategy (cert-manager,
Hetzner managed certificates on the load balancer, or manual
certificates).

**Risk**: the ingress exit criterion could be met with HTTP-only
traffic, which would be technically correct but would force the next
phase to retrofit TLS into an already-running ingress path.

**Assessment**: minor gap. The proposal does not need to solve the
full certificate lifecycle, but noting whether Phase 1 ingress is
TLS-capable or HTTP-only would reduce ambiguity for Phase 2 planners.

### F-6. kube-hetzner bootstrap seam not reflected in exit criteria — INFO

The OpenTofu research notes that kube-hetzner's quick start requires
`packer`, `kubectl`, and `hcloud`, and creates a MicroOS snapshot
before `tofu apply`. The proposal's exit criterion says OpenTofu can
create the Hetzner substrate and the kube-hetzner bootstrap "from a
clean environment," but does not acknowledge the Packer image-build
step that precedes the OpenTofu apply.

**Risk**: the rebuild story may appear simpler in the exit criteria
than it is in practice. The Packer step is not a secret — kube-hetzner
documents it — but the exit criteria do not account for it.

**Assessment**: documentation-level concern. Noting the Packer
prerequisite in the exit criteria or the rebuild story would make the
"no undocumented manual steps" commitment more precise.

---

## Assessment against criteria

### 1. Is Phase 1 appropriately narrow for a foundation bootstrap?

**Yes.** The scope is substrate, reconciler, secrets, ingress, and
object storage. No application services, no identity, no authorization,
no access proxy, no database, no eventing, no multi-region. The exit
criteria are concrete and testable. The proposal names scope creep as
its own biggest failure mode (section 6) and constrains against it.
This is a disciplined bootstrap scope.

### 2. Does it defer anything that should be in the bootstrap path?

**Mostly no.** Two minor gaps exist:

- **Observability** (F-3): some minimum diagnostic surface would
  strengthen bootstrap validation, but pulling in a full monitoring
  stack would violate the narrowness principle.
- **TLS** (F-5): a production-capable foundation arguably includes TLS,
  but the proposal can address this as an implementation decision
  without expanding proposal-level scope.

Nothing critical is deferred that would block a working foundation.
Buildkite agent deployment is correctly deferred — the bootstrap does
not need CI execution, only a reconciler.

### 3. Does it pull in later-phase work too early?

**No.** Every in-scope item is directly required for the bootstrap
substrate:

- OpenTofu + kube-hetzner: the cluster exists
- Flux CD: the cluster has a reconciliation path
- SOPS + age: secrets can be committed and reconciled
- Kong: traffic can reach the cluster
- Hetzner Object Storage: the cluster has an S3-compatible target

Pomerium, Authentik, OPAL/Cedar, Postgres, Smallstep, SeaweedFS,
Kafka, Debezium, Redis, and all application services are correctly
excluded. The proposal does not succumb to the temptation of deploying
"just one more" locked component during bootstrap.

### 4. Is the Buildkite / Flux / ingress / secrets split proportionate?

**Yes, with one caveat.**

- **Flux**: correctly positioned as the sole reconciler and deployed in
  Phase 1. Proportionate.
- **Buildkite**: correctly deferred for agent deployment. The boundary
  is documented as a design constraint. The exit criterion about it is
  a policy assertion rather than an integration test (F-2), which is
  acceptable at this stage. Proportionate.
- **Kong (ingress)**: correctly scoped to north-south baseline traffic.
  Not overloaded with identity, authorization, or operator-access
  responsibilities. Proportionate.
- **SOPS + age (secrets)**: correctly scoped to GitOps-native bootstrap
  secrets. Explicitly positioned as a pragmatic bootstrap choice that
  later phases may replace. Proportionate.

The split allocates the right amount of weight to each concern for a
foundation phase.
