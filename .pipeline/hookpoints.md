# INIT-009 Phase 5 Hookpoint Research

Generated for `worktrees/init-009-gitops-substrate/`.

Inputs read:

- `.pipeline/proposal.md` final, 978 lines.
- `.pipeline/synthesis.md`, D1-D12.
- `.pipeline/research.md`, Phase 1 evidence.
- Existing `k8s/` tree.
- `plans/proposals/gitops-foundation.md`.
- `plans/research/gitops-foundation.md`.
- `plans/research/gitops-foundation-needs.md`.
- `plans/research/gitops-foundation-hookpoints.md`.
- `infra/README.md`.
- `infra/tests/validate_platform_bootstrap.sh`.
- `plans/risk/init-009-{audit,scope,shortcut}.md`.

Summary:

- The legacy `k8s/` tree exists and has exactly 38 tracked files.
- No `gitops/` directory exists yet.
- No active code in `daemon/`, `services/`, `infra/tests/`, or migrations
  points at `k8s/` or `gitops/`.
- `infra/README.md` is still environment-root shaped and needs a cross-link
  to the GitOps layer after INIT-008 channel wording lands.
- `infra/tests/validate_platform_bootstrap.sh` is independent and should be
  preserved; the GitOps harness belongs under `gitops/tests/`.
- `flux`, `kind`, `sops`, `age`, and `age-keygen` are missing locally.
- `kubectl` is installed at `v1.34.1`; embedded Kustomize is `v5.7.1`.
- `BLOCKS_IMPLEMENTATION`: this worktree does not contain INIT-008's
  `infra/channels/dev.yaml`; SLICE-032 must consume that branch dependency
  before implementing the D12 channel contract, not copy a static fixture.

## 1. Per-Slice File Map

### SLICE-031 - Toolchain Preinstall And Legacy `k8s/` Disposal

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `gitops/scripts/install-tools.sh` | CREATE | Entry point for idempotent Linux-first install/check of `flux`, `kind`, `sops`, `age`, `age-keygen`, `kubectl`, and embedded Kustomize. | Missing on disk; parent `gitops/` is missing. Must be executable. |
| `gitops/tests/validate_gitops.sh` | CREATE | Initial harness entry point for layout/tool checks; later slices extend it. | Missing on disk. Placement mirrors `infra/tests/validate_platform_bootstrap.sh` but remains GitOps-owned. |
| `k8s/` | DELETE | Proposal D5/Q2 deletes old environment-shaped GitOps authority with no alias, wrapper, symlink, or compatibility path. | Exists on disk with 38 tracked files under `base/`, `clusters/`, `overlays/`, and `tests/`. |
| `k8s/base/controllers/kustomization.yaml` | DELETE | Part of stale old base tree. | Contains old controller-contract ConfigMap. |
| `k8s/base/kustomization.yaml` | DELETE | Part of stale old base tree. | Composes `controllers`, `namespaces`, `platform`, and `policies`. |
| `k8s/base/namespaces/kustomization.yaml` | DELETE | Part of stale old base tree. | Generates namespace resources for old base. |
| `k8s/base/namespaces/platform-system.yaml` | DELETE | Part of stale old base tree. | Namespace manifest. |
| `k8s/base/namespaces/workloads.yaml` | DELETE | Part of stale old base tree. | Namespace manifest. |
| `k8s/base/platform/kustomization.yaml` | DELETE | Part of stale old base tree. | Old metadata uses `clusterTopology=control-and-app`. |
| `k8s/base/policies/kustomization.yaml` | DELETE | Part of stale old base tree. | Old Buildkite boundary metadata, useful concept but stale path. |
| `k8s/clusters/**` | DELETE | Old per-environment, per-cluster Flux roots conflict with channel-aligned dev control root. | 24 tracked files; includes six `gotk-sync.yaml` roots pointing at `./k8s/clusters/...`. |
| `k8s/overlays/**` | DELETE | Old `dev/staging/production` environment overlays conflict with channel overlays. | 6 tracked files, one per environment/cluster role. |
| `k8s/tests/test_gitops_foundation.sh` | DELETE | Old harness validates the deleted topology. | Tracked shell test; broad references to `k8s/`, `base`, `overlays`, and `clusters`. |
| Any non-plan stale test references to `k8s/` | MODIFY/DELETE if found | Acceptance requires no active non-plan references to `k8s/(base\|clusters\|overlays)`. | Grep found no current active code/test/infra references outside the `k8s/` tree itself. |

