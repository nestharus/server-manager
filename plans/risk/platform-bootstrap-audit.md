# Risk Audit — Platform Bootstrap

**Proposal:** `plans/proposals/platform-bootstrap.md`
**Auditor:** Claude (automated risk audit)
**Date:** 2026-04-14
**Overall verdict:** LOW

All five previously identified MEDIUM findings (state locking, credential
custody, hosting ratification, Crossplane ownership, kubeconfig handoff)
have been adequately addressed with concrete exit criteria. No remaining
finding rises above LOW severity.

---

## Criterion 1 — Security, correctness, reliability, or data-integrity risk

### F-1. State-locking mechanism requires design resolution at implementation time — LOW

The proposal mandates working lock acquisition as a first-class exit
criterion, demonstrated by an intentional concurrent-plan test. It also
requires object versioning and an exercised state-restore procedure.
These exit criteria are strong.

The practical gap is that Vultr Object Storage is S3-compatible but Vultr
does not offer a DynamoDB-equivalent service. OpenTofu's S3 backend
historically relies on DynamoDB for state locking. The proposal does not
prescribe the specific locking mechanism, which means the implementation
team will need to evaluate alternatives — for example, a consul-based
lock, a PostgreSQL-backed backend, an HTTP backend with locking support,
or conditional-write support in Vultr's S3 implementation.

This is LOW because the exit criterion is gating: if locking does not
work, the initiative cannot close. The implementation team should expect
this as a known design-decision point rather than an assumed default.

### F-2. Vultr API token rotation path not exit-gated — LOW

The credential-custody exit criteria are thorough: storage location,
access-control boundary, backup procedure, and per-environment scoping
are all required deliverables. The handoff contract also specifies
credential lifetime for the kubeconfig.

However, the exit criteria do not explicitly require a rotation or
revocation procedure for the Vultr API token itself. The adjacent
Application Cluster Provisioning proposal requires a documented
rotation/revocation path for connection-secret credentials. For
consistency and security posture, the bootstrap credential should also
have at least a documented rotation path, even if initially manual.

This is LOW because the credential-custody deliverable naturally creates
the right context for a rotation procedure to be defined during
implementation.

### F-3. Object-storage bucket destroy/recreate on update — LOW

The OpenTofu provider research notes that Vultr's object-storage bucket
resources treat some updates as destroy/recreate operations. Since the
state bucket holds critical infrastructure state, an incautious
configuration change to the bucket resource could trigger state loss.

This is LOW because: (a) the exit criteria require object versioning,
which provides a recovery path; (b) the exit criteria require an
exercised state-restore procedure; and (c) state-bucket configuration
should be stable after initial creation, making update-triggered
destroys unlikely in practice.

### Previous MEDIUM — State locking: RESOLVED

The revised proposal elevates state locking from an implicit assumption
to a first-class exit criterion with a mandatory concurrent-plan test,
required object versioning, and a required exercised restore procedure.
This is the correct resolution.

### Previous MEDIUM — Credential custody: RESOLVED

The revised proposal adds an explicit credential-custody deliverable
with defined storage, access control, backup, and per-environment
scoping requirements. This is the correct resolution.

### Previous MEDIUM — Kubeconfig handoff: RESOLVED

The revised proposal defines a detailed handoff contract specifying: API
server endpoint, kubeconfig/connection-secret storage path, retrieval
access control, encryption-at-rest posture, and credential lifetime
model. The exit criteria mirror these requirements. This is the correct
resolution.

---

## Criterion 2 — Conflicts with locked decisions

### No conflicts found

The proposal was cross-referenced against all decisions in
`platform-decisions-overlay.md`:

| Locked decision | Proposal alignment |
| --- | --- |
| Authentik (human identity) | Explicitly out of scope; no conflict |
| OPAL/Cedar (authorization) | Explicitly out of scope; no conflict |
| Pomerium (access proxy) | Explicitly out of scope; no conflict |
| Buildkite (CI/CD direction) | Explicitly out of scope; no conflict |
| Flux CD (reconciler) | Preserved as the locked direction; proposal stops before GitOps bootstrap |
| Provider-native object storage preferred over self-hosted | Honored — uses Vultr Object Storage |
| SeaweedFS, MinIO, other self-hosted S3 | Correctly out of scope |
| Two-tier model (platform cluster + application clusters) | Preserved |

The proposal correctly requires updating `platform-decisions-overlay.md`
to lock Vultr as the hosting decision and marking `phase1-foundation.md`
as superseded — both as gating exit criteria. This resolves the overlay's
"still open" hosting item through an explicit ratification path rather
than implicit commitment.

### Previous MEDIUM — Hosting ratification: RESOLVED

The revised proposal makes overlay update a gating exit criterion, citing
the provider comparison research as the ratification basis, and requires
marking the Hetzner-based `phase1-foundation.md` as superseded. The
procedural gap is closed.

---

## Criterion 3 — Provider, state-storage, bootstrap, and control-plane choices

### F-4. VKE/VPC networking verification is correctly gated — LOW

The proposal acknowledges in section 6 that "the current research notes
some ambiguity around VKE and VPC terminology" and treats verification
as a gating pre-implementation task. The exit criteria require VKE/VPC
attachment verification on a throwaway cluster before the per-environment
network topology is committed.

The Hetzner-vs-Vultr research confirms the ambiguity: Vultr's December
2025 docs say VKE uses legacy VPC while VPC 2.0 had a stated end-of-life
of December 31, 2025. If the attachment semantics differ from assumption,
per-environment network isolation may not hold as described.

