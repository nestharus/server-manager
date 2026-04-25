# INIT-009 Phase 1 Research: GitOps Substrate

## Scope

Evidence-only research for INIT-009: GitOps Substrate.

Goal: document the problem space for Flux CD, SOPS+age secrets, and
Kustomize layout after the INIT-008 channel pivot.

No solution design in this file. Proposal-phase questions are recorded as
questions, not answers.

Binding constraints:

- Flux CD is locked as the GitOps reconciler.
  Source: `plans/platform-decisions-overlay.md:19-20`.
- INIT-009 is pending and scoped as "Flux CD + Kustomize layout +
  SOPS+age secrets."
  Source: `product-strategy/tickets/PHASE_5_INDEX.md:15`.
- Buildkite is INIT-011, not INIT-009.
  Source: `product-strategy/tickets/PHASE_5_INDEX.md:15-17`.
- Phase 5 is local-only; no Vultr deployment or real cluster bootstrap.
  Source: `memory/local-only-verification.md:7-29`,
  `product-strategy/tickets/PHASE_5_INDEX.md:3,24-40`.
- INIT-008 replaces hard environments with channel/template inheritance.
  Source: `memory/channel-template-pattern.md:7,34-40,67-78`,
  `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:10-15,25-46`.

---

## 1. Current repo state for GitOps

The current repo is not GitOps-greenfield.

`git ls-files k8s | wc -l` reports 38 tracked files under `k8s/`.

Existing tree:

- `k8s/base/`
- `k8s/overlays/{dev,staging,production}/{app-cluster,control-cluster}/`
- `k8s/clusters/{dev,staging,production}/{app-cluster,control-cluster}/`
- `k8s/tests/test_gitops_foundation.sh`

Prior research also describes "38 files under `k8s/`."
Source: `plans/research/gitops-foundation.md:180-194`,
`plans/research/gitops-foundation-needs.md:154-167`.

`k8s/base/kustomization.yaml` composes:

- `platform`
- `controllers`
- `namespaces`
- `policies`

Source: `k8s/base/kustomization.yaml:1-7`.

`k8s/base/namespaces/` defines:

- `platform-system`
- `workloads`

Source: `k8s/base/namespaces/kustomization.yaml:1-5`,
`k8s/base/namespaces/platform-system.yaml:1-4`,
`k8s/base/namespaces/workloads.yaml:1-4`.

`k8s/base/platform/kustomization.yaml` generates
`gitops-platform-defaults` with:

- `gitops.foundation.layer=base`
- `gitops.foundation.domain=platform`
- `gitops.foundation.desiredStateOwner=git`
- `gitops.foundation.clusterTopology=control-and-app`

Source: `k8s/base/platform/kustomization.yaml:1-11`.

`k8s/base/controllers/kustomization.yaml` generates
`gitops-controller-contract` with:

- `gitops.foundation.reconciler=flux`
- `gitops.foundation.remoteReconciliation=disallowed`
- `gitops.foundation.controlClusterMutatesPeers=false`

Source: `k8s/base/controllers/kustomization.yaml:1-11`.

`k8s/base/policies/kustomization.yaml` generates
`gitops-boundary-policy` with:

- `gitops.foundation.buildkiteRole=validate-render-test-and-open-prs`
- `gitops.foundation.buildkiteClusterMutation=disallowed`
- `gitops.foundation.promotionModel=path-based-git-change`

Source: `k8s/base/policies/kustomization.yaml:1-11`.

Current overlays are environment-aligned:

- `gitops.foundation.environment=dev`
- `gitops.foundation.environment=staging`
- `gitops.foundation.environment=production`

Examples:
`k8s/overlays/dev/app-cluster/kustomization.yaml:1-13`,
`k8s/overlays/production/control-cluster/kustomization.yaml:1-13`.

Current Flux roots are environment-aligned.

Example `dev` app root:

- `GitRepository.metadata.name: dev-app-cluster-root`
- `Kustomization.metadata.name: dev-app-cluster-root`
- `Kustomization.spec.path: ./k8s/clusters/dev/app-cluster/manifests`
- `prune: true`
- `wait: true`