Notes:

- This slice owns the deletion. No later slice should keep `k8s/` live.
- Shell metadata applies to `install-tools.sh` and `validate_gitops.sh`.
- Implementation note: installer acquisition sources/checksums are not listed
  in the proposal; shortcut risk SH-1 requires the implementation to pin
  official URLs plus SHA256s in the script header.

### SLICE-032 - `gitops/` Directory And Kustomize Layout

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `gitops/README.md` | CREATE | Root layout and channel-overlay overview. | Missing on disk. Later slices also modify. |
| `gitops/bases/flux-system/README.md` | CREATE | Documents active Flux base ownership. | Missing on disk. |
| `gitops/bases/flux-system/kustomization.yaml` | CREATE | Empty/initial Kustomize base that SLICE-033 populates. | Missing on disk; later modified by SLICE-033 and SLICE-035. |
| `gitops/bases/crossplane/README.md` | CREATE | Empty handoff base for INIT-017. | Missing on disk. README must name owner and empty-base rule. |
| `gitops/bases/crossplane/kustomization.yaml` | CREATE | Empty placeholder base for INIT-017. | Missing on disk. Must remain resource-empty until INIT-017. |
| `gitops/bases/cert-manager/README.md` | CREATE | Empty handoff base for INIT-018. | Missing on disk. |
| `gitops/bases/cert-manager/kustomization.yaml` | CREATE | Empty placeholder base for INIT-018. | Missing on disk. Must remain resource-empty. |
| `gitops/bases/external-dns/README.md` | CREATE | Empty handoff base for INIT-018. | Missing on disk. |
| `gitops/bases/external-dns/kustomization.yaml` | CREATE | Empty placeholder base for INIT-018. | Missing on disk. Must remain resource-empty. |
| `gitops/bases/cluster-security/README.md` | CREATE | Empty handoff base for INIT-019. | Missing on disk. |
| `gitops/bases/cluster-security/kustomization.yaml` | CREATE | Empty placeholder base for INIT-019. | Missing on disk. Must remain resource-empty. |
| `gitops/channels/dev/README.md` | CREATE | Documents active dev control-cluster channel overlay. | Missing on disk. |
| `gitops/channels/dev/kustomization.yaml` | CREATE | Active channel composition root. | Missing on disk. Must compose Flux base, empty downstream bases, and `../../secrets/dev`. |
| `gitops/secrets/dev/README.md` | CREATE | Initial per-channel secrets docs; SLICE-034 expands custody details. | Missing on disk. |
| `gitops/tests/validate_gitops.sh` | MODIFY | Adds `--layout-only` assertions. | Missing until SLICE-031 creates it. |
| `infra/channels/dev.yaml` | READ/DEPENDENCY | D12 says implementation consumes INIT-008 `dev` channel input. | Missing in this worktree; research cites sibling `worktrees/init-008-platform-bootstrap/infra/channels/dev.yaml`. |

Notes:

- `BLOCKS_IMPLEMENTATION`: the INIT-008 channel registry is absent from this
  worktree. Rebase/merge the INIT-008 branch before SLICE-032, or record a
  new decision. Do not create a parked copy as a compatibility fixture.
- Scope risk SCP-003 and shortcut risk SH-7 require layout validation to fail
  if empty downstream bases contain resources before their owning initiatives.

### SLICE-033 - Flux Self-Management Manifests And Dev Root

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `gitops/bases/flux-system/gotk-components.yaml` | CREATE | Flux controller install payload for the control cluster. | Missing on disk. Must not introduce app workloads. |
| `gitops/bases/flux-system/gotk-sync.yaml` | OMIT | Superseded by split `source-gitrepository.yaml` and `root-kustomization.yaml` files. | Intentionally omitted so the source and root reconciliation contracts stay independently testable. |
| `gitops/bases/flux-system/source-gitrepository.yaml` | CREATE | `GitRepository` named `server-manager`, interval `1m`. | Missing on disk. Must use same repo, local URL patched for kind. |
| `gitops/bases/flux-system/root-kustomization.yaml` | CREATE | Root `Kustomization` to `./gitops/channels/dev`, interval `5m`, prune/wait true. | Missing on disk. |
| `gitops/bases/flux-system/kustomization.yaml` | MODIFY | Include Flux component/source/root resources. | Created in SLICE-032. Shared touch with SLICE-032 and SLICE-035. |
| `gitops/channels/dev/flux-system.yaml` | CREATE | Channel-level Flux composition or Kustomization glue. | Missing on disk. |
| `gitops/channels/dev/patches/flux-source-local.yaml` | CREATE | Local-only source URL patch used by the kind harness. | Missing on disk. Shared with SLICE-035. |
| `gitops/tests/validate_gitops.sh` | MODIFY | Adds `--flux-render-only` checks for GitRepository/Kustomization properties and forbidden paths. | Shared with all implementation slices. |

