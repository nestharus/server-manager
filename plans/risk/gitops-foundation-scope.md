# Scope risk — GitOps Foundation

Assessed against: `plans/proposals/gitops-foundation.md`
Cross-referenced with: `plans/platform-decisions-overlay.md`,
`plans/proposals/platform-bootstrap.md`,
`plans/proposals/app-cluster-provisioning.md`,
`plans/proposals/phase1-foundation.md`

## Overall verdict: LOW

GitOps Foundation is appropriately scoped as a topology and ownership
initiative. It defines the repository layering
(`base/overlays/clusters/<env>`), per-cluster Flux root model,
path-based environment separation, the two-tier cluster split
(`control-cluster` / `app-cluster`), the Git/Flux/Buildkite operating
boundary, and the promotion model — and it stops there. It does not
write manifests, bootstrap clusters, or implement CI pipelines. The
exit criteria are testable topology assertions, not running-system
proofs.

The prior MEDIUM finding (F-1 in the previous assessment) identified a
missing reciprocal interface commitment toward Application Cluster
Provisioning: GitOps Foundation did not specify where Crossplane claims
land in the control-cluster root or how per-cluster Flux roots are
bootstrapped onto newly provisioned downstream clusters. That gap is
now closed. The proposal's §3 "Interfaces to adjacent initiatives"
includes an explicit clause covering both Crossplane claim placement
and downstream-cluster Flux bootstrap, and §7 includes a matching exit
criterion. The cross-cluster dependency rule is also well-placed.

All five findings below are LOW. None require proposal revision before
implementation.

---

## Findings

### F-1. Prior MEDIUM resolved — Crossplane claim placement and child-cluster Flux bootstrap interface now present — LOW

The prior assessment flagged a one-sided seam: `app-cluster-provisioning.md`
§3 declared that GitOps Foundation owns claim placement in Git and
per-cluster Flux root bootstrapping for downstream clusters, but
`gitops-foundation.md` §3 did not reciprocate. That gap is closed.

The proposal now includes (§3, "Interfaces to adjacent initiatives"):

> Crossplane ClusterClaim resources for application cluster provisioning
> land under the control-cluster root in the appropriate environment
> path (e.g., clusters/\<env\>/control-cluster/). When Application
> Cluster Provisioning creates a new downstream cluster, the per-cluster
> Flux root for that cluster is bootstrapped into the
> clusters/\<env\>/app-cluster/ path following the same per-cluster root
> model defined above.

And §7 exit criteria now require:

> a defined topology slot exists for Crossplane cluster claims under the
> control-cluster root, and a defined bootstrap path exists for wiring
> per-cluster Flux roots onto newly provisioned downstream clusters
> under clusters/\<env\>/app-cluster/

This answers both questions the prior MEDIUM raised:

1. Where Crossplane `ClusterClaim` resources land in Git: under the
   control-cluster root for the appropriate environment.
2. How freshly provisioned downstream app clusters get their Flux root:
   bootstrapped into `clusters/<env>/app-cluster/` using the same
   per-cluster root model.

The reciprocal commitment is now symmetrical with
`app-cluster-provisioning.md` §3 "Claim submission seam."

**Residual**: the clause defines placement at the directory level
(`clusters/<env>/control-cluster/`) but does not prescribe subdirectory
convention (e.g., whether claims sit at
`clusters/<env>/control-cluster/crossplane/claims/` or directly in the
root). This is an appropriate level of abstraction for a topology
proposal — the exact directory structure is an implementation detail,
not a scope question.

**Severity**: LOW. Resolved from MEDIUM. No proposal change needed.

### F-2. Cross-cluster dependency rule is well-placed — LOW

The proposal adds a new interface rule (§3):

> Cross-cluster platform dependencies are expressed as independent
> declarations in each cluster root with a shared source of truth in
> base/, not as one cluster reconciling on behalf of another.

This rule reinforces the per-cluster Flux root model already defined in
§3 "Per-cluster Flux roots" and closes a potential interpretation gap:
without this rule, an implementer could have used the control cluster's
Flux instance to reconcile objects into the app cluster, which would
violate the one-reconciler-per-cluster model.

**Risk**: none. The rule is consistent with the existing architecture
and adds clarity without expanding scope.

**Severity**: LOW. No action needed.

### F-3. Crossplane installation ownership is now resolved across initiatives — LOW

The prior assessment noted a three-way gap over who installs Crossplane
on the control cluster. That ambiguity is now closed:
`app-cluster-provisioning.md` §2 explicitly states that it owns the
Crossplane core install as a day-zero prerequisite, and §3 reaffirms
"This initiative owns the Crossplane installation baseline."
`platform-bootstrap.md` §5 explicitly excludes Crossplane. GitOps
Foundation's open question 4 ("Which shared platform controllers belong
in the control cluster base from day one?") remains open, but the
Crossplane-specific ownership is no longer ambiguous.

**Risk**: from GitOps Foundation's perspective, the risk is LOW. This
initiative is not blocked by the Crossplane install decision. It
defines the topology slot; Application Cluster Provisioning owns the
tooling.

**Recommendation**: when resolving open question 4, note that
Crossplane base manifests are owned by Application Cluster
Provisioning, not by GitOps Foundation's `base/platform/` or
`base/controllers/` layer. This avoids re-opening the ownership
question during implementation.

### F-4. Promotion model open question is a scope hinge — LOW