Source: `k8s/clusters/dev/app-cluster/gotk-sync.yaml:1-25`.

Example production control root:

- `GitRepository.metadata.name: production-control-cluster-root`
- `Kustomization.spec.path:
  ./k8s/clusters/production/control-cluster/manifests`

Source: `k8s/clusters/production/control-cluster/gotk-sync.yaml:1-25`.

Current cluster-root manifests are environment-aligned.

`k8s/clusters/dev/app-cluster/manifests/kustomization.yaml` references:

- `../../../../overlays/dev/app-cluster`
- `bootstrap`
- `gitops.foundation.scope=clusters/dev/app-cluster`

Source: `k8s/clusters/dev/app-cluster/manifests/kustomization.yaml:1-15`.

`k8s/clusters/dev/control-cluster/manifests/kustomization.yaml` references:

- `../../../../overlays/dev/control-cluster`
- `claims`
- `gitops.foundation.scope=clusters/dev/control-cluster`

Source: `k8s/clusters/dev/control-cluster/manifests/kustomization.yaml:1-15`.

Topology slots exist from prior GitOps work:

- App bootstrap slot:
  `gitops.foundation.slot=downstream-flux-bootstrap`.
  Source:
  `k8s/clusters/dev/app-cluster/manifests/bootstrap/kustomization.yaml:1-11`.
- Control claims slot:
  `gitops.foundation.slot=crossplane-cluster-claims`.
  Source:
  `k8s/clusters/dev/control-cluster/manifests/claims/kustomization.yaml:1-11`.

The old topology test exists and passes locally:

- `bash k8s/tests/test_gitops_foundation.sh`
- Result: `PASS: GitOps foundation topology checks succeeded.`
- The run emitted awk escape warnings but exited 0.

The test enforces:

- base exists and is environment-neutral,
- overlays exist for `dev`, `staging`, `production`,
- clusters exist for `dev`, `staging`, `production`,
- cluster roots contain Flux toolkit manifests,
- Flux paths stay inside `clusters/<env>/<cluster>`,
- Buildkite files do not contain direct cluster mutation commands.

Source: `k8s/tests/test_gitops_foundation.sh:131-256`.

Render checks succeeded locally:

- `kubectl kustomize k8s/base`
- `kubectl kustomize k8s/clusters/dev/app-cluster/manifests`
- `kubectl kustomize k8s/clusters/dev/control-cluster/manifests`

Current GitOps secret surface:

- no `.sops.yaml`
- no `*.sops.yaml`
- no `*.age`
- no `gitops/` tree
- no `flux/` tree

Search command:

```bash
find . -maxdepth 3 -type f \( -path './gitops/*' -o -path './flux/*' \
  -o -name '.sops.yaml' -o -name '*.sops.yaml' -o -name '*.age' \) | wc -l
```

Result: `0`.

Current `infra/` in this INIT-009 worktree is still pre-channel:

- `infra/environments/dev/`
- `infra/environments/staging/`
- `infra/environments/production/`

Source: `infra/README.md:5-17`,
`infra/environments/dev/main.tf:19-38`,
`infra/environments/staging/main.tf:20-39`,
`infra/environments/production/main.tf:19-38`.

INIT-008's channel files live in the sibling worktree, not this worktree:

- `infra/channels/dev.yaml`
- `infra/schemas/platform-channel.schema.json`
- `infra/schemas/platform-channel-resolved.schema.json`
- `infra/roots/channels/dev/`

Source:
`worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:72-127`,
`worktrees/init-008-platform-bootstrap/infra/channels/dev.yaml:1-25`.

Research finding:

- Current repo has old Flux/Kustomize substrate.
- Current repo lacks SOPS+age substrate.
- Current repo lacks INIT-008 channel files in this worktree.
- Current GitOps tree is valid enough to render, but stale against channels.

---

## 2. Prior decisions and where they live