Notes:

- Current old `k8s/clusters/*/gotk-sync.yaml` files are not modified; they are
  deleted by SLICE-031.
- Scope risk SCP-010 asks implementation/docs to clarify whether the local
  source patch is always composed or split into a local-only Kustomization.

### SLICE-034 - SOPS+age Per-Channel Secrets Workflow

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `gitops/secrets/dev/.sops.yaml` | CREATE | Per-channel SOPS creation rules with committed public age recipient. | Missing on disk. Must not contain literal `age1...`. |
| `gitops/secrets/dev/bootstrap-creds.enc.yaml` | CREATE | Encrypted sample secret proving SOPS+age decrypt path. | Missing on disk. Shortcut risk SH-5 recommends renaming to `sample-secret.enc.yaml` or `verification-fixture.enc.yaml`; proposal still names bootstrap-creds. |
| `gitops/secrets/dev/README.md` | MODIFY | Documents private-key custody and add/remove/rotate runbook contract. | Created in SLICE-032. |
| `gitops/scripts/bootstrap-flux.sh` | CREATE | Generates/uses local age key and exports `SOPS_AGE_KEY_FILE` for validation. | Missing on disk. Also owned by SLICE-035. |
| `gitops/tests/validate_gitops.sh` | MODIFY | Adds `--sops-only` decrypt verification. | Shared harness. |
| `gitops/README.md` | MODIFY | Adds SOPS+age custody model and local-only private-key guidance. | Created in SLICE-032; also modified in SLICE-035/036. |

Notes:

- There are currently no `.sops.yaml`, `*.sops.yaml`, `*.age`, or encrypted
  SOPS fixtures in the repo.
- Shortcut risk SH-4 requires the committed `.sops.yaml` to carry a real
  recipient generated or supplied during implementation.

### SLICE-035 - Local kind Verification Harness

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `gitops/scripts/bootstrap-flux.sh` | MODIFY/CREATE | End-to-end local kind bootstrap, Flux install/reconcile, local Git source, SOPS proof. | Missing on disk. Created by SLICE-034 or here; sequential integration avoids conflict. |
| `gitops/tests/validate_gitops.sh` | MODIFY | Completes full `--cluster` validation and boundary checks. | Shared with SLICE-031..034 and SLICE-036. |
| `gitops/channels/dev/patches/flux-source-local.yaml` | MODIFY | Wires local/in-cluster Git source URL for kind. | Created in SLICE-033. |
| `gitops/bases/flux-system/*` | MODIFY | May adjust Flux manifests for bootstrap details. | Created/populated in SLICE-032/033. |
| `gitops/README.md` | MODIFY | Documents local bootstrap commands and proof boundaries. | Created in SLICE-032. |

Notes:

- `infra/tests/validate_platform_bootstrap.sh` stays in place and should still
  pass; do not fold it into the GitOps harness.
- Shortcut risks SH-2, SH-6, SH-8, and SH-10 are concentrated here.

