# Phase 1 Foundation — Risk Audit

Date: 2026-04-14

## Overall verdict: MEDIUM

The proposal is architecturally sound, tightly scoped, and consistent with
locked platform decisions. No HIGH-severity findings. Several MEDIUM findings
relate to a premature hosting commitment and operational gaps that, if left
unaddressed during implementation, would leave the foundation layer fragile
in ways that later phases inherit.

---

## Findings

### F-1. Foundation built on an unlocked hosting decision against research recommendation

**Severity: MEDIUM**

The platform-decisions-overlay explicitly lists the hosting decision as "still
open." The Hetzner-vs-Vultr research recommends Vultr for this platform's
shape. The OpenTofu-providers research confirms Vultr has cleaner first-party
provider coverage (managed Kubernetes, object storage, managed databases all
in-provider). The self-hosted-S3 research recommends managed provider storage
with Vultr as the stronger primary bucket.

The proposal commits the entire Phase 1 foundation to Hetzner: kube-hetzner
for Kubernetes, Hetzner Object Storage for S3, Hetzner networking and load
balancing for ingress, and hcloud as the primary OpenTofu provider. If the
hosting decision is later resolved to Vultr, essentially all Phase 1 work
requires rework:

- different Kubernetes path (VKE vs kube-hetzner / k3s)
- different OpenTofu provider surface (vultr vs hcloud + secondary providers)
- different object-storage provisioning (first-party vs MinIO provider shim)
- different networking model (managed VPC vs self-managed private networks)
- different operational burden profile (managed control plane vs self-managed)

This is not a conflict with a locked decision — the proposal may be the
document that locks the choice. But building an entire phase on an explicitly
unlocked decision without first ratifying that decision is the single largest
rework risk in this proposal.

**Recommendation:** Ratify the Hetzner hosting decision as a locked platform
decision before Phase 1 implementation begins. If the team is not ready to
lock Hetzner, Phase 1 should not proceed — the rework cost of reversing this
after implementation is nearly total. The ratification should explicitly
acknowledge the research recommendation for Vultr and document the reasons
for choosing Hetzner despite that recommendation.

---

### F-2. Age key custody and rotation are unspecified

**Severity: MEDIUM**

The proposal selects SOPS + age as the GitOps-native secrets path and
correctly identifies secrets bootstrap as "a high-leverage failure point." But
it does not specify:

- where the age private key is stored outside git
- who holds the key and under what access controls
- whether a backup copy exists and where
- whether or how the key is rotated

If the age private key is lost, every encrypted secret in the git history
becomes unrecoverable. If it is compromised, every secret in the repo is
exposed. This is the single highest-leverage operational gap in the proposal.

**Recommendation:** Define a key custody procedure as a Phase 1 exit
criterion. At minimum: where the key is stored, who can access it, and how
the key is backed up. Rotation strategy can follow in a later phase, but
custody cannot wait.

---

### F-3. Hetzner firewall limitations leave LB and private traffic unprotected at the cloud layer

**Severity: MEDIUM**

The Hetzner research establishes that Hetzner firewalls cannot protect
private-network traffic and cannot be attached to load balancers. The proposal
does not address this.

In practice, this means:

- traffic between nodes on the Hetzner private network has no cloud-layer
  firewall enforcement
- traffic arriving through the Hetzner load balancer to Kong has no cloud-layer
  firewall in front of the LB itself

This does not make the platform insecure by default — Kubernetes NetworkPolicy
and application-layer controls can compensate — but it means the cloud
perimeter is thinner than teams accustomed to VPC security groups may expect.

**Recommendation:** Acknowledge this limitation in the Phase 1 architecture
documentation. Ensure Kubernetes NetworkPolicy or a CNI-level equivalent is
part of the baseline cluster state that Flux reconciles, even if policies are
initially permissive. Do not rely on Hetzner firewalls for east-west or
LB-to-cluster protection.

