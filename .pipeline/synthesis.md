# INIT-008 Phase 2 Synthesis — Platform Bootstrap

Purpose: bridge Phase 1 research into a proposal-ready decision surface for
INIT-008. This document does not choose implementation mechanics. It records
what the Phase 3 proposal must settle, what defaults already have evidence
behind them, and what gaps still block a binding proposal.

Primary synthesis inputs:

- `.pipeline/research.md`
- `plans/platform-decisions-overlay.md`
- `infra/README.md`
- `product-strategy/tickets/PHASE_5_INDEX.md`
- `product-strategy/tickets/INIT-001.md` through `INIT-007.md`
- `product-strategy/engineering roadmap.md`

Constraint reminders carried forward from the source set:

- Vultr is the locked infrastructure substrate for INIT-008 work; proposal
  work is not allowed to reopen provider selection. Evidence:
  `.pipeline/research.md:145-152, 173-185, 196-218`;
  `infra/README.md:1-3`.
- INIT-008 is locally verified only. No deployment, no production apply, and
  no visible environment mutation are in scope for this phase. Evidence:
  `product-strategy/tickets/PHASE_5_INDEX.md:3-4, 24-30, 32-40`;
  `.pipeline/research.md:354-433`.
- The live repo state, not older draft material, is the authoritative starting
  point for the proposal. Evidence: `.pipeline/research.md:145-152, 194-320,
  469-476`.

## 1. Initiative framing (INIT-008 ticket sketch)

This section mirrors the existing INIT ticket shape while adapting it to the
Phase 5 platform-substrate context.

### Strategic Context

**Subsystem:** Deployment Substrate; Platform Bootstrap
**Phase:** Phase 5 entry initiative; recovery of unticketed Phase 0 substrate
**Executive priority:** First dependency in the Phase 5 initiative chain; all
later deployment-substrate initiatives assume a bootstrap contract exists.

Phase 0 foundation was never turned into a dedicated initiative, but the
product roadmap already shipped INIT-001 through INIT-007 against the implied
existence of a working platform substrate. The current repo proves partial
bootstrap intent through checked-in OpenTofu assets, yet still contains split
authority, incomplete remote-state handoff, and unresolved bootstrap
acceptance questions. INIT-008 exists to convert that implied substrate into a
proposal-ready initiative with a bounded local-verification contract. Evidence:
`product-strategy/tickets/PHASE_5_INDEX.md:1-23`;
`product-strategy/engineering roadmap.md:5-10, 17-33, 97-117`;
`.pipeline/research.md:30-164, 322-340, 492-498`.

### Justification Chain

#### Phase 0 Trigger

The engineering roadmap names "deployable service substrate aligned to
`infra/`" as a Phase 0 deliverable and requires hosting formalization,
operational secret management, and a functional shared test harness before
Phase 0 is complete. INIT-008 is the first initiative in Phase 5 precisely
because the repo already contains `infra/` roots, but not yet a settled
bootstrap contract. Evidence:
`product-strategy/engineering roadmap.md:9, 19-33, 97-117`;
`product-strategy/tickets/PHASE_5_INDEX.md:10-23`.

#### Dependency Chain

Phase 0 must complete before Phase 1 begins, but the feature roadmap already
contains Phase 1 through Phase 4 tickets. Phase 5 therefore acts as a catch-up
execution lane for the unticketed foundation. INIT-008 is dependency head for
the later GitOps, delivery, ingress, data-plane, auth, and workload
initiatives because those initiatives assume a platform cluster, remote state,
and environment roots already exist as a clean baseline. Evidence:
`product-strategy/engineering roadmap.md:119-125`;
`product-strategy/tickets/PHASE_5_INDEX.md:3-4, 10-23, 32-40`;
`.pipeline/research.md:181-183, 271-285, 492-498`.

#### Problem Axis

The current repo has a real bootstrap footprint:

- `infra/bootstrap/state-backend` exists and validates locally.
- `infra/modules/platform-network` and `infra/modules/platform-cluster` exist.
- `infra/environments/dev`, `staging`, and `production` exist.

The repo does not yet answer the proposal-critical questions that make that
footprint operationally coherent:

- Which surface formally ratifies Vultr as the authoritative host.
- How the backend bucket actually comes to exist.
- How environment state is isolated.
- Which environment and sizing baseline INIT-008 is validating first.
- What locking, credential custody, DNS, and public endpoint expectations are
  actually inside the initiative boundary.

Evidence: `.pipeline/research.md:32-143, 145-193, 334-340, 443-476`.

#### Proposal Mechanism

The proposal does not need to invent a new subsystem. It needs to settle the
contract around the existing platform-bootstrap surfaces already present in the
repo:

- bootstrap root
- remote-state handoff into environment roots
- shared VPC module
- shared VKE module
- environment-root parameterization
- local verification surface

That mechanism stays explicitly narrower than later Phase 5 initiatives. Flux,
Buildkite, workload manifests, auth, ingress, database operators, observability,
and application-cluster composition remain separate initiatives. Evidence:
`product-strategy/tickets/PHASE_5_INDEX.md:14-22`;
`.pipeline/research.md:109-119, 181-182, 271-285, 477-490`.

#### Executive Priority

**Pain severity:** structural-gap. The repo has infra intent, but the current
state is not yet a proposal-grade, authority-clean substrate.

**Competitive position:** not market-driven; this is roadmap debt retirement.
Its value is internal dependency unlock rather than external differentiation.

**Dependency depth:** 0 within Phase 5 entry. Later platform initiatives depend
on its output surface.

**Operational risk of delay:** active-harm to roadmap sequencing. The longer
INIT-008 stays ambiguous, the longer later Phase 5 initiatives inherit split
authority and stale assumptions.

**Opportunity cost:** Every downstream initiative keeps paying bootstrap
ambiguity tax instead of treating `infra/` as a settled foundation.

Evidence: `product-strategy/tickets/PHASE_5_INDEX.md:10-23, 32-40`;
`product-strategy/engineering roadmap.md:9, 97-117, 119-125`;
`.pipeline/research.md:145-193, 322-340, 492-498`.

#### Engineering Assessment

**Effort:** initiative-level L-XL (leans L) based on the engineering roadmap's
"deployable service substrate aligned to `infra/`" estimate, narrowed here to
bootstrap-only scope. Individual candidate slices range from S to L.

**Prototyping:** no separate prototype is currently justified from the source
set; the open questions are mostly authority, scope, and contract questions
rather than unknown external behavior. The one implementation-time unknown that
still needs diligence is VKE/VPC attachment behavior, which research classifies
as an implementation blocker rather than a proposal blocker.

**Risk:** Medium-high until the proposal settles remote-state completeness,
state isolation, lock posture, and credential custody.

**Foundation dependencies:** none earlier in Phase 5; INIT-008 is itself a
foundation initiative for INIT-009 through INIT-016.

Evidence: `product-strategy/engineering roadmap.md:97-100`;
`.pipeline/research.md:447-452, 458-476, 492-498`.

### Scope (in)

The proposal for INIT-008 should treat the following as in-scope:

- Formalizing the authoritative Vultr/OpenTofu bootstrap record for this
  initiative so later docs stop conflicting. Evidence:
  `.pipeline/research.md:147-152, 173-185, 196-208, 458-466, 471-476`.
- Settling the state-backend bootstrap contract, including required inputs,
  actual resources, operator outputs, and the unresolved bucket-existence seam.
  Evidence: `.pipeline/research.md:43-62, 372-389, 405-413, 465, 475`.
- Settling the remote-state handoff into `backend.tfbackend` files, including
  placeholder replacement, runtime credentials, and environment state
  isolation. Evidence:
  `.pipeline/research.md:120-132, 390-413, 448, 451, 462, 475`.
