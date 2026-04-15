# Shortcut risk assessment — Application Cluster Provisioning

**Proposal:** `plans/proposals/app-cluster-provisioning.md`
**Auditor:** Claude (automated shortcut risk assessment)
**Date:** 2026-04-14
**Overall verdict:** LOW

All four previously identified findings (two MEDIUM, two LOW) have been
adequately addressed by proposal revisions. No remaining finding rises
above LOW severity.

---

## Criterion 1 — Does the proposal replace one shortcut with another?

**Severity: LOW**

The previous MEDIUM finding was that Crossplane was adopted as the
cluster-fleet control plane without re-deriving the choice from the
current decision process — its only prior traceability was the legacy
base-application pattern that the proposal itself flags as cautionary.

The revised proposal resolves this with a direct architectural
justification in section 1:

> The alternative — driving application cluster lifecycle through
> OpenTofu — would either collapse the two-tier model (one OpenTofu root
> managing both tiers) or require an external orchestration layer to
> bridge OpenTofu applies into the control cluster's desired-state model.
> Crossplane keeps cluster provisioning inside Kubernetes, composable
> with Flux-reconciled Git state, and aligned with the per-cluster GitOps
> root model.

This is a substantive argument, not a legacy inheritance. The
justification identifies two concrete failure modes of the OpenTofu
alternative and explains why Crossplane avoids them. The proposal also
requires the choice to be recorded in `platform-decisions-overlay.md` as
a locked decision (section 1, exit criterion in section 7), bringing
Crossplane through the same ratification process as Flux, Buildkite,
and the auth stack.

The remaining narrow concern is that the comparison is scoped to
Crossplane-vs-OpenTofu and does not evaluate other Kubernetes-native
cluster-fleet mechanisms (e.g., Cluster API). This is LOW because the
OpenTofu comparison is the most architecturally relevant one given the
platform's existing tool surface, and the proposal's scope is fleet
provisioning from a control cluster, not a general cluster-management
abstraction study.

### Previous MEDIUM — Crossplane inherited from legacy: RESOLVED

The revised proposal justifies Crossplane on its own architectural
merits, names the OpenTofu alternative and its failure modes, and
requires overlay ratification. The shortcut-for-shortcut swap concern
is closed.

---

## Criterion 2 — Does it hide unresolved complexity behind vague deferrals?

**Severity: LOW**

The previous assessment rated this LOW with two sub-concerns: ambiguous
"managed-cluster path" vocabulary that obscured the hosting-decision
dependency, and floating ProviderConfig ownership between initiatives.
Both are resolved.

**Hosting-decision dependency — resolved.** The revised proposal
explicitly surfaces the complexity difference between provider paths in
section 6 (Open questions):

> Implementation complexity differs significantly between the Vultr path
> (managed VKE, first-party cluster API) and the Hetzner path
> (self-managed k3s, no managed-cluster API — composition would need a
> provider-terraform wrapper).

The first composition is gated on the hosting decision being locked.
This is honest about the dependency and does not smooth over the
complexity difference. Platform Bootstrap (`platform-bootstrap.md`)
requires locking Vultr as a gating exit criterion, so this dependency
has a clear resolution path.

