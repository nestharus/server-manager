# INIT-009 Phase 2 Synthesis: GitOps Substrate

Purpose: bridge Phase 1 research into a proposal-ready decision surface for
INIT-009. This is synthesis, not proposal. It records what the proposal must
settle, which defaults are evidence-backed, which questions require user
answers, and which stale GitOps materials must stop acting as live authority.

Primary synthesis inputs:

- `.pipeline/research.md` - Phase 1 evidence over current GitOps, Flux,
  Kustomize, SOPS+age, and local-verification state.
- `memory/channel-template-pattern.md` - channel/template inheritance is the
  binding Phase 5 pattern.
- `memory/local-only-verification.md` - all Phase 5 verification is local-only.
- `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md` - final
  INIT-008 channel-registry and platform-channel precedent.
- `worktrees/init-008-platform-bootstrap/.pipeline/synthesis.md` - D1-D12
  framing precedent.
- `product-strategy/tickets/INIT-001.md` - initiative ticket shape.
- `product-strategy/tickets/PHASE_5_INDEX.md` - Phase 5 boundaries and
  INIT-009 placement.

Constraint reminders carried forward:

- Flux CD is locked as the GitOps reconciler. Evidence:
  `.pipeline/research.md:14-20, 225-236`.
- INIT-009 is scoped to Flux CD, Kustomize layout, and SOPS+age secrets.
  Evidence: `.pipeline/research.md:14-20, 225-236`;
  `product-strategy/tickets/PHASE_5_INDEX.md:14-22`.
- Buildkite, container delivery, ingress, data plane, app workloads, auth, and
  observability are later Phase 5 initiatives. Evidence:
  `product-strategy/tickets/PHASE_5_INDEX.md:14-22`.
- Phase 5 verification is local-only: no Vultr apply, no real VKE bootstrap,
  no remote registry push, and no public DNS. Evidence:
  `memory/local-only-verification.md:7-49`;
  `.pipeline/research.md:371-403`.
- Channel/template inheritance replaces hard environments. Flux structures for
  INIT-009 must align with channels, not `dev/staging/production`
  environment roots. Evidence: `memory/channel-template-pattern.md:7-78`;
  `.pipeline/research.md:262-361`.

## 1. Initiative framing (INIT-009 ticket sketch)

This section mirrors the existing INIT ticket shape while adapting it to the
Phase 5 GitOps-substrate context.

### Strategic Context

**Subsystem:** Deployment Substrate; GitOps Substrate
**Phase:** Phase 5 foundation initiative; recovery of unfinished Phase 0
GitOps and secret-management substrate
**Executive priority:** Second dependency in the Phase 5 initiative chain.
INIT-008 creates the channel registry and platform-channel roots that INIT-009
must reconcile through Flux.

Phase 0 acceptance criteria require a deployable service substrate aligned to
`infra/`, operational secret management, and a shared test harness. The current
repo contains a Flux/Kustomize substrate, but it is environment-shaped and
stale against the INIT-008 channel pivot. The repo does not contain a SOPS+age
substrate. INIT-009 exists to turn that partial, stale GitOps footprint into a
channel-aligned, locally verified Flux/Kustomize/SOPS substrate. Evidence:
`.pipeline/research.md:24-223, 434-460`;
`product-strategy/engineering roadmap.md:102-117`;
`product-strategy/tickets/PHASE_5_INDEX.md:1-40`.

### Justification Chain

#### Engineering Roadmap Trigger

The engineering roadmap names "deployable service substrate operational
against the `infra` baseline" and "secret management is operational" as Phase
0 acceptance criteria. Phase 1 research found both are only partial or missing:
the old `k8s/` tree renders but encodes `dev/staging/production`, and no SOPS
or age files exist. Evidence: `.pipeline/research.md:24-223, 434-460`;
`product-strategy/engineering roadmap.md:102-117`.

#### Phase 0 GitOps Acceptance Criteria

INIT-009 directly addresses the GitOps and secret-management gaps left open by
Phase 0:

- deployable substrate is partial because current manifests are stale against
  channel/template inheritance;
