# Application Cluster Provisioning — Risk Audit

Date: 2026-04-14 (revised proposal re-audit)

## Overall verdict: LOW

The revised proposal resolves all four MEDIUM findings from the prior
audit. Connection-secret RBAC, production-class deletion protection,
Crossplane install ownership, and claim-authoring RBAC are now
committed in exit criteria with specific, verifiable acceptance
conditions. The OpenTofu/Crossplane tool boundary is explicit. The
claim schema field-honesty test (previously LOW, F-8) has been promoted
to exit criteria. The operator-only claim path is bounded as
bootstrap-only with coordination gating against GitOps Foundation.

No HIGH-severity findings. No MEDIUM-severity findings remain. The
four surviving LOW findings are implementation-time concerns that do
not require proposal changes.

---

## Resolution of prior MEDIUM findings

### Prior F-1 (MEDIUM → RESOLVED): Connection-secret controls

The exit criteria now require:

- published connection secrets in a dedicated, RBAC-restricted namespace
  with default-deny posture and explicit allow-lists (exit criterion 8)
- a documented rotation/revocation path for connection-secret
  credentials, even if initially manual (exit criterion 9)

Both parts of the prior recommendation are committed verbatim. The
scope section (item 7) reinforces the operational boundary by naming
RBAC controls on connection-secret access as in-scope. The risks
section elevates this to a first-class named risk with the specific
control shape required.

**Assessment:** Adequately resolved. No remaining gap.

### Prior F-2 (MEDIUM → RESOLVED): Production-class deletion protection

The exit criteria now require:

- production-class claims default to a protective `deletionPolicy`
  (such as `Orphan` with explicit operator unlock) that prevents
  destructive reconciliation without a deliberate policy change
  (exit criterion 10)

The risks section commits to the same posture: protective deletion
policy "from the first version." The exit criterion is specific enough
to be testable — it names the mechanism class and the enforcement
condition.

**Assessment:** Adequately resolved. No remaining gap.

### Prior F-3 (MEDIUM → RESOLVED): Crossplane install ownership

This was the sharpest prior finding: no initiative in the corpus owned
Crossplane core install. The revised proposal resolves it bilaterally:

- This initiative's scope (section 2, item 1) explicitly states: "This
  initiative owns the Crossplane installation because Platform Bootstrap
  is scoped to substrate only and explicitly excludes cluster-fleet
  management logic."
- Section 3 (control-plane boundary) repeats the assignment: "This
  initiative owns the Crossplane installation baseline: core controller,
  CRDs, provider package, and `ProviderConfig` bootstrap on the control
  cluster."
- Exit criterion 1 requires Crossplane core as a day-zero deliverable.
- Platform Bootstrap's out-of-scope section and bootstrap handoff
  section confirm the exclusion: "Crossplane installation is explicitly
  outside this initiative's boundary; Application Cluster Provisioning
  owns the Crossplane core install as its own day-zero prerequisite."

The ownership is now unambiguous with bilateral confirmation from both
initiatives. No seam gap remains.

**Assessment:** Adequately resolved. No remaining gap.

### Prior F-5 (MEDIUM → RESOLVED): Claim-authoring RBAC

The exit criteria now require:

- a minimum RBAC posture for claim CRUD: only a named group may create
  or delete production-class claims; dev-class claims may have a wider
  authoring group (exit criterion 11)

The risks section adds context: claim-authoring RBAC is "part of this
initiative's operational contract" and "does not depend on the locked
auth stack — it is native Kubernetes RBAC on the control cluster." This
correctly scopes the control to what is available before
`Authentik`/`OPAL`/`Cedar` deploy.

**Assessment:** Adequately resolved. No remaining gap.

---

## Findings (revised proposal)

### F-1. Hosting decision still open; composition correctly gated

**Criterion:** Provider, state-storage, bootstrap, and control-plane
choices

**Severity: LOW**

`platform-decisions-overlay.md` still lists `Hetzner` vs `Vultr` as
open. The proposal handles this correctly: the first composition is
explicitly gated on the hosting decision lock (section 6, risks; open
question 1), and the exit criteria require "at least one
provider-specific composition exists for the locked hosting substrate."
The Crossplane justification (section 1) is sound — it avoids
collapsing the two-tier model or requiring external orchestration to
bridge OpenTofu applies into the control cluster's desired-state model.

The composition cost asymmetry between a managed-cluster API (Vultr
VKE) and a self-managed path (Hetzner k3s) is acknowledged in the open
questions. This is not a defect; it is a correctly deferred decision.

**Recommendation:** No proposal change. Surface the composition
strategy (first-party provider vs. wrapped OpenTofu module) as an
explicit implementation decision after the hosting lock lands.

---

### F-2. No minimum notification path for stuck claims

**Criterion:** Security, correctness, reliability, or data-integrity
risk

**Severity: LOW**

