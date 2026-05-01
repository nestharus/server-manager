# BUG-4 — Supported-surface risk gate

**Verdict:** LOW

BUG-4 (local Flux pinned to a stale in-cluster gitserver snapshot) is
recovered by an operator-only CLI flag that re-runs the existing seed
path against the existing in-cluster `git-daemon`. The proposal modifies
exactly two scripts and one operator doc:

- `infra/scripts/bring-up-local-channel.sh` — adds
  `--reseed-gitserver-only`, mutually exclusive with `--force`,
  `--repair`, and `--cluster-only` (proposal §3 lines 129-137).
- `infra/scripts/install-flux-for-channel.sh` — adds
  `--reseed-gitserver-only`, an early branch that reuses
  `git_daemon_pod`, `wait_for_git_daemon`, `seed_git_daemon`,
  `apply_source_crs`, and `wait_for_source_reconciliation`
  (proposal §3 lines 138-149).
- `infra/README.md` — new "Narrow local GitOps reseed" subsection
  (proposal §3 lines 152-160).

No application source, no manifest, no Helm chart, no CRD, no
Kustomization spec, no controller image tag, and no container env var
is touched (proposal §3 "Scope boundary" line 162-165 and §5 anti-scope
lines 277-287). The change exclusively adds an operator-driven *re-entry*
into the same `seed_git_daemon` write surface that already exists in
`install-flux-for-channel.sh` lines 168-205.

## Surfaces touched

### 1. Public API surface — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Application HTTP / gRPC routes (`services/api/**`, `services/web/**`, `services/discord/**`) | as deployed | unchanged — proposal §3 "Scope boundary" line 162-165 limits source code changes to `infra/scripts/`; anti-scope §5 forbids touching the GitRepository URL, Pomerium, Authentik, or any controller (lines 278-287) | none |
| Operator CLI: `bring-up-local-channel.sh` flags (`--channel`, `--force`, `--repair`, `--cluster-only`, `-h/--help`) | as defined at script lines 16-33 | adds `--reseed-gitserver-only`, mutually exclusive with `--force`, `--repair`, `--cluster-only` (proposal Q2 lock at lines 38-58, §3 lines 131-137) | none — purely additive flag; refusing the flag combo is a fail-fast `die` consistent with the existing `--force/--repair` mutex at script lines 94-96 |
| Operator CLI: `install-flux-for-channel.sh` flags (`--channel`, `-h/--help`) | as defined at script lines 30-42 | adds `--reseed-gitserver-only` and an early-exit reseed branch; in non-reseed mode the existing `main()` ordering at script lines 474-499 is unchanged | none — additive flag; default invocation behavior preserved |
| Flux `GitRepository/humility-local` URL | `http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git` (RCA lines 17-21) | unchanged — anti-scope §5 line 278 explicitly forbids repointing Flux to GitHub | none |
| Flux `Kustomization/humility-local` spec | as rendered into the in-cluster snapshot | unchanged — proposal Q4 lines 78-101 keeps the resume patch (`spec.suspend: false`) as an explicit *operator step after TG-1*, not script behavior; anti-scope §5 line 287 forbids in-script Kustomization resume |
| Synthetic gitserver commit identity | `Humility GitOps Seed <gitops-seed@humility.local>` / subject `seed local gitops snapshot` (RCA lines 43-49; install script lines 195-198) | unchanged — `seed_git_daemon` is reused verbatim, which means the new synthetic commit uses the same author, committer, and subject; only the SHA differs | none — gate criterion 1's intent is "no contract change observable to clients"; clients of the in-cluster gitserver are Flux's source-controller (consumes `refs/heads/main` regardless of SHA) and OPAL (consumes `policy/` content regardless of SHA), and both already tolerate a new synthetic commit on each post-install run |

Risk on §1: **none** — gate criterion 1 (no public API change) holds.
The proposal's diff budget of "under 230 changed lines" across two
scripts and one README (proposal §6 lines 290-303) means there is no
new exported endpoint, no removed flag, no renamed flag, and no
re-typed CLI surface. Operator-CLI additions are purely opt-in.

### 2. Cluster-side surface — reused, not extended

This is gate criterion 2's primary subject. The proposal's reseed mode
performs only actions that the existing `install-flux-for-channel.sh`
post-install path *already* performs in this exact order:

| Cluster action | Existing path (line in `install-flux-for-channel.sh`) | Reseed mode (proposal §3 lines 144-149) | Risk |
|---|---|---|---|
| Apply `gitops/sources/local/git-daemon.yaml` | line 479 | reuses; same file path; `kubectl apply` is idempotent against the live `Namespace/git-system`, `PersistentVolumeClaim/git-daemon-pvc`, `Deployment/git-daemon`, `Service/git-local` (RCA lines 56-66) | none — manifest already lives in the cluster; re-apply is a no-op when the manifest matches the current snapshot |
| Wait for git-daemon (`wait_for_git_daemon`) | line 480 (calls helper at lines 147-166) | reuses helper verbatim | none — read-only readiness probe |
| Seed `/srv/git/humility-local.git` (`seed_git_daemon`) | line 481 (calls helper at lines 168-205) | reuses helper verbatim — same `kubectl exec` into `git-daemon` container, same `tar` upload from `${SNAPSHOT_DIR}`, same `git init --initial-branch=main`, same author/committer, same `git push --force origin main`, same `git --git-dir update-server-info` | none — this *is* the existing write surface; the recovery is "re-do the seed step that was last done at 2026-04-29T06:29:30Z, this time from the current worktree" (RCA lines 43-49, 130-184) |
| Apply rendered source CRs (`apply_source_crs`) | line 484 (calls helper at lines 221-225) | reuses helper verbatim — same two files: `${SNAPSHOT_DIR}/gitops/sources/${CHANNEL_ID}/gitrepository.yaml` and `${SNAPSHOT_DIR}/gitops/sources/${CHANNEL_ID}/kustomization.yaml` | none — `kubectl apply` against the same generated resources |
| Wait for `GitRepository/humility-local` Ready (`wait_for_source_reconciliation`) | line 485 (calls helper at lines 241-249) | reuses helper verbatim | none — read-only `kubectl wait` |
| Render snapshot via `render-gitops-source.py` | line 472 | reuses; same renderer, same `${REPO_ROOT}/.tmp/gitops-source/${CHANNEL_ID}` output (proposal Q3 lock lines 60-75) | none — write only to `.tmp/`, not to the cluster |

Skipped vs. existing post-install path (proposal Q2 lock lines 50-58):

| Skipped action (existing line) | Why skip is safe |
|---|---|
| `kubectl apply -f gitops/flux/gotk-components.yaml` and Flux controller wait (lines 475-476) | Flux controllers are already installed and healthy; the RCA confirms `source-controller` is actively polling and `kustomize-controller` last reconciled at the stale revision (research lines 36-37) |
| `ensure_age_secret` (line 483) | The SOPS age secret is already present in `flux-system` (or whichever `DECRYPTION_SECRET_NAMESPACE` resolves to), since the cluster is *currently* reconciling a SOPS-encrypted snapshot (RCA lines 17-29). The bootstrap helper at script lines 207-219 is a no-op when the secret exists, so even an inadvertent inclusion would be safe; explicit skip is cleaner |
| `wait_for_infisical_server`, `bootstrap_infisical_*`, `refresh_minio_after_storage_bootstrap`, `refresh_infisical_operator_after_bootstrap`, `wait_for_infisical_runtime` (lines 487-496) | Infisical is already bootstrapped and serving secrets; re-running these would attempt to re-create universal-auth identities, re-rotate object-storage credentials, and rolling-restart the Infisical operator — broader blast radius and unrelated to the reseed root cause (proposal Q2 line 56-58) |
| `distribute_step_ca_trust` and `bootstrap_pomerium_oidc_application` (called from `bring-up-local-channel.sh:install_flux_post_install`, script lines 416-425) | step-ca trust is already distributed to `auth-system/pomerium-step-ca-trust` and Pomerium is using it; OIDC bootstrap re-issues an Authentik OAuth2 Provider mutation and a Pomerium pod restart — both unrelated to the reseed root cause (proposal Q2 line 56-58) |
| `wait_for_reconciliation` (line 497) — wait for `Kustomization/humility-local` Ready | Intentionally skipped because the Kustomization is currently `spec.suspend: true` (RCA lines 25-32). Resume is an explicit operator action *after* TG-1 verifies the GitRepository advanced (proposal Q4 lines 78-101, anti-scope §5 line 287). Implicit resume in the script would re-introduce the regression-risk path identified in RCA "Flux Resume Safety" lines 187-205 |
| Cluster create/delete/repair (`create_cluster`, `delete_existing_state`) | proposal §3 lines 134-137 explicitly requires reseed mode to "Not create, delete, repair, or recreate the k3d cluster"; mutex with `--force`/`--repair` at proposal lines 45-46 enforces this at the operator-CLI level |

