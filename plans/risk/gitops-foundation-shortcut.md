# Shortcut Risk Assessment — GitOps Foundation

**Proposal:** `plans/proposals/gitops-foundation.md`
**Assessor:** Claude (shortcut risk)
**Date:** 2026-04-14
**Overall verdict:** LOW

---

## Criterion 1 — Does the proposal replace one shortcut with another?

**Severity: LOW**

The original `phase1-foundation.md` bundled infrastructure provisioning,
GitOps topology, cluster fleet management, secrets, and ingress into a
single monolithic phase on Hetzner. The three-initiative split
(Platform Bootstrap, GitOps Foundation, Application Cluster
Provisioning) decomposes that bundle into initiatives with distinct
ownership boundaries. GitOps Foundation inherits only the topology and
reconciliation-boundary concerns. It does not replicate the monolith
under a new name, and it does not introduce a different shortcut in
place of the old one.

The proposal is a topology definition, not an implementation vehicle.
That narrow scope means there are few places where a shortcut could
hide. The structural choices — path-based environment separation,
per-cluster Flux roots, hard CI/Flux boundary — are explicit design
decisions with clear rationale, not convenience compromises.

The control cluster is explicitly not positioned as a remote deployment
engine for other clusters, closing the hub-and-spoke shortcut that
legacy patterns tend to invite. `app-cluster-provisioning.md` confirms
this: reconciliation happens inside each target cluster through its own
Flux controllers.

No shortcut replacement detected.

---

## Criterion 2 — Does it hide unresolved complexity behind vague deferrals?

**Severity: LOW**

Deferrals in the proposal are explicit. They live in the open-questions
section (section 6) and the interfaces section (section 3) rather than
being smuggled into ambiguous prose. Four items deserve mention; none
reach MEDIUM.

### 2a. Flux installation ownership gap

The most notable deferral is that no initiative in the current set
explicitly owns Flux installation:

- Platform Bootstrap excludes "installing or configuring Flux CD"
- GitOps Foundation excludes "writing Flux manifests, Kustomization
  objects, or bootstrap code"
- Application Cluster Provisioning excludes "installing Flux or other
  workload controllers into downstream clusters"

The interfaces section says "Cluster bootstrap *may* create the initial
Flux installation" — using hedging language rather than assigning
ownership. However, this is a cross-initiative gap in the initiative
set, not hidden complexity within GitOps Foundation itself. GitOps
Foundation defines the topology that Flux must follow; the actual Flux
bootstrap is implementation work that falls naturally into the
implementation phase of this initiative or a dedicated bootstrap task.
The exit criteria are interpretable as topology-level deliverables
("each physical cluster has exactly one Flux root path") rather than
requiring running Flux instances. Rating remains LOW because the
deferral is explicit, not concealed, and both sibling proposals accept
this seam from opposite sides.

### 2b. Cross-cluster platform dependencies

The proposal says "cross-cluster platform dependencies may exist later,
but reconciliation still happens inside each target cluster through that
cluster's own Flux controllers." This preserves the per-cluster
reconciler rule, but it defers *how* data crosses the control/app
boundary (e.g., secrets published by the control cluster that the app
cluster needs to consume). Topology-only scope justifies this deferral,
and `app-cluster-provisioning.md` explicitly accepts the handoff
contract at the same seam.

### 2c. Promotion mechanism

Open question 2 leaves the concrete promotion mechanism open (direct PRs
vs. structured promotion workflow). The topology locks the structural
part: promotion is a path-based Git change into the target environment
root. Only the review/automation wrapper around that change is deferred.
Acceptable for a topology initiative, but the first initiative that
needs to promote will have to settle this without reopening topology.

### 2d. Repository home

Open question 1 asks whether the topology lives in a dedicated repo or a
subtree. The proposal's own section 2 lists "define the canonical
repository layering" as in-scope. Leaving the repo-vs-subtree question
open past proposal acceptance would mean the initiative exits without
closing a promise from its own scope list. This is a must-close-before-
implementation item rather than a general open question.

None of these hide complexity that would block adoption of the topology.
They are interface questions for adjacent initiatives, with two (2c, 2d)
that should be resolved inside this initiative rather than deferred
indefinitely.

---

## Criterion 3 — Does it introduce temporary operator-only seams or duplicate control paths?

**Severity: LOW**

The proposal is unusually strict on this criterion — it exists partly to
prevent duplicate control paths. No temporary operator-only seams are
introduced.

- Hard boundary: "no bucket-watched Flux source, no CI-driven cluster
  mutation path, and no second deployment engine next to Flux."
- Buildkite's Git-facing role is bounded to validation, artifact
  production, and "opening a PR or preparing a promotion change for
  review." No live-cluster credentials on the CI side.