- secret management is missing because there is no `.sops.yaml`, no encrypted
  secret fixture, and no local SOPS/age tooling;
- shared test harness is partial because the old topology test validates the
  environment-triad shape instead of channels.

Evidence: `.pipeline/research.md:199-223, 434-460, 482-520`.

#### INIT-009 Ticket Need

INIT-008 establishes platform channels and a channel registry. INIT-009 must
decide how Flux sources, Flux Kustomizations, Kustomize inheritance, encrypted
secret workflows, and local verification attach to that channel registry.
Without this initiative, later Phase 5 work has no stable GitOps target for
container delivery, Buildkite validation, ingress, data-plane operators, or
application workloads. Evidence: `.pipeline/research.md:262-361, 521-606`;
`memory/channel-template-pattern.md:67-78`;
`product-strategy/tickets/PHASE_5_INDEX.md:14-22`.

### Scope (in)

The proposal for INIT-009 should treat the following as in-scope:

- Flux source and Kustomization topology for channel-aligned local
  reconciliation. Evidence: `.pipeline/research.md:262-361, 521-547`.
- Kustomize layout that mirrors channel parent inheritance without preserving
  hard environment roots. Evidence: `memory/channel-template-pattern.md:34-78`;
  `.pipeline/research.md:269-361, 548-558`.
- Disposition of the existing `k8s/` tree, which is valid enough to render but
  stale against channels. Evidence: `.pipeline/research.md:24-223, 249-257`.
- SOPS+age bootstrap workflow and local verification target. Evidence:
  `.pipeline/research.md:199-223, 231-236, 559-570`.
- Local-only Flux verification using `flux check --pre`, a kind/k3d local
  cluster, Flux install/reconcile, Kustomize build, and SOPS decrypt. Evidence:
  `memory/local-only-verification.md:7-49`; `.pipeline/research.md:371-431`.
- Test and drift/boundary checks that replace the old environment-triad
  assertions with channel assertions. Evidence:
  `.pipeline/research.md:126-198, 482-520, 572-588`.
- Documentation of the handoff surfaces later INIT-010 through INIT-014 consume
  without absorbing those initiatives. Evidence:
  `memory/channel-template-pattern.md:71-74`;
  `product-strategy/tickets/PHASE_5_INDEX.md:14-22`.

### Scope (out)

The proposal for INIT-009 should treat the following as explicitly deferred:

- Buildkite pipeline authoring or CI execution. That is INIT-011. Evidence:
  `product-strategy/tickets/PHASE_5_INDEX.md:16-17`;
  `.pipeline/research.md:231-236, 515-520`.
- Container image build, tagging, registry push, or smoke-run delivery. That is
  INIT-010 and remains local-only when it arrives. Evidence:
  `product-strategy/tickets/PHASE_5_INDEX.md:16`;
  `memory/local-only-verification.md:9-18`.
- Ingress, TLS, public DNS, and north-south routing. That is INIT-012.
  Evidence: `product-strategy/tickets/PHASE_5_INDEX.md:18`;
  `memory/local-only-verification.md:23-49`.
- Data-plane operators, migrations, and Postgres runtime. That is INIT-013.
  Evidence: `product-strategy/tickets/PHASE_5_INDEX.md:19`.
- Application workloads for `services/api` and `services/discord`. Those are
  INIT-014 even if INIT-009 creates empty or placeholder-ready GitOps slots.
  Evidence: `product-strategy/tickets/PHASE_5_INDEX.md:20`;
  `memory/channel-template-pattern.md:73`.
- Auth stack and observability stack rollout. Those are INIT-015 and INIT-016.
  Evidence: `product-strategy/tickets/PHASE_5_INDEX.md:21-22`.
- Real Vultr VKE bootstrap, remote cluster reconciliation, remote image push,
  or public-audience publish. Phase 5 is local-only. Evidence:
  `memory/local-only-verification.md:23-49`;
  `.pipeline/research.md:396-403`.

### Acceptance Criteria

When INIT-009 is complete, the observable outcomes should be:

- [ ] The proposal names the channel-to-Flux mapping and Flux Kustomization
      cardinality without relying on `dev/staging/production` environments.
- [ ] The active GitOps layout aligns with INIT-008 channel registry outputs
      and displaces or deletes the old environment-shaped `k8s/` tree.
- [ ] Kustomize inheritance maps to channel parent inheritance or an explicitly
      documented channel-resolution handoff.
- [ ] Flux source and Kustomization resources have a locally verifiable source
      path, cadence, prune/wait behavior, and drift policy.
- [ ] SOPS+age has a working local substrate: `.sops.yaml`, age recipient
      policy, encrypted sample or fixture, and local decrypt verification.
- [ ] The verification harness runs locally against kind or k3d and includes
      `flux check --pre`, Flux install/reconcile, Kustomize build, and SOPS
      decrypt where tools are available.
- [ ] Missing toolchain prerequisites are either installed by an INIT-009 slice
      or documented as explicit operator prerequisites.
- [ ] The initiative remains bounded to GitOps substrate and does not absorb
      Buildkite, container delivery, ingress, data-plane, or app workloads.

Evidence for the acceptance framing:
`.pipeline/research.md:371-431, 434-520, 521-606`;
`memory/local-only-verification.md:7-49`;
`product-strategy/tickets/PHASE_5_INDEX.md:14-22`.

## 2. Binding decisions (D1-D12)

### D1 - Channel-to-Flux mapping

- Options: (a) one Flux Kustomization per channel; (b) one root
  Kustomization with per-channel overlays; (c) hybrid source root plus
  per-channel child Kustomizations.
- Preferred: open; the proposal must bind this after accounting for
  INIT-008's channel registry and local-only dev channel.
- Why binding: This decides every downstream GitOps path, Flux object name,
  and local reconciliation test. It also determines whether later INIT-014
  workload manifests inherit channel configuration cleanly.
- Traceability: `.pipeline/research.md:262-361, 463-472`;
  `memory/channel-template-pattern.md:67-78`;
  `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:25-46, 72-127`.

### D2 - Flux Kustomization cardinality

- Options: (a) one Flux Kustomization per channel; (b) one Flux
  Kustomization per channel per cluster role; (c) one source plus multiple
  reconciled component Kustomizations inside each channel.
- Preferred: open; research explicitly flags the ambiguity between "per
  channel" and "per channel plus cluster role."
- Why binding: The old GitOps tree has app/control cluster roots. The channel
  pattern says Kustomizations align with channels. The proposal must decide
  whether cluster role remains a Flux cardinality dimension or becomes an
  internal Kustomize composition detail.
- Traceability: `.pipeline/research.md:126-198, 337-344, 469-472`;
  `memory/channel-template-pattern.md:69-74`.

### D3 - Local cluster choice

- Options: (a) kind; (b) k3d; (c) support both in scripts/tests.
- Preferred: `kind` can default if the user does not choose, because neither
  tool is installed and Phase 5 references kind/k3d generically.
- Why binding: Flux install/reconcile verification needs one executable local
  cluster target. Supporting both from day one may widen the harness.
- Traceability: `.pipeline/research.md:371-395, 419-431, 484-498`;
  `memory/local-only-verification.md:7-18`.

### D4 - SOPS+age key custody and recipient strategy

- Options: (a) one operator age recipient for Phase 5; (b) per-channel age
  recipients now; (c) multiple recipients now with an explicit rotation model.
- Preferred: open; research locks SOPS+age but says the current GitOps material
  under-documents it.
- Why binding: The recipient strategy controls `.sops.yaml`, encrypted sample
  content, local decrypt verification, and whether channel onboarding has a
  secret-management burden in INIT-009.
- Traceability: `.pipeline/research.md:199-223, 231-236, 416-431, 474-480,
  559-570`; `product-strategy/tickets/PHASE_5_INDEX.md:15`.

### D5 - Existing `k8s/` disposal path

- Options: (a) delete the existing `k8s/` tree and replace with channel-shaped
  GitOps substrate; (b) selectively migrate reusable files; (c) preserve old
  tree under a legacy path.
