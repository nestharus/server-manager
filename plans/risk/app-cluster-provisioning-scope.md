# Scope risk — Application Cluster Provisioning

## Overall verdict: LOW

The initiative is internally well-scoped and the three cross-initiative
boundary gaps identified in the prior MEDIUM assessment have all been
resolved in the revised proposals. The Crossplane install seam is now
explicitly owned by this initiative as a day-zero step. GitOps
Foundation reciprocates the claim-placement and downstream Flux bootstrap
contract. The first composition is explicitly gated on the hosting
decision lock. The OpenTofu/Crossplane tool boundary is clearly defined.
No scope creep, inappropriate deferral, or premature pull of later-phase
work is observed.

## Prior MEDIUM findings — resolution status

### Prior Finding 2 — Crossplane install seam (was MEDIUM, now RESOLVED)

The prior assessment found that neither this initiative nor Platform
Bootstrap owned the Crossplane core install on the control cluster.

**Resolution:** The revised proposal explicitly claims Crossplane
installation as a day-zero in-scope step (§2: "Install Crossplane core,
the required provider package, and baseline ProviderConfig on the
control cluster as a day-zero prerequisite"). The rationale is stated
clearly: "Platform Bootstrap is scoped to substrate only and explicitly
excludes cluster-fleet management logic." Platform Bootstrap reciprocates
by stating in §3: "Crossplane installation is explicitly outside this
initiative's boundary; Application Cluster Provisioning owns the
Crossplane core install as its own day-zero prerequisite" and listing it
in §5 out-of-scope with the parenthetical ownership attribution. The
exit criteria (§7) include the Crossplane install as a deliverable. Both
sides of the seam now agree.

### Prior Finding 3 — One-sided claim-path with GitOps Foundation (was MEDIUM, now RESOLVED)

The prior assessment found that GitOps Foundation did not mention
Crossplane claims, claim manifest placement, or the per-cluster Flux
bootstrap step onto newly provisioned downstream clusters.

**Resolution:** GitOps Foundation §3 "Interfaces to adjacent
initiatives" now includes an explicit reciprocal clause: "Crossplane
ClusterClaim resources for application cluster provisioning land under
the control-cluster root in the appropriate environment path (e.g.,
clusters/<env>/control-cluster/). When Application Cluster Provisioning
creates a new downstream cluster, the per-cluster Flux root for that
cluster is bootstrapped into the clusters/<env>/app-cluster/ path
following the same per-cluster root model defined above." GitOps
Foundation §7 exit criteria also include: "a defined topology slot exists
for Crossplane cluster claims under the control-cluster root, and a
defined bootstrap path exists for wiring per-cluster Flux roots onto
newly provisioned downstream clusters." The seam is now bilateral with
matching commitments on both sides.

### Prior Finding 4 — Hosting lock unresolved upstream (was MEDIUM, now RESOLVED)

The prior assessment found that the hosting decision remained open and
the proposal did not state an explicit sequencing gate.

**Resolution:** The revised proposal §6 risks now explicitly states:
"The first accepted composition cannot land until the hosting decision is
locked in platform-decisions-overlay.md." The composition strategy (§3)
reinforces this: "If the platform locks Vultr, the first composition
targets Vultr. If it locks Hetzner, the first composition targets
Hetzner." Platform Bootstrap proposes locking Vultr VKE and requires
updating the overlay as an acceptance condition. While
platform-decisions-overlay.md still lists hosting as open, the gating
dependency is now explicit in the proposal text and prevents accidental
parallel work on the wrong provider composition.

## Findings

### Finding 1 — Initiative is appropriately narrow (LOW, positive)

The initiative solves exactly one problem: provision downstream
application clusters from an existing control cluster via Crossplane and
publish a readiness/connection contract. The claim surface is limited to
one composite type and one namespaced claim type. The resource model (§3)
explicitly warns against pseudo-DSL fields and cites the legacy
base-application schema as the cautionary case. The out-of-scope list
(§5) covers sixteen distinct exclusions spanning Flux installation on
child clusters, application deployment, CI/CD, eventing infrastructure,
preview environments, TTL cleanup, tenant models, and product-surface
concerns.

### Finding 2 — No inappropriate deferral of in-scope work (LOW, positive)

All load-bearing concerns are retained inside the initiative:

- Crossplane core install, provider package, and ProviderConfig
  bootstrap are day-zero in-scope deliverables
- Connection-secret and kubeconfig publication contract is in scope (§3
  handoff contract)
- Lifecycle contract for create, update, and delete is in scope (§2, §7)
- Readiness and failure condition semantics are in scope (§4, §7)
- RBAC controls on claim authoring and connection-secret access are in
  scope (§2, §6)
- Deletion policy with production-class protection is in scope (§6, §7)
- Credential rotation/revocation path is in scope (§7)

No work that belongs inside this initiative has been pushed to a sibling.

### Finding 3 — No premature pull of later-phase work (LOW, positive)

The proposal explicitly excludes installing Flux on child clusters,
deploying applications or runtime services, CI/CD orchestration, release
promotion, eventing infrastructure (Kafka/Debezium/Redis), dynamic
preview environments, TTL cleanup, tenant models, and product-surface
concerns. It also rejects collapsing back into Platform Bootstrap or
GitOps Foundation. No forward-pulling of later-phase scope is observed.

### Finding 4 — Boundaries with siblings are proportionate and clear (LOW)

The three-way split is architecturally clean with matching commitments:

- **Platform Bootstrap boundary:** Platform Bootstrap owns the control
  cluster substrate and explicitly excludes Crossplane. This initiative
  begins where a stable control cluster exists and installs Crossplane as
  its own day-zero step. The handoff is unambiguous.
- **GitOps Foundation boundary:** GitOps Foundation owns where cluster
  claims live in Git (under the control-cluster root), how they are
  reconciled, and how per-cluster Flux roots are bootstrapped onto newly
  provisioned downstream clusters. This initiative owns what the claim
  means once it exists and what infrastructure outputs it publishes. Both
  proposals now state matching claims.
- **Tool boundary:** OpenTofu owns cloud primitives at the platform
  substrate level. Crossplane owns downstream application-cluster
  lifecycle from within the control cluster. The boundary rule is
  explicit: Crossplane compositions must not reproduce cloud primitives
  that OpenTofu already manages (§3).

### Finding 5 — Exit criteria are comprehensive and testable (LOW, positive)

The exit criteria (§7) include fifteen specific conditions covering
Crossplane installation, decision recording, claim surface validation,
per-field composition testing, connection-secret RBAC, deletion policy,
claim-authoring RBAC, failure conditions, lifecycle documentation, and
handoff contract documentation. Each criterion is verifiable without
subjective judgment.

## Recommendations

1. **No proposal changes required.** All prior MEDIUM findings have been
   resolved through explicit revisions to the proposal text and
   reciprocal commitments in sibling proposals.

2. **Preserve the hosting-lock gate during implementation.** The
   explicit gating of the first composition on the hosting decision is
   the right sequencing discipline. Implementation planning should
   respect this gate and not begin provider-specific composition work
   until Platform Bootstrap's acceptance locks the overlay.

3. **Default open question 3 (node-pool overrides) to class-driven.**
   The proposal argues for an honest claim contract where fields match
   composition behavior. Defaulting the first version to class-driven
   worker topology with no per-claim node-pool override would lock in
   that stance and remove a foreseeable scope-creep vector. This is
   addressable during implementation without proposal changes.
