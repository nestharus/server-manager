# GitOps Foundation — Risk Audit (rerun)

Date: 2026-04-14

## Overall verdict: LOW

The `GitOps Foundation` proposal is a topology-and-boundary initiative. It
commits no implementation, selects no hosting-dependent component, and
preserves every locked decision in `platform-decisions-overlay.md`. Its
operating rules (per-cluster Flux root, Git-as-desired-state, hard
Buildkite/Flux boundary, two-tier control/app split) are all risk-reducing
rather than risk-introducing.

Since the prior audit, the proposal has been revised to incorporate two
recommendations:

- **Secrets single-path constraint (prior F-3):** The interfaces section
  now states "A cluster root may rely on at most one secret-reconciliation
  path at any one time; changing the path is a topology-affecting change."
  This closes the prior finding.
- **Cross-cluster dependency rule (prior F-4):** The interfaces section
  now states "Cross-cluster platform dependencies are expressed as
  independent declarations in each cluster root with a shared source of
  truth in `base/`, not as one cluster reconciling on behalf of another."
  This closes the prior finding.
- **Crossplane claim placement interface:** A new clause defines the
  topology slot for Crossplane claims under the control-cluster root and
  the Flux-root bootstrap path for downstream clusters under
  `clusters/<env>/app-cluster/`.

No HIGH or MEDIUM findings. The remaining LOW findings are
boundary-clarifications that can be resolved during implementation without
proposal changes.

---

## Criterion 1 — Security, correctness, reliability, or data-integrity risk

### F-1. Single-repo path-based separation exposes all environments to repo-level compromise — LOW

Path-based environment separation means a single repository contains
`dev`, `staging`, and `production` state. A credential leak or
unauthorized merge affects all environments simultaneously.

The proposal mitigates this by stating that production remains "isolated
behind its own Git history, approvals, and Flux roots" (section 3,
Environment separation). Branch protection rules, `CODEOWNERS`, and
required reviews for production paths are standard GitOps practice and can
be enforced during implementation.

**Why LOW:** This is inherent to path-based GitOps and is the standard
tradeoff accepted by the Flux community. The alternative (branch-based
separation) is explicitly rejected with sound reasoning. Implementation-
time controls close the gap.

### F-2. No explicit approval model for production-path promotions — LOW

The proposal defines promotion as "changing Git in the target environment
path, then letting Flux reconcile the merged result" but does not specify
required reviewers, approval gates, or protected-path rules for production
changes.

**Why LOW:** This is a topology proposal, not an implementation
specification. The constraint is clearly stated: promotion is a reviewed
Git change, not live-cluster mutation. The enforcement mechanism (branch
protection, required approvals, CODEOWNERS) is a standard implementation
concern.

### F-3. Flux drift-correction alerting not specified — LOW

The proposal assigns drift correction to Flux but does not specify how
drift events are surfaced to operators (alerting, notification channels,
escalation).

**Why LOW:** Observability and alerting are explicitly out of scope for
this topology initiative. The Flux reconciler model includes built-in
health checks and conditions. Alerting integration belongs in the
observability initiative, not in the GitOps topology definition.

---

## Criterion 2 — Conflicts with locked decisions

### No conflicts found

The proposal was checked against every locked decision in
`platform-decisions-overlay.md`:

| Locked decision | Proposal alignment |
| --- | --- |
| Authentik (human identity) | Not referenced; correctly out of scope |
| OPAL/Cedar (authorization) | Not referenced; correctly out of scope |
| Pomerium (access proxy) | Not referenced; correctly out of scope |
| Smallstep (conditional PKI) | Not referenced; correctly out of scope |
| Buildkite (canonical CI/CD) | Aligned — explicitly bars Buildkite from cluster mutation |
| Flux CD (GitOps reconciler) | Aligned — Flux is the sole reconciler |
| Kafka/Debezium/Redis deferred | Not referenced; correctly out of scope |
| Provider-native object storage first | Not referenced; correctly out of scope |

The proposal is also provider-agnostic — it does not assume Hetzner or
Vultr and survives either hosting ratification.

---

## Criterion 3 — Provider, state-storage, bootstrap, and control-plane choices

### F-4. Provider-agnostic topology is appropriate for scope — SOUND

GitOps Foundation deliberately avoids provider-specific decisions. The
repository layering (`base/overlays/clusters`), per-cluster Flux root
model, and environment separation pattern work identically regardless of
the underlying substrate. Provider and substrate decisions are correctly
owned by Platform Bootstrap.

### F-5. Per-cluster Flux root model prevents cross-cluster blast radius — SOUND

The rule that each cluster reconciles only its own path under
`clusters/<env>/<cluster-name>` and that no cluster reconciles a parent
directory is a strong blast-radius control. Combined with the two-tier
split (control-cluster and app-cluster), this prevents a reconciliation
error in one cluster from affecting another.

### F-6. Multi-app-cluster naming convention is ambiguous — LOW

The directory structure shows a single `app-cluster/` entry per
environment, and the Flux root examples reference "the dev app cluster"
(singular). However, Application Cluster Provisioning supports provisioning
multiple downstream clusters. The Crossplane clause says new clusters are
"bootstrapped into the `clusters/<env>/app-cluster/` path."

This creates a minor ambiguity: is `app-cluster/` a single Flux root or a
parent directory containing multiple cluster roots?