This is LOW because the gating is explicit and precedes any commitment.
The initiative cannot close without verified VKE/VPC behavior.

### Provider choice assessment

Vultr VKE is well-supported by both research documents. The provider
comparison recommends Vultr as the stronger platform host for managed
Kubernetes. The OpenTofu provider research confirms that Vultr offers a
broader first-party provider surface (VKE, DNS, load balancers, object
storage, managed databases) than Hetzner for this use case. The choice
is sound for the initiative boundary.

### State-storage choice assessment

Vultr Object Storage as the S3-compatible backing for infrastructure
state is the right first step. It avoids an early dependency on
self-hosted storage, keeps state external to the cluster being created,
and aligns with the locked decision to prefer provider-native object
storage. The locking mechanism gap (F-1) is an implementation-level
concern, not an architectural one.

### Bootstrap path assessment

OpenTofu as the canonical operator entrypoint with per-environment roots
is sound. The per-environment isolation model prevents cross-environment
blast radius. The shared-module-plus-environment-root pattern is standard
and well-understood.

### Control-plane choice assessment

Managed VKE control plane is the correct choice for reducing bootstrap
burden. The proposal explicitly avoids recreating a self-managed cluster
stack, which is consistent with the initiative's goal of minimizing
bootstrap complexity. Managed VKE eliminates the self-managed etcd, volume
backup, and firewall exposures that dominated the `phase1-foundation.md`
risk profile.

---

## Criterion 4 — Production-critical gaps at phase boundary

### F-5. DNS ownership at boundary is an acknowledged open question — LOW

The proposal lists DNS record ownership as an open question: whether
bootstrap or later ingress/GitOps work owns platform-relevant DNS
records. This is correctly identified and does not create an unowned
production-critical gap because the bootstrap exit criteria do not
depend on DNS beyond what is needed for the bootstrap path itself.

Later initiatives (GitOps Foundation, ingress, identity) will need DNS,
but the open question is a design decision to be resolved during
implementation, not an unowned gap.

### Boundary assessment: Bootstrap to GitOps Foundation

The handoff seam is well-defined. The proposal delivers a running VKE
platform cluster with a published handoff contract (API endpoint,
kubeconfig storage path, access control, encryption posture, credential
lifetime). GitOps Foundation can attach Flux to this known-good cluster
without re-arguing substrate decisions.

The repository layout stability requirement in the exit criteria ensures
the GitOps initiative has a stable target for Flux root placement.

### Boundary assessment: Bootstrap to Application Cluster Provisioning

The boundary is explicit. Crossplane installation is stated as outside
this initiative's scope, and Application Cluster Provisioning owns the
Crossplane core install as its own day-zero prerequisite. The platform
cluster's existence and reachability via the handoff contract is the
only dependency. Both proposals agree on this boundary.

### Boundary assessment: Hosting ratification

The exit criteria require updating `platform-decisions-overlay.md` to
lock Vultr as the hosting decision with the provider comparison research
as ratification basis. This prevents a gap where implementation proceeds
against an unlocked decision.

### Previous MEDIUM — Crossplane ownership: RESOLVED

The revised proposal explicitly excludes Crossplane and names Application
Cluster Provisioning as the owner of Crossplane installation as its own
day-zero prerequisite. The Application Cluster Provisioning proposal
(section 2, section 3) confirms this ownership. The boundary is clean and
both proposals agree on the handoff.

---

## Summary table

| ID  | Finding | Criterion | Severity |
| --- | --- | --- | --- |
| F-1 | State-locking mechanism requires design resolution (DynamoDB absent on Vultr) | Security / reliability | LOW |
| F-2 | Vultr API token rotation path not exit-gated | Security | LOW |
| F-3 | Object-storage bucket destroy/recreate on update | Data integrity | LOW |
| F-4 | VKE/VPC networking verification is correctly gated | Provider choices | LOW |
| F-5 | DNS ownership at boundary is an acknowledged open question | Phase boundary | LOW |

| Previous MEDIUM | Status |
| --- | --- |
| State locking | Resolved — exit-gated with concurrent-plan test, versioning, restore procedure |
| Credential custody | Resolved — explicit deliverable with defined scope |
| Hosting ratification | Resolved — overlay update is a gating exit criterion |
| Crossplane ownership | Resolved — explicitly out of scope with named owner |
| Kubeconfig handoff | Resolved — detailed handoff contract in exit criteria |

---

## Recommendations summary

1. **State locking (F-1):** During implementation, evaluate the specific
   locking mechanism early. If Vultr Object Storage does not support
   conditional writes suitable for lock acquisition, plan for an
   alternative (HTTP backend, consul, or PostgreSQL backend). The exit
   criterion already gates this; treat it as a first-sprint design task.

2. **API token rotation (F-2):** When defining the credential-custody
   deliverable, include a rotation procedure for the Vultr API token
   alongside the storage and access-control documentation. Even a manual
   rotation runbook satisfies this at the bootstrap stage.

3. **Bucket lifecycle safety (F-3):** Pin the state-bucket OpenTofu
   resource configuration early and treat any subsequent modification
   with the same care as a state-migration operation. Object versioning
   (already exit-gated) provides the safety net.

4. **VKE/VPC verification (F-4):** Execute the throwaway-cluster
   verification before any production network topology decisions. The
   proposal already gates this correctly.

5. **DNS ownership (F-5):** Resolve the open question during
   implementation planning. The likely answer is that bootstrap owns only
   the records needed for cluster API reachability, with all other DNS
   deferred to ingress and GitOps initiatives.