- Per-cluster Flux roots explicitly forbid any cluster from reconciling
  a parent path, preventing accidental cross-cluster blast radius.
- The control cluster is explicitly not a second deployment engine for
  remote clusters. `app-cluster-provisioning.md` confirms: Crossplane
  provisions child clusters and publishes a connection contract, but
  reconciliation happens inside each child cluster through its own Flux
  root.
- No "temporary" operator kubectl/helm paths are introduced to bridge
  the gap before Flux is installed. The proposal declares that ongoing
  state changes flow through Git and Flux, and leaves the pre-Flux
  bootstrap window to Platform Bootstrap's scope.

The proposal does not create any path where an operator would need to
manually mutate clusters as a workaround for missing automation.

---

## Criterion 4 — Does it compromise the two-tier model or other locked decisions for convenience?

**Severity: LOW**

The proposal reinforces every locked decision it touches:

- **Two-tier preserved:** Every environment has both a `control-cluster`
  root and an `app-cluster` root under both `overlays/` and `clusters/`.
  Exit criteria enforce this. The proposal states: "The control-cluster
  is not a second deployment engine for remote clusters. It is just
  another cluster with its own Flux root."
- **Flux CD as sole reconciler:** Locked in `platform-decisions-overlay.md`
  (Flux replaces Argo CD), hardened here as a "hard boundary, not a
  preference."
- **Buildkite CI-only role:** Locked direction, codified here as a hard
  wall. Buildkite validates and prepares Git changes but does not mutate
  clusters directly.
- **Provider neutrality:** The topology is substrate-agnostic. The
  `platform-decisions-overlay.md` hosting decision does not affect the
  GitOps topology. `platform-bootstrap.md` locks Vultr VKE while
  `phase1-foundation.md` targeted Hetzner — the GitOps topology survives
  either outcome without modification.
- **Crossplane integration:** Topology slot for cluster claims defined
  under control-cluster roots, consistent with Application Cluster
  Provisioning's ownership model. The topology defines where claims land
  without absorbing claim semantics.
- **Auth stack untouched:** Authentik, OPAL/Cedar, Pomerium, and
  Smallstep are correctly out of scope and named only as adjacent
  initiatives that plug into the topology.

The proposal's own acknowledged risks (overlay sprawl, per-cluster root
repetition, increased promotion paths) are structural tradeoffs of the
two-tier + per-cluster-root model. They are flagged transparently rather
than hidden behind convenience compromises.

No locked-decision compromises detected.

---

## Summary table

| # | Criterion | Severity | Finding |
|---|-----------|----------|---------|
| 1 | Shortcut replacement | LOW | Clean decomposition from monolithic Phase 1; no shortcut traded for another |
| 2 | Vague deferrals | LOW | Deferrals are explicit with interface contracts; Flux bootstrap ownership is a cross-initiative gap but not hidden |
| 3 | Operator-only seams / duplicate paths | LOW | Hard CI/Flux boundary stated; no temporary operator seams introduced |
| 4 | Two-tier model / locked decisions | LOW | Every locked decision is preserved or reinforced; no convenience compromises |

**Overall: LOW** — All findings are addressable during implementation
without proposal changes.

---

## Recommendations

1. **Clarify Flux bootstrap ownership across initiatives.** The current
   initiative set has an explicit gap: no proposal owns Flux
   installation. During implementation planning, assign Flux bootstrap
   to a specific initiative or task. The natural home is the
   implementation phase of GitOps Foundation itself, since this
   initiative defines the Flux root topology. Consider updating the
   interfaces section to change "Cluster bootstrap *may* create the
   initial Flux installation" to a definitive ownership statement.

2. **Resolve repo-home and promotion-mechanism before implementation.**
   Both are listed as in-scope deliverables (section 2) but left as open
   questions (section 6). If they stay open past proposal acceptance,
   downstream initiatives will either stall or make the decision outside
   the initiative that should own it. Reclassify these as must-close
   items rather than general open questions.

3. **Pin the cross-cluster data-flow rule when adjacent initiatives
   land.** When secrets and platform-service initiatives arrive, enforce
   that cross-cluster dependencies are expressed as independent
   declarations in each cluster root with a shared source of truth in
   `base/`, not as one cluster reconciling on behalf of another. This
   keeps the per-cluster Flux root rule from being quietly undermined by
   shared-component wiring.

4. **Tighten exit criteria language.** Exit criterion "each physical
   cluster has exactly one Flux root path" could be read as requiring
   running Flux or as requiring a defined topology slot. If the intent
   is topology-only, add a clarifying phrase (e.g., "defined in the
   repository layout"). If the intent includes Flux configuration, scope
   the initiative accordingly.