### SLICE-036 - Documentation And Handoff

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `gitops/README.md` | MODIFY | Final authority for layout, channel overlays, self-managing Flux, SOPS+age, and local verification. | Missing today; created earlier. |
| `infra/README.md` | MODIFY | Cross-link from infra substrate/channel model to `gitops/` root. | Exists; currently documents `infra/environments/{dev,staging,production}` and no `gitops/` link. |
| `plans/proposals/gitops-foundation.md` | DELETE or REWRITE | Old proposal is active-looking but environment-shaped and says it does not write Flux manifests. | Exists, 321 lines. Default disposal is delete unless concepts are rewritten without contradictions. |
| `plans/research/gitops-foundation.md` | DELETE or SUPERSEDE | Old research preserves Flux/Kustomize concepts but includes stale SealedSecrets and old `k8s/` implementation summary. | Exists, 205 lines. Useful evidence is already embedded in `.pipeline/research.md`. |
| `plans/research/gitops-foundation-needs.md` | DELETE or REWRITE | Old needs map points directly at `k8s/base`, `k8s/overlays`, and `k8s/clusters`. | Exists, 167 lines. Default delete unless reduced to evergreen needs. |
| `plans/research/gitops-foundation-hookpoints.md` | DELETE | Old hookpoints assume greenfield `k8s/` and SealedSecrets. | Exists, 148 lines. Proposal explicitly says current hookpoints must replace it. |
| Local index/planning notes naming `k8s/` as active | MODIFY if in active docs; otherwise leave historical docs with explicit stale status | Prevents stale references from acting as live authority. | `product-strategy/engineering research.md` also names `k8s/` as existing infra; not in proposal file list but grep flagged it. |
| `gitops/tests/validate_gitops.sh` | MODIFY | Adds `--docs-only` stale-reference checks. | Shared harness. |

Notes:

- Scope risk SCP-002: do not rewrite INIT-008 channel-registry content in
  `infra/README.md`; only remove stale environment-root guidance and add a
  one-line GitOps cross-link.
- Shortcut risk SH-9: a banner alone is not enough if contradictory old
  sections remain. Delete or physically remove contradictions.

## 2. `k8s/` Deletion Plan

Owner: SLICE-031.

Top-level structure and tracked file counts:

| Path | File count | Notes |
|---|---:|---|
| `k8s/base/` | 7 | Old shared Kustomize base: controllers, namespaces, platform metadata, policies. |
| `k8s/clusters/` | 24 | Three environments times two cluster roles, with `gotk-sync.yaml` and manifest slots. |
| `k8s/overlays/` | 6 | `dev`, `staging`, `production` overlays for app/control roles. |
| `k8s/tests/` | 1 | Old topology acceptance test. |
| `k8s/` total | 38 | Verified with `git ls-files k8s \| wc -l`. |

Deletion sequence:

1. Create `gitops/scripts/install-tools.sh` and initial
   `gitops/tests/validate_gitops.sh` so the new validation entrypoint exists.
2. Delete `k8s/tests/test_gitops_foundation.sh`; its assertions are not
   reusable as active tests because they validate old environment roots.
3. Delete `k8s/clusters/**`; this removes old Flux roots that point at
   `./k8s/clusters/...`.
4. Delete `k8s/overlays/**`; this removes old environment/cluster-role
   overlays.
5. Delete `k8s/base/**`; concepts may be re-expressed under `gitops/bases/`,
   but no file or path compatibility remains.
6. Remove empty `k8s/` directories.
7. Run:

```bash
test ! -e k8s
rg 'k8s/(base|clusters|overlays)' . --glob '!plans/**' --glob '!.pipeline/**' && exit 1 || true
```

Current code references:

- No `daemon/`, `services/`, `infra/tests/`, migrations, or root runtime files
  reference `k8s/` or `gitops/`.
- The only active on-disk code references are inside the soon-deleted `k8s/`
  tree itself.
- Planning/doc references exist and are handled by SLICE-036.

## 3. New `gitops/` Directory Layout

Full target skeleton:

```text
gitops/
  README.md
  bases/
    flux-system/
      README.md
      kustomization.yaml
      gotk-components.yaml
      source-gitrepository.yaml
      root-kustomization.yaml
    crossplane/
      README.md
      kustomization.yaml
    cert-manager/
      README.md
      kustomization.yaml
    external-dns/
      README.md
      kustomization.yaml
    cluster-security/
      README.md
      kustomization.yaml
  channels/
    dev/
      README.md
      kustomization.yaml
      flux-system.yaml
      patches/
        flux-source-local.yaml
  secrets/
    dev/
      .sops.yaml
      README.md
      bootstrap-creds.enc.yaml
  scripts/
    install-tools.sh
    bootstrap-flux.sh
  tests/
    validate_gitops.sh
```

Placeholder base requirements:

- `gitops/bases/crossplane/` is owned by INIT-017.
- `gitops/bases/cert-manager/` is owned by INIT-018.
- `gitops/bases/external-dns/` is owned by INIT-018.
- `gitops/bases/cluster-security/` is owned by INIT-019.
- Each placeholder contains only `README.md` and an empty
  `kustomization.yaml` until its owning initiative lands.