- Settling the environment-root baseline for the first validated environment
  and confirming how `dev`, `staging`, and `production` are normalized against
  that choice. Evidence:
  `.pipeline/research.md:88-119, 101-107, 460-462, 487-488`.
- Freezing the INIT-008 boundary around platform VPC + VKE + object storage +
  state backend, without absorbing later application-cluster or service-layer
  concerns. Evidence:
  `.pipeline/research.md:109-119, 181-182, 271-285, 310-320, 450`.
- Defining a local verification contract for bootstrap and environment roots
  that is stronger than ad hoc doc claims and still avoids deployment. Evidence:
  `.pipeline/research.md:354-433, 488`.

### Scope (out)

The proposal for INIT-008 should treat the following as explicitly deferred:

- Any real Vultr apply or deployment workflow. Evidence:
  `product-strategy/tickets/PHASE_5_INDEX.md:3-4, 28-29, 40`;
  `.pipeline/research.md:356-368`.
- Flux install, GitOps layout, and reconciliation mechanics. Those belong to
  INIT-009. Evidence:
  `product-strategy/tickets/PHASE_5_INDEX.md:15`;
  `.pipeline/research.md:117-118, 177, 275, 450`.
- Container build pipeline and Buildkite CI/CD. Those belong to INIT-010 and
  INIT-011. Evidence:
  `product-strategy/tickets/PHASE_5_INDEX.md:16-17`;
  `.pipeline/research.md:178, 199, 301`.
- Ingress, TLS, and broad north-south routing. Those belong to INIT-012 unless
  the proposal narrowly justifies a minimal bootstrap exception. Evidence:
  `product-strategy/tickets/PHASE_5_INDEX.md:18`;
  `.pipeline/research.md:463-464`.
- Data-plane workloads such as CloudNativePG and deploy-time migrations. Those
  belong to INIT-013. Evidence:
  `product-strategy/tickets/PHASE_5_INDEX.md:19`;
  `.pipeline/research.md:338`.
- Application workloads and workload manifests. Those belong to INIT-014.
  Evidence: `product-strategy/tickets/PHASE_5_INDEX.md:20`;
  `product-strategy/engineering roadmap.md:97-110`.
- Auth stack decisions or implementation. Those belong to INIT-015 and are
  already locked separately in the overlay. Evidence:
  `product-strategy/tickets/PHASE_5_INDEX.md:21`;
  `plans/platform-decisions-overlay.md:6-13`.
- Observability stack selection or rollout. That belongs to INIT-016. Evidence:
  `product-strategy/tickets/PHASE_5_INDEX.md:22`.
- Crossplane installation or application-cluster compositions. Those belong to
  the later application-cluster initiative. Evidence:
  `.pipeline/research.md:118, 181-182, 275, 314-320`.

### Acceptance Criteria

When INIT-008 is complete, the observable outcomes should be:

- [ ] One authoritative decision surface ratifies the Vultr/OpenTofu bootstrap
      baseline, and no active Phase 5 input still treats hosting as open.
- [ ] The bootstrap root has an explicit contract covering what it creates, the
      inputs it requires, the outputs it hands off, and how bucket existence is
      guaranteed for remote state.
- [ ] The proposal names the state isolation model for `dev`, `staging`, and
      `production`, rather than inheriting the current shared-bucket assumption
      by accident.
- [ ] The proposal fixes the first validated environment and baseline sizing so
      environment roots are intentionally parameterized rather than merely
      checked in.
- [ ] The proposal defines what INIT-008 claims about locking, credential
      custody, DNS ownership, and public reachability, and what it explicitly
      leaves to later initiatives.
- [ ] A local verification surface exists for the bootstrap root and all three
      environment roots, with no committed backend credentials and no required
      deployment step.
- [ ] The initiative remains bounded to platform bootstrap and does not absorb
      Flux, CI/CD, ingress, auth, application workloads, or data-plane work.