**Why LOW:** The per-cluster root model text is unambiguous — each physical
cluster gets its own root path, and no Flux root targets a parent directory.
The directory structure is illustrative, not prescriptive. The naming
convention for multiple app clusters is an implementation detail resolvable
when the first multi-cluster environment is created.

---

## Criterion 4 — Production-critical gaps at phase boundary

### Cross-initiative boundary alignment — SOUND

The proposal's seams match the sibling proposals without overlap:

- **Platform Bootstrap** ends at "substrate ready, Flux not yet installed."
  GitOps Foundation begins at "Flux is the sole reconciler" and defers the
  actual Flux install to bootstrap. No double-ownership.
- **Application Cluster Provisioning** explicitly states that GitOps
  Foundation owns where cluster claims live in git and how per-cluster Flux
  roots are bootstrapped onto downstream clusters. GitOps Foundation
  reciprocates with the Crossplane claim placement clause. No
  double-ownership.
- **Phase 1 Foundation** is hosting-coupled and implementation-oriented;
  GitOps Foundation is a topology definition that Phase 1 can implement
  against. No conflict.

### F-7. Flux-root bootstrap trigger for new app clusters spans two initiatives — LOW

GitOps Foundation owns "how per-cluster Flux roots are bootstrapped onto
newly provisioned downstream clusters." Application Cluster Provisioning
owns the cluster creation trigger and the connection contract. The
bootstrap sequence is:

1. App Cluster Provisioning creates a downstream cluster and publishes a
   connection contract
2. GitOps Foundation's mechanism bootstraps a Flux root onto that cluster

The interface is clearly stated and ownership is assigned. The sequencing
mechanism (manual, automated via Flux notification, or triggered by
Crossplane composition) is not specified.

**Why LOW:** The proposal correctly defines the topology slot and assigns
ownership. The sequencing mechanism is an implementation detail that
depends on Flux and Crossplane capabilities available at implementation
time. No production-critical concern is left unowned.

### F-8. Promotion workflow left as open question — LOW

The proposal lists the promotion mechanism as an open question: "direct PRs
against target paths only, or a more structured promotion workflow that
still lands as reviewed Git changes?"

**Why LOW:** The architectural constraint is locked — promotion is a Git
change, not live-cluster mutation. The open question is about workflow
ergonomics (PR-based vs. structured automation), not about the safety
boundary. Either answer is compatible with the topology.

### F-9. No sanctioned incident-response escape hatch named — LOW

The proposal makes Git the sole desired-state system and Flux the sole
reconciler. It does not address how an operator acts during an incident
where the correct action is faster than a Git PR round-trip (e.g. scaling
a Deployment during a live outage, pausing a reconciliation that is
actively making things worse).

**Why LOW:** A topology initiative does not need to solve this, but naming
the escape hatch prevents later initiatives from inventing one silently.
Acceptable answers include "suspend the `Kustomization`, act, then
reconverge via Git" or a defined out-of-band access path. This can be
addressed during implementation.

---

## Summary table

| ID  | Criterion        | Finding                                                     | Severity |
| --- | ---------------- | ----------------------------------------------------------- | -------- |
| F-1 | Security         | Single-repo path-based separation; repo compromise scope    | LOW      |
| F-2 | Security         | No explicit approval model for production-path promotions   | LOW      |
| F-3 | Security         | Flux drift-correction alerting not specified                 | LOW      |
| F-4 | Choices          | Provider-agnostic topology appropriate for scope            | SOUND    |
| F-5 | Choices          | Per-cluster Flux roots prevent cross-cluster blast radius   | SOUND    |
| F-6 | Choices          | Multi-app-cluster naming convention ambiguous               | LOW      |
| F-7 | Phase boundary   | Flux-root bootstrap trigger spans two initiatives           | LOW      |
| F-8 | Phase boundary   | Promotion workflow left as open question                    | LOW      |
| F-9 | Phase boundary   | No sanctioned incident-response escape hatch named          | LOW      |

---

## Prior findings — disposition

| Prior ID | Prior finding                                        | Status   |
| -------- | ---------------------------------------------------- | -------- |
| F-3      | Secrets interface permits silent multi-path drift    | CLOSED — single-path constraint added to proposal |
| F-4      | Cross-cluster dependency coordination unbounded      | CLOSED — cross-cluster dependency rule added to proposal |

---

## Recommendations

1. **F-1/F-2 — Production path protection:** During implementation, define
   branch protection rules and `CODEOWNERS` entries requiring explicit
   approval for changes under `clusters/production/` and
   `overlays/production/`.

2. **F-6 — Multi-cluster naming:** When the first multi-app-cluster
   environment is implemented, establish a naming convention. Suggested
   pattern: `clusters/<env>/app-<name>/` to keep each cluster root at the
   same directory depth as the control-cluster root.

3. **F-7 — Flux-root bootstrap sequencing:** During implementation of
   GitOps Foundation and Application Cluster Provisioning, define the
   concrete trigger mechanism for bootstrapping Flux roots onto new
   downstream clusters. Document the sequencing contract as part of the
   shared interface.

4. **F-8 — Promotion workflow:** Decide the promotion mechanism before the
   second environment is promoted to. The topology supports either
   approach; the decision affects developer workflow and review policy,
   not architecture.

5. **F-9 — Incident-response pattern:** Name the sanctioned escape hatch
   during implementation. A one-line statement such as "suspend the
   Kustomization, act, then reconverge via Git" preserves the hard boundary
   by making the exception explicit.
