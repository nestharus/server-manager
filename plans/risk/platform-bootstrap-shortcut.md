# Shortcut risk assessment — Platform Bootstrap

**Proposal:** `plans/proposals/platform-bootstrap.md`
**Date:** 2026-04-14
**Overall verdict:** LOW

---

## Criterion 1 — Does the proposal replace one shortcut with another?

**Severity: LOW**

The proposal replaces the Hetzner / self-managed k3s / kube-hetzner
substrate from `phase1-foundation.md` with Vultr VKE managed Kubernetes.
This is a substrate swap, but it is not a shortcut-for-shortcut trade.

1. **The swap is research-driven.** `plans/research/hetzner-vs-vultr.md`
   recommends Vultr as the stronger platform host. The decisive factors
   are managed control plane (eliminates self-managed etcd, upgrade, and
   recovery burden), stronger private-networking surface, broader managed
   service coverage, and a cleaner OpenTofu provider story for managed
   Kubernetes resources. The research also flags VKE/VPC attachment
   ambiguity as a concrete diligence item — a bounded unknown, not an
   equivalent substitute shortcut.

2. **The new path is operationally simpler, not merely different.**
   Self-managed k3s via kube-hetzner required the team to own
   control-plane lifecycle, etcd backup, Packer-based bootstrap, and
   volume-backup gaps from day one. Managed VKE offloads the control
   plane to the provider. The bootstrap seam shrinks: OpenTofu owns
   the VKE cluster lifecycle through the first-party Vultr provider
   without an intermediate module layer like kube-hetzner.

3. **The supersession path is explicit and gated.** Section 1 states
   "This initiative supersedes the substrate direction of the earlier
   `phase1-foundation.md`." The exit criteria require updating
   `platform-decisions-overlay.md` to lock Vultr as the hosting
   decision, citing the provider comparison research, and marking
   `phase1-foundation.md` as superseded. This is a procedural gate, not
   an assumed outcome.

4. **VKE/VPC ambiguity is gated, not hidden.** Section 6 flags VPC
   terminology ambiguity as a risk. The exit criteria require VKE/VPC
   attachment verification on a throwaway cluster before the
   per-environment network topology is committed. The initiative cannot
   close without verified behavior.

No shortcut-for-shortcut swap is present. The substrate change is
research-backed, operationally simpler, and procedurally gated.

---

## Criterion 2 — Does it hide unresolved complexity behind vague deferrals?

**Severity: LOW**

The proposal's deferrals are explicit, bounded, and map to named
successor initiatives or to legitimate implementation-time design
decisions.

### Named deferrals to successor initiatives

| Deferred concern | Owner | Boundary |
| --- | --- | --- |
| Flux CD install, GitOps topology | `gitops-foundation.md` | Handoff contract specifies endpoint, kubeconfig path, access control, encryption posture, credential lifetime |
| Crossplane, cluster-fleet provisioning | `app-cluster-provisioning.md` | Crossplane install is app-cluster-provisioning's day-zero prerequisite; both proposals agree on the boundary |
| Identity, authorization, access proxy | Later initiatives | Correctly out of scope; no hidden dependency |
| CI/CD pipeline design | Later initiatives | Correctly out of scope; initiative is pre-CI |
| Self-hosted object storage | Later initiatives | Provider-native S3 is the locked first path |

Each deferral points to a named initiative with a defined handoff seam.
None are open-ended "we'll figure it out later" statements.

### Open questions in section 6

1. **Which environment first** — legitimate implementation-sequencing
   decision. Does not affect architecture.

2. **Region and node-pool baseline** — sizing decision appropriate for
   implementation. The proposal defines the structural requirements
   (minimal, control-oriented, explicitly defined worker pools).

3. **State isolation model** (separate instances, buckets, or
   prefix-plus-policy) — the most substantive open item. The answer
   affects the strength of per-environment state isolation. However,
   the exit criteria gate on the result: "each declared platform
   environment has its own OpenTofu root and isolated remote-state
   boundary." The implementation must deliver isolation; only the
   mechanism is deferred. Appropriate at proposal stage.

4. **DNS ownership** — correctly identified boundary question. The exit
   criteria do not depend on DNS beyond what the bootstrap path itself
   requires.

5. **Reserved public endpoint** — boundary question between bootstrap
   and later ingress work. The proposal correctly stops at network
   attachment and cluster reachability.

### State-locking mechanism

The most technically interesting deferral is the state-locking
mechanism. Vultr Object Storage is S3-compatible but Vultr does not
offer a DynamoDB-equivalent service. The proposal does not prescribe
the specific locking mechanism but gates on the result: working lock
acquisition demonstrated by an intentional concurrent-plan test, object
versioning, and an exercised state-restore procedure. The complexity is
real but honestly surfaced, and the exit criteria prevent the initiative
from closing without a working solution.

No hidden complexity or vague deferrals found. All open items are either
gated by exit criteria or are legitimate implementation-time decisions
that do not affect architectural direction.

---

## Criterion 3 — Does it introduce temporary operator-only seams or duplicate control paths?

**Severity: LOW**

### No duplicate control paths

OpenTofu is the single infrastructure control path for this initiative.
No competing mutation path exists. Per-environment roots with
per-environment remote state enforce isolation by design — a plan or
apply for one environment cannot implicitly affect another environment's
cluster or state.

### Operator-only access is transitional, not a workaround

The cluster is operator-accessible-only at end-of-bootstrap because
Flux does not exist yet. This is inherent to the initiative's defined
stopping point, not a parallel control path. The proposal explicitly
defines the handoff seam where GitOps Foundation installs Flux and
takes over in-cluster reconciliation.