Section 3 "Environment separation" correctly defines promotion as a
path-based Git change. Section 6 open question 2 asks whether the
mechanism should be "direct PRs against target paths only, or a more
structured promotion workflow." If interpreted expansively, the
structured option could pull in promotion bots or release automation —
all of which §5 explicitly excludes.

**Risk**: the open question as phrased is safe because §5 constrains
the answer. An implementer reading only §3 and §6 without §5 could
justify building promotion tooling, but the exclusion is clear enough
to catch this during review.

**Recommendation**: no proposal change needed. When the open question
is resolved during implementation, keep the answer within the §5
constraint: define the promotion pattern, not the promotion automation.

### F-5. Repository-vs-subtree decision affects the Platform Bootstrap handoff — LOW

Section 6 open question 1 asks whether the topology lives in a
dedicated desired-state repository or a subtree of a broader platform
repo. The topology design is internally valid under either answer.
However, `platform-bootstrap.md` §3 handoff seam says "the repository
layout is stable enough for a later Flux bootstrap initiative to attach
cleanly," which assumes a known repo structure.

**Risk**: if this question is left open when Platform Bootstrap
implements its handoff artifact, the two initiatives may make
incompatible assumptions about where Git state lives.

**Recommendation**: resolve this question in coordination with Platform
Bootstrap before either initiative begins implementation. The answer
does not change GitOps Foundation's internal scope.

---

## Assessment against criteria

### 1. Is this initiative appropriately narrow for the problem it claims to solve?

**Yes.** The claimed problem is "make the deployment model unambiguous."
The initiative answers that with three pieces: a path-based layering
contract, a per-cluster reconciler-scope rule, and a Git/Flux/CI
operating boundary. Nothing beyond those three is asserted as in scope.
Manifest authoring, bootstrap code, CI pipelines, secrets, ingress, and
application rollout are all explicitly deferred. The proposal names
overlay sprawl and per-cluster-root repetition as its own failure modes
(§6), which is the right level of self-awareness for a topology
initiative.

### 2. Does it defer anything that should stay inside this initiative?

**No.** The prior gap (F-1 in the previous assessment) is closed. The
interface catalog now covers six integration points: secrets, ingress,
application delivery, cluster bootstrap, Crossplane claim placement /
downstream Flux bootstrap, and cross-cluster dependencies. This is
comprehensive for a topology initiative. All deferred items are
correctly outside scope:

- Flux manifests and Kustomization objects: implementation phase
- Buildkite pipelines: CI initiative
- Cluster provisioning: Platform Bootstrap / App Cluster Provisioning
- Crossplane installation: App Cluster Provisioning day-zero
- Secrets, ingress, identity: later platform-service initiatives
- Promotion automation: later phase

### 3. Does it pull later-phase work too early?

**No.** Every in-scope item is a prerequisite for the other Phase 1
initiatives, not a shortcut into them:

- The repository layout must be defined before Flux manifests can be
  written to it.
- The per-cluster Flux root model must be defined before Flux is
  installed.
- The Git/Flux/Buildkite boundary must be defined before either
  reconciler or CI is configured.
- The promotion model must be defined before environment promotion is
  implemented.
- The interfaces (including the new Crossplane and cross-cluster
  clauses) must be defined before adjacent initiatives target them.

The proposal resists the temptation to implement what it defines. §5
explicitly excludes writing manifests, bootstrap code, CI pipelines,
and any deployment-path implementation.

### 4. Are the boundaries with the other two Phase 1 initiatives proportionate and clear?

**Yes.**

- **GitOps Foundation / Platform Bootstrap**: clean. Platform Bootstrap
  owns substrate provisioning, per-environment OpenTofu roots, base
  networking, and object-storage state backing. GitOps Foundation picks
  up at the handoff seam and defines the Git-side shape without
  installing anything. The boundary is explicit and consistent across
  both proposals.

- **GitOps Foundation / Application Cluster Provisioning**: clean. The
  prior one-sided seam (F-1) is resolved. GitOps Foundation now
  explicitly defines where Crossplane claims land in Git and how
  per-cluster Flux roots are bootstrapped onto downstream clusters. App
  Cluster Provisioning owns the claim content, compositions, readiness
  contract, and Crossplane installation. The cross-cluster dependency
  rule prevents either initiative from creating a central-mutator
  pattern. Both proposals reference each other's ownership at the seam,
  and the commitments are symmetrical.

- **Proportionality**: the three initiatives together cover substrate,
  topology, and cluster provisioning without overlapping scope. Each
  initiative's out-of-scope list aligns with the others' in-scope
  lists. No initiative subsumes the others.

---

## Recommendations summary

1. **F-1 (resolved)**: no action needed. The prior MEDIUM is closed by
   the new interface clause and exit criterion.

2. **F-2**: no action needed. The cross-cluster dependency rule is
   well-placed and consistent.

3. **F-3**: when resolving open question 4 during implementation, note
   that Crossplane base manifests are owned by Application Cluster
   Provisioning, not GitOps Foundation's base layer.

4. **F-4**: no proposal change needed. Keep promotion-mechanism
   resolution within the §5 automation exclusion.

5. **F-5**: resolve the repo-vs-subtree question in coordination with
   Platform Bootstrap before either initiative begins implementation.

No recommendations require proposal revision. All five are addressable
during implementation coordination.