| Decision | Status | Source |
|---|---:|---|
| Flux CD replaces Argo CD as GitOps reconciler. | LOCKED | `plans/platform-decisions-overlay.md:19-20`; `memory/platform-stack.md:17-18` |
| Buildkite is canonical CI/CD direction. | LOCKED | `plans/platform-decisions-overlay.md:19`; `memory/platform-stack.md:17` |
| Buildkite is INIT-011, not INIT-009. | LOCKED | `product-strategy/tickets/PHASE_5_INDEX.md:15-17` |
| INIT-009 scope is Flux CD + Kustomize + SOPS+age. | LOCKED | `product-strategy/tickets/PHASE_5_INDEX.md:15`; `memory/phase-5-in-progress.md:11-15` |
| SOPS+age is the GitOps bootstrap secrets pattern. | LOCKED / carried | `plans/proposals/phase1-foundation.md:41-45,123-142`; `plans/risk/phase1-scope.md:171-200`; `product-strategy/tickets/PHASE_5_INDEX.md:15` |
| Phase 5 is local-only. | LOCKED | `memory/local-only-verification.md:7-29`; `product-strategy/tickets/PHASE_5_INDEX.md:3,24-40`; `memory/phase-5-in-progress.md:22-28` |
| No Vultr deployment or real VKE bootstrap in Phase 5. | LOCKED | `memory/local-only-verification.md:23-29,41-49`; `product-strategy/tickets/PHASE_5_INDEX.md:28,40` |
| Channel/template inheritance replaces hard environments. | LOCKED | `memory/channel-template-pattern.md:7,34-40,67-78`; `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:10-15,25-46` |
| INIT-008 produces channel registry and channel roots. | FOUNDATION | `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:72-127,184-227,275-324` |
| Current active INIT-008 channel is `dev` only. | FOUNDATION | `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:37-46,184-227`; `worktrees/init-008-platform-bootstrap/infra/channels/dev.yaml:1-25` |
| Vultr/VKE/OpenTofu is the platform substrate direction. | LOCKED | `memory/platform-stack.md:9-18`; `plans/proposals/platform-bootstrap.md:5-37,85-106,173-196`; `plans/risk/platform-bootstrap-audit.md:94-119` |

Note: `plans/platform-decisions-overlay.md:25-28` still lists hosting as open.
Later memory and platform-bootstrap risk material close that toward Vultr.
Source: `memory/platform-stack.md:9-18`,
`plans/risk/platform-bootstrap-audit.md:108-119`.

---

## 3. Prior material: current vs stale

