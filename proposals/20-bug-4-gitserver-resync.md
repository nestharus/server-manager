# Proposal 20 - BUG-4: Local Gitserver Resync

## 1. Problem statement

Root cause: the local GitOps source is intentionally decoupled from GitHub and
only advances when the in-cluster gitserver is explicitly reseeded. The current
cluster's gitserver was last reseeded from an older rendered snapshot. Later
branch commits exist on GitHub/local disk but were not transferred into
`/srv/git/humility-local.git`.

Resuming `Kustomization/humility-local` without changing the gitserver source
would not advance Flux. It would reconcile the same
`main@sha1:5d872983...` artifact again.

## 2. Decisions

### Q1. Recovery option

Lock: Option A, reseed `humility-local.git` from the current worktree snapshot.

The fix should preserve the INIT-102 local GitOps architecture: Flux follows
the in-cluster `git-local` HTTP service, and operators advance that source by
rendering a complete local snapshot and force-pushing a new synthetic `main`
commit into `/srv/git/humility-local.git`. This directly addresses the root
cause from the RCA without changing the channel contract, introducing GitHub
as a new Flux dependency, or re-running the full local bootstrap sequence.
Because the snapshot is rendered from the current
`recovery/test-first-audit` checkout, the resulting source includes the
INIT-134, INIT-135, BUG-1, and BUG-3 manifests present in that worktree.

### Q2. Narrow reseed interface

Lock: add a `bring-up-local-channel.sh --reseed-gitserver-only` workflow.

The operator-facing command should remain the local channel entrypoint because
`infra/README.md` already teaches operators to use
`infra/scripts/bring-up-local-channel.sh` for local cluster lifecycle. A new
flag is narrower than full bring-up but avoids creating a second top-level
operator script with overlapping channel resolution, kubeconfig validation,
and cluster-contract checks.

Implementation should extend only `infra/scripts/`:

- `bring-up-local-channel.sh` accepts `--reseed-gitserver-only`.
- The flag is mutually exclusive with `--force`, `--repair`, and
  `--cluster-only`.
- The flag requires the existing k3d cluster and matching kubeconfig, verifies
  the local channel contract, then delegates to the Flux installer in reseed
  mode.
- `install-flux-for-channel.sh` accepts an internal/public
  `--reseed-gitserver-only` mode that runs only the pieces needed to render a
  snapshot, ensure the git-daemon manifest is applied and available, seed the
  bare repo, apply the generated source CRs, and wait for
  `GitRepository/humility-local`.
- The reseed mode must not run Infisical bootstraps, Pomerium OIDC bootstrap,
  step-ca trust distribution, full Flux controller re-apply beyond what is
  needed for a missing `git-daemon`, or Kustomization resume.

### Q3. Snapshot preservation

Lock: yes, preserve the snapshot marker, generated CRs, and OPAL policy files
by rendering a complete snapshot through the existing
`infra/scripts/render-gitops-source.py`.

The reseed path must not manually copy selected manifests. It should use the
same renderer as full post-install so the in-cluster synthetic repo contains:

- the `gitops/` tree;
- the `policy/` tree;
- generated Cedar policy files and `.manifest`;
- generated `gitops/sources/local/{gitrepository.yaml,kustomization.yaml}`;
- `gitops/channels/local/generated/gitops-snapshot-marker.yaml`.

This keeps Flux, OPAL policy materialization, and the snapshot sentinel aligned
with the established local GitOps shape.

### Q4. Resume sequence

Lock: reseed first, verify the GitRepository observed a new artifact revision,
then resume the Kustomization with:

```bash
KUBECONFIG=~/.kube/humility-local.yaml \
  kubectl patch kustomization humility-local \
    -n flux-system \
    --type=merge \
    -p '{"spec":{"suspend":false}}'
```

After the patch, request/watch reconciliation:

```bash
KUBECONFIG=~/.kube/humility-local.yaml \
  flux reconcile kustomization humility-local \
    --namespace flux-system \
    --with-source

KUBECONFIG=~/.kube/humility-local.yaml \
  kubectl -n flux-system wait kustomization/humility-local \
    --for=condition=Ready \
    --timeout=300s
```

