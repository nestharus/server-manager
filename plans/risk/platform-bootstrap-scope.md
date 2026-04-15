# Platform Bootstrap — scope risk assessment

Assessed against: `plans/proposals/platform-bootstrap.md`
Cross-referenced with: `plans/platform-decisions-overlay.md`,
`plans/proposals/gitops-foundation.md`,
`plans/proposals/app-cluster-provisioning.md`,
`plans/proposals/phase1-foundation.md`

## Overall verdict: LOW

Platform Bootstrap is scoped tightly to one job: produce a reproducible
`Vultr VKE` platform cluster with provider-native VPC networking and
S3-compatible remote state, per environment, via per-environment
`OpenTofu` roots. It stops before Flux installation, before Crossplane,
and before any in-cluster platform service.

The two boundary defects identified in the prior assessment have been
resolved. Crossplane installation ownership is now explicitly assigned
to Application Cluster Provisioning as its day-zero prerequisite, and
all three proposals agree on this assignment. The handoff artifact is
now specified with comparable precision to Application Cluster
Provisioning's readiness contract: API server endpoint, kubeconfig or
connection-secret storage path, retrieval access control,
encryption-at-rest posture, and credential lifetime model. Four LOW
findings remain, all addressable during implementation without proposal
changes.

---

## Findings

### F-1. Hosting decision still marked open in the overlay — LOW

`plans/platform-decisions-overlay.md` under "Still open after this
overlay" lists *"Hosting decision: Hetzner vs Vultr"* as unresolved.
`plans/proposals/platform-bootstrap.md` treats `Vultr VKE` as locked
throughout. `plans/proposals/phase1-foundation.md` treats `Hetzner` +
`k3s` via `kube-hetzner` as locked. Two proposals in the same directory
contradict each other on the hosting substrate, and the overlay still
says the question is open.

**Risk**: downstream readers may reopen a settled question, or may
implement the wrong provider path because the authoritative record is
unclear. This is a documentation coherence issue, not a scope defect
inside Platform Bootstrap itself — the proposal is internally consistent
on Vultr.

**Recommendation**: update the overlay to reflect the actual decision
and mark `phase1-foundation.md` as superseded by the three-initiative
split. No scope change to Platform Bootstrap is needed.

### F-2. "Minimal reserved public endpoint" open question creates a scope-creep hinge — LOW

Section 6 open questions include: *"Does the first bootstrap path need a
minimal reserved public endpoint for later platform services, or is
cluster reachability plus network attachment sufficient for this
initiative?"*