Evidence for the acceptance framing:
`.pipeline/research.md:334-340, 356-433, 443-476, 492-498`;
`product-strategy/tickets/PHASE_5_INDEX.md:14-22, 32-40`.

## 2. Binding decisions (D1–D12)

| ID | Decision | Options surfaced in research | Preferred direction (if any) | Why it's binding now | Traceability |
| --- | --- | --- | --- | --- | --- |
| D1 | Name the single authoritative surface that ratifies Vultr for INIT-008. | (a) `DECISIONS.md` canonical with overlay/README aligned; (b) overlay canonical with roadmap revised; (c) split authority persists. | (a) `DECISIONS.md`, because the engineering roadmap explicitly requires it while the repo already behaves as Vultr-specific. | Later Phase 5 proposals cannot inherit a contradiction about whether hosting is settled. | `.pipeline/research.md:147-152, 173-185, 198-208, 334-336, 458-466, 471-476`; `product-strategy/engineering roadmap.md:9, 102-104` |
| D2 | Commit to the INIT-008 boundary versus later Phase 5 initiatives. | (a) Narrow bootstrap boundary around VPC/VKE/object storage/state backend/env roots; (b) absorb GitOps/ingress/secrets/app-cluster concerns; (c) hybrid boundary. | (a), matching the Phase 5 index and current platform-bootstrap boundary. | Scope control determines acceptance criteria, slice count, and whether INIT-008 remains tractable. | `.pipeline/research.md:109-119, 177-182, 271-285, 310-320, 450, 477-490`; `product-strategy/tickets/PHASE_5_INDEX.md:14-22` |
| D3 | Choose how the remote-state bucket is guaranteed to exist. | (a) Bucket lifecycle in bootstrap root; (b) bucket lifecycle outside Terraform with bootstrap only emitting connection material; (c) separate root/later slice; (d) keep assuming existence implicitly. | `open` | Environment roots cannot credibly target remote state until the repo stops assuming `humility-tfstate` without a named existence path. | `.pipeline/research.md:52-62, 120-132, 376-380, 405-413, 465, 474-475, 496-497` |
| D4 | Choose the environment state isolation model. | (a) One bucket with distinct keys; (b) multiple buckets in shared backing; (c) separate object-storage instances per environment; (d) another explicit model. | `open`; current repo only reflects "same bucket, different keys" as an unchecked default. | State isolation is a core bootstrap guarantee and an explicit proposal blocker. | `.pipeline/research.md:122-130, 398-413, 451, 462, 475, 498` |
| D5 | Name the first validated bootstrap target environment. | `dev`, `staging`, `production`, or simultaneous multi-environment validation. | `dev`, because README already describes it as the always-on iteration environment and Phase 5 verification is local-only. | The proposal cannot write coherent acceptance criteria without naming the first target. | `.pipeline/research.md:103-107, 458-461`; `infra/README.md:35-38` |
| D6 | Choose whether the checked-in baseline parameters are affirmed or revised. | (a) Preserve current `ewr`, Kubernetes version, and node-count baselines; (b) revise one or more roots; (c) abstract into a new shared parameter model. | (a) has the strongest current evidence, but the proposal still has to affirm or replace it explicitly. | Otherwise the roots remain accidental checked-in state rather than intentional substrate. | `.pipeline/research.md:101-107, 461, 487-488` |
| D7 | Define INIT-008's bootstrap credential custody boundary. | (a) Bounded operator custody contract inside INIT-008; (b) stronger local secret-handling mechanics now; (c) defer custody to later secrets/GitOps work; (d) leave custody undocumented. | (a), because the repo already exposes sensitive outputs without a secrets platform and the proposal boundary stays narrower than later secrets initiatives. | Credential custody is both a Phase 0 acceptance gap and a proposal blocker. | `.pipeline/research.md:131, 339, 449, 498`; `plans/proposals/platform-bootstrap.md:257-260, 302-315` |
| D8 | Choose INIT-008's locking and restore posture for remote state. | (a) Claim working locking in the selected backend path; (b) claim a bounded non-locking or alternative-lock posture; (c) change the state-backend contract so locking moves out of the current path. | `open` | Current platform-bootstrap material treats locking and restore procedure as exit criteria, so the proposal cannot stay vague. | `.pipeline/research.md:448, 498`; `plans/proposals/platform-bootstrap.md:252-256, 297-300` |
| D9 | Choose whether any DNS work belongs to bootstrap. | (a) No DNS in INIT-008; (b) narrow bootstrap DNS exception; (c) broader DNS ownership in bootstrap. | (a), unless the proposal can justify a minimal exception, because the checked-in INIT-008 surface has no DNS resources and ingress is already ticketed later. | DNS ownership changes the initiative boundary and can silently turn bootstrap into ingress work. | `.pipeline/research.md:111-118, 463, 477-490`; `product-strategy/tickets/PHASE_5_INDEX.md:18` |
| D10 | Choose whether INIT-008 requires only reachability or a reserved public endpoint. | (a) Reachability plus network attachment only; (b) reserve a minimal public endpoint now; (c) broader north-south exposure in bootstrap. | (a), because no dedicated public-endpoint resource exists now and later ingress work is already separated. | This directly affects scope, networking expectations, and whether ingress becomes a hidden dependency. | `.pipeline/research.md:464, 477-490`; `product-strategy/tickets/PHASE_5_INDEX.md:18` |
| D11 | Define the local verification contract. | (a) Current validation-heavy surface only; (b) validation plus clean `tofu plan` targets for bootstrap and the chosen environment root; (c) broader simulator-heavy verification. | (b), because the Phase 5 index frames INIT-008 around authoring plus `tofu plan`, and research already identifies what clean plan surfaces would target. | Without a named local-verification contract, INIT-008 cannot define observable done-ness while respecting the no-deployment rule. | `.pipeline/research.md:356-433`; `product-strategy/tickets/PHASE_5_INDEX.md:14, 28-29, 37` |
| D12 | Choose INIT-008's provider/version reproducibility posture. | (a) Keep current `>= 1.8.0` and `~> 2.30` constraints as sufficient; (b) tighten reproducibility expectations with a checked-in lock posture; (c) revise provider expectations before proposal scope is fixed. | (b), because older material drifted against provider behavior and no lockfile is currently committed under `infra/`. | Provider-version ambiguity is one reason stale object-storage material persisted; the proposal should define what counts as reproducible bootstrap state. | `.pipeline/research.md:133-144, 227, 239-241, 250-252, 488`; `infra/README.md:39` |