| Document | Survives | Needs revision | Stale |
|---|---|---|---|
| `plans/research/gitops-foundation.md` | Flux pull model, `GitRepository` + `Kustomization`, Kustomize layering, prune/wait/timeout. Sources: `plans/research/gitops-foundation.md:14-44,94-125,159-178`. | Multi-environment `dev/staging/production` layout and old implementation summary. Sources: `plans/research/gitops-foundation.md:55-93,180-194`. | SealedSecrets discussion conflicts with SOPS+age scope. Sources: `plans/research/gitops-foundation.md:127-157`; `product-strategy/tickets/PHASE_5_INDEX.md:15`. |
| `plans/research/gitops-foundation-hookpoints.md` | GitOps consumes Platform Bootstrap substrate; control cluster must not remotely reconcile peers. Sources: `plans/research/gitops-foundation-hookpoints.md:11-35,109-123`. | It says `k8s/` was greenfield and assumes `infra/environments/dev/main.tf`. Sources: `plans/research/gitops-foundation-hookpoints.md:5-31`. | `k8s/clusters/<env>/...` as final root shape. Sources: `plans/research/gitops-foundation-hookpoints.md:67-108`; `memory/channel-template-pattern.md:69-74`. |
| `plans/research/gitops-foundation-needs.md` | Shared intent, variation, Flux entrypoints, scoped Flux paths, CI/CD boundary. Sources: `plans/research/gitops-foundation-needs.md:11-44,78-95`. | Need 3 and Need 4 are environment separation and old two-tier-per-env shape. Sources: `plans/research/gitops-foundation-needs.md:45-76`. | Implementation references to `k8s/overlays/{dev,staging,production}` and `k8s/clusters/{dev,staging,production}`. Source: `plans/research/gitops-foundation-needs.md:41-60,154-167`. |
| `plans/proposals/gitops-foundation.md` | Git desired state, Flux sole reconciler, Buildkite non-mutating, scoped cluster paths, adjacent interfaces. Sources: `plans/proposals/gitops-foundation.md:103-124,168-232`. | Layout, scope, repo shape, and promotion are environment-based. Sources: `plans/proposals/gitops-foundation.md:12-17,32-46,51-101,126-147,234-249`. | Says this initiative does not write Flux manifests, but INIT-009 includes Flux/Kustomize/SOPS and manifests already exist. Sources: `plans/proposals/gitops-foundation.md:251-256`; `product-strategy/tickets/PHASE_5_INDEX.md:15`; `k8s/clusters/dev/app-cluster/gotk-sync.yaml:1-25`. |
| `plans/risk/gitops-foundation-{audit,scope,shortcut}.md` | Prior proposal was LOW risk for old topology/boundary; useful concerns include no duplicate deployment engine, topology ownership, Crossplane claim placement, and path-scope risk. Sources: `plans/risk/gitops-foundation-audit.md:1-12,31-68`; `plans/risk/gitops-foundation-scope.md:9-32,83-100`; `plans/risk/gitops-foundation-shortcut.md:109-136`. | Findings are environment-based and must be rerun after channel proposal. Sources: `plans/risk/gitops-foundation-audit.md:37-68,123-138`; `plans/risk/gitops-foundation-scope.md:9-20`; `plans/risk/gitops-foundation-shortcut.md:49-72,84-105,139-174`. | Prior LOW findings are not approval for channel-aligned INIT-009. |
| `plans/proposals/phase1-foundation.md` | SOPS+age reasoning and Buildkite/Flux boundary. Sources: `plans/proposals/phase1-foundation.md:107-142`. | None to carry as active INIT-009 design. | Hetzner, kube-hetzner, k3s, and Hetzner Object Storage assumptions. Sources: `plans/proposals/phase1-foundation.md:5-19,92-105,158-173`; `memory/platform-stack.md:9-18`. |
| `plans/proposals/platform-bootstrap.md` | Platform Bootstrap stops before GitOps bootstrap and defines endpoint/kubeconfig/repo-layout handoff. Source: `plans/proposals/platform-bootstrap.md:173-196`. | Per-environment roots are replaced by INIT-008 channel roots. Sources: `plans/proposals/platform-bootstrap.md:56-62,158-171`; `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:10-15,72-127`. | Treat as pre-channel where it conflicts with INIT-008 final proposal. |

---

## 4. Channel-pattern alignment

Binding channel facts:

- Channel is not environment.
  Source: `memory/channel-template-pattern.md:34-40`.
- Channel schema fields include `id`, `parent`, `exposure`, `tenant`,
  `allow_ephemeral_children`, and platform target data.
  Source: `memory/channel-template-pattern.md:24-33`.
- INIT-009 should align Flux Kustomizations with channels, one per channel,
  not classic environments.
  Source: `memory/channel-template-pattern.md:69-70`.
- Kustomize inheritance should mirror channel parent inheritance.
  Source: `memory/channel-template-pattern.md:69-70`.

INIT-008 adapts the channel model to platform channels:

- `id`
- optional `parent`
- `exposure`
- optional `tenant`
- `allow_ephemeral_children`
- `enabled_platforms`
- platform OpenTofu settings

Source: `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:25-46,128-183`.

INIT-008 active channel:

- `id: dev`
- `parent: null`
- `exposure: dev`
- `tenant: null`
- `allow_ephemeral_children: true`
- `enabled_platforms: [kubernetes]`

Source: `worktrees/init-008-platform-bootstrap/infra/channels/dev.yaml:1-25`.

INIT-008 target layout includes:

- `infra/channels/dev.yaml`
- `infra/channels/fixtures/...`
- `infra/schemas/platform-channel.schema.json`
- `infra/schemas/platform-channel-resolved.schema.json`
- `infra/roots/channels/dev/`
- channel resolver/spawn/validation scripts

Source: `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:72-118`.

INIT-008 explicitly removes:

- `infra/environments/dev/`
- `infra/environments/staging/`
- `infra/environments/production/`

Source: `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:119-127`.

OpenTofu consumes resolved channel JSON, not raw inherited YAML.
Source: `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:179-183,325-355`.