If `flux` is unavailable, the fallback is to annotate
`Kustomization/humility-local` with `reconcile.fluxcd.io/requestedAt=$(date
+%s)` and then use `kubectl wait`.

### Q5. Current worktree source

Lock: "current worktree" means the user's git checkout at
`/home/nes/projects/server-manager/worktrees/recovery-test-first-audit`.

The reseed command is run from that checkout. `REPO_ROOT` is resolved from the
script path, so the implementation should document that operators must invoke
the script from, or by absolute path within, the desired checkout. The rendered
snapshot source of truth is the files present in that worktree at execution
time, currently branch `recovery/test-first-audit` at
`8a3e83442b190632c77be660d9bb808b12e85f50`.

The synthetic gitserver commit SHA is expected to differ from the worktree Git
SHA. Verification should compare the new artifact revision against the old
gitserver SHA `5d872983c9d8d2b708023f185682dbecadcfc2d4`, not against the
worktree commit.

## 3. Substrate

### Modified scripts

- `infra/scripts/bring-up-local-channel.sh`
  - Add `--reseed-gitserver-only` to usage and argument parsing.
  - Validate that the local cluster already exists, the kubeconfig matches the
    k3d cluster, kubectl can reach the cluster, and the live node topology
    matches the resolved channel.
  - Delegate to `infra/scripts/install-flux-for-channel.sh --channel local
    --reseed-gitserver-only`.
  - Do not create, delete, repair, or recreate the k3d cluster in this mode.

- `infra/scripts/install-flux-for-channel.sh`
  - Add `--reseed-gitserver-only` to usage and argument parsing.
  - Reuse existing helpers where possible: channel resolution, `kubectl_cmd`,
    `git_daemon_pod`, `wait_for_git_daemon`, `seed_git_daemon`,
    `apply_source_crs`, and `wait_for_source_reconciliation`.
  - Render `SNAPSHOT_DIR="${REPO_ROOT}/.tmp/gitops-source/${CHANNEL_ID}"` using
    `render-gitops-source.py`.
  - Apply `gitops/sources/local/git-daemon.yaml`, wait for the git-daemon
    Deployment, reseed `/srv/git/humility-local.git`, apply generated source
    CRs, and wait for the GitRepository.
  - Exit after source reconciliation. Do not resume the Kustomization inside
    the script; resume remains an explicit operator step after TG-1 passes.

### Documentation

- `infra/README.md`
  - Add a "Narrow local GitOps reseed" subsection under "GitOps Substrate".
  - Document when to use the flag: an existing local cluster whose in-cluster
    gitserver is stale relative to the desired checkout.
  - Document the exact command, TG-1 revision check, explicit resume patch,
    reconcile watch, and representative manifest checks.
  - State that this is not a full bootstrap and does not directly mutate
    Pomerium or Authentik secrets.

### Scope boundary

No source code changes outside `infra/scripts/`. The only non-script change is
operator documentation in `infra/README.md`.

## 4. Test plan

### TG-1: gitserver artifact advances

Before reseed, record the current artifact:

```bash
KUBECONFIG=~/.kube/humility-local.yaml \
  kubectl get gitrepository -n flux-system humility-local \
    -o jsonpath='{.status.artifact.revision}{"\n"}'
```

Run:

```bash
bash infra/scripts/bring-up-local-channel.sh \
  --channel local \
  --reseed-gitserver-only
```

Acceptance:

- `kubectl get gitrepository -n flux-system humility-local -o
  jsonpath='{.status.artifact.revision}'` shows a new SHA.
- The new revision is not `main@sha1:5d872983c9d8d2b708023f185682dbecadcfc2d4`
  and not abbreviated as `5d872983`.
- `GitRepository/humility-local` is `Ready=True`.

### TG-2: Flux Kustomization resumes successfully

After TG-1 passes, resume:

```bash
KUBECONFIG=~/.kube/humility-local.yaml \
  kubectl patch kustomization humility-local \
    -n flux-system \
    --type=merge \
    -p '{"spec":{"suspend":false}}'
```