## 3. Gaps that block proposal writing

Each row below restates a Phase 1 research blocker tagged
`BLOCKS_PROPOSAL`, with the closure condition and the actor that can close it.

| Gap | What the gap is | What evidence or user decision closes it | Closure path | Traceability |
| --- | --- | --- | --- | --- |
| G1 | Hosting formalization source of truth is split across overlay, README, and roadmap requirements. | One authority decision that names the canonical source and aligns the other documents to it. | Proposal can close this by adopting the roadmap's `DECISIONS.md` requirement unless the user wants a different authority model. | `.pipeline/research.md:149-152, 183-185, 203-207, 466, 473, 496`; `product-strategy/engineering roadmap.md:9, 104` |
| G2 | Environment backends assume `humility-tfstate`, but bootstrap does not currently create a bucket resource. | A proposal-level choice that explicitly names how bucket existence is guaranteed in the supported path. | Proposal must close this; additional research is only needed if current evidence cannot justify an option. | `.pipeline/research.md:52-62, 124-130, 412, 465, 475, 497` |
| G3 | The repo implies one bucket with per-environment keys, but the proposal has not committed to whether that is the intended isolation model. | A binding choice among the isolation options, with rationale tied to environment ownership and blast radius. | Proposal can close it if the user accepts a default; user call if the tradeoff is considered irreversible. | `.pipeline/research.md:451, 462, 475, 498` |
| G4 | No proposal-authoritative document names which environment INIT-008 validates first. | A proposal statement naming the first target and why it is first. | Proposal can default to `dev` from repo evidence unless the user wants a different entry posture. | `.pipeline/research.md:460`; `infra/README.md:35-38` |
| G5 | The repo has concrete region/version/node values checked in, but the proposal still treats the baseline as open. | Either affirm the checked-in values as the intended baseline or revise them before the proposal closes. | Proposal can close it if it adopts current roots; user call only if a different cost/performance posture is desired. | `.pipeline/research.md:103-107, 461` |
| G6 | Lock acquisition and restore procedure are treated as exit criteria, but the proposal has not yet settled what guarantee INIT-008 is making. | A proposal-level claim about lock support and restore expectations for the chosen backend path. | Additional research may be needed if the current source set cannot justify the claim; the proposal cannot stay silent. | `.pipeline/research.md:448, 498`; `plans/proposals/platform-bootstrap.md:252-256, 297-300` |
| G7 | Sensitive bootstrap outputs exist, but there is no agreed operational custody story within INIT-008's local-only boundary. | A bounded custody contract that says what operators do with bootstrap outputs and what INIT-008 does not claim to automate yet. | User call if stronger-than-manual handling is required now; otherwise the proposal can define the bounded contract itself. | `.pipeline/research.md:131, 339, 449, 498`; `plans/proposals/platform-bootstrap.md:257-260, 302-315` |
| G8 | Current code has no DNS resources, but the proposal still has not settled whether bootstrap must own any DNS records. | A direct statement that DNS is out, or a narrowly bounded statement of the exact DNS exception kept in scope. | User call is preferable because bringing DNS in changes initiative scope and dependency boundaries. | `.pipeline/research.md:463` |
| G9 | Current bootstrap code does not provision a dedicated public endpoint, but the proposal still asks whether bootstrap needs one. | A binding statement that INIT-008 is either reachability-only or reserves a minimal public endpoint. | User call is preferable because this changes scope and could pull ingress concerns forward from INIT-012. | `.pipeline/research.md:464` |
| G10 | Older object-storage-fix research and proposals still describe a bootstrap bucket resource that no longer exists in the repo. | Explicit displacement of the stale docs in proposal inputs and a proposal statement that live repo state is the operative truth. | Proposal should close this directly; no user call is needed unless the older docs are to remain active authority. | `.pipeline/research.md:150-152, 225-243, 265-280, 292-296, 474, 497` |

