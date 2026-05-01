# RCA: BUG-6 OPAL git divergence after gitserver reseed

## Scope

This is root-cause analysis only. It documents why OPAL Server fails after
`--reseed-gitserver-only` force-pushes a fresh synthetic commit to
`humility-local.git`, why Flux handles the same update, and which intervention
points exist. It does not select or prescribe a fix.

Sources used:

- Local manifests and scripts in this worktree.
- Read-only live cluster inspection through
  `/home/nes/.kube/humility-local.yaml` on 2026-05-01.
- OPAL 0.7.12 source, cloned at tag `0.7.12`
  (`065c539f683e452ab03f80ab99cc7077d56c21d2`) into `.tmp/opal-src`.
- Flux source-controller source, cloned at
  `73644f6b45cc43fd73bfe1b9d17eaa9c3ae0b297` into
  `.tmp/source-controller-src`.
- OPAL docs: <https://docs.opal.ac/tutorials/track_a_git_repo/> and
  <https://docs.opal.ac/getting-started/configuration/>.
- Flux docs: <https://fluxcd.io/flux/components/source/gitrepositories/>.
- Git pull docs: <https://git-scm.com/docs/git-pull/2.47.1>.

## Symptom + State

After BUG-4's reseed path updates the in-cluster Git repository,
`OPAL Server` keeps running but its repository watcher can no longer advance
its local clone. The live server log shows repeated polling failures:

```text
2026-05-01T09:44:04Z opal_common.sources.git_policy_source INFO
Pulling changes from remote: 'origin'

2026-05-01T09:44:07Z opal_common.sources.base_policy_source ERROR
Error occurred during polling task check_for_changes: Cmd('git') failed due to:
exit code(128)
  cmdline: git pull -v -- origin
  stderr: 'fatal: Need to specify how to reconcile divergent branches.'
```

The live OPAL checkout state confirms the branch divergence:

```text
/opal/regoclone/opal_repo_clone
## main...origin/main [ahead 1, behind 1]

HEAD / main:     690fe990191b018c8ab6d298977b029a52c2021c
origin/main:     b12075e46c959382817beb651291baf9e2581636
gitserver main:  b12075e46c959382817beb651291baf9e2581636
```

The live repo config has no pull strategy:

```text
remote.origin.url=http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git
remote.origin.fetch=+refs/heads/*:refs/remotes/origin/*
branch.main.remote=origin
branch.main.merge=refs/heads/main
```

`git config --global --list` and `git config --system --list` both failed
because there is no readable global or system config in the container. Git is
`2.39.2`. No `pull.rebase`, `pull.ff`, or equivalent strategy is configured.

Flux has already accepted the same remote update. The live
`GitRepository/flux-system/humility-local` reports:

```text
revision: main@sha1:b12075e46c959382817beb651291baf9e2581636
Ready=True
message: stored artifact for revision 'main@sha1:b12075e...'
```

Impact: when OPAL cannot publish the new policy bundle to OPAL Client/Cedar,
the Cedar policy plane can remain empty or stale after reseed/restart
sequences. The observed application symptom is that
`authorize_public_intake` returns 403 while OPA/Cedar has no usable policy
bundle.

## Architecture Review

### OPAL policy polling

The local OPAL manifest is under `gitops/channels/local/auth/opal-cedar/`
(not `auth/opal/` in this checkout).

`render-values.yaml` sets:

```yaml
server:
  policyRepoUrl: http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git
  extraEnv:
    OPAL_POLICY_REPO_POLICY_EXTENSIONS: ".cedar"
    OPAL_FILTER_FILE_EXTENSIONS: ".cedar"
    OPAL_POLICY_REPO_MAIN_BRANCH: main
```

The rendered Deployment sets:

```yaml
OPAL_POLICY_REPO_URL: http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git
OPAL_POLICY_REPO_POLLING_INTERVAL: "30"
OPAL_POLICY_REPO_MAIN_BRANCH: main
```

OPAL docs describe this mode as branch tracking: OPAL Server clones the tracked
branch, detects upstream changes, and pulls them into its local checkout. The
docs list polling and webhook modes. They list config for repo URL, clone path,
branch, polling interval, webhook secret, filtering, and bundle settings; they
do not document a pull-strategy variable.

