# RCA: BUG-4 Flux pinned to old gitserver revision

## Scope

This is root-cause analysis only. It documents the live cluster state, the
repository-defined gitserver workflow, why Flux remains on
`main@sha1:5d872983c9d8d2b708023f185682dbecadcfc2d4`, and candidate
intervention points. It does not select or prescribe a fix.

## Symptom + State

Live cluster inspection used `/home/nes/.kube/humility-local.yaml`.

`GitRepository/flux-system/humility-local` is healthy but still reading the
in-cluster service:

```text
url: http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git
artifact revision: main@sha1:5d872983c9d8d2b708023f185682dbecadcfc2d4
artifact lastUpdateTime: 2026-04-29T06:29:32Z
Ready=True, message: stored artifact for revision 'main@sha1:5d872983...'
```

`Kustomization/flux-system/humility-local` is currently suspended:

```text
spec.suspend: true
lastAppliedRevision: main@sha1:5d872983c9d8d2b708023f185682dbecadcfc2d4
lastAttemptedRevision: main@sha1:5d872983c9d8d2b708023f185682dbecadcfc2d4
Ready=False, reason=HealthCheckFailed
message: timeout waiting for Deployment/server-manager/server-manager-api status: 'InProgress'
```

The `Ready=False` message is stale status from the last active reconcile, not
evidence that the suspended Kustomization is currently applying changes.
`source-controller` continues to poll the source and logs repeated "no changes
since last reconciliation" messages for the same `5d872983` revision.

The in-cluster gitserver commit is not a GitHub/worktree commit. In this
worktree, `git show 5d872983...` fails with `bad object`. Inside the
gitserver, it is a synthetic commit:

```text
author/committer: Humility GitOps Seed <gitops-seed@humility.local>
date: 2026-04-29 06:29:30 +0000
subject: seed local gitops snapshot
tree file count: 281
marker source_sha: c87315565da1
```

The current branch is `recovery/test-first-audit` at
`8a3e83442b190632c77be660d9bb808b12e85f50`, and it contains INIT-134
`ded70553e36125cd667680e20ed9ef0f9b668f21`.

## Architecture

The service at `git-local.git-system.svc.cluster.local:8080` is not Gitea or
Forgejo. It is a small in-cluster Git HTTP server defined by
`gitops/sources/local/git-daemon.yaml`:

- `Namespace/git-system`
- `PersistentVolumeClaim/git-daemon-pvc`, 1Gi, `ReadWriteOnce`
- `Deployment/git-daemon`, image `alpine/git:v2.45.2`
- `Service/git-local`, `ClusterIP`, port `8080`

The Deployment has two containers:

- `git-daemon`: sleeps forever, mounts `/srv/git` read-write, and is used by
  bootstrap scripts through `kubectl exec`.
- `git-http`: creates `/tmp/www/cgi-bin/git`, sets
  `GIT_PROJECT_ROOT=/srv/git` and `GIT_HTTP_EXPORT_ALL=1`, then runs BusyBox
  `httpd` on port 8080 with `git http-backend`.

Despite the Deployment name, there is no externally exposed `git daemon`
protocol and no Gitea/Forgejo-style application. The only live Service is
ClusterIP HTTP. There is no `git-system` Ingress, CronJob, or sync Job.

The git data lives on PVC `git-daemon-pvc`, bound to local-path PV
`pvc-16645b3f-d048-4d2d-b534-573a5af68833` on
`k3d-humility-local-server-0`:

```text
/var/lib/rancher/k3s/storage/pvc-16645b3f-d048-4d2d-b534-573a5af68833_git-system_git-daemon-pvc
```

The PV reclaim policy is `Delete`; it is persistent across Pod restarts but
not durable outside the k3d/local-path lifecycle.

## Commit Flow

The canonical local flow is documented in `infra/README.md` and implemented by
`infra/scripts/bring-up-local-channel.sh` plus
`infra/scripts/install-flux-for-channel.sh`.

The flow is:

1. `bring-up-local-channel.sh local` verifies/creates the k3d cluster.
2. It calls `install-flux-for-channel.sh --channel local` unless
   `--cluster-only` was passed.