## 4. Slice decomposition proposal

Research already suggested a separable decomposition. The refined version below
keeps the initiative at six candidate slices, which is the high end of the
requested range. If proposal work discovers a seventh materially independent
slice, that is a signal INIT-008 itself should split rather than quietly widen.

Note: `.pipeline/proposal.md` supersedes the slice names below. The evidence
anchors remain valid, but the final names are `SLICE-026: Channel Contract and
Registry Skeleton`, `SLICE-027: Platform Template and Dev Channel Root`, and
`SLICE-028: State-Backend and Remote-State Handoff Contract`.

| Name | Scope summary | Dependencies on other slices | Local-verification surface | Magnitude estimate | Evidence anchor |
| --- | --- | --- | --- | --- | --- |
| `SLICE-025: Authority Alignment and Input Reconciliation` | Formalize the authoritative Vultr/OpenTofu record for INIT-008 and displace stale bootstrap inputs that no longer match live repo state. | none | Document diff plus repo-consistency checks, with `infra/tests/validate_platform_bootstrap.sh` still passing against the active code path. | S | `.pipeline/research.md:145-193, 194-320, 471-476, 490-496` |
| `SLICE-026: State-Backend Bootstrap Contract` | Settle what `infra/bootstrap/state-backend` is responsible for creating, what inputs it requires, what outputs operators receive, and how the bucket-existence seam is characterized. | `SLICE-025` | `cd infra/bootstrap/state-backend && tofu fmt -check && tofu init -backend=false && tofu validate` | M | `.pipeline/research.md:43-62, 372-389, 405-413, 483` |
| `SLICE-027: Remote-State Handoff and Isolation` | Settle how environment roots consume bootstrap outcomes, replace backend placeholders, isolate state across environments, and define what locking/restore posture INIT-008 claims. | `SLICE-026` | `tofu init -backend=false && tofu validate` for all environment roots, plus a clean `tofu plan` target for the chosen first environment once runtime inputs are supplied locally. | M-L (leans M) | `.pipeline/research.md:120-132, 390-413, 448, 451, 462, 475, 484` |
| `SLICE-028: Platform Network and VKE Module Baseline` | Freeze the INIT-008 responsibility of the shared VPC and VKE modules, including current outputs, provider/version posture, and the downstream contract later initiatives inherit. | `SLICE-025` | Module assertions in `infra/tests/validate_platform_bootstrap.sh`, plus environment-root `tofu validate` runs that exercise both modules. | M | `.pipeline/research.md:63-119, 133-144, 394-396, 485-488` |
| `SLICE-029: Environment-Root Normalization` | Align `dev`, `staging`, and `production` roots with the first validated environment choice and intended baseline parameters, so the three roots read as deliberate substrate variants rather than accidental carryover. | `SLICE-027`, `SLICE-028` | `tofu fmt -check`, `tofu init -backend=false`, and `tofu validate` for `dev`, `staging`, and `production`. | M | `.pipeline/research.md:88-132, 356-365, 460-462, 487` |
| `SLICE-030: Local Verification Harness Hardening` | Raise the checked-in local proof surface so INIT-008 done-ness is demonstrated by repeatable validation and plan targets, not only by repo structure and historical notes. | `SLICE-026`, `SLICE-027`, `SLICE-028`, `SLICE-029` | `infra/tests/validate_platform_bootstrap.sh`, per-root `tofu fmt -check`, per-root `tofu init -backend=false`, per-root `tofu validate`, and the proposal-defined clean `tofu plan` target(s). | M | `.pipeline/research.md:356-433, 488`; `product-strategy/tickets/PHASE_5_INDEX.md:14, 37` |

