# Risk audit — BUG-4 local gitserver resync

Inputs:
- Proposal: `proposals/20-bug-4-gitserver-resync.md`
- RCA: `research/33-bug-4-flux-gitserver-rca.md`
- Substrate: `infra/scripts/bring-up-local-channel.sh` (extend),
  `infra/scripts/install-flux-for-channel.sh` (extend), `infra/README.md`
  (operator subsection)

## Verdict

**Risk level: LOW.** APPROVED — proceed to implementation.

The proposed `--reseed-gitserver-only` flow attacks the RCA's named root cause
(in-cluster gitserver pinned to a stale synthetic snapshot at
`5d872983c9d8d2b708023f185682dbecadcfc2d4`) by reusing the canonical
`render-gitops-source.py` + `seed_git_daemon` mechanism, preserves the
INIT-102 local GitOps architecture, isolates side effects to a narrow code
path, and ships a discriminating three-gate test plan. Two non-blocking
implementation notes are recorded below.

## Findings

### F-1 Resync genuinely advances the in-cluster bare repo HEAD — PASS

Mechanism inspection:

- `seed_git_daemon` (`infra/scripts/install-flux-for-channel.sh:168-205`)
  re-init's a fresh `/tmp/humility-gitops-seed` repo on every call, runs
  `git commit -m 'seed local gitops snapshot'`, and `git push --force origin
  main` into `/srv/git/humility-${CHANNEL_ID}.git`. The committer date is
  taken from the container clock at exec time, so even an unchanged tree
  yields a different commit object SHA than the live `5d872983` (committed
  `2026-04-29T06:29:30Z`).
- The current worktree's rendered snapshot tree already differs from the
  live snapshot in eight GitOps files (RCA "Why `5d872983` Is Pinned" listing
  INIT-134 API env vars, INIT-134 fixture keys, INIT-135 routes, snapshot
  marker `c87315565da1` → `5186a18b4d46`). A different tree guarantees a
  different commit SHA.
- `git push --force` replaces `refs/heads/main`. There is no fast-forward
  protection that could leave the bare repo on the old tip.