3. `install-flux-for-channel.sh` resolves `infra/channels/local.yaml`.
4. It renders a local snapshot into `.tmp/gitops-source/local` via
   `infra/scripts/render-gitops-source.py`.
5. It applies Flux controllers.
6. It applies `gitops/sources/local/git-daemon.yaml`.
7. `seed_git_daemon` copies the rendered snapshot into the running
   `git-daemon` container, creates a fresh Git repository in
   `/tmp/humility-gitops-seed`, commits it as `seed local gitops snapshot`,
   and force-pushes that synthetic `main` to `/srv/git/humility-local.git`.
8. It applies the rendered `GitRepository` and `Kustomization` CRs from the
   snapshot.

Important consequences:

- Flux does not track the GitHub branch directly. `infra/channels/local.yaml`
  points Flux at the in-cluster URL and `refs/heads/main`.
- The in-cluster commit SHA is a synthetic snapshot commit, not the source
  worktree commit SHA.
- Re-running the Flux post-install path from a different worktree/branch can
  replace the in-cluster `main` with that worktree's rendered snapshot.
- There is no continuous sync from GitHub origin to the gitserver.
- There is no CI workflow found under `.github/workflows/`; in this worktree
  `.github/` is absent.

The HTTP surface is effectively read-oriented for normal clients. The served
container mounts `/srv/git` read-only, and the bare repo config only contains
core bare-repo settings. The workflow that writes data uses `kubectl exec` into
the separate `git-daemon` container and pushes by local filesystem path.

## Why `5d872983` Is Pinned

`5d872983` is the latest commit that exists in the in-cluster bare repo:

```text
refs/heads/main -> 5d872983c9d8d2b708023f185682dbecadcfc2d4
HEAD -> refs/heads/main
```

There is no evidence of a broken background sync mechanism. The expected sync
mechanism does not exist. The source-controller logs show successful polling
with no newer revision available from the gitserver.

The apparent "old revision" is a stale snapshot, not a stale GitHub commit.
The snapshot was seeded at `2026-04-29T06:29:30Z`, before the current
`recovery/test-first-audit` branch's newer GitOps manifests were loaded into
the in-cluster repo.

A freshly rendered snapshot from the current worktree differs from the live
gitserver snapshot in these GitOps files:

```text
gitops/channels/local/applications/server-manager/api-deployment.yaml
gitops/channels/local/applications/server-manager/e2e-fixtures-infisicalsecret.yaml
gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml
gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml
gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml
gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml
gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml
gitops/channels/local/generated/gitops-snapshot-marker.yaml
```

Notable missing/stale content in the live gitserver snapshot:

- INIT-134 API env vars are absent from `api-deployment.yaml`:
  `WEB_PUBLIC_BASE_URL`, `GLOBAL_APPLICATIONS_REVIEW_CHANNEL_ID`,
  `GLOBAL_APPLICATION_MANAGERS_ROLE_ID`, and
  `GLOBAL_PRIMARY_GUILD_CHANNEL_URL`.
- INIT-134 fixture secret keys are absent from
  `e2e-fixtures-infisicalsecret.yaml`:
  `applications-review-channel-id`, `application-managers-role-id`, and
  `primary-guild-channel-url`.
- INIT-135 public chapter routes are absent from the server-manager and
  Pomerium rate-limit/Ingress manifests.
- INIT-135 Pomerium officer routes and `discord_user_id` identity forwarding
  are absent/stale in `auth/pomerium/secrets-infisicalsecret.yaml`.
- INIT-135 public intake v2 seed SQL is absent; the live snapshot still has the
  INIT-122 v1 form seed.
- The live snapshot marker is `c87315565da1`; the current rendered snapshot
  marker is `5186a18b4d46`.

Root cause: the local GitOps source is intentionally decoupled from GitHub and
only advances when the in-cluster gitserver is explicitly reseeded. The current
cluster's gitserver was last reseeded from an older rendered snapshot. Later
branch commits exist on GitHub/local disk but were not transferred into
`/srv/git/humility-local.git`.