The exit criteria require that failed claims "surface actionable
conditions and failure reasons without requiring a separate custom
controller" and that operator runbooks cover "failure triage." This is
passive — it describes what is available on the object, not what
actively notifies operators. A failed provisioning can sit indefinitely
until a downstream consumer notices the missing cluster.

This is LOW because the exit criteria do require runbooks and
actionable status conditions, which together form a minimum operational
path. Active alerting (Flux notification controller, Prometheus alert
on `Synced=False`/`Ready=False` beyond a bounded window) is a
straightforward implementation-time addition that does not require
proposal-level change.

**Recommendation:** During implementation, add at least one active
notification path for claims stuck in a non-ready state beyond a
bounded window. This is a runbook-adjacent concern, not a proposal
defect.

---

### F-3. ProviderConfig credential custody path is implicit

**Criterion:** Security, correctness, reliability, or data-integrity
risk

**Severity: LOW**

The proposal owns Crossplane core install and `ProviderConfig` baseline
as day-zero deliverables. The `ProviderConfig` requires a cloud
provider credential (API token) to provision downstream clusters. The
scope section names "provider credentials" as part of the operational
boundary, and the namespace/credential model is a deliverable.

However, the exit criteria do not explicitly require that the
`ProviderConfig` credential follow a defined custody model (storage
location, access boundary, rotation path). Platform Bootstrap's exit
criteria define credential custody for the Vultr API token at the
substrate level; this initiative inherits or extends that model for the
Crossplane provider credential.

This is LOW because Platform Bootstrap's credential custody exit
criteria establish the pattern, and this initiative's scope includes
"provider credentials" in the operational boundary. The implementation
can naturally extend the upstream credential model without a proposal
change.

**Recommendation:** During implementation, ensure the `ProviderConfig`
credential follows the same custody model as the Platform Bootstrap
provider token: defined storage location, access-control boundary,
backup procedure, and rotation path.

---

### F-4. Upstream proposal reconciliation is nearly resolved

**Criterion:** Production-critical gaps at phase boundary

**Severity: LOW**

The prior audit flagged two competing upstream proposals
(`phase1-foundation.md` and `platform-bootstrap.md`). Platform
Bootstrap now explicitly states it supersedes the substrate direction of
`phase1-foundation.md` and requires updating
`platform-decisions-overlay.md` to lock Vultr as the hosting decision
and mark `phase1-foundation.md` as superseded.

The overlay still lists the hosting decision as open, but this is
correct governance: the decision locks when Platform Bootstrap is
accepted, not before. This initiative correctly does not pre-commit to
a provider, and its first composition is gated on the lock.

**Recommendation:** No proposal change. The upstream reconciliation
lands when Platform Bootstrap is accepted; this initiative's
precondition is structurally sound.

---

## Locked-decision alignment

No conflicts with ratified locked decisions. The proposal is consistent
with `platform-decisions-overlay.md`:

- `Flux CD` remains the reconciler; this initiative does not install
  Flux into downstream clusters and explicitly defers GitOps topology
  to GitOps Foundation.
- `Buildkite` is not asked to mutate clusters; the initiative only
  publishes a readiness contract.
- Provider-native object storage, `Authentik`, `OPAL/Cedar`,
  `Pomerium`, and `Smallstep` are correctly out of scope.
- The still-open hosting decision (`Hetzner` vs `Vultr`) is handled by
  gating the first composition on the locked substrate.
- The proposal correctly calls for locking Crossplane as a platform
  decision in the overlay, following the same governance model as Flux
  and Buildkite.

The initiative boundary is respected: this proposal does not absorb
Platform Bootstrap (upstream) or GitOps Foundation (downstream), and it
does not collapse the two-tier control/app cluster model. The
OpenTofu/Crossplane tool boundary is explicit and prevents
split-ownership of cloud primitives.

---

## Summary table

| ID  | Finding                                               | Severity |
| --- | ----------------------------------------------------- | -------- |
| F-1 | Composition gated on unlocked hosting decision        | LOW      |
| F-2 | No active notification path for stuck claims          | LOW      |
| F-3 | ProviderConfig credential custody path is implicit    | LOW      |
| F-4 | Upstream proposal reconciliation nearly resolved      | LOW      |

## Prior MEDIUM findings — resolution status

| Prior ID | Finding                                             | Prior    | Revised  |
| -------- | --------------------------------------------------- | -------- | -------- |
| F-1      | Connection-secret RBAC controls                     | MEDIUM   | RESOLVED |
| F-2      | Production-class deletion protection                | MEDIUM   | RESOLVED |
| F-3      | Crossplane install / ProviderConfig ownership       | MEDIUM   | RESOLVED |
| F-5      | Claim-authoring RBAC                                | MEDIUM   | RESOLVED |
| F-8      | Claim schema field-honesty test (promoted to exit)  | LOW      | RESOLVED |