OPAL 0.7.12 source matches the live behavior:

- `GitPolicySource` says change checks happen after a `git pull` from the
  tracked remote (`.tmp/opal-src/.../git_policy_source.py:11-18`).
- Initial state either clones into the configured path or reuses an existing
  valid repo (`git_policy_source.py:55-87`).
- Each poll calls `self._tracker.pull()` (`git_policy_source.py:89-108`).
- `BranchTracker._pull()` calls `self.tracked_remote.pull(*args, **kwargs)`
  with no `--rebase`, `--no-rebase`, `--ff-only`, reset, or custom refspec
  override (`branch_tracker.py:74-83`).
- The polling loop catches exceptions and logs them, then sleeps and retries
  (`base_policy_source.py:72-83`). It does not repair the checkout.

OPAL's container Dockerfile sets `OPAL_POLICY_REPO_REUSE_CLONE_PATH=true`; the
live clone path is consequently stable at:

```text
/opal/regoclone/opal_repo_clone
```

The fixed path explains why a rolling restart or pod replacement creates a
fresh container filesystem and clears the local divergent checkout.

### Configurable pull strategy

No configurable pull strategy was found.

Evidence:

- The official configuration guide lists `OPAL_POLICY_REPO_URL`,
  `OPAL_POLICY_REPO_CLONE_PATH`, `OPAL_POLICY_REPO_CLONE_FOLDER_PREFIX`,
  `OPAL_POLICY_REPO_REUSE_CLONE_PATH`, `OPAL_POLICY_REPO_MAIN_BRANCH`,
  `OPAL_POLICY_REPO_MANIFEST_PATH`, `OPAL_POLICY_REPO_CLONE_TIMEOUT`,
  `OPAL_REPO_WATCHER_ENABLED`, `OPAL_POLICY_REPO_POLLING_INTERVAL`,
  webhook settings, filters, and bundle settings.
- Grep across OPAL 0.7.12 source and docs found no `REBASE`, `RESET`,
  `pull.rebase`, `pull.ff`, `POLICY_REPO_*PULL*`,
  `POLICY_REPO_*REBASE*`, `POLICY_REPO_*RESET*`, or
  `POLICY_REPO_*STRATEGY*` setting.
- The implemented call is GitPython's remote pull with no strategy arguments.

The live OPAL server therefore uses Git's unconfigured pull behavior. Git's
own docs state that when the current branch and remote diverge, pull requires
the caller to specify how to reconcile the branches with `--rebase`,
`--no-rebase`, or corresponding config.

### Local gitserver behavior

The in-cluster gitserver is defined by `gitops/sources/local/git-daemon.yaml`:

- `Namespace/git-system`
- `PersistentVolumeClaim/git-daemon-pvc`
- `Deployment/git-daemon`
- `Service/git-local`

The Deployment has two containers:

- `git-daemon`: sleeps forever, mounts `/srv/git` read/write, and is written
  by bootstrap scripts through `kubectl exec`.
- `git-http`: serves `/srv/git` read-only over BusyBox `httpd` plus
  `git http-backend` on port 8080.

`infra/channels/local.yaml` points the local GitOps source at the same
in-cluster repo OPAL uses:

```yaml
gitops:
  git_url: http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git
  git_ref: refs/heads/main
  interval: 1m
```

### Reseed force-push pattern

`seed_git_daemon()` in `infra/scripts/install-flux-for-channel.sh` renders a
new local snapshot and then:

1. Deletes and recreates `/tmp/humility-gitops-seed`.
2. Runs `git init --initial-branch=main`.
3. Commits the rendered snapshot as `seed local gitops snapshot`.
4. Adds the bare in-cluster repo as `origin`.
5. Runs `git push --force origin main`.
6. Updates the bare repo HEAD and server info.

The commit is intentionally synthetic and not derived from the previous
gitserver `main`. Every reseed can create a one-commit history with no ancestry
relationship to the previous synthetic commit. That is a non-fast-forward
remote branch rewrite for any long-lived clone that already has the previous
commit checked out.