---

### F-4. No minimum observability in exit criteria

**Severity: MEDIUM**

The proposal explicitly defers "broad observability" and scopes Phase 1
to foundation bootstrap only. However, the exit criteria do not require any
health visibility into the foundation itself — no cluster health monitoring,
no node alerting, no Flux reconciliation failure notifications, and no Kong
ingress error visibility.

A foundation layer with no visibility into its own health is operationally
fragile. If k3s degrades, a node goes unresponsive, Flux stops reconciling,
or Kong starts returning errors, the team has no signal until something
downstream breaks visibly.

**Recommendation:** Add a minimal observability requirement to the exit
criteria. This does not need to be a full monitoring stack. It can be as
narrow as: kube-state-metrics or equivalent for cluster health, Flux
notification controller for reconciliation failures, and basic Kong error
logging. The goal is "the foundation can tell you when it is unhealthy,"
not "full observability platform."

---

### F-5. etcd backup not explicitly required in exit criteria

**Severity: MEDIUM**

The kube-hetzner research notes that the module supports etcd S3 backups, and
the proposal provisions Hetzner Object Storage with S3-compatible credentials.
But the Phase 1 exit criteria do not require etcd backups to be configured and
validated.

etcd is the cluster state store. Without backups, a control-plane failure
means rebuilding the cluster from scratch, including re-bootstrapping Flux,
secrets, Kong, and all baseline state. The research calls out that the team
owns "cluster lifecycle, upgrades, and recovery from day 1."

**Recommendation:** Add "etcd backups are configured, writing to the
provisioned object storage, and a restore has been validated at least once" to
the exit criteria. The kube-hetzner module already supports this; it just
needs to be required, not optional.

---

### F-6. Hetzner volume backup gap inherited by all stateful workloads

**Severity: MEDIUM**

The Hetzner research explicitly states that Hetzner does not provide snapshots
or backups for volumes, and that server backups and snapshots exclude attached
volumes. The proposal does not address this.

Phase 1 itself may not deploy stateful application workloads, but the
foundation it creates is the substrate all later phases build on. Any later
phase that deploys stateful services (Postgres, Authentik, platform databases)
onto this cluster inherits the volume backup gap unless the foundation phase
establishes a volume-level backup strategy or at least documents the
constraint.

**Recommendation:** Document in Phase 1 exit criteria or architecture docs
that Hetzner provides no volume-level backup or snapshot capability. Identify
whether the team plans to address this in Phase 1 (e.g., Velero or similar)
or explicitly defer it with a documented acceptance of the gap.

---

### F-7. kube-hetzner bootstrap seam may undermine reproducibility claim

**Severity: LOW**

The proposal's exit criteria require that "the foundation can be rebuilt
without relying on undocumented manual changes." The kube-hetzner path
includes a Packer image build step (MicroOS snapshot creation) that runs
before `tofu apply`. This step requires local tooling (`packer`, `kubectl`,
`hcloud` CLI) and is outside the pure OpenTofu CRUD graph.