Risk on §2: **none** — gate criterion 2 (no cluster-side changes
beyond what existing `seed_git_daemon` already does) holds. The reseed
mode is *exactly* the union of existing helpers
`{apply git-daemon.yaml, wait_for_git_daemon, seed_git_daemon,
apply_source_crs, wait_for_source_reconciliation}` — each of which is
already invoked unconditionally on every full post-install. The
reseed-only mode is a *narrower* subset of the existing post-install,
not a superset.

The one new behavior to flag: a successful reseed produces a new
synthetic commit SHA on `refs/heads/main` of the in-cluster bare repo,
which Flux's `source-controller` will publish as a new artifact
revision. RCA "Flux Resume Safety" lines 187-205 already documents
that "Resuming `Kustomization/humility-local` without changing the
gitserver source would not advance Flux. It would reconcile the same
`main@sha1:5d872983...` artifact again." The reseed advances the
artifact; downstream behavior (Kustomization re-reconcile against the
new revision) is then gated on the explicit operator resume step in
TG-2 (proposal §4 lines 196-227).

### 3. Environment variables — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `bring-up-local-channel.sh` env reads | `K3D_REGISTRY_PORT` (script line 13, default 5000) | unchanged — proposal §3 lines 129-137 adds only flag parsing; no new env reads | none |
| `install-flux-for-channel.sh` env reads | none beyond `KUBECONFIG` set internally to the resolved `KUBECONFIG_PATH` (script lines 119-125) | unchanged — proposal §3 lines 138-149 adds only flag parsing and a reseed branch using existing helpers | none |
| Container env vars (any Deployment under `gitops/**`) | as rendered | unchanged — proposal touches no manifest under `gitops/**` (proposal §3 line 162-165) | none |
| Flux/source-controller pod env | as deployed by `gitops/flux/gotk-components.yaml` | unchanged — proposal anti-scope §5 line 287 forbids in-script controller re-apply beyond the existing `git-daemon.yaml` apply | none |

Risk on §3: **none** — gate criterion 3 (no env vars) holds. The
proposal introduces zero new env-var reads and zero new env-var writes;
the only operator-visible knob is the new CLI flag.

### 4. Database migrations — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| API service Alembic head | current head | unchanged — proposal §3 line 162-165 limits source code changes to `infra/scripts/`; no `services/api/migrations/**` touched | none |
| Postgres / CNPG / Infisical Postgres schemas | as deployed | unchanged — anti-scope §5 line 280-281 explicitly forbids touching Pomerium/Authentik secrets; by extension, no DB schema work is in scope | none |
| In-cluster bare git repo `/srv/git/humility-local.git` | one synthetic commit at `5d872983` (RCA lines 17-22, 130-138) | a new synthetic commit on `refs/heads/main` rendered from the current worktree (proposal §1 lines 5-14, §3 lines 144-149) | none — this is git data, not a database schema; the gate's intent is "no Alembic / SQL DDL work", which holds. The git-data write is the existing `seed_git_daemon` surface (gate criterion 2) |

Risk on §4: **none** — gate criterion 4 (no DB migrations) holds.

### 5. Dependencies — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Required CLI tools (`bring-up-local-channel.sh`) | `k3d`, `docker`, `kubectl`, plus `infra/scripts/install-cluster-tools.sh --check` (script lines 610-616) | unchanged — proposal §3 lines 129-137 adds only flag parsing | none |
| Required CLI tools (`install-flux-for-channel.sh`) | `kubectl`, `tar`, `base64`, `python3` or `python` (script lines 448-451) | unchanged — proposal §3 lines 138-149 reuses helpers that already require these tools | none |
| New Python packages, Helm charts, container images, controllers, or CRDs | none | none — proposal §3 lines 162-165 limits source code changes to `infra/scripts/`; anti-scope §5 lines 282-285 explicitly forbids "a CI sync workflow", "a standalone GitHub-to-gitserver mirror, CronJob, or controller" | none |
| `render-gitops-source.py` invocation | `${REPO_ROOT}/.tmp/gitops-source/${CHANNEL_ID}` (script line 472) | reused verbatim (proposal §3 lines 144-145, Q3 lock lines 60-75) | none — same renderer, same output path |