`reseed_gitserver_only()` reuses the same seed function, applies the source
CRs, waits for Flux to report the expected artifact revision, and prints the
separate Kustomization resume command. It does not touch OPAL.

### Flux polling

Flux uses the same Git URL but a different consumption model.

Flux source-controller creates a temporary directory during reconciliation and
removes it afterward (`gitrepository_controller.go:278-291`). Its checkout
path builds clone options with `ShallowClone: true`, constructs a Git client
for the temporary directory, and calls `gitReader.Clone(...)`
(`gitrepository_controller.go:977-1037`). It then stores a tar.gz artifact
identified by the resolved revision (`gitrepository_controller.go:817-842`).

Flux docs describe the same artifact model: `GitRepository` reports the latest
synchronized Git state as `.status.artifact`, and the artifact is a compressed
tar archive retrievable in-cluster. They also document interval polling and
manual reconcile annotation behavior.

## Why Force-Push Breaks OPAL But Not Flux

The immediate root cause is a contract mismatch between the local reseed model
and OPAL's polling implementation:

- BUG-4 reseed rewrites `refs/heads/main` to a new synthetic commit that does
  not descend from the previous synthetic commit.
- OPAL keeps a persistent local working clone at
  `/opal/regoclone/opal_repo_clone`.
- OPAL polls by running GitPython `origin.pull()` against that working clone.
- The clone's fetch refspec updates `origin/main` with a leading `+`, so the
  remote-tracking ref can move to the forced commit.
- The local checked-out branch `main` remains at the previous synthetic commit.
- The local branch and `origin/main` become `ahead 1, behind 1`.
- Because no pull reconciliation strategy is configured, Git aborts with
  `fatal: Need to specify how to reconcile divergent branches.`
- OPAL catches and logs the polling exception but does not reset, reclone, or
  republish policy.

Flux avoids the failure because it does not maintain a long-lived checked-out
branch that must be reconciled with the rewritten remote branch. It resolves
the current remote revision into a fresh temporary checkout and stores an
artifact. A new forced remote head is simply a different artifact revision.

The observed sequence fits this model:

```text
Before reseed:
  OPAL main and origin/main: 690fe990...

After reseed:
  gitserver main:            b12075e46...
  Flux artifact:             main@sha1:b12075e46...
  OPAL local main:           690fe990...
  OPAL origin/main:          b12075e46...
  OPAL status:               ahead 1, behind 1
  OPAL poll:                 git pull -v -- origin -> divergent branches fatal
```

## Solution Candidates

These are intervention candidates only, not a proposed fix.

### Option A: Configure OPAL with a divergence-tolerant pull/update strategy

Candidate shape: make OPAL's local checkout track the remote branch by
fetching and hard-resetting to `origin/main`, or otherwise configure a pull
strategy that can handle rewritten remote history.

Tradeoffs:

- Directly addresses the OPAL failure mode.
- Matches the local gitserver contract if reseeds are authoritative snapshots
  and local OPAL clone state is disposable.
- No documented OPAL 0.7.12 env var was found for this behavior.
- A plain `pull.rebase` or merge policy may create local synthetic ancestry
  rather than "remote snapshot wins" semantics.
- Implementing this inside OPAL would likely require image/runtime changes or
  an upstream OPAL feature; implementing it outside OPAL would need a wrapper
  or sidecar-like intervention.

### Option B: Make BUG-4 reseed also bounce OPAL Server

Candidate shape: after successful gitserver reseed and Flux source revision
verification, restart `Deployment/auth-system/opal-server` so the fixed clone
path is recreated in a fresh container filesystem.

Tradeoffs:

- Matches the current manual workaround.
- Does not require changing OPAL internals or the reseed commit model.
- Adds an auth-plane restart to a GitOps source maintenance command.
- A restart is a recovery action, not a git semantics fix.
- OPAL Client/Cedar hydration timing would need to be accounted for; an
  `opal-server` restart alone may not prove Cedar policy availability unless
  runtime policy probes are included elsewhere.

### Option C: Redesign reseed to create fast-forward commits

