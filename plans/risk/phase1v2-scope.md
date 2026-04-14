# Phase 1 Foundation v2 — Scope risk assessment

## Verdict

**LOW** (with 3 non-blocking observations to raise to the user).

The proposal is well-sized for Phase 1. The 3-environment model
(`dev` persistent, `staging` on-demand, `production` persistent) maps
cleanly to a one-person-plus-agents workflow. Each explicitly
in-scope item is justified, each explicitly out-of-scope item
(HPA/KEDA, Infisical, application-load benchmarks, video QA as a CI
gate) has a defensible deferral. The cost model is realistic at the
stated sizing. Nothing in scope is unreachable; nothing out of scope
blocks Phase 2 outright.

---

## Findings

### 1. Ingress controller is deferred but Phase 2 depends on it — LOW

**Severity:** LOW
**Finding:** §3 "Load balancer behavior" ends with "The cluster
foundation must support a chosen ingress controller; it does not need
to conflate that with the environment model itself." No ingress
controller is named and it is not in the §11 Definition of Done. §12
"What Phase 2 needs" does not list ingress either. Phase 2 will deploy
`api/`, `web/`, and `discord/` services which all require reachable
HTTPS endpoints, so an ingress controller decision is a Phase 2
prerequisite. Deferring the *decision* is reasonable; leaving it
totally unnamed risks a Phase 2 blocker.

**Recommendation:** Add a single sentence to §12 naming ingress
controller selection (`ingress-nginx` or `traefik`) and TLS
(`cert-manager`) as explicit Phase 2 entry requirements the foundation
supports but does not install. No implementation change required to
clear LOW.

### 2. Bootstrap and CI pipeline are unspecified — LOW

**Severity:** LOW
**Finding:** The proposal specifies the *target* Terraform layout and
Flux topology but not the *procedure* that brings a new environment
from `tofu apply` to a Flux-reconciling cluster. `flux bootstrap`
against three different cluster roots is new scope compared to the
current skeleton. The proposal also assumes Buildkite Personal at `$0`
but does not state what Buildkite does in Phase 1 (OpenTofu plan/apply?
Flux image updates? Benchmark runs?). For a one-person-plus-agents
workflow, the bootstrap runbook matters more than the end-state
topology.

**Recommendation:** Either add a §11 DoD item "a documented bootstrap
runbook exists for each environment root" or note explicitly that the
bootstrap procedure is deferred to the implementation phase artifact.
Same for the Buildkite pipeline scope — if CI is `$0/mo` because the
pipeline barely exists yet, say so.

### 3. Module path names in draft code do not match the proposal — LOW

**Severity:** LOW
**Finding:** §4 specifies `infra/modules/vke-cluster/` and
`infra/modules/object-storage/`. The current repo has
`infra/modules/cluster/`, `infra/modules/networking/`, and
`infra/modules/storage/`, all empty. This is a code/proposal
mismatch, not a scope problem, but if the hookpoint phase interprets
`modules/networking/` as in-scope it will silently add a module the
proposal did not request. Networking on VKE is Calico-by-default with
no networking module needed in Phase 1.

**Recommendation:** Proposal is correct. Either drop
`modules/networking/` and `modules/storage/` as stale scaffolding or
rename `modules/cluster/` to `modules/vke-cluster/` and
`modules/storage/` to `modules/object-storage/` during
implementation. No proposal change required.

### 4. Video QA POC is the weakest in-scope item but bounded — LOW

**Severity:** LOW
**Finding:** §9 includes the `Playwright -> video -> Gemini` flow as
a DoD requirement (§11 bullet 11). Everything else in the DoD is
platform substrate; video QA is an application-layer proof that does
not exercise any foundation capability the other items do not already
cover. If Phase 1 slips, this is the natural thing to cut. Keeping it
in is defensible — it proves the `dev` cluster can host Playwright +
egress to Gemini — but it is the lowest-justification scope item.

**Recommendation:** Keep in, but flag to the user that this is the
first item to move to Phase 1.5 if the Terraform/Flux restructure
takes longer than expected. No proposal change required.

### 5. Staging amortization assumption is optimistic — LOW