- Preferred: delete or selective migration only; preserving a legacy tree is
  incompatible with the channel pivot and no-backwards-compatibility rule.
- Why binding: The repo has 38 tracked old-shape files that render and pass old
  tests. The proposal must prevent those tests and paths from remaining as
  accidental authority.
- Traceability: `.pipeline/research.md:24-223, 249-257, 521-535`;
  `memory/channel-template-pattern.md:67-78`.

### D6 - Flux source repository shape

- Options: (a) this `server-manager` repo is the Flux source; (b) a separate
  GitOps repo is the Flux source; (c) this repo for Phase 5 local verification
  and a separate repo deferred to deployment.
- Preferred: open; single repo is simpler for a solo local operator, while
  separate repo is the more isolated GitOps pattern.
- Why binding: The Flux `GitRepository` URL, path scoping, local source
  simulation, and future deployment handoff all depend on this choice.
- Traceability: `.pipeline/research.md:93-125, 320-361, 488-492`;
  `plans/proposals/gitops-foundation.md:103-124, 168-232`.

### D7 - Kustomize layout and channel inheritance mapping

- Options: (a) bases plus channel overlays; (b) single channel tree with
  generated/resolved manifests; (c) hybrid base plus resolved-channel inputs.
- Preferred: Kustomize over Helm can default for raw manifests, but exact
  layout remains proposal work.
- Why binding: Channel `parent` inheritance must map to Kustomize composition
  or to an explicit resolved-channel artifact. Without that, INIT-009 can
  reintroduce hard environments under different names.
- Traceability: `.pipeline/research.md:262-361, 548-558`;
  `memory/channel-template-pattern.md:24-40, 67-78`;
  `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:325-355`.

### D8 - Manifest packaging surface

- Options: (a) raw YAML plus Kustomize; (b) Helm charts via Flux
  `HelmRelease`; (c) mixed model with raw YAML for substrate and Helm for
  third-party controllers later.
- Preferred: raw YAML plus Kustomize can default for INIT-009 substrate.
- Why binding: The packaging surface determines what the local build/test
  harness renders and what later workload initiatives must target.
- Traceability: `.pipeline/research.md:94-125, 371-380, 521-558`;
  `plans/research/gitops-foundation.md:94-125`.

### D9 - Reconcile cadence and drift policy

- Options: (a) one-minute source polling with report-and-reconcile drift; (b)
  slower cadence; (c) observe-only drift reporting without reconcile.
- Preferred: `1m` source cadence and report-plus-reconcile drift can default,
  with prune/wait retained if proposal keeps Flux's current semantics.
- Why binding: Cadence, prune, wait, and drift behavior are acceptance
  criteria for Flux substrate and affect local verification expectations.
- Traceability: `.pipeline/research.md:93-125, 371-380, 511-520`;
  `plans/research/gitops-foundation.md:14-44, 159-178`.

### D10 - Local verification surface

- Options: (a) render-only Kustomize checks; (b) render plus `flux check --pre`;
  (c) full local cluster harness with Flux install/reconcile and SOPS decrypt.
- Preferred: full local harness is the evidence-backed target, bounded to
  kind/k3d and local secrets.
- Why binding: Phase 5 done-ness is local verification. INIT-009 cannot rely
  on cloud cluster behavior or remote deployment as proof.
- Traceability: `.pipeline/research.md:371-431, 482-520, 572-588`;
  `memory/local-only-verification.md:7-49`;
  `product-strategy/tickets/PHASE_5_INDEX.md:24-40`.

### D11 - Toolchain prerequisite installation strategy

- Options: (a) INIT-009 installs or vendors the required local tools; (b)
  INIT-009 documents operator prerequisites only; (c) split: scripts check and
  docs install.
- Preferred: open; required tools are missing locally, so the proposal must
  assign responsibility.
- Why binding: Without `flux`, `kind`/`k3d`, `sops`, `age`, and `age-keygen`,
  the promised verification surface cannot run.
- Traceability: `.pipeline/research.md:416-431, 482-498, 572-580`.