**ProviderConfig ownership — resolved.** The revised proposal assigns
Crossplane installation ownership unambiguously to this initiative
(section 2: "This initiative owns the Crossplane installation because
Platform Bootstrap is scoped to substrate only"; section 3: "This
initiative owns the Crossplane installation baseline: core controller,
CRDs, provider package, and ProviderConfig bootstrap on the control
cluster"). The credential-path ambiguity is closed.

**Remaining open questions are bounded.** The three remaining open
questions (provider path, clusterClass values, node-pool override scope)
are genuine design decisions gated on locked inputs. None are vague
deferrals — each has a clear resolution trigger and bounded scope.

---

## Criterion 3 — Does it introduce temporary operator-only seams or duplicate control paths?

**Severity: LOW**

The previous MEDIUM finding had two sub-concerns: an unclear boundary
between two infrastructure control planes (OpenTofu and Crossplane),
and an unbounded operator-only claim-submission path. Both are resolved.

### Tool boundary — resolved

The revised proposal adds an explicit "Tool boundary: Crossplane and
OpenTofu" subsection in section 3 with a hard tier separation:

- **OpenTofu** owns cloud primitives at the platform substrate level:
  VPC networking, object storage, VKE cluster creation, and
  per-environment state isolation.
- **Crossplane** owns downstream application-cluster lifecycle from
  within the control cluster: cluster provisioning, node-pool
  attachment, and connection-secret publication for child clusters only.

The proposal adds a concrete anti-overlap rule:

> Crossplane compositions must not reproduce cloud primitives that
> OpenTofu already manages in the platform tier (VPCs, shared
> networking, state storage). If a cloud resource is owned by a Platform
> Bootstrap OpenTofu root, Crossplane references it by ID or imports it
> as a data source — it does not recreate it.

This is the tool-overlap clause the previous assessment recommended. The
boundary is defined by tier (platform substrate vs downstream cluster
lifecycle), not by resource type, which is the right level of
abstraction. The reference-by-ID-not-recreate rule provides a concrete
enforcement mechanism.

### Operator-only claim path — resolved

The revised proposal bounds the operator-only submission seam in
section 3 ("Claim submission seam"):

> Manual kubectl apply of claims is acceptable only as a bootstrap-only
> seam; the first accepted implementation must land in coordination with
> GitOps Foundation so that the GitOps submission path replaces the
> operator-only path promptly.

This directly implements the previous recommendation to bound the
operator path and coordinate with GitOps Foundation. The "bootstrap-only"
designation with GitOps coordination is a clear time-bound: the operator
path is a transient bootstrap mechanism, not a durable submission
channel.

The remaining narrow concern is that "promptly" is not a hard deadline.
This is LOW because the coordination requirement with GitOps Foundation
creates cross-initiative accountability, and the GitOps Foundation
proposal (section 3, "Interfaces to adjacent initiatives") already
defines the topology slot for Crossplane cluster claims under the
control-cluster root. Both initiatives agree on the handoff, so the
seam has a clear owner on each side.

### Previous MEDIUM — Two control planes without clear boundary: RESOLVED

The revised proposal defines a hard tier boundary between OpenTofu and
Crossplane with an explicit anti-overlap rule and reference-by-ID
mechanism.

### Previous MEDIUM — Unbounded operator-only claim path: RESOLVED

The revised proposal bounds the operator path to bootstrap-only and
requires coordination with GitOps Foundation for the GitOps submission
path.

---

## Criterion 4 — Does it compromise the two-tier model or other locked decisions?

**Severity: LOW**

The previous assessment rated this LOW with one narrow concern:
Crossplane adoption bypassed the decision-overlay process. The revised
proposal resolves this by requiring Crossplane to be recorded as a
locked decision in `platform-decisions-overlay.md` (section 1, exit
criterion in section 7).

The proposal continues to actively preserve the two-tier model:

- The control cluster is not created by the Crossplane claims it hosts
  (section 3, "Control-plane boundary").
- Application clusters are the only resources this initiative provisions
  (section 3).
- Flux installation into downstream clusters is explicitly out of scope
  (section 5).
- Application deployment is explicitly out of scope (section 5).

Cross-referencing against `platform-decisions-overlay.md`:

| Locked decision | Proposal alignment |
| --- | --- |
| Authentik (human identity) | Explicitly out of scope; no conflict |
| OPAL/Cedar (authorization) | Explicitly out of scope; no conflict |
| Pomerium (access proxy) | Explicitly out of scope; no conflict |
| Buildkite (CI/CD direction) | Not addressed by this initiative; no conflict |
| Flux CD (reconciler) | Preserved — Flux-as-sole-reconciler boundary respected; downstream Flux installation deferred to GitOps Foundation |
| Two-tier model | Preserved — control cluster is upstream, not self-provisioned |
| Provider-native object storage | Not in scope; no conflict |

The proposal also correctly coordinates with the GitOps Foundation
topology slot for cluster claims (section 3, "Claim submission seam"),
matching the GitOps Foundation proposal's interface definition for
Crossplane claims under the control-cluster root.

---

## Summary table

| Criterion | Finding | Severity |
| --- | --- | --- |
| Shortcut-for-shortcut swap | Crossplane justified against OpenTofu alternative; overlay ratification required | LOW |
| Hidden complexity in deferrals | Hosting dependency surfaced; ProviderConfig ownership pinned; open questions bounded | LOW |
| Duplicate control paths / operator-only seams | Tool boundary explicit with anti-overlap rule; operator path bootstrap-only with GitOps coordination | LOW |
| Compromise of locked decisions | Two-tier model preserved; Crossplane enters overlay process | LOW |
| **Overall** | | **LOW** |

| Previous MEDIUM | Status |
| --- | --- |
| Crossplane inherited from legacy without justification | Resolved — justified against OpenTofu alternative with concrete architectural argument; overlay ratification is exit-gated |
| Two infrastructure control planes without clear boundary | Resolved — explicit tier boundary with anti-overlap rule and reference-by-ID mechanism |
| Unbounded operator-only claim path | Resolved — bounded to bootstrap-only with GitOps Foundation coordination requirement |

---

## Recommendations

1. **Crossplane overlay entry (housekeeping):** When the proposal is
   accepted, ensure the `platform-decisions-overlay.md` entry for
   Crossplane includes the justification against the OpenTofu-driven
   alternative, not just the selection. The exit criteria already gate
   this; treat it as a proposal-acceptance deliverable.

2. **Tool boundary enforcement during implementation:** The anti-overlap
   rule ("Crossplane references by ID, does not recreate") should be
   validated in code review for every composition. Consider a
   composition-review checklist item that asks: "Does this composition
   create any resource that an OpenTofu root already manages?"

3. **GitOps coordination timing:** The "promptly" language for replacing
   the operator-only claim path is adequate at the proposal level. During
   implementation planning, convert this to a concrete coordination
   milestone with GitOps Foundation — e.g., "operator-only path is
   replaced before the second application cluster is provisioned."

4. **Cluster API as a future reference point:** The Crossplane-vs-OpenTofu
   comparison is the right scope for this proposal. If the platform later
   considers multi-provider fleet management or upstream Kubernetes
   cluster lifecycle standards, Cluster API should enter the comparison
   at that point. This is not a current gap — it is a future evaluation
   trigger.