## Flux Resume Safety

Resuming `Kustomization/humility-local` without changing the gitserver source
would not advance Flux. It would reconcile the same
`main@sha1:5d872983...` artifact again.

Observed likely effects:

- It would continue to apply the old desired state and can overwrite manual
  `kubectl apply` changes for objects that Flux owns.
- It can prune objects owned by the Kustomization inventory if they are not in
  the old snapshot.
- It would not pull INIT-134/INIT-135 manifests from GitHub because the
  `GitRepository` URL does not point to GitHub.
- The old snapshot itself is not an unsupported-resource crash path; the last
  active failure recorded by Flux was an application health-check timeout for
  `Deployment/server-manager/server-manager-api`.

Therefore the unsafe part is configuration regression/drift enforcement, not a
source fetch failure.

## Recovery Options

These are candidate intervention points, not a selected fix.

### Option A: Reseed `humility-local.git` from the current worktree snapshot

Mechanism already exists in `install-flux-for-channel.sh`: render the snapshot,
copy it into the `git-daemon` container, create a synthetic commit, and
force-push to `/srv/git/humility-local.git`.

Tradeoffs:

- Preserves the current architecture and the documented local GitOps flow.
- Produces another synthetic gitserver commit rather than preserving GitHub
  commit identity.
- Requires care because the full post-install script also performs other
  bootstrap actions after seeding.
- A narrow reseed would need to duplicate or isolate `seed_git_daemon` behavior.

### Option B: Re-bootstrap the local channel from this branch

Use the documented local bring-up/post-install path from a worktree at the
desired branch state.

Tradeoffs:

- Exercises the canonical operator workflow.
- May run broader bootstrap side effects beyond only updating the gitserver:
  Flux install/apply, Infisical bootstraps, Pomerium OIDC bootstrap, and waits.
- If run from the wrong worktree or dirty state, it can seed the wrong snapshot
  again.

### Option C: Push into the bare repo by an ad hoc `kubectl exec` workflow

Use the same underlying write surface as `seed_git_daemon`: write from inside
the `git-daemon` container to `/srv/git/humility-local.git`.

Tradeoffs:

- Small blast radius if it only updates the bare repo.
- Less documented than the full install script.
- Must preserve the snapshot shape expected by Flux and OPAL, including
  `gitops/`, `policy/`, generated Cedar files, `.manifest`, generated source
  CRs, and the snapshot marker.

### Option D: Repoint Flux to GitHub origin / branch directly

Change `GitRepository/humility-local` or the channel contract to use GitHub
instead of `git-local`.

Tradeoffs:

- Aligns Flux revisions with real GitHub commits.
- Bypasses the local gitserver architecture chosen in INIT-102.
- Requires decisions around authentication, network availability, local/offline
  behavior, OPAL's policy repo URL, and whether the local channel should remain
  self-contained.
- Would be a design change rather than a recovery-only action.

## Canonical Contributor Flow

For this local channel, the canonical documented path is not "push to
git-local". It is:

```text
commit/update local worktree -> run bring-up/post-install from that worktree -> render .tmp/gitops-source/local -> seed in-cluster bare repo -> Flux reconciles git-local main
```

No docs or manifests found a background GitHub-to-gitserver sync path. The
available repo evidence points to local operator reseeding as the intended way
the cluster's gitserver receives changes.

## Findings Summary

1. `git-local` is plain BusyBox HTTP plus `git http-backend`, backed by a PVC,
   not Gitea/Forgejo.
2. The gitserver stores a synthetic rendered-snapshot repository, not a mirror
   of GitHub origin.
3. `5d872983` is the current in-cluster synthetic snapshot commit, created by
   `Humility GitOps Seed` at `2026-04-29T06:29:30Z`.
4. Flux is not truly "pinned" by a Flux setting; it is following the newest
   commit available from the in-cluster `main` branch.
5. The sync gap is procedural: newer `recovery/test-first-audit` GitOps
   manifests were not reseeded into `/srv/git/humility-local.git`.
6. Resuming Flux before advancing the gitserver would reconcile the old
   snapshot and can revert/prune manually applied newer state.