## 5. Open questions for user

These are the questions most likely to benefit from direct user resolution
before the proposal phase writes a binding design. Where a safe default already
has strong repo evidence, the proposal can choose it and record the default.

### MUST_ANSWER

- State isolation posture: Should INIT-008 treat environment isolation as a
  stronger boundary than the current "same bucket, different keys" pattern, or
  is that keyed model acceptable as the intended baseline? Traceability:
  `.pipeline/research.md:451, 462, 475`.
- DNS/public exposure boundary: Should INIT-008 own any DNS or reserved public
  endpoint surface now, or should all north-south exposure remain deferred to
  INIT-012 unless a later initiative proves it necessary? Traceability:
  `.pipeline/research.md:463-464`;
  `product-strategy/tickets/PHASE_5_INDEX.md:18`.
- Credential custody strength: Is a documented operator custody contract
  sufficient for bootstrap credentials and kubeconfig handoff in INIT-008, or
  do you want a stronger local secret-handling mechanism required before the
  proposal can close? Traceability:
  `.pipeline/research.md:339, 449`;
  `plans/proposals/platform-bootstrap.md:257-260, 302-315`.

### CAN_DEFAULT

- First validated environment: default to `dev` unless you want `staging` or
  `production` to be the first target. Traceability:
  `.pipeline/research.md:460`; `infra/README.md:35-38`.
- Region and node baseline: default to the checked-in `ewr` and current per-root
  node counts unless you want INIT-008 to revise those values now. Traceability:
  `.pipeline/research.md:103-107, 461`.