Risk on §5: **none** — gate criterion 5 (no new dependencies) holds.

### 6. `git-system` namespace + `git-daemon` manifest reuse — confirmed

This is gate criterion 6's explicit subject.

| Surface | Pre (live in cluster per RCA §Architecture lines 56-87) | Post (reseed mode) | Reuse evidence |
|---|---|---|---|
| `Namespace/git-system` | exists | unchanged — `kubectl apply -f gitops/sources/local/git-daemon.yaml` re-asserts existing namespace metadata; no spec change | manifest path is the same one already applied at install script line 479; reseed mode reuses (proposal §3 line 146) |
| `Deployment/git-daemon` (image `alpine/git:v2.45.2`, two containers `git-daemon` + `git-http`) | exists, healthy (RCA lines 56-73) | unchanged — re-apply is a no-op when the manifest matches; if the manifest in the worktree has drifted from the live spec, that drift would also be applied on the *next* full post-install, so reseed mode is not introducing a new drift surface | proposal §3 line 146 reuses the same file path |
| `Service/git-local` (`ClusterIP`, port `8080`) | exists (RCA line 64) | unchanged — same manifest reapply | proposal §3 line 146 |
| `PersistentVolumeClaim/git-daemon-pvc` (1Gi, `ReadWriteOnce`, `Delete` reclaim) | bound to local-path PV `pvc-16645b3f-d048-4d2d-b534-573a5af68833` on `k3d-humility-local-server-0` (RCA lines 79-87) | unchanged — `kubectl apply` against an existing bound PVC does not rebind storage; PV reclaim policy is unchanged | none — gate intent is "no new persistence surface", which holds |
| Bare repo `/srv/git/humility-local.git` HEAD | `refs/heads/main` -> `5d872983c9d8d2b708023f185682dbecadcfc2d4` (RCA lines 130-138) | new synthetic SHA on `refs/heads/main` rendered from current worktree | this is the *intended* recovery effect (proposal §1 lines 5-14, TG-1 lines 168-194); the write surface is `seed_git_daemon` (existing helper, gate criterion 2) |
| `git-daemon` container exec surface (`kubectl exec ... -c git-daemon`) | already used by full post-install at install script lines 178-204 | reused verbatim | proposal §3 line 142 reuses `git_daemon_pod` and `seed_git_daemon` helpers |
| `git-http` container HTTP surface (BusyBox `httpd` + `git http-backend` on port 8080) | already serving Flux's `source-controller` reads (RCA lines 67-77) | unchanged — reseed writes through the `git-daemon` exec container, not through the `git-http` HTTP surface; `git-http` is only a reader | none |

Risk on §6: **none** — gate criterion 6 (`git-system` namespace +
manifest already exist; reseed only reuses them) holds. The proposal
adds zero new Kubernetes resources, zero new namespaces, zero new
PVCs/PVs, and zero new Services. Every cluster-side surface the
reseed mode touches is already defined, applied, and bound by the
existing post-install path.

### 7. Operator documentation — additive

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `infra/README.md` GitOps Substrate section | as documented (operator runs `bring-up-local-channel.sh` with current flags) | adds a "Narrow local GitOps reseed" subsection covering when to use `--reseed-gitserver-only`, the TG-1 artifact-revision check, the explicit `kubectl patch ... spec.suspend=false` resume command, and the `flux reconcile` / `kubectl wait` watch sequence (proposal §3 lines 152-160, §4 TG-4 lines 263-275) | none — documentation-only addition |
| AGENTS.md | unchanged — proposal does not edit AGENTS.md | unchanged | none |

Risk on §7: **none** — operator docs surface is additive.

## Supported-surface findings summary