If answered expansively, this could pull ingress controllers, DNS
ownership, or TLS provisioning into the bootstrap phase — all of which
Section 5 explicitly excludes. Section 3 "Base networking" already
constrains the answer correctly (*"a clear public-entry seam for later
ingress and access layers, without deploying those layers yet"*), but
the open question is phrased loosely enough that an implementer could
justify going further.

**Risk**: the open question is an implicit scope hinge. Answered wrong,
it silently absorbs work that belongs to GitOps Foundation or a later
platform-services initiative.

**Recommendation**: when resolved, constrain the answer to reserved
cloud-level primitives only (e.g., a static IP or load-balancer
reservation), not a deployed ingress path. Consider tightening the
question's wording to make that constraint explicit.

### F-3. Per-environment roots vs. first-environment-only delivery — LOW

Section 2 defines per-environment OpenTofu roots as in scope. Section 3
"Platform shape" narrows the immediate target to *"one reproducible
platform cluster in the first environment, with the layout designed so
the same pattern can be repeated for additional environments by changing
only the environment root and its variables."* Section 7 exit criteria
require *"each declared platform environment has its own OpenTofu root
and isolated remote-state boundary."*

There is a small ambiguity: does the initiative require multiple
per-environment roots declared up front, or only the first environment's
root with a module pattern designed for repetition? This matters because
GitOps Foundation's topology assumes `dev`, `staging`, and `production`
roots exist.

**Risk**: interpreted narrowly, Platform Bootstrap delivers one
environment root and leaves staging/production scaffolding to a later
phase. Interpreted broadly, it scaffolds all three — still proportionate
but doubles the surface area. The narrow reading is the cleaner
bootstrap framing; the broad reading crosses into topology work that
belongs in GitOps Foundation.

**Recommendation**: clarify "declared" in the exit criterion. The
recommended reading is "each environment that has been brought up has its
own root," not "all future environments must have pre-declared roots."

### F-4. DNS ownership boundary straddles bootstrap and later initiatives — LOW

Section 6 open questions include: *"Which DNS records, if any, must be
owned by the bootstrap layer rather than by later ingress or GitOps
work?"*

Section 3 "Base networking" correctly constrains the networking
deliverable to *"DNS and address management only where required to make
the bootstrap path reproducible."* However, the open question leaves
room for the bootstrap layer to claim DNS records that logically belong
to ingress, identity, or application-layer initiatives. DNS record
ownership is a common source of split-ownership drift when
infrastructure and platform-service layers share the same provider
account.

**Risk**: if bootstrap claims DNS records beyond what reproducibility
strictly requires (e.g., application-facing FQDNs, wildcard records for
ingress), it creates a management seam where some DNS is OpenTofu-owned
and some is Flux-owned, without a clear boundary. This is mitigated by
the proposal's own constraint in §3, which limits DNS to bootstrap
reproducibility.

**Recommendation**: when resolved, limit bootstrap-owned DNS to
records required for cluster API-server reachability and state-backend
access. All service-facing DNS should be deferred to the initiative
that owns the service.

---

## Assessment against criteria

### 1. Is this initiative appropriately narrow for the problem it claims to solve?

**Yes.** The claimed problem is "produce a reproducible platform cluster
substrate so that GitOps and child-cluster provisioning can start from a
known base." The in-scope items — Vultr VKE, Vultr VPC networking,
Vultr Object Storage for remote state, per-environment OpenTofu roots,
one reproducible bootstrap path — are exactly what that problem requires
and nothing more. The proposal correctly identifies scope creep as its
top risk (§6) and uses exit criteria (§7) as a stop-check against it.

The exit criteria are operationally substantive — concurrent-plan test,
state-restore exercise, credential-custody procedure — but proportionate
for foundation-layer infrastructure where a state corruption or lost
credential cascades to every initiative above.

### 2. Does it defer anything that should stay inside this initiative?

**No.** The two gaps identified in the prior assessment have been closed:

- Crossplane installation is now explicitly assigned to Application
  Cluster Provisioning as its day-zero prerequisite. Platform Bootstrap
  §3 and §5 both state this, and App Cluster Provisioning §2 and §3
  accept the assignment. The three proposals are now consistent.

- The handoff artifact is now specified in §3 and §7 with explicit
  precision: API server endpoint, kubeconfig or connection-secret
  storage path, retrieval access control, encryption-at-rest posture,
  and credential lifetime model. This matches the rigor of Application
  Cluster Provisioning's readiness contract.

Flux, secrets management, ingress, cert-manager, and all platform
services remain correctly deferred — none are required for "cluster
exists, is reachable, has remote state."

### 3. Does it pull later-phase work too early?

**No.** Every in-scope item is a prerequisite for any later initiative:

- Vultr VKE: the cluster must exist before anything reconciles into it.
- Vultr VPC: the cluster must be networked before ingress or identity
  can attach.
- Vultr Object Storage (for tfstate): remote state must exist before
  per-environment roots are trustworthy.
- Per-environment OpenTofu roots: environment isolation must exist
  before GitOps defines environment paths.
- Handoff contract: the next initiative needs a specified connection
  path, not an implicit assumption about cluster reachability.

No application services, no identity, no authorization, no ingress
controller, no secrets engine, no observability stack, no CI pipeline,
no self-hosted storage. The proposal holds the line. The open questions
in §6 (public endpoint, DNS ownership) are soft edges but the
proposal's own constraints in §3 and §5 bound them.

### 4. Are the boundaries with the other two Phase 1 initiatives proportionate and clear?

**Yes.**

- **Platform Bootstrap ↔ GitOps Foundation**: clean. Platform Bootstrap
  owns substrate and per-environment OpenTofu roots; GitOps Foundation
  owns repository layout (`base/`, `overlays/`, `clusters/<env>/...`),
  per-cluster Flux roots, and the promotion model. The seam is explicit
  and consistent across both proposals.

- **Platform Bootstrap ↔ Application Cluster Provisioning**: clean.
  Platform Bootstrap provisions the control/platform cluster and
  publishes a handoff contract. Application Cluster Provisioning
  installs Crossplane on that cluster as its own day-zero step and
  provisions child application clusters. The Crossplane installation
  seam that was ambiguous in the prior assessment is now resolved — all
  three proposals agree that App Cluster Provisioning owns the install.
  The two-tier model is preserved without overlap.

- **Proportionality**: the three initiatives carry roughly equivalent
  weight (substrate vs. topology vs. fleet provisioning). None subsumes
  the others. Platform Bootstrap is the smallest in scope, which is
  appropriate — substrate failures cascade further than topology or
  provisioning failures, so a tight scope reduces blast radius where it
  matters most.

---

## Recommendations summary

1. **F-1 (LOW)**: update `platform-decisions-overlay.md` to reflect the
   actual hosting decision; mark `phase1-foundation.md` as superseded if
   the three-initiative split is now authoritative.
2. **F-2 (LOW)**: when resolving the "minimal reserved public endpoint"
   open question, constrain the answer to cloud-level primitives only.
3. **F-3 (LOW)**: clarify "declared" in the exit criterion to avoid
   ambiguity between first-environment delivery and all-environment
   scaffolding.
4. **F-4 (LOW)**: when resolving the DNS ownership open question, limit
   bootstrap-owned DNS to cluster API-server and state-backend
   reachability. Defer all service-facing DNS to the initiative that
   owns the service.

No proposal revisions are required. All four findings are addressable
during implementation.