Mismatch:

- Current GitOps tree uses `dev/staging/production`.
- Channel memory says INIT-009 should use channel ids.
- Current tests enforce the old environment list.

Sources: `k8s/tests/test_gitops_foundation.sh:217-249`,
`memory/channel-template-pattern.md:69-74`.

Proposal-phase questions:

- What is the authoritative channel-to-GitOps path mapping?
  Sources:
  `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:72-127`,
  `k8s/clusters/dev/app-cluster/gotk-sync.yaml:18-24`.

- Does "one Flux Kustomization per channel" mean one Flux object per channel
  id, or one per channel id per cluster role?
  Sources: `memory/channel-template-pattern.md:69-70`,
  `k8s/tests/test_gitops_foundation.sh:226-249`.

- How does channel `parent` inheritance map to Kustomize composition when
  INIT-008 also has pre-process channel resolution?
  Sources: `memory/channel-template-pattern.md:69-70`,
  `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:325-355`.

- How does channel `id` flow into Flux `GitRepository` and `Kustomization`
  names?
  Sources: `k8s/clusters/dev/app-cluster/gotk-sync.yaml:1-25`,
  `k8s/clusters/production/control-cluster/gotk-sync.yaml:1-25`.

- Does Flux consume raw channel YAML, resolved channel JSON, generated
  Kustomize artifacts, or only committed manifests?
  Source: `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:179-183,302-313`.

- Which active channels are in scope for local verification?
  Evidence: INIT-008 ships active `dev` only.
  Source: `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:37-46,221-227`.

---

## 5. Local verification surface

Can be verified locally:

- `flux check --pre` against local cluster.
  Source: `memory/local-only-verification.md:11-15`.
- Kustomize render via standalone `kustomize build` or `kubectl kustomize`.
  Local evidence: `kubectl kustomize` succeeded for base and current dev
  app/control manifests.
- `sops --decrypt` with local age key once tools and sample encrypted secret
  exist.
  Sources: `plans/proposals/phase1-foundation.md:123-142`,
  `plans/risk/phase1-scope.md:171-200`.
- Flux install/reconcile against kind/k3d local cluster.
  Source: `memory/local-only-verification.md:14`.
- Drift/boundary checks, based on old test precedent.
  Source: `k8s/tests/test_gitops_foundation.sh:103-129,197-215`.

Cannot be verified today:

- `flux check --pre`: `flux` missing and no local cluster CLI installed.
- SOPS decrypt: `sops`, `age`, and `age-keygen` missing.
- Local Flux reconcile: both `kind` and `k3d` missing.

Local cluster choice:

- `kind`: missing.
- `k3d`: missing.
- Because neither is installed, choice cannot be availability-based.
- Proposal input: default to `kind` unless proposal research finds a
  project-specific k3d requirement.
- Evidence: Phase 5 references `kind/k3d` generically and current installed
  Kubernetes CLI is `kubectl`, not a k3s-specific stack.
  Sources: `product-strategy/tickets/PHASE_5_INDEX.md:15,35`,
  `memory/local-only-verification.md:14`.

Must not be verified in Phase 5:

- No Vultr deployment.
- No real Vultr VKE bootstrap.
- No remote image push.
- No real DNS registration.
- No public-audience publish.

Source: `memory/local-only-verification.md:23-29,41-49`.

---

## 6. Toolchain check

Checked locally on 2026-04-25 from:

`/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate`

| Tool | Installed | Version / evidence |
|---|---:|---|
| `flux` | No | `command -v flux` missing |
| `kind` | No | `command -v kind` missing |
| `k3d` | No | `command -v k3d` missing |
| `sops` | No | `command -v sops` missing |
| `age` | No | `command -v age` missing |
| `age-keygen` | No | `command -v age-keygen` missing |
| `kubectl` | Yes | `/usr/local/bin/kubectl`; client `v1.34.1`; embedded `kustomizeVersion: v5.7.1` |
| `kustomize` | No | standalone `command -v kustomize` missing |

Install prerequisites:

- Flux CLI.
- One local cluster CLI: `kind` or `k3d`.
- SOPS CLI.
- age CLI package with `age` and `age-keygen`.
- Standalone `kustomize` only if `kubectl kustomize` is not accepted.

---

## 7. Phase 0 acceptance criteria gap

Source acceptance criteria:
`product-strategy/engineering roadmap.md:102-117`.

| Criterion | Status | Evidence |
|---|---:|---|
| Hosting decision formalized in `DECISIONS.md`. | PARTIAL | Memory locks Vultr; this pass did not find matching `DECISIONS.md` ratification. Sources: `memory/platform-stack.md:9-18`; `product-strategy/engineering roadmap.md:102-105`. |
| Deployable service substrate operational against `infra`. | PARTIAL | Current `k8s/` renders and old topology test passes, but tree is stale against INIT-008 channel registry. Sources: `k8s/tests/test_gitops_foundation.sh:217-256`; `memory/channel-template-pattern.md:69-74`. |
| Secret management is operational. | MISSING | No `.sops.yaml`, no age artifacts, and `sops`/`age` CLIs missing. Sources: Section 1 and Section 6. |
| Shared test harness functional. | PARTIAL | Existing GitOps test passes but validates old env shape, not channels. Source: `k8s/tests/test_gitops_foundation.sh:217-256`. |
| Data portability recorded as schema property. | NOT INIT-009 DIRECT | Relevant only if GitOps introduces durable config schemas; INIT-008 channel schemas are strict. Sources: `product-strategy/engineering roadmap.md:111-115`; `worktrees/init-008-platform-bootstrap/infra/schemas/platform-channel.schema.json:1-204`. |
| Discord interaction framework can register commands and call API. | NOT INIT-009 DIRECT | Later app workload concern, not GitOps substrate. Source: `product-strategy/engineering roadmap.md:112-114`. |
| Graceful degradation mechanics selected. | NOT INIT-009 DIRECT | Drift/reconcile observability may connect later; primary criterion is application/deferred-effect substrate. Source: `product-strategy/engineering roadmap.md:113-115`. |

Most relevant gaps:

- Secret management is missing.
- Deployable substrate is partial because old Kustomize exists but is not
  channel-aligned.
- Test harness is partial because old topology tests pass for stale shape.

---

## 8. Known risks and open questions

### BLOCKS_PROPOSAL

- Channel-to-GitOps path mapping is unresolved.
  Sources: `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:72-127`,
  `k8s/clusters/dev/app-cluster/gotk-sync.yaml:18-24`.

- Flux Kustomization cardinality is unresolved: per channel, or per channel
  plus cluster role.
  Sources: `memory/channel-template-pattern.md:69-70`,
  `k8s/tests/test_gitops_foundation.sh:226-249`.

- SOPS+age is locked but under-documented in current GitOps material.
  Sources: `plans/research/gitops-foundation.md:127-157`,
  `product-strategy/tickets/PHASE_5_INDEX.md:15`.

- INIT-008 dependency state is not present in this worktree.
  Sources: `infra/README.md:5-17`,
  `worktrees/init-008-platform-bootstrap/infra/channels/dev.yaml:1-25`.

### BLOCKS_IMPLEMENTATION

- Required tools are missing: `flux`, `kind`/`k3d`, `sops`, `age`,
  `age-keygen`.
  Source: Section 6.

- Existing tests enforce `dev/staging/production`.
  Source: `k8s/tests/test_gitops_foundation.sh:226-249`.

- Existing manifests use placeholder Git URL
  `ssh://git@example.com/humility/discord.git`.
  Source: `k8s/clusters/dev/app-cluster/gotk-sync.yaml:7-10`.

- No current `.sops.yaml` or encrypted sample secret exists.
  Source: Section 1.

- No local cluster is available until `kind` or `k3d` is installed.
  Source: Section 6.

### INFORMATIONAL

- Old Kustomize tree renders with `kubectl kustomize`.
  Source: Section 1.

- Old GitOps topology test passes despite stale channel fit.
  Source: Section 1.

- Prior risk gate was LOW for the old proposal, not for channel-aligned
  INIT-009.
  Sources: `plans/risk/gitops-foundation-audit.md:1-12`,
  `plans/risk/gitops-foundation-scope.md:9-20`,
  `plans/risk/gitops-foundation-shortcut.md:1-7`.

