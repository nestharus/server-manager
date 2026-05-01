# BUG-4 — Scope risk gate

**Verdict:** LOW

BUG-4 advances the in-cluster `humility-local.git` snapshot to the current
worktree state so Flux's `GitRepository/humility-local` observes a new
artifact revision and the suspended `Kustomization/humility-local` can
resume against fresh INIT-134/INIT-135 manifests. The RCA
(`research/33-bug-4-flux-gitserver-rca.md` §"Why `5d872983` Is Pinned",
§"Architecture") establishes that this is a procedural drift between the
synthetic snapshot in `/srv/git/humility-local.git`
(`5d872983c9d8d2b708023f185682dbecadcfc2d4`, sealed
`2026-04-29T06:29:30Z`) and the worktree at
`recovery/test-first-audit@8a3e83442b190632c77be660d9bb808b12e85f50`, not
a Flux/source-controller defect. The proposal locks Option A reseed
(`proposals/20-bug-4-gitserver-resync.md` §2 Q1) using the
already-shipped `seed_git_daemon` mechanism in
`infra/scripts/install-flux-for-channel.sh:168-205` and adds a narrow
`--reseed-gitserver-only` flag instead of a second top-level operator
script, a GitHub mirror, or a `GitRepository` URL repoint
(§2 Q2, §5). Diff budget is under 230 lines across two scripts plus one
operator docs subsection (§6).

## Gate checks

### 1. Only changes `infra/scripts/*` (no source/gitops/contracts changes)

**PASS** with one in-scope documentation file noted.

§3 "Substrate" enumerates exactly three touched paths:

- `infra/scripts/bring-up-local-channel.sh` — flag parsing plus a
  reseed-only branch that delegates to the Flux installer (≈30-60
  changed lines per §6).
- `infra/scripts/install-flux-for-channel.sh` — `--reseed-gitserver-only`
  mode that reuses existing helpers `git_daemon_pod`,
  `wait_for_git_daemon`, `seed_git_daemon`, `apply_source_crs`, and
  `wait_for_source_reconciliation` (≈40-90 changed lines per §6).
- `infra/README.md` — one "Narrow local GitOps reseed" subsection under
  "GitOps Substrate" (≈40-80 changed lines per §6).

§3 "Scope boundary" is explicit: "No source code changes outside
`infra/scripts/`. The only non-script change is operator documentation
in `infra/README.md`." The gate's parenthetical scopes the exclusion to
"source/gitops/contracts changes" — `infra/README.md` is operator
documentation, not source/gitops/contracts surface, so this is in
spirit. The proposal does not touch:

- `services/**` runtime code.
- `gitops/**` manifests (the rendered snapshot uses the existing
  `render-gitops-source.py` against the worktree's current `gitops/`
  tree — what is rendered is whatever is already committed; the reseed
  ships those files into the bare repo without modifying them).
- `infra/channels/local.yaml` or any other channel contract.
- `policy/**` Cedar sources.
- `infra/scripts/render-gitops-source.py` (reused as-is per §3).
- `infra/scripts/resolve_platform_channel.py` (reused via existing
  `kubectl_cmd`/channel-resolution paths).

The two new script branches ride the existing helper surface in
`install-flux-for-channel.sh:140-249` rather than reimplementing
seeding, source apply, or reconciliation waits. ✅

### 2. No GitHub-side workflow added (no `.github/workflows/` touched)

**PASS.** §5 anti-scope is explicit on three independent banned
mechanisms that would each have required `.github/workflows/`:

- "Do not add a CI sync workflow."
- "Do not add a standalone GitHub-to-gitserver mirror, CronJob, or
  controller."
- "Do not change Flux's `GitRepository` URL to GitHub."

§3 also confirms the only mutated surface is `infra/scripts/*` plus
`infra/README.md`. The RCA §"Commit Flow" notes "There is no CI workflow
found under `.github/workflows/`; in this worktree `.github/` is
absent" — the proposal preserves that condition rather than introducing
the directory. The reseed mechanism runs synchronously from an
operator's host shell against the already-bound kubeconfig, with no
GitHub auth, no scheduled job, and no Actions runner. ✅

### 3. No design change to Flux `GitRepository` URL (still git-local)

**PASS.** §5 anti-scope: "Do not change Flux's `GitRepository` URL to
GitHub." §2 Q1 commitment: the reseed "preserve[s] the INIT-102 local
GitOps architecture: Flux follows the in-cluster `git-local` HTTP
service." §2 Q3 lock: source CRs are re-applied from the rendered
snapshot's `gitops/sources/local/{gitrepository.yaml,kustomization.yaml}`
— the same shape as the existing in-cluster CR, pointing at
`http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git`
(per RCA §"Symptom + State").

The reseed advances the *content* of `/srv/git/humility-local.git` via
the documented `seed_git_daemon` flow
(`install-flux-for-channel.sh:168-205`) and re-applies the rendered
source CR; it does not edit the `spec.url` field. TG-1 acceptance
checks `status.artifact.revision` for a new SHA, not a new URL. RCA
Option D ("Repoint Flux to GitHub origin / branch directly") was
explicitly considered and rejected as "a design change rather than a
recovery-only action" — the proposal locks Option A instead. ✅

### 4. No new top-level operator script (extends `bring-up-local-channel.sh`)