TG-1 acceptance ("new revision is not `main@sha1:5d872983...` and not
abbreviated `5d872983`") is the right discriminator and would catch a no-op
reseed.

### F-2 Reseed uses canonical render + seed_git_daemon — PASS

Proposal Q3 explicitly locks "preserve the snapshot marker, generated CRs,
and OPAL policy files by rendering a complete snapshot through the existing
`infra/scripts/render-gitops-source.py`." Section 3 substrate enumerates the
exact helpers reused: channel resolution, `kubectl_cmd`, `git_daemon_pod`,
`wait_for_git_daemon`, `seed_git_daemon`, `apply_source_crs`, and
`wait_for_source_reconciliation`.

Anti-scope §5 forbids hand-copying selected manifests into the bare repo, so
the implementer cannot regress to a partial-tree workaround.

The expected snapshot shape (gitops/ tree, policy/ tree, generated Cedar
files + `.manifest`, generated `gitops/sources/local/{gitrepository,
kustomization}.yaml`, and `gitops-snapshot-marker.yaml`) is
the same shape the existing post-install path produces. Flux + OPAL contracts
remain intact.

### F-3 Mutual exclusion with --force / --repair / --cluster-only — PASS

Proposal Q2 locks: "The flag is mutually exclusive with `--force`,
`--repair`, and `--cluster-only`." Each exclusion is semantically correct:

- `--force`: deletes the cluster (and the `git-daemon-pvc` local-path PV,
  reclaim policy `Delete` per RCA "Architecture") — incompatible with a
  reseed-only contract that requires the cluster to already exist.
- `--repair`: targets stale generated kubeconfig state; no role for a path
  that requires kubeconfig-matches-cluster as a precondition.
- `--cluster-only`: skips Flux post-install entirely; the inverse of a
  Flux-source reseed.

Existing parser already validates `--force` vs `--repair` exclusion at
`bring-up-local-channel.sh:94-96`. The implementer must extend that block to
cover `--reseed-gitserver-only` against all three. Mechanically trivial.

### F-4 Reseed does NOT run Infisical / Pomerium OIDC / step-ca bootstrap — PASS, with implementation note

Proposal Q2 names the explicit forbidden list: "Infisical bootstraps,
Pomerium OIDC bootstrap, step-ca trust distribution, full Flux controller
re-apply beyond what is needed for a missing `git-daemon`, or Kustomization
resume." Section 3 substrate confirms the reseed-mode `install-flux-for-channel.sh`
sequence stops after `wait_for_source_reconciliation`.

**Implementation note (non-blocking):** The substrate guidance for
`bring-up-local-channel.sh` (§3) says "Delegate to
`install-flux-for-channel.sh --channel local --reseed-gitserver-only`" and
"Do not create, delete, repair, or recreate the k3d cluster in this mode."
It does not explicitly call out that `bring-up-local-channel.sh`'s own
`install_flux_post_install` function (currently at
`bring-up-local-channel.sh:416-425`) calls `distribute_step_ca_trust` and
`bootstrap_pomerium_oidc_application` *after* the FLUX_INSTALLER. The Q2
prohibition covers this transitively, but the implementer must wire the new
flag to either short-circuit `install_flux_post_install` before those calls
or add a guard inside it. A literal reading of "Delegate to..." plus
unchanged `install_flux_post_install` would still execute step-ca + Pomerium
OIDC bootstrap, which Q2 forbids.

Recommend: have the reseed branch call the FLUX installer directly (or a
new dedicated function), not `install_flux_post_install`.

### F-5 Resume sequence is documented and safe — PASS

Sequence per Q4 + Anti-scope §5:

1. Cluster already in steady state with `Kustomization/humility-local`
   `spec.suspend: true` (RCA "Symptom + State"). Resume is *not* triggered
   inside the script — Anti-scope §5 forbids "resume the Kustomization until
   TG-1 proves the GitRepository artifact advanced."
2. Operator runs `bring-up-local-channel.sh --reseed-gitserver-only`. Reseed
   force-pushes the new synthetic commit; `wait_for_source_reconciliation`
   triggers `flux reconcile source git ... --with-source` and
   `kubectl wait gitrepository ... --for=condition=Ready`. Note:
   `Ready=True` was already true on the old artifact, but the explicit
   `flux reconcile source git` invocation (`install-flux-for-channel.sh:244`)
   forces an immediate re-poll, so Ready=True after the call reflects the
   new revision.
3. TG-1 independently verifies the artifact revision advanced past
   `5d872983` (this is the discriminator the script does not enforce
   internally — operator gate).
4. Only after TG-1 passes does the operator patch
   `spec.suspend: false`, run `flux reconcile kustomization`, and
   `kubectl wait kustomization Ready=True`.

This explicitly avoids the unsafe path the RCA flagged ("Resuming Flux
before advancing the gitserver would reconcile the old snapshot and can
revert/prune manually applied newer state"). The fallback resume mechanism
when `flux` CLI is unavailable (`reconcile.fluxcd.io/requestedAt` annotation
+ `kubectl wait`) is also documented in Q4.

### F-6 TG-1 / TG-2 / TG-3 testable and discriminating — PASS, with refinement note on TG-3

**TG-1** records the pre-reseed `status.artifact.revision`, runs the reseed,
then asserts (a) the new revision differs from
`main@sha1:5d872983c9d8d2b708023f185682dbecadcfc2d4`, (b) is not
abbreviated as `5d872983`, and (c) `GitRepository/humility-local` is
`Ready=True`. Discriminator-strong: a no-op reseed (e.g., reseed mode that
wrote nothing) would fail (a). A reseed that left source-controller still
serving the old artifact would fail (a) too.

**TG-2** patches `spec.suspend: false`, runs `flux reconcile kustomization
... --with-source`, and waits `Ready=True` with a 300s timeout. The
acceptance text additionally requires that the stale `HealthCheckFailed`
message ("timeout waiting for `Deployment/server-manager/server-manager-api`
status: 'InProgress'") no longer appears. Discriminating against "old
snapshot reapplied with the same stale failure mode."

**TG-3** is the load-bearing content discriminator — TG-1 passes whenever
*any* new SHA lands on `main`, including a different-but-still-stale
snapshot (e.g., an operator running the script from the wrong worktree, the
risk Q5 calls out). TG-3 verifies INIT-134 env vars on
`server-manager-api`, INIT-134 fixture secret keys, INIT-135 Pomerium
routes for public chapter intake / officer review, and `discord_user_id`
identity forwarding. This catches the worktree-misalignment failure mode
that TG-1 cannot detect alone.

**Refinement note (non-blocking):** TG-3's representative check uses
`rg 'public|chapter|officer|discord_user_id'` against
`kubectl ... -n auth-system get ingress,secret,configmap -o yaml`. The
disjunction `public|chapter|officer` is loose and could match unrelated
resource names or labels. The implementer should tighten the regex to
INIT-135-specific anchors (e.g., the actual route hostnames or policy keys
documented in the INIT-135 manifests) before this becomes a regression
detector. Acceptance for the audit is unchanged — the gate is testable —
but the operator should be aware they may need to refine the rg pattern in
the runbook.

## Observations (non-blocking)

1. **`install_flux_post_install` skip wiring.** See F-4 implementation note.
   The implementer should ensure the new reseed branch in
   `bring-up-local-channel.sh` does not fall through to `install_flux_post_install`,
   which would re-run step-ca trust distribution and Pomerium OIDC bootstrap
   in violation of proposal Q2.

2. **TG-3 rg pattern tightening.** See F-6 refinement note. Tighten the
   `rg 'public|chapter|officer|discord_user_id'` regex against
   INIT-135-specific route/policy anchors before relying on it for
   regression detection in future incidents.

3. **Diff budget.** Proposal §6 estimates under 230 changed lines, scoped to
   `infra/scripts/bring-up-local-channel.sh`,
   `infra/scripts/install-flux-for-channel.sh`, and `infra/README.md`. An
   implementation that introduces new manifests, services, CronJobs, CI
   workflows, GitHub credentials, or broader bootstrap rewrites is outside
   this proposal and should fail risk re-review.

## Acceptance check (proposed)

When implementation lands, the following must all hold:

- `infra/scripts/bring-up-local-channel.sh` accepts
  `--reseed-gitserver-only`, mutually exclusive with `--force`, `--repair`,
  and `--cluster-only`. The reseed branch validates that the cluster
  exists, kubeconfig matches, kubectl can reach the cluster, and the live
  node topology matches the resolved channel — and does *not* invoke
  `install_flux_post_install` (i.e., does not call `distribute_step_ca_trust`
  or `bootstrap_pomerium_oidc_application`).
- `infra/scripts/install-flux-for-channel.sh` accepts
  `--reseed-gitserver-only`. In that mode it: renders the snapshot via
  `render-gitops-source.py`, applies `gitops/sources/local/git-daemon.yaml`,
  reuses `wait_for_git_daemon`, `seed_git_daemon`, `apply_source_crs`, and
  `wait_for_source_reconciliation`, and exits without running
  `ensure_age_secret` (already present), Infisical bootstraps, full Flux
  controller re-apply beyond `git-daemon`, or `wait_for_reconciliation` of
  the Kustomization.
- `infra/README.md` gains a "Narrow local GitOps reseed" subsection under
  "GitOps Substrate" documenting when to use the flag, the exact command,
  the TG-1 revision check, the explicit resume patch, the
  reconcile/watch commands, and that this is not a full bootstrap.
- TG-1: `GitRepository/humility-local`'s `status.artifact.revision`
  advances past `main@sha1:5d872983...` and the GitRepository is
  `Ready=True`.
- TG-2: after explicit `spec.suspend: false` patch, `Kustomization/humility-local`
  reaches `Ready=True` and no longer reports the stale
  `Deployment/server-manager/server-manager-api` `InProgress` timeout.
- TG-3: `Deployment/server-manager/server-manager-api` contains
  `WEB_PUBLIC_BASE_URL`, `GLOBAL_APPLICATIONS_REVIEW_CHANNEL_ID`,
  `GLOBAL_APPLICATION_MANAGERS_ROLE_ID`, and
  `GLOBAL_PRIMARY_GUILD_CHANNEL_URL`; the e2e fixture surface contains the
  expected INIT-134 keys; INIT-135 Pomerium public/officer routes and
  `discord_user_id` forwarding reach the cluster.
- TG-4: operator docs cover the narrow reseed and reflect that local Flux
  follows the in-cluster gitserver, not GitHub origin.

AUDIT_DONE: plans/risk/bug-4-audit.md