- `validate_gitops.sh --layout-only` should enforce the empty-base rule.

Harness placement:

- `gitops/tests/validate_gitops.sh` is the GitOps harness.
- `infra/tests/validate_platform_bootstrap.sh` remains the infra harness.
- The two harnesses can be called independently; INIT-009 acceptance requires
  the infra harness to keep passing but not to move.

## 4. Cross-Reference Grep

Repo-wide `k8s/` references:

- `k8s/**`: expected current implementation references; all deleted in
  SLICE-031.
- `plans/research/gitops-foundation.md`: old implementation summary and
  `k8s/` source list; delete/supersede in SLICE-036.
- `plans/research/gitops-foundation-needs.md`: old `k8s/base`,
  `k8s/overlays`, and `k8s/clusters` needs; delete/rewrite in SLICE-036.
- `plans/research/gitops-foundation-hookpoints.md`: old hookpoint map;
  delete in SLICE-036.
- `product-strategy/engineering research.md`: says `infra/` and `k8s/`
  exist as infrastructure foundations. If treated as current strategy input,
  revise or annotate as superseded by INIT-009.
- `plans/research/buildkite-capabilities.md`: URL contains
  `agent-stack-k8s`; unrelated to repo path and can stay.
- `plans/risk/init-009-*`: current risk evidence; can stay as historical
  pipeline material.
- `.tmp/gitops-foundation-*`: scratch/review material; not active authority.

Current `gitops/` references outside `.pipeline/`:

- Prior GitOps planning and risk files reference `gitops-foundation.md`, not a
  root `gitops/` directory.
- No current active `gitops/` tree exists.
- `plans/risk/platform-bootstrap-*` references `gitops-foundation.md` as a
  handoff; not a root directory reference but stale after SLICE-036 disposal.

Tool/documentation contradictions:

- `plans/research/gitops-foundation.md` discusses SealedSecrets; contradicts
  INIT-009 SOPS+age and should be deleted/superseded.
- `plans/research/gitops-foundation.md` uses Kustomization interval `10m`;
  proposal pins root Kustomization `5m`.
- Old proposal/research use `base -> overlays -> clusters/<env>`; proposal
  replaces that with `gitops/bases`, `gitops/channels/<channel>`, and
  `gitops/secrets/<channel>`.
- `plans/proposals/platform-bootstrap.md` stops before Flux and still names
  environment roots; treat as pre-channel where it conflicts with INIT-008.
- `plans/platform-decisions-overlay.md` says Flux replaces Argo CD; this
  supports INIT-009 and does not contradict the new layout.
- `plans/research/buildkite-capabilities.md` says Buildkite plus Flux should
  replace custom CI/CD choreography; supports the boundary.

## 5. Toolchain Prerequisite Verification

Local verification result:

| Tool | Installed? | Version/status | Required by proposal | Install command to document in installer |
|---|---:|---|---|---|
| `flux` | N | Missing | `>= 2.8.0` | Download official Flux release tarball for `v2.8.0`, verify SHA256, install `flux` to `/usr/local/bin`. |
| `kind` | N | Missing | `>= 0.31.0` | `curl -fsSLo kind https://kind.sigs.k8s.io/dl/v0.31.0/kind-linux-amd64`; verify SHA256; install executable. |
| `sops` | N | Missing | `>= 3.10.0` | Download official `getsops/sops` `v3.10.0` Linux amd64 binary, verify SHA256, install executable. |
| `age` | N | Missing | `>= 1.3.0` | Download official `FiloSottile/age` `v1.3.0` Linux amd64 tarball, verify SHA256, install `age`. |
| `age-keygen` | N | Missing | `>= 1.3.0` | Same `age` tarball; install bundled `age-keygen`. |
| `kubectl` | Y | `/usr/local/bin/kubectl`, client `v1.34.1` | `>= 1.31.0` | Already satisfies requirement; installer can skip or verify official `dl.k8s.io` release if absent. |
| embedded Kustomize | Y | `kubectl` reports `kustomizeVersion: v5.7.1` | `v5.7.1` | No standalone install required. Validate via `kubectl version --client -o yaml`. |
| standalone `kustomize` | N | Missing | Not required | Do not require; proposal accepts embedded Kustomize. |

Idempotent installer expectations:

- `--check` prints every installed version and exits non-zero for missing or
  below-minimum tools.
- Installer must not use arbitrary `curl | bash`.
- Installer header should list exact official release URLs and SHA256s.
- Installer may use official release artifacts, Linux package manager, or
  pinned module proxy as allowed by shortcut risk SH-1.

## 6. Stale Material Disposal

Default under no-backwards-compatibility: delete stale active materials unless
they are rewritten to remove contradictions.

| Path | Recommendation | Why |
|---|---|---|
| `plans/proposals/gitops-foundation.md` | DELETE or full rewrite; prefer DELETE if `gitops/README.md` carries surviving concepts. | Active-looking proposal is environment-shaped, says INIT-009 does not write Flux manifests, and conflicts with channel layout. |
| `plans/research/gitops-foundation.md` | DELETE/supersede. | Useful Flux/Kustomize evidence is embedded in pipeline docs; SealedSecrets and `k8s/` summary are stale. |
| `plans/research/gitops-foundation-needs.md` | DELETE unless reduced to evergreen principles. | Current file maps needs to `k8s/` paths and old environment separation. |
| `plans/research/gitops-foundation-hookpoints.md` | DELETE. | It is explicitly invalid after current risk gate and assumes old `k8s/`. |
| `product-strategy/engineering research.md` | Consider a narrow supersession note if it remains active planning input. | Grep flags `infra/` + `k8s/` as existing foundations. Not in proposal's required stale list, so track for SLICE-036. |

## 7. Implementation Order And Shared Files

Recomputed order:

1. SLICE-031: create tool/harness entrypoints, delete `k8s/`.
2. SLICE-032: create `gitops/` skeleton and empty downstream bases.
3. SLICE-033: add active Flux manifests and dev channel root.
4. SLICE-034: add SOPS+age policy and encrypted fixture.
5. SLICE-035: integrate full local kind bootstrap/reconcile harness.
6. SLICE-036: finalize docs, infra cross-link, and stale-material disposal.

Parallelism:

- SLICE-033 and SLICE-034 are conceptually parallel after SLICE-032, but both
  touch `gitops/tests/validate_gitops.sh` and `gitops/README.md`.
- To avoid merge conflicts, run all slices sequentially in this worktree.

Shared file conflict map:

| Path | Slices | Conflict note |
|---|---|---|
| `gitops/tests/validate_gitops.sh` | 031, 032, 033, 034, 035, 036 | Highest-conflict file; sequential edits only. |
| `gitops/README.md` | 032, 034, 035, 036 | Docs accumulate; sequential edits. |
| `gitops/bases/flux-system/kustomization.yaml` | 032, 033, 035 | Created empty, then populated/tuned. |
| `gitops/channels/dev/patches/flux-source-local.yaml` | 033, 035 | Created for render, then wired for kind source. |
| `gitops/scripts/bootstrap-flux.sh` | 034, 035 | Secret key setup and cluster bootstrap must be integrated. |
| `gitops/secrets/dev/README.md` | 032, 034 | Initial README then custody details. |
| `infra/README.md` | 036 only | Avoid changing INIT-008 content beyond cross-link/stale removal. |
| stale `plans/**/gitops-foundation*` | 036 only | Delete/rewrite after GitOps docs are authoritative. |

Per-slice action count, using actual on-disk legacy deletion count:

| Slice | CREATE | MODIFY | DELETE | Conditional/Dependency |
|---|---:|---:|---:|---|
| SLICE-031 | 2 | 0 | 38 | 0 active non-plan `k8s/` refs found. |
| SLICE-032 | 14 | 1 | 0 | Requires INIT-008 `infra/channels/dev.yaml`, currently absent. |
| SLICE-033 | 6 | 2 | 0 | None. |
| SLICE-034 | 3 | 3 | 0 | Fixture filename may need proposal note if renamed. |
| SLICE-035 | 0 | 5 | 0 | `bootstrap-flux.sh` created in SLICE-034, completed here. |
| SLICE-036 | 0 | 4 | 4 | Delete is preferred stale-material disposal; rewrite only if contradictions are physically removed. |

## 8. Risk-Deferred LOW Observations To Honor

Audit risk:

| Observation | Slice | Handling |
|---|---|---|
| No audit checklist findings. | Track only | `plans/risk/init-009-audit.md` is LOW with no findings. |

Scope risk:

| ID | Observation | Slice | Handling |
|---|---|---|---|
| SCP-001 | Anti-scope should explicitly enumerate INIT-015, INIT-016, INIT-020. | SLICE-036 | Add to docs/anti-scope or successor handoff. |
| SCP-002 | `infra/README.md` must not rewrite INIT-008 channel registry content. | SLICE-036 | Limit change to stale environment removal plus `gitops/` cross-link. |
| SCP-003 | Empty downstream bases need programmatic validation. | SLICE-032 | Add `--layout-only` checks for no `resources:` entries and owner READMEs. |
| SCP-004 | INIT-018 may later collapse/rename cert-manager and ExternalDNS bases. | SLICE-036 | Note INIT-018 owns future restructuring; current bases remain empty. |
| SCP-010 | Local source patch inside channel overlay may confuse future deployment. | SLICE-033/036 | Document whether always composed or local-only split; track for future deployment initiative if unchanged. |

Shortcut risk:

| ID | Observation | Slice | Handling |
|---|---|---|---|
| SH-1 | Tool downloads need official sources and SHA256s. | SLICE-031 | Pin URLs/checksums in installer header. |
| SH-2 | Reusing kind clusters can mask stale Flux objects. | SLICE-035 | Fresh cluster by default; require `--reuse` and extra assertions. |
| SH-3 | Do not copy INIT-008 `dev` channel fixture. | SLICE-032 | Consume branch dependency or mark transient fixture with delete-on-merge invariant. Currently blocks. |
| SH-4 | Do not commit literal `age1...`. | SLICE-034 | Generate/use real recipient and prove decrypt. |
| SH-5 | `bootstrap-creds.enc.yaml` name may invite real creds. | SLICE-034 | Prefer rename if allowed; otherwise document fixture-only loudly. Proposal names old path, so changing name may require proposal note. |
| SH-6 | Empty-base reconcile can fake completion. | SLICE-035 | Assert applied revision/source SHA, not just green status. |
| SH-7 | Empty downstream bases need enforcement. | SLICE-032 | Same as SCP-003; fail on resources before owner initiative. |
| SH-8 | Local Git source mechanism must be locked. | SLICE-035 | Prefer in-kind `gitserver` fed by `git bundle`; forbid public hosts. |
| SH-9 | Banner-only stale disposal is insufficient. | SLICE-036 | Delete old docs or remove contradictory sections physically. |
| SH-10 | Flux branch must match worktree branch/commit. | SLICE-035 | Derive branch from `git rev-parse --abbrev-ref HEAD`; assert Flux revision equals `git rev-parse HEAD`. |

## 9. Implementation Prerequisites Table

| Prerequisite | Status | Carry-forward |
|---|---|---|
| INIT-008 channel registry in this worktree | MISSING | `BLOCKS_IMPLEMENTATION` for SLICE-032 D12. Rebase/merge INIT-008 or record new decision. |
| `flux` CLI | MISSING | Install in SLICE-031 before Flux render/bootstrap checks. |
| `kind` CLI | MISSING | Install in SLICE-031 before SLICE-035. |
| `sops` CLI | MISSING | Install in SLICE-031 before SLICE-034 decrypt checks. |
| `age` and `age-keygen` | MISSING | Install in SLICE-031 before SLICE-034 key generation. |
| `kubectl` | PRESENT | `/usr/local/bin/kubectl`, `v1.34.1`. |
| embedded Kustomize | PRESENT | `v5.7.1` through `kubectl`. |
| Local-only constraint | ACTIVE | Harness must not call Vultr/Cloudflare, run `tofu apply`, push images, deploy workloads, or depend on public Git. |
| Discord-visible writes | NOT APPLICABLE | INIT-009 is local file/tooling work only; no Tier 3 Discord action is involved. |

## 10. BLOCKS_IMPLEMENTATION

| Flag | Affected slice | Evidence | Required resolution |
|---|---|---|---|
| `BLOCKS_IMPLEMENTATION: INIT-008_CHANNEL_REGISTRY_ABSENT` | SLICE-032 | This worktree has only `infra/environments/{dev,staging,production}`. Research cites sibling `worktrees/init-008-platform-bootstrap/infra/channels/dev.yaml`; no `infra/channels/dev.yaml` exists here. | Rebase/merge the INIT-008 branch before implementation, or record a new decision changing D12. Do not copy a static channel fixture as a compatibility shim. |