**PASS.** §2 Q2 lock: "add a `bring-up-local-channel.sh
--reseed-gitserver-only` workflow … A new flag is narrower than full
bring-up but avoids creating a second top-level operator script with
overlapping channel resolution, kubeconfig validation, and
cluster-contract checks." §5 anti-scope: "Do not modify
`bring-up-local-channel.sh` flow beyond the new optional flag."

The flag is mutually exclusive with the existing `--force`, `--repair`,
and `--cluster-only` modes (§3, §2 Q2) — i.e. it is one new branch
within the existing arg-parser at
`bring-up-local-channel.sh:66-97`, not a parallel entrypoint. The
delegation to `install-flux-for-channel.sh --channel local
--reseed-gitserver-only` (§3) reuses that script's existing
`parse_args`/`main` shape; the reseed mode is an internal flag in the
same `parse_args` at `install-flux-for-channel.sh:63-81`, not a new
script file. The two existing operator scripts in `infra/scripts/` —
`bring-up-local-channel.sh` and `install-flux-for-channel.sh` — remain
the only top-level entrypoints. ✅

### 5. No change to OPAL/Cedar/Pomerium config beyond what's already in gitops

**PASS.** §2 Q3 lock: the reseed renders "a complete snapshot through
the existing `infra/scripts/render-gitops-source.py`" so the in-cluster
synthetic repo contains "the `gitops/` tree; the `policy/` tree;
generated Cedar policy files and `.manifest`; generated
`gitops/sources/local/{gitrepository.yaml,kustomization.yaml}`;
`gitops/channels/local/generated/gitops-snapshot-marker.yaml`." Whatever
OPAL/Cedar/Pomerium files are in the worktree are what gets shipped —
nothing is *added* to or *edited* in the config; the proposal only
changes which already-committed snapshot the cluster sees.

§5 anti-scope reinforces this in three directions:

- "Do not touch the cluster's Pomerium or Authentik secrets directly;
  they re-sync from Infisical." (Pomerium config is unchanged at the
  source; runtime secrets are not script-mutated either.)
- "Do not hand-copy selected manifests into the bare repo." (The reseed
  cannot smuggle a config change in via selective copy; it tars the
  full rendered snapshot per `seed_git_daemon` at
  `install-flux-for-channel.sh:177-204`.)
- "Do not run a full local re-bootstrap as the recovery mechanism."
  (§2 Q2 also enumerates what reseed mode must *not* run: "Infisical
  bootstraps, Pomerium OIDC bootstrap, step-ca trust distribution,
  full Flux controller re-apply beyond what is needed for a missing
  `git-daemon`, or Kustomization resume.")

The reseed is config-neutral by construction: it propagates the
already-merged INIT-134 (API env vars, fixture keys) and INIT-135
(public chapter routes, Pomerium officer routes,
`discord_user_id` forwarding) manifests that the RCA §"Why `5d872983`
Is Pinned" enumerates as the drift content. Those are pre-existing
worktree files, not new design choices made in this proposal. ✅

## Findings

- **Diff budget headroom.** §6 caps the implementation at ~230 changed
  lines across two scripts plus one docs subsection. The new branches
  reuse `git_daemon_pod`, `wait_for_git_daemon`, `seed_git_daemon`,
  `apply_source_crs`, and `wait_for_source_reconciliation` rather than
  reimplementing them, which keeps the script churn bounded and
  reviewable.
- **No new external dependencies.** No new CLI tools, no GitHub auth,
  no new Helm chart, no new container image. The implementation
  surface is bash + the already-required `kubectl`/`tar`/`base64`/
  `python3`.
- **TG-1 guards regression.** The artifact-revision precondition in §4
  TG-1 ("not `main@sha1:5d872983c9d8d2b708023f185682dbecadcfc2d4` and
  not abbreviated as `5d872983`") prevents accidental no-op runs from
  being mistaken for success — important because the reseed reuses the
  same synthetic-commit mechanism that produced the current stale
  snapshot.
- **Operator-docs commitment is in scope.** TG-4 and §3 require the
  `infra/README.md` subsection to document the artifact check, explicit
  resume patch, and reconcile/watch commands. The gate criterion 1
  parenthetical does not exclude operator docs, so this remains
  in-scope and is the right place for the recovery runbook (the
  alternative, a separate runbook file, would be the kind of
  out-of-place artifact the gate is designed to catch).
- **Resume sequencing held outside the script.** §2 Q4 and §3 are
  explicit that the reseed mode "exit[s] after source reconciliation.
  Do not resume the Kustomization inside the script." This keeps the
  potentially-destructive resume (which can prune objects per RCA
  §"Flux Resume Safety") as an explicit, documented operator step
  gated on TG-1, rather than rolled into automation.

## Verdict

**LOW.** All five gate checks pass. The proposal is a narrow,
recovery-only delta that reuses existing in-script substrate to advance
a single in-cluster artifact revision, with anti-scope clauses pinning
out the four design-change escape hatches (GitHub repoint, CI mirror,
ad hoc `kubectl exec`, full re-bootstrap) that BUG-4's RCA Options B/C/D
would have invited. The `infra/README.md` subsection is in scope as
operator documentation and is required by TG-4. Cleared for shortcut
gate.

SCOPE_DONE: plans/risk/bug-4-scope.md