### D12 - INIT-008 dependency and channel registry input shape

- Options: (a) INIT-009 assumes INIT-008's final channel files are present by
  branch dependency; (b) proposal carries a minimal channel fixture until
  INIT-008 merges; (c) proposal waits for INIT-008 branch integration before
  hookpoints.
- Preferred: open; research found INIT-008 channel files in a sibling worktree,
  not in this INIT-009 worktree.
- Why binding: Flux/Kustomize paths cannot be channel-aligned if the proposal
  does not name the channel registry source it consumes.
- Traceability: `.pipeline/research.md:199-223, 302-329, 463-480`;
  `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:72-127, 184-227`.

## 3. Gaps that block proposal writing

Each row restates a Phase 1 `BLOCKS_PROPOSAL` item, with the closure condition
and the actor or artifact that can close it.

| Gap | What the gap is | Closure path | Traceability |
| --- | --- | --- | --- |
| G1 | Channel-to-GitOps path mapping is unresolved. | Proposal must choose the authoritative mapping from channel id to Flux source path and reconciled Kustomize path. This may require a user answer if same-repo versus separate-repo changes operational ownership. | `.pipeline/research.md:320-361, 463-468`; `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:72-127` |
| G2 | Flux Kustomization cardinality is unresolved. | Proposal must state whether "one Kustomization per channel" literally means one Flux object per channel or one per channel plus cluster role/component. | `.pipeline/research.md:337-344, 469-472`; `memory/channel-template-pattern.md:69-70` |
| G3 | SOPS+age is locked but under-documented. | Proposal must name the Phase 5 recipient strategy, `.sops.yaml` scope, local age key handling, and decrypt verification target. User should answer whether one recipient is acceptable for Phase 5. | `.pipeline/research.md:199-223, 231-236, 474-480, 559-570`; `product-strategy/tickets/PHASE_5_INDEX.md:15` |
| G4 | INIT-008 dependency state is absent from this worktree. | Proposal must either depend on the INIT-008 final channel registry branch, require rebasing/merging before implementation, or define a temporary local fixture that is not a compatibility surface. | `.pipeline/research.md:199-223, 302-329, 477-480`; `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:72-127` |

Implementation blockers that the proposal must acknowledge but does not need
to fully close at synthesis time:

- Required tools are missing: `flux`, `kind`/`k3d`, `sops`, `age`, and
  `age-keygen`. Evidence: `.pipeline/research.md:416-431, 482-488`.
- Existing tests enforce `dev/staging/production`. Evidence:
  `.pipeline/research.md:126-198, 488-492`.
- Existing Flux manifests use a placeholder Git URL. Evidence:
  `.pipeline/research.md:488-496`.
- No `.sops.yaml` or encrypted sample secret exists. Evidence:
  `.pipeline/research.md:199-223, 492-496`.
- No local cluster is available until kind or k3d is installed. Evidence:
  `.pipeline/research.md:383-395, 496-498`.

## 4. Slice decomposition proposal

This is a proposal-ready decomposition sketch, not implementation scope. The
Phase 3 proposal may rename slices, but it should keep the initiative bounded
to six slices or fewer unless it explicitly splits INIT-009.