- Authority record: default to `DECISIONS.md` as the formal host record, with
  overlay and README aligned to it. Traceability:
  `.pipeline/research.md:183-185, 336, 466, 473`;
  `product-strategy/engineering roadmap.md:9, 104`.
- Remote-state input authority: default to treating live repo code and
  `.pipeline/research.md` as authoritative over older object-storage-fix docs.
  Traceability: `.pipeline/research.md:225-243, 265-280, 292-296, 474`.
- Bootstrap scope boundary: default to keeping Flux, Buildkite, ingress, auth,
  workloads, and Crossplane out of INIT-008. Traceability:
  `.pipeline/research.md:177-182, 271-285, 310-320, 450`;
  `product-strategy/tickets/PHASE_5_INDEX.md:15-22`.

## 6. Stale material explicitly displaced

The proposal phase should revise or supersede the following stale or partially
stale materials so INIT-008 stops carrying backward-compatibility assumptions
in its planning inputs.

| Path | Proposal-phase action | Reason | Traceability |
| --- | --- | --- | --- |
| deleted provider-comparison research file | Supersede as active choice input | Useful as historical provider-choice evidence, but hosting is no longer an open proposal question for INIT-008. | `.pipeline/research.md:209-218` |
| `plans/research/vultr-fix-hookpoints.md` | Supersede | Assumes a bootstrap bucket resource exists and frames the problem as a provider bump; live repo no longer matches that state. | `.pipeline/research.md:220-232, 474` |
| `plans/research/vultr-object-storage-fix.md` | Supersede | Describes a stale bug state centered on `vultr_object_storage_bucket` that the checked-in repo no longer contains. | `.pipeline/research.md:233-244, 474` |
| `plans/research/opentofu-providers.md` | Revise for active use | OpenTofu/Vultr conclusions remain useful, but its bucket-resource claims and host-comparison framing are stale for INIT-008 proposal work. | `.pipeline/research.md:245-257` |
| `plans/research/platform-bootstrap-hookpoints.md` | Revise | Its module and ordering analysis remains useful, but the bucket-resource description is stale and must not be carried forward unchanged. | `.pipeline/research.md:258-270` |
| `plans/proposals/platform-bootstrap.md` | Revise | This is the closest current proposal ancestor, but it still relies on unresolved authority cleanup and broader remote-state assumptions than live code proves. | `.pipeline/research.md:271-286` |
| `plans/proposals/vultr-object-storage-fix.md` | Supersede | The live repo already removed the bucket resource instead of taking this proposal's provider-bump path. | `.pipeline/research.md:287-297, 474` |
| `plans/proposals/phase1-foundation.md` | Supersede | Retired provider, self-managed Kubernetes, retired module substrate, and bundled Flux/Kong/bootstrap scope are all displaced by the current Vultr-managed Phase 5 split. | `.pipeline/research.md:298-309` |
| `plans/proposals/app-cluster-provisioning.md` | Revise as boundary input | Its platform/application split remains useful, but it still inherits stale hosting-formalization ambiguity and cannot be treated as clean authority. | `.pipeline/research.md:310-320` |

## Synthesis readout

Proposal writing is ready to proceed once it treats the following as the
binding synthesis result:

- INIT-008 is not a greenfield substrate invention; it is a contract-cleanup
  and scope-fix initiative over an already checked-in Vultr/OpenTofu baseline.
- The proposal's critical work is deciding authority, remote-state completeness,
  state isolation, first-target baseline, custody, and boundary questions.
- The initiative should stay at six candidate slices or fewer. If proposal work
  discovers additional independent slices, the safer interpretation is that the
  initiative boundary is widening and should be split.
- The strongest remaining blockers are not missing code surfaces. They are
  unresolved choices about what the existing code is actually claiming.

Evidence summary:
`.pipeline/research.md:30-164, 173-193, 322-340, 443-498`;
`product-strategy/tickets/PHASE_5_INDEX.md:1-40`;
`product-strategy/engineering roadmap.md:9, 17-33, 97-117`.