Then reconcile/watch:

```bash
KUBECONFIG=~/.kube/humility-local.yaml \
  flux reconcile kustomization humility-local \
    --namespace flux-system \
    --with-source

KUBECONFIG=~/.kube/humility-local.yaml \
  kubectl -n flux-system wait kustomization/humility-local \
    --for=condition=Ready \
    --timeout=300s
```

Acceptance:

- `Kustomization/humility-local` reaches `Ready=True`.
- Status no longer reports "stalled by failed health check on api Deployment"
  or the stale `Deployment/server-manager/server-manager-api` in-progress
  timeout from the old artifact.

### TG-3: resumed cluster contains new manifests

Inspect live resources after the resumed reconcile.

Acceptance:

- `Deployment/server-manager/server-manager-api` contains
  `WEB_PUBLIC_BASE_URL`.
- `Deployment/server-manager/server-manager-api` contains the INIT-134 Discord
  notification env vars from the current snapshot:
  `GLOBAL_APPLICATIONS_REVIEW_CHANNEL_ID`,
  `GLOBAL_APPLICATION_MANAGERS_ROLE_ID`, and
  `GLOBAL_PRIMARY_GUILD_CHANNEL_URL`.
- The e2e fixture runtime secret surface contains the expected five keys for
  the current snapshot, including the INIT-134 additions.
- INIT-135 Pomerium routes for public chapter intake and officer review reach
  the cluster.
- INIT-135 identity forwarding includes `discord_user_id` where the current
  Pomerium secret/config manifests define it.

Representative checks:

```bash
KUBECONFIG=~/.kube/humility-local.yaml \
  kubectl -n server-manager get deploy server-manager-api -o yaml | \
  rg 'WEB_PUBLIC_BASE_URL|GLOBAL_APPLICATIONS_REVIEW_CHANNEL_ID|GLOBAL_APPLICATION_MANAGERS_ROLE_ID|GLOBAL_PRIMARY_GUILD_CHANNEL_URL'

KUBECONFIG=~/.kube/humility-local.yaml \
  kubectl -n server-manager get infisicalsecret e2e-fixtures -o yaml

KUBECONFIG=~/.kube/humility-local.yaml \
  kubectl -n auth-system get ingress,secret,configmap -o yaml | \
  rg 'public|chapter|officer|discord_user_id'
```

### TG-4: operator docs cover narrow reseed

Acceptance:

- `infra/README.md` documents `bring-up-local-channel.sh
  --reseed-gitserver-only`.
- The docs explain that local Flux follows the in-cluster gitserver, not
  GitHub.
- The docs include the artifact revision check, the explicit resume patch, and
  the reconcile/watch commands.
- Future operators can perform this recovery without re-running full
  bootstrap or re-deriving the gitserver PVC/exec workflow from the RCA.

## 5. Anti-scope

- Do not change Flux's `GitRepository` URL to GitHub.
- Do not touch the cluster's Pomerium or Authentik secrets directly; they
  re-sync from Infisical.
- Do not add a CI sync workflow.
- Do not modify `bring-up-local-channel.sh` flow beyond the new optional flag.
- Do not run a full local re-bootstrap as the recovery mechanism.
- Do not add a standalone GitHub-to-gitserver mirror, CronJob, or controller.
- Do not hand-copy selected manifests into the bare repo.
- Do not resume the Kustomization until TG-1 proves the GitRepository artifact
  advanced.

## 6. Diff budget

Expected implementation diff:

- `infra/scripts/bring-up-local-channel.sh`: small flag parsing and one
  reseed-only branch, roughly 30-60 changed lines.
- `infra/scripts/install-flux-for-channel.sh`: reseed-only flag plus an early
  mode branch that reuses existing helper functions, roughly 40-90 changed
  lines.
- `infra/README.md`: one focused operator subsection, roughly 40-80 changed
  lines.

Total target: under 230 changed lines. Any implementation that needs new
manifests, new services, CI, GitHub credentials, or broad bootstrap rewrites is
outside this proposal and should fail risk review.