If this bootstrap seam is not treated as part of the documented, automated
rebuild path, the reproducibility claim is weakened. The proposal
acknowledges this risk in section 6 ("if that seam is not treated as part
of the official bootstrap, the platform will drift into undocumented setup").

**Recommendation:** Ensure the Packer/MicroOS image build step is scripted,
version-controlled, and documented as an explicit prerequisite in the rebuild
procedure. Consider automating it via Buildkite or a Makefile target so it
is not a manual local-machine-only step.

---

### F-8. TLS termination strategy for Kong ingress is unspecified

**Severity: LOW**

The exit criteria require Kong to serve as the baseline ingress layer and to
validate traffic from public entry to in-cluster services. They do not mention
TLS. A production-capable ingress path serving public traffic without TLS is
not production-ready.

This is likely an implementation detail that will be addressed, but because
the proposal frames Phase 1 as "production-capable platform foundation," the
gap is worth noting.

**Recommendation:** Specify the TLS termination strategy (cert-manager with
Let's Encrypt, Hetzner managed certificates on the LB, or manual certificate
provisioning through SOPS) as part of the Kong ingress exit criteria.

---

### F-9. Hetzner Object Storage is EU-only and single-DC-per-bucket

**Severity: LOW**

The research establishes that Hetzner Object Storage is available only in
fsn1, nbg1, and hel1, and each bucket is stored within a single data center.
The proposal acknowledges that offsite copy strategy is later work.

This is acceptable for Phase 1 bootstrap use cases (etcd backups, bootstrap
artifacts, credential-managed buckets). It becomes a real risk only if later
phases treat these buckets as the sole copy of critical data without adding
offsite replication.

**Recommendation:** No action required in Phase 1, but document that Hetzner
Object Storage is not a DR solution and later phases must add offsite copy
before storing irreplaceable data.

---

### F-10. Kubernetes NetworkPolicy not mentioned

**Severity: LOW**

The baseline cluster state reconciled by Flux does not mention
NetworkPolicy. Combined with F-3 (Hetzner firewall limitations), the cluster
would default to fully open pod-to-pod communication. This is acceptable for
a bootstrap phase with no application workloads, but it means Phase 2 must
add network segmentation before deploying identity, authorization, or
application services.

**Recommendation:** No action required in Phase 1 if the exit criteria
explicitly note that NetworkPolicy is deferred. If Phase 1 delivers any
services beyond pure infrastructure (e.g., Kong with admin API), consider
a baseline deny-all policy with explicit allows.

---

### F-11. Object-storage bucket provisioning crosses a provider boundary

**Severity: LOW**

The research confirms that Hetzner Object Storage is not managed by the
`hcloud` provider and requires a secondary provider path (MinIO Terraform
provider) for bucket automation. The proposal acknowledges this and accepts
it.

This is operationally safe but adds one automation seam. The risk is that
bucket provisioning drifts out of the main OpenTofu graph into ad-hoc
scripts if not handled carefully.

**Recommendation:** Ensure bucket provisioning is part of the same OpenTofu
configuration (even if via a secondary provider), not a separate manual step.

---

## Summary table

| ID   | Finding                                              | Severity |
| ---- | ---------------------------------------------------- | -------- |
| F-1  | Foundation built on unlocked hosting decision        | MEDIUM   |
| F-2  | Age key custody and rotation unspecified              | MEDIUM   |
| F-3  | Hetzner firewall gaps on LB and private traffic      | MEDIUM   |
| F-4  | No minimum observability in exit criteria            | MEDIUM   |
| F-5  | etcd backup not required in exit criteria            | MEDIUM   |
| F-6  | Hetzner volume backup gap for stateful workloads     | MEDIUM   |
| F-7  | kube-hetzner bootstrap seam vs reproducibility claim | LOW      |
| F-8  | TLS termination strategy unspecified                 | LOW      |
| F-9  | Hetzner Object Storage EU-only, single-DC            | LOW      |
| F-10 | Kubernetes NetworkPolicy not mentioned               | LOW      |
| F-11 | Object-storage bucket automation crosses provider    | LOW      |

## Locked-decision alignment

No conflicts found with ratified locked decisions. The proposal is consistent
with all locked decisions in the platform-decisions-overlay:

- Authentik, OPAL/Cedar, Pomerium: correctly deferred
- Smallstep: correctly deferred as conditional
- Buildkite: correctly scoped to CI only, not deployment
- Flux CD: correctly installed as sole reconciler
- Provider-native object storage: correctly preferred over self-hosted
- SeaweedFS: correctly deferred as fallback only

The hosting decision (F-1) is not a conflict with a locked decision — it is
a conflict with an explicitly open decision. The proposal assumes a resolution
that contradicts the research recommendation. This must be ratified before
implementation, not discovered after.