**Severity:** LOW
**Finding:** §10 amortizes staging to ~$11/mo assuming "four 24-hour
RC runs per month" against a full-month rate of ~$74/mo. The §13.1
risk correctly identifies that staging *left running* breaks the
model. In practice, a cluster that takes ~10 minutes to provision and
`~5-10 minutes` to bootstrap Flux + sealed secrets + monitoring is
unlikely to be torn down mid-investigation. A more realistic
amortization is probably two 2–3 day runs per month, closer to
`$15-20/mo`. Still cheap, but not $11.

**Recommendation:** Soften the §10 amortized figure to a range
(`$11-25/mo`) so budget conversations do not anchor on the low end. No
scope change required.

### 6. State concurrency discipline is a runbook, not a control — LOW

**Severity:** LOW
**Finding:** §4 and §13.7 correctly call out the "one writer per
environment" rule against Vultr Object Storage backends. The
mitigation is procedural ("no concurrent infra mutation against the
same state"). In a one-person-plus-agents workflow, this is the
single most-likely-to-be-violated rule because agents can be spawned
in parallel. This is scoped correctly — solving it with a real
distributed lock is out of scope for Phase 1 — but it needs an
operational check the proposal does not name.

**Recommendation:** Add to §11 DoD or §4 "one operator-level rule
documented in repo root (e.g., AGENTS.md or DECISIONS.md) forbids
parallel `tofu apply` against the same environment." Low effort, high
value against an easily-made mistake.

---

## Overall assessment

Phase 1 v2 is correctly sized. The proposal closes the exact gaps
identified in `plans/research/phase1-environments-and-benchmarks.md`
(Hetzner storage-class assumptions, single-path Flux bootstrap, vague
autoscaling, undefined benchmark contract) and adds structural
contracts (per-cluster Flux roots, per-env OpenTofu roots,
per-env secrets) without smuggling in application-layer scope.

The asymmetric promotion model (`dev -> production` for functional
changes, `dev -> staging -> production` for infra-heavy changes) is
the right shape for a one-operator project. A symmetric `dev ->
staging -> production` default would triple the operator burden
without narrowing real risk. A two-environment model (no staging)
would leave benchmarks and infra validation with no
production-shaped target. This proposal threads both needles.

Items explicitly out of scope (HPA/KEDA, Infisical, ingress
controller choice, identity/policy, application benchmarks, video QA
as release gate) are correctly deferred. None of them is a Phase 2
blocker if the Phase 1 DoD is met, with the single caveat that
ingress selection becomes load-bearing the moment Phase 2 starts.

The cost model at `$129/mo` steady-state is credible given:
- current Vultr public pricing for `vc2-1c-2gb` (~$10) and
  `vc2-2c-4gb` (~$20)
- VKE's $0 managed control plane
- Vultr Object Storage standard tier ($18)
- Buildkite Personal ($0) — which is realistic *only* if the pipeline
  stays minimal, which finding #2 flags.

No scope item is unreachable by a one-person-plus-agents workflow
within a reasonable foundation window. No missing scope item blocks
Phase 2 outright, though ingress selection and bootstrap procedure
(findings #1 and #2) will be the first things Phase 2 needs.

---

## What LOW requires

LOW is already satisfied by the current proposal. No revision is
required to clear the scope gate. The six findings above are
observations to raise to the user as part of the implementation
planning handoff, not gates:

- Findings #1, #2 (ingress + bootstrap): add one-sentence clarifications
  to §12 or §11 during implementation planning, not a proposal rewrite.
- Finding #3 (module names): resolve during implementation by aligning
  code to the proposal names (`vke-cluster`, `object-storage`) and
  removing the stale `networking` stub.
- Finding #4 (video QA POC): keep as first slip candidate if schedule
  pressure appears.
- Finding #5 (staging amortization): soften the cost range in §10 if
  the proposal is revised for any other reason; otherwise leave.
- Finding #6 (state concurrency): add the single-writer rule to
  `AGENTS.md` or `DECISIONS.md` as part of implementation, not a
  proposal change.

All three risk gates (audit, scope, shortcut) must independently
return LOW before implementation starts. This assessment returns LOW
on scope.