| Slice | Scope summary | Dependencies | Local verification anchor | Evidence anchor |
| --- | --- | --- | --- | --- |
| `SLICE-031: Channel GitOps Topology and Stale Tree Disposition` | Decide channel-to-Flux mapping, Kustomize layout family, and the delete/migrate path for the old `k8s/` tree. | INIT-008 channel registry input must be available or explicitly assumed. | Old environment tests removed or replaced; channel path checks render locally. | `.pipeline/research.md:24-223, 249-361, 521-558` |
| `SLICE-032: Flux Source and Dev Channel Reconciliation Skeleton` | Establish the Flux source and Kustomization skeleton for the active `dev` channel without shipping app workloads. | `SLICE-031` | `flux check --pre`, local source path validation, and Flux reconcile against empty/substrate-only manifests. | `.pipeline/research.md:93-125, 320-361, 521-547`; `product-strategy/tickets/PHASE_5_INDEX.md:15,20` |
| `SLICE-033: SOPS+age Secrets Workflow` | Add the SOPS+age policy, recipient strategy, encrypted sample/fixture, and decrypt verification contract. | `SLICE-031` for path placement; user answer on recipient strategy. | `sops --decrypt` with local age key; no committed private key. | `.pipeline/research.md:199-223, 231-236, 416-431, 559-570` |
| `SLICE-034: Local Cluster Verification Harness` | Choose kind/k3d, install/document prerequisites, run Flux install/reconcile locally, and integrate Kustomize build checks. | `SLICE-032`; toolchain responsibility decision. | kind/k3d cluster, `flux check --pre`, `flux install`, Kustomize build, sample reconcile. | `.pipeline/research.md:371-431, 572-580`; `memory/local-only-verification.md:7-49` |
| `SLICE-035: Drift, Boundary, and Buildkite-Mutation Guardrails` | Replace old topology guardrails with channel-aligned path-scope, drift, and CI boundary checks without implementing Buildkite. | `SLICE-031`, `SLICE-032` | Shell/pytest checks proving Flux paths stay scoped and CI files do not mutate clusters. | `.pipeline/research.md:126-198, 511-520, 582-588`; `product-strategy/tickets/PHASE_5_INDEX.md:16-17` |
| `SLICE-036: Downstream Handoff Documentation` | Document what INIT-010 through INIT-014 consume: channel id, image tag expectations, Buildkite parameterization boundary, and workload manifest slots. | `SLICE-031` through `SLICE-035` | Documentation plus linkable local verification commands; no app workload deployment. | `.pipeline/research.md:590-606`; `memory/channel-template-pattern.md:71-74`; `product-strategy/tickets/PHASE_5_INDEX.md:16-20` |

## 5. Open questions for user

These are the questions most likely to benefit from direct user resolution
before Phase 3 writes a binding proposal. Where a safe default already has
strong repo evidence, the proposal can choose it and record the default.

### MUST_ANSWER

- Local cluster preference: Should INIT-009 standardize on `kind` or `k3d` for
  the local Flux harness? Neither is installed, and Phase 5 allows either.
  Traceability: `.pipeline/research.md:383-395, 416-431`;
  `memory/local-only-verification.md:11-18`.
- Existing `k8s/` tree disposal: Should the old environment-shaped tree be
  deleted entirely, or should selected pieces be migrated into the new
  channel-shaped layout? The default under no-backwards-compatibility is
  delete or selective migration, not legacy preservation. Traceability:
  `.pipeline/research.md:24-223, 249-257, 521-535`;
  `memory/channel-template-pattern.md:67-78`.
- Flux source repo: Should Flux point at this `server-manager` repo, or should
  INIT-009 plan for a separate GitOps repository? Single-repo is simpler for a
  solo local operator; separate-repo is the more isolated GitOps pattern.
  Traceability: `.pipeline/research.md:320-361, 488-492`;
  `plans/proposals/gitops-foundation.md:103-124, 168-232`.
- SOPS age recipient strategy: Is one operator age recipient acceptable for
  Phase 5, with multi-recipient or per-channel recipients deferred, or should
  per-channel recipients exist now? Traceability:
  `.pipeline/research.md:199-223, 474-480, 559-570`;
  `product-strategy/tickets/PHASE_5_INDEX.md:15`.
- Toolchain installation responsibility: Should INIT-009 include installation
  or bootstrapping for `flux`, `kind`/`k3d`, `sops`, `age`, and `age-keygen`,
  or should those remain operator prerequisites documented by INIT-009?
  Traceability: `.pipeline/research.md:416-431, 482-488`.

### CAN_DEFAULT

- Manifest packaging: default to raw YAML plus Kustomize for substrate
  manifests. Flux supports Helm too, but Kustomize matches the existing
  substrate and keeps INIT-009 narrower. Traceability:
  `.pipeline/research.md:94-125, 548-558`;
  `plans/research/gitops-foundation.md:94-125`.
