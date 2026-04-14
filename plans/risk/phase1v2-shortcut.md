# Phase 1 Foundation v2 — shortcut risk assessment

## Verdict: MEDIUM

The proposal is unusually self-aware about the four canonical shortcut
patterns the assessment prompt calls out. It explicitly disarms three of
them (sealed-secrets-as-bootstrap vs permanent, mechanical autoscaling
as substitute for policy, undefined benchmarking). The fourth — Hetzner
leftovers in the draft code — is only partially covered: the proposal
names `hcloud-volumes` but is silent on two equally stale Hetzner
artefacts (`infra/tests/validate_terraform.sh`, `infra/.terraform.lock.hcl`)
and leaves state-concurrency mitigation as procedural-only despite the
research flagging that `use_lockfile` on Vultr Object Storage is
unverified. Several structural inconsistencies between the proposal and
the current code are also not acknowledged, creating a risk that
follow-up implementation quietly re-introduces the "we will figure it
out" pattern this proposal is trying to prevent.

## Findings

### 1. Hetzner-era test contract is invisible to the proposal — MEDIUM

`infra/tests/validate_terraform.sh` still asserts `hcloud` provider
source, `hetznercloud/hcloud` version pin, `provider "hcloud"` block,
`hcloud_token` variable, `kube-hetzner` module reference,
`control_plane_count = 1`/`= 3`, and `location = "fsn1"` for staging and
production. The proposal reorganises `infra/` into modules and
environment roots (section 4) but never mentions this test script or
what should replace it. If the implementation phase keeps the proposal
literal, the new layout will land next to a test script that still
validates the old platform, and the natural path of least resistance is
to silently delete it rather than rewrite it against the new contract.

*Recommendation*: the proposal should explicitly require replacing
`validate_terraform.sh` with a VKE-aware equivalent (or state that it is
retired and what replaces it), so the implementation phase cannot treat
the stale file as "out of scope."

### 2. Stale `.terraform.lock.hcl` not addressed — LOW

`infra/.terraform.lock.hcl` still pins
`registry.opentofu.org/hetznercloud/hcloud`. The proposal calls for no
Hetzner assumptions but does not require the lock file to be
regenerated. Because OpenTofu can tolerate extra locked providers, this
could remain latent and produce confusing drift later.

*Recommendation*: definition-of-done should include "provider lock file
contains only the providers this phase declares."

### 3. State-concurrency mitigation is procedural only — MEDIUM