- Buildkite boundary remains important but implementation belongs to
  INIT-011.
  Source: `product-strategy/tickets/PHASE_5_INDEX.md:15-17`.

---

## 9. Suggested slice decomposition sketch

Sketch only. Proposal phase must refine.

### SLICE-031: Stale GitOps material disposition

Evidence:

- Old proposal is environment-triad-based.
  Source: `plans/proposals/gitops-foundation.md:51-101`.
- Current `k8s/` tree exists and is old-shaped.
  Source: `plans/research/gitops-foundation.md:180-194`.
- INIT-008 channel pivot is binding.
  Source: `memory/channel-template-pattern.md:69-78`.

### SLICE-032: Channel-aligned Flux source/Kustomization contract

Evidence:

- Flux CD is locked.
  Source: `plans/platform-decisions-overlay.md:19-20`.
- One Kustomization per channel is stated.
  Source: `memory/channel-template-pattern.md:69-70`.
- Existing Flux names and paths use environments.
  Source: `k8s/clusters/dev/app-cluster/gotk-sync.yaml:1-25`.

### SLICE-033: Channel-aligned Kustomize layout

Evidence:

- Kustomize layering exists as a mechanism.
  Source: `plans/research/gitops-foundation.md:94-125`.
- Channel inheritance uses `parent` and resolved JSON.
  Sources: `memory/channel-template-pattern.md:24-40`,
  `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:325-355`.
- Existing overlays encode `gitops.foundation.environment`.
  Source: `k8s/overlays/dev/app-cluster/kustomization.yaml:8-13`.

### SLICE-034: SOPS+age secrets workflow

Evidence:

- SOPS+age is named by INIT-009 scope and prior foundation proposal.
  Sources: `product-strategy/tickets/PHASE_5_INDEX.md:15`,
  `plans/proposals/phase1-foundation.md:123-142`.
- Current repo has no SOPS/age files.
  Source: Section 1.
- Local SOPS/age tools are missing.
  Source: Section 6.

### SLICE-035: Local Flux verification harness

Evidence:

- Phase 5 is local-only.
  Source: `memory/local-only-verification.md:7-29`.
- Flux check/dry-run should target kind/k3d.
  Source: `memory/local-only-verification.md:14`.
- Neither `kind` nor `k3d` is installed.
  Source: Section 6.

### SLICE-036: Drift and boundary checks

Evidence:

- Existing test checks Flux path scope and Buildkite mutation ban.
  Source: `k8s/tests/test_gitops_foundation.sh:103-129,197-215`.
- Buildkite boundary belongs to INIT-011 but must not be contradicted.
  Source: `product-strategy/tickets/PHASE_5_INDEX.md:15-17`.

### SLICE-037: Downstream handoff documentation

Evidence:

- INIT-010 image tags carry channel identity.
  Source: `memory/channel-template-pattern.md:71`.
- INIT-011 pipelines parameterize on channel.
  Source: `memory/channel-template-pattern.md:72`.
- INIT-014 workload manifests inherit per-channel config.
  Source: `memory/channel-template-pattern.md:73`.

---

## Research bottom line

The repo already contains a Flux/Kustomize substrate, but it is the prior
environment-shaped GitOps foundation.

INIT-008 changes the axis from `dev/staging/production` environments to
platform channels with `id`, `parent`, `exposure`, and resolved channel JSON.

Prior material preserves useful concepts:

- Git desired state.
- Flux as sole reconciler.
- Scoped Flux Kustomization paths.
- Kustomize layering.
- Buildkite not mutating clusters.

Prior material cannot be carried forward unchanged because:

- paths and names encode `dev/staging/production`,
- old research uses SealedSecrets rather than SOPS+age,
- current tests enforce old environment shape,
- this worktree does not yet contain INIT-008 channel registry files.

Highest-priority proposal inputs:

1. Define the channel-to-Flux mapping before changing manifests.
2. Replace SOPS/age ambiguity with a local-only verification target.
3. Decide how to dispose of or migrate the existing 38-file old-shape `k8s/`
   tree.