Candidate shape: instead of initializing a fresh repository in
`/tmp/humility-gitops-seed`, clone/fetch the current gitserver HEAD, overlay
the rendered snapshot, commit on top of the previous synthetic commit, and
push normally.

Tradeoffs:

- Aligns with OPAL's current `git pull` assumption.
- Preserves a linear synthetic history in `humility-local.git`.
- Requires careful handling when the bare repo is missing, corrupt, empty, or
  already diverged.
- Changes the BUG-4 reseed contract from "snapshot replacement by force-push"
  to "append-only synthetic history."
- May accumulate large generated snapshots in the local PVC history unless
  garbage-collection behavior is considered.

### Option D: Switch OPAL from git polling to webhook-triggered updates

Candidate shape: disable or reduce polling and trigger OPAL via its webhook
path when the policy source changes.

Tradeoffs:

- Removes the fixed 30-second polling loop and its recurring log failure.
- OPAL docs support webhook-triggered Git checks primarily around GitHub-style
  webhooks; the local gitserver is not GitHub and does not emit push webhooks.
- A custom reseed-triggered webhook would still need OPAL to update its local
  checkout. If the underlying implementation still uses `git pull`, webhook
  triggering changes when the failure happens, not necessarily the divergence
  behavior.
- Could be useful if paired with a different OPAL policy source/update
  mechanism, but by itself it does not prove non-fast-forward tolerance.

## Affected Paths

Primary local files:

- `gitops/channels/local/auth/opal-cedar/render-values.yaml`
- `gitops/channels/local/auth/opal-cedar/rendered/opal-0.0.29.yaml`
- `gitops/channels/local/auth/opal-cedar/kustomization.yaml`
- `gitops/channels/local/auth/networkpolicies.yaml`
- `gitops/sources/local/git-daemon.yaml`
- `infra/channels/local.yaml`
- `infra/scripts/install-flux-for-channel.sh`
- `infra/scripts/bring-up-local-channel.sh`
- `infra/scripts/render-gitops-source.py`

Policy/runtime validation surfaces:

- `policy/cedar/channels/local/services/server-manager-api/`
- `infra/tests/validate_auth_stack_local.sh`
- `infra/tests/validate_access_policy_local.sh`
- `infra/tests/validate_tenant_isolation_local.sh`
- `infra/tests/test_opal_manifest_authority.py`
- `infra/tests/test_access_policy_runtime_gate.py`
- `services/api/app/services/authorization.py`
- `services/api/app/infrastructure/authz.py`

Live cluster objects:

- `Deployment/auth-system/opal-server`
- `Deployment/auth-system/opal-client`
- `Service/auth-system/opal-client`
- `GitRepository/flux-system/humility-local`
- `Deployment/git-system/git-daemon`
- `Service/git-system/git-local`
- `PersistentVolumeClaim/git-system/git-daemon-pvc`
- `/srv/git/humility-local.git` inside the git-daemon PVC
- `/opal/regoclone/opal_repo_clone` inside the OPAL Server container

## Findings

1. OPAL 0.7.12 polls by running `git pull` against a persistent local clone.
2. The OPAL live clone is currently divergent: local `main` is
   `690fe990...`; `origin/main` and gitserver `main` are `b12075e46...`.
3. No live repo/global/system Git config defines `pull.rebase`, `pull.ff`, or
   another pull reconciliation strategy.
4. No OPAL 0.7.12 config variable or documented setting was found for pull
   strategy, rebase, hard reset, or divergence recovery.
5. BUG-4's reseed path force-pushes a fresh synthetic root commit, so it is
   intentionally non-fast-forward for existing clones.
6. Flux handles the same force-push because source-controller uses temporary
   shallow checkouts and artifact revisions, not a persistent working branch.
7. Restarting OPAL clears the symptom because the clone lives in the
   container filesystem and is recreated from the current gitserver head.
8. The root cause is not Git HTTP service availability. The gitserver remote
   is reachable; Flux and OPAL both fetch it. The failure is OPAL's attempt to
   reconcile a rewritten remote branch into its existing local branch with no
   pull strategy.

## Non-Fix Statement

This RCA does not recommend one option. It records the intervention points
above for the proposal/risk-gate phase.