Research (`phase1-environments-and-benchmarks.md` §4) explicitly flagged
that Vultr's own guide says Object Storage "does not provide file
locking" while the local backend enables `use_lockfile = true`, and
listed "Is the current Terraform backend locking model accepted for a
one-person-plus-agents workflow?" as an open question. The proposal
acknowledges the concern (risk #7) but mitigates with only "one writer
per environment at a time." For a workflow where agents can easily run
concurrently, a human-memorable rule is a known-weak control. This is
the canonical shape of a "we will be careful" shortcut.

*Recommendation*: either verify and document that `use_lockfile` on
Vultr Object Storage actually works, or introduce a mechanical barrier
(e.g. a CI concurrency group per environment, or a documented
pre-apply lock-check command) before Phase 1 is considered done.

### 4. Proposal/code module naming drift is unacknowledged — LOW

Proposal §4 names `modules/vke-cluster` and `modules/object-storage`.
Current code already contains empty placeholder directories
`infra/modules/{cluster,networking,storage}/`. The proposal neither
adopts the existing names nor deletes/renames the empty dirs. The
implementation phase will have to make that call without guidance,
which is the small-scale version of "undefined becomes figure-it-out
later."

*Recommendation*: proposal should state which placeholder directories
are renamed, which are retired, and whether `networking` survives at
all (it is not mentioned anywhere in v2).

### 5. Ingress controller unselected — LOW

The proposal acknowledges VKE ships no ingress controller and says
"the cluster foundation must support a chosen ingress controller"
(§3). No selection is made. DoD (§11) does not require an ingress
controller to be installed — only that LoadBalancer services provision
correctly. That is defensible as Phase 1 scope, but it leaves a
visible "TBD" in the foundation that is easy to drift into "we will
pick later" territory once Phase 2 starts.

*Recommendation*: either commit to a default (e.g. ingress-nginx) with
a sentence of justification, or explicitly mark ingress-controller
selection as a Phase 2 prerequisite, so the gap is tracked rather than
forgotten.

### 6. Benchmark gate is defined but structurally non-functional in Phase 1 — LOW

§8 defines metrics, 20%/25% regression thresholds, a storage path, and
mandates one successful staging run in DoD. That is much better than
"we will benchmark later." However:

- Regression-vs-baseline gates require a prior accepted run. Phase 1
  DoD requires exactly one run. The comparison logic the proposal
  defines cannot fire in Phase 1 and is not exercised until Phase 2+.
- Threshold numbers (20% / 25%) are not sourced and not tied to any
  SLO. They read as reasonable defaults, which is exactly the shape of
  numbers that quietly become permanent.
- Pipeline latency, DB latency, and full-application API latency are
  "defined now, fully exercised later." This is legitimate because
  Phase 1 deploys no such services — but the proposal should say so
  explicitly rather than leaving the reader to infer it.

*Recommendation*: label threshold numbers as provisional with a
specific review moment (e.g. "re-evaluated after first three staging
runs on real services"), and make the deferral of application-level
benchmarks conditional on services existing, not on a vague later
phase.

### 7. `hcloud-volumes` defect is named but not listed as a v2 change item — LOW

Proposal §7 and risk #3 correctly call out that
`k8s/base/monitoring/helmrelease.yaml` still sets
`storageClassName: hcloud-volumes` in three places. The proposal says
this "must be fixed as part of the foundation implementation that
follows this proposal." Strictly this is not a shortcut (the fix is
required), but phrasing it as "follows this proposal" rather than
putting it in DoD (§11) weakens accountability. The DoD does include
"monitoring PVCs use valid Vultr storage classes," so this is covered —
but only implicitly.

*Recommendation*: tighten DoD to name the specific file paths whose
storage class must change, so the fix cannot be overlooked.

### 8. Autoscaling-as-contract framing is handled well — NO RISK

Proposal §3 explicitly rejects "mechanical autoscaling" framing,
explains that `max_nodes > min_nodes` is the narrow contract,
distinguishes node-pool autoscaling from workload autoscaling (HPA /
KEDA), and defers workload autoscaling to later phases with a clear
reason. This is the template for how the other shortcut risks should
have been handled.

### 9. Sealed-secrets bootstrap-vs-permanent is handled well — NO RISK

Proposal §6 explicitly states sealed-secrets is bootstrap-only,
Infisical is long-term, no compatibility shim, and the old path is
removed when the new path is accepted. This directly matches the
"No Backwards Compatibility" rule in AGENTS.md and is the opposite of
the permanence drift the prompt warns about.

## Overall assessment

Phase 1 v2 is visibly a reaction against the softness in the original
Phase 1 proposal, and on the biggest three shortcut vectors
(sealed-secrets, autoscaling, benchmarking) the proposal is tighter
than typical foundation work. It avoids feature-flag permanence, gives
benchmarking a real contract, and names storage-class and Flux-topology
defects head-on.

The reason the verdict is MEDIUM rather than LOW is narrower: the
proposal cleans up the visible Hetzner references (`hcloud-volumes`,
Hetzner-specific reasoning) but leaves a second tier of Hetzner-era
artefacts (`validate_terraform.sh`, `.terraform.lock.hcl`,
placeholder `infra/modules/*` dirs) unaddressed, and downgrades the
research-flagged state-locking question to a procedural rule. Each
individual item is small; together they look like the exact "residue
from the previous platform that nobody formally owned" pattern that
caused v1 to be superseded.

## What LOW requires

1. Proposal explicitly names `infra/tests/validate_terraform.sh` as
   retired or rewritten, with a successor described (or a line in DoD
   stating no test references Hetzner providers, modules, locations,
   or variable names).
2. Proposal or DoD requires `infra/.terraform.lock.hcl` to contain
   only providers actually declared by Phase 1 v2.
3. State-concurrency mitigation (risk #7) upgraded from "one writer at
   a time" to a mechanical control — either verified `use_lockfile`
   behaviour on Vultr Object Storage with a citation, or a CI/tooling
   barrier that prevents concurrent env-level apply.
4. Module-layout drift resolved: proposal either renames existing
   `infra/modules/{cluster,networking,storage}` to match v2 names, or
   states which are retired. `networking` in particular needs a
   disposition since it is not referenced anywhere in v2.
5. Ingress controller either selected with one-line justification or
   explicitly deferred to Phase 2 with a named owner/prerequisite so
   it is tracked rather than implicit.
6. Benchmark thresholds (20% / 25%) labelled provisional with a
   defined review moment, and application-level benchmark deferral
   tied to "services do not yet exist" rather than to a later phase
   label.
7. DoD (§11) names the specific storage-class fix site
   (`k8s/base/monitoring/helmrelease.yaml`) instead of relying on the
   implicit "valid Vultr storage classes" clause.

None of these require redesign. They are mostly proposal-text
tightenings that move deferred decisions out of the "we will figure it
out" slot and into either a named commitment or a named later phase.