- Reconcile cadence: default source cadence to `1m` unless proposal research
  finds a local-cluster reason to slow it down. Traceability:
  `plans/research/gitops-foundation.md:14-44`;
  `.pipeline/research.md:371-380`.
- Drift policy: default to report plus reconcile, preserving Flux prune/wait
  semantics where applicable. Traceability:
  `.pipeline/research.md:93-125, 371-380, 511-520`;
  `plans/research/gitops-foundation.md:14-44, 159-178`.

## 6. Stale material to displace

The proposal phase should revise, supersede, or delete the following GitOps
foundation materials so INIT-009 stops carrying environment-triad assumptions.
Per the no-backwards-compatibility rule, deletion is preferred when a document
is no longer an active planning input.

| Path | Proposal-phase action | Reason | Traceability |
| --- | --- | --- | --- |
| `plans/research/gitops-foundation.md` | Revise only if kept as current research; otherwise supersede/delete as active input. | Flux pull model, `GitRepository` + `Kustomization`, Kustomize layering, prune/wait, and timeout remain useful. Multi-environment layout and SealedSecrets content are stale against channel pattern and SOPS+age scope. | `.pipeline/research.md:249-252`; `product-strategy/tickets/PHASE_5_INDEX.md:15`; `memory/channel-template-pattern.md:67-78` |
| `plans/research/gitops-foundation-hookpoints.md` | Supersede/delete as active hookpoint input; rerun hookpoints after proposal risk clears. | It assumes greenfield `k8s/`, old `infra/environments/dev/main.tf`, and `k8s/clusters/<env>/...` as final root shape. | `.pipeline/research.md:252`; `memory/channel-template-pattern.md:69-74` |
| `plans/research/gitops-foundation-needs.md` | Revise if preserving needs language; otherwise supersede/delete as active input. | Shared intent, variation, Flux entrypoints, scoped paths, and CI/CD boundary survive. Environment separation and two-tier-per-env implementation references are stale. | `.pipeline/research.md:253`; `memory/channel-template-pattern.md:67-78` |
| `plans/proposals/gitops-foundation.md` | Supersede/delete as active proposal. | Git desired state, Flux sole reconciler, Buildkite non-mutating boundary, and scoped paths survive as concepts. The proposal's path shape, scope, repo layout, and promotion model are environment-based, and it says it will not write Flux manifests even though INIT-009 now includes Flux/Kustomize/SOPS substrate. | `.pipeline/research.md:254`; `product-strategy/tickets/PHASE_5_INDEX.md:15` |

Related but non-target GitOps risk material should be treated as historical
only:

- `plans/risk/gitops-foundation-{audit,scope,shortcut}.md` can inform risk
  concerns, but prior LOW findings do not approve the channel-aligned
  INIT-009 proposal. Evidence: `.pipeline/research.md:255, 511-514`.
- `plans/proposals/phase1-foundation.md` can inform SOPS+age reasoning and
  Buildkite/Flux boundaries, but its Hetzner/k3s/Object Storage assumptions are
  stale. Evidence: `.pipeline/research.md:256`.

## Synthesis readout

Proposal writing is ready to proceed once it treats the following as binding:

- INIT-009 is not greenfield. It replaces or migrates an existing 38-file,
  environment-shaped Flux/Kustomize tree.
- Channel/template inheritance is the law. Flux and Kustomize structures align
  to channel ids, not hard `dev/staging/production` environments.
- SOPS+age is part of INIT-009's core scope, not a later optional add-on.
- Done-ness is local-only: kind/k3d, Flux local reconcile, Kustomize render,
  and SOPS decrypt are the proof surface.
- The strongest proposal blockers are choices, not code discovery: channel path
  mapping, Kustomization cardinality, SOPS recipient strategy, INIT-008 channel
  dependency state, local cluster choice, old-tree disposal, source repo shape,
  and toolchain responsibility.

Evidence summary:
`.pipeline/research.md:24-223, 225-361, 371-431, 463-606`;
`memory/channel-template-pattern.md:7-78`;
`memory/local-only-verification.md:7-49`;
`product-strategy/tickets/PHASE_5_INDEX.md:1-40`.