This transitional state does not risk calcification because:

- The handoff contract is precise (API endpoint, kubeconfig storage
  path, access control, encryption posture, credential lifetime),
  giving GitOps Foundation a concrete integration target.
- The repository layout stability requirement in the exit criteria
  ensures the GitOps initiative has a stable target for Flux root
  placement.
- No operator-driven in-cluster mutation pattern is established that
  would compete with later Flux reconciliation.

### Bootstrap execution is standard, not a seam

The bootstrap path itself requires operator execution (running
`tofu apply`). This is the standard infrastructure-as-code bootstrap
pattern, not a workaround or a seam that will calcify. The exit
criteria require that this path is reproducible without hidden manual
steps.

No temporary operator-only seams or duplicate control paths are
introduced.

---

## Criterion 4 — Does it compromise the two-tier model or other locked decisions for convenience?

**Severity: LOW**

### Locked-decision alignment

| Decision | Status | Notes |
| --- | --- | --- |
| Two-tier model | Preserved | "platform clusters are provisioned here; separate application clusters remain a later initiative." The proposal explicitly refuses to collapse control and workload planes or pre-provision the later cluster fleet. |
| Git as desired state | Preserved | Acknowledged as locked; deferred to GitOps Foundation with defined handoff seam. |
| Flux CD as reconciler | Preserved | Acknowledged as locked; initiative stops before GitOps bootstrap. No competing reconciler introduced. |
| Provider-native S3 before self-hosted | Honored | Vultr Object Storage is the first-path choice. SeaweedFS, MinIO, and Ceph are explicitly out of scope. |
| Auth stack (Authentik, OPAL/Cedar, Pomerium) | Correctly deferred | Listed in section 5 exclusions. No auth-adjacent shortcuts. |
| Buildkite as CI direction | Correctly deferred | Listed in section 5 exclusions. Initiative is pre-CI. |
| Crossplane for cluster fleet | Correctly deferred | Explicitly excluded. Application Cluster Provisioning owns the Crossplane install as its day-zero prerequisite. Both proposals agree. |

### Hosting ratification is properly gated

The overlay currently lists "Hosting decision: Hetzner vs Vultr" as
still open, while this proposal commits to Vultr. This is not a
compromise of a locked decision — it is the ratification of an
unformalized decision that the research supports. The proposal handles
this correctly: the exit criteria require updating
`platform-decisions-overlay.md` to lock Vultr, citing the provider
comparison research. The ratification is procedurally gated, not
assumed.

### No architectural convenience compromises

The proposal does not collapse the two-tier model for bootstrap
simplicity. It does not introduce a competing reconciler to speed up
initial cluster configuration. It does not pull Crossplane into
bootstrap scope to avoid a handoff seam. It does not substitute
provider-console manual steps for OpenTofu automation. Each of these
would be a natural convenience temptation for a bootstrap initiative,
and each is explicitly rejected.

---

## Findings

### F-1. State isolation mechanism is open but exit-gated — LOW

Open question 3 leaves the choice between separate object-storage
instances, separate buckets, or prefix-plus-policy within the same
provider account fully open. The answer affects security boundary
strength. However, the exit criteria gate on the result ("each declared
platform environment has its own OpenTofu root and isolated remote-state
boundary"), preventing the initiative from shipping with inadequate
isolation. The mechanism decision is appropriate for implementation
planning.

**Recommendation:** Resolve to at least separate buckets per environment
during implementation planning. Prefix-plus-policy within a shared
bucket creates a weaker isolation boundary that could allow
misconfigured IAM to cross environment boundaries.

### F-2. Handoff seam precision could be tighter — LOW

The handoff to GitOps Foundation is described as "the repository layout
is stable enough for a later Flux bootstrap initiative to attach
cleanly" (section 3). The handoff contract itself is precise (API
endpoint, kubeconfig path, access control, encryption posture, credential
lifetime), but the repository-layout stability criterion is qualitative.
`gitops-foundation.md` specifies the concrete layout
(`base/ → overlays/ → clusters/<env>/...`), but Platform Bootstrap does
not reference that layout or commit to compatibility with it.

This is a missed precision opportunity, not hidden complexity. The
bootstrap initiative does not need to implement the GitOps layout, but
it could name the expected repository structure from the sibling
proposal as the target its layout must not conflict with.

**Recommendation:** During implementation, verify that the repository
structure created by Platform Bootstrap is compatible with the
`base/overlays/clusters` topology defined in `gitops-foundation.md`.
This is a coordination item, not a proposal revision.

---

## Summary

| Criterion | Severity |
| --- | --- |
| Shortcut-for-shortcut swap | LOW |
| Hidden complexity behind deferrals | LOW |
| Operator-only seams / duplicate control paths | LOW |
| Compromise of two-tier or locked decisions | LOW |
| **Overall** | **LOW** |

The proposal does not replace one shortcut with another: the
Hetzner/k3s-to-Vultr/VKE substrate swap is research-driven, reduces
operational burden, and is procedurally gated through overlay
ratification and predecessor supersession. Deferrals are explicit,
bounded, and map to named successor initiatives with defined handoff
contracts. No operator-only seams or duplicate control paths are
introduced — the post-bootstrap operator-only access is a transitional
state between initiatives with a precise handoff contract. No locked
decisions are compromised; the two-tier model, Flux reconciler
direction, provider-native S3 preference, and auth stack decisions are
all preserved or correctly deferred.

The two findings are coordination-level items addressable during
implementation without proposal changes.