| Gate | Verdict |
|---|---|
| 1. No public API change | PASS — diff is two scripts (CLI flag added) and one README; no app source, no HTTP/gRPC route, no manifest under `gitops/**`, no Flux URL change (proposal §3 lines 162-165, anti-scope §5 lines 277-287) |
| 2. No cluster-side changes beyond what existing `seed_git_daemon` already does | PASS — reseed mode is the strict subset `{apply git-daemon.yaml, wait_for_git_daemon, seed_git_daemon, apply_source_crs, wait_for_source_reconciliation}` of helpers already invoked on every full post-install (install-flux-for-channel.sh:478-485); skipped subset (Infisical bootstraps, Pomerium OIDC bootstrap, step-ca trust, full controller re-apply, Kustomization resume) is enumerated in proposal Q2 lines 50-58 |
| 3. No env vars | PASS — proposal adds zero env-var reads and zero env-var writes; no Deployment env changes |
| 4. No DB migrations | PASS — no Alembic head change; the only data write is the existing `seed_git_daemon` git push to `/srv/git/humility-local.git` |
| 5. No new dependencies | PASS — reuses already-required tools (`kubectl`, `tar`, `base64`, `python3`/`python`, `k3d`, `docker`, `render-gitops-source.py`); anti-scope §5 lines 282-285 forbids adding a CronJob, controller, mirror, or CI workflow |
| 6. `git-system` namespace + manifest already exist; reseed only reuses them | PASS — `Namespace/git-system`, `Deployment/git-daemon`, `Service/git-local`, `PersistentVolumeClaim/git-daemon-pvc` are all defined in `gitops/sources/local/git-daemon.yaml` and live in cluster (RCA lines 56-87); reseed mode re-applies the same file (idempotent), waits for the existing Deployment, execs the existing `git-daemon` container, and pushes to the existing bare repo at `/srv/git/humility-local.git` |

## Out-of-scope items intentionally not addressed

- Repointing `GitRepository/humility-local` at GitHub (RCA Option D
  lines 252-264, proposal anti-scope §5 line 278). Would change the
  channel contract, introduce GitHub auth/network as a new local-Flux
  dependency, and require OPAL repo URL decisions; explicitly out of
  scope.
- Background GitHub-to-gitserver sync (RCA "Commit Flow" line 122,
  proposal anti-scope §5 lines 282-285). Would add a new
  controller/CronJob/CI surface; explicitly out of scope.
- Direct Pomerium / Authentik secret manipulation (proposal anti-scope
  §5 lines 280-281). They re-sync from Infisical; reseed mode skips
  Pomerium OIDC bootstrap and step-ca trust distribution.
- Kustomization resume inside the script (proposal anti-scope §5
  line 287, Q4 lines 78-101). Resume remains an explicit operator
  step gated on TG-1 evidence that the GitRepository artifact
  advanced; otherwise the resumed Kustomization would reconcile the
  *old* artifact and risk regression/drift enforcement (RCA "Flux
  Resume Safety" lines 187-205).
- Hand-copy of selected manifests into the bare repo (proposal
  anti-scope §5 line 286, Q3 lock lines 60-75). The reseed must
  render a *complete* snapshot via `render-gitops-source.py` so
  Flux, OPAL policy materialization, and the `gitops-snapshot-marker.yaml`
  sentinel stay aligned with the documented local GitOps shape.
- Full local re-bootstrap as the recovery mechanism (RCA Option B
  lines 224-237, proposal anti-scope §5 line 283). Would re-run
  Infisical/Pomerium/step-ca bootstraps and broaden blast radius
  beyond the reseed root cause.

## Verdict

**LOW** — the change adds an operator-only CLI flag that re-invokes
the existing `seed_git_daemon` helper chain against the existing
in-cluster `git-daemon` Deployment in the existing `git-system`
namespace, writing to the existing bare repo at
`/srv/git/humility-local.git`. Zero new Kubernetes resources, zero
new env vars, zero new dependencies, zero new public APIs, zero new
DB schema. The only behavioral delta is a new synthetic commit SHA on
the in-cluster `refs/heads/main`, which is the intended recovery
effect; downstream Kustomization advancement is gated on an explicit
operator resume step (TG-2) that is *out of script scope*.

SUPPORTED_SURFACE_DONE: plans/risk/bug-4-supported-surface.md
