# Proposal 25 - BUG-6: OPAL divergence after gitserver reseed

## 1. Problem statement

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

## 2. Decisions

### Q1. Recovery option

Lock: candidate B, make BUG-4 reseed also bounce OPAL Server.

After `--reseed-gitserver-only` force-pushes the new synthetic snapshot and
Flux source-controller confirms the matching `GitRepository` artifact
revision, the script should restart `Deployment/auth-system/opal-server`. This
matches the known manual recovery path: OPAL's clone lives in the container
filesystem, so replacing the OPAL Server pod gives it a fresh checkout from the
current gitserver head.

Candidate B is deliberately narrower than changing OPAL internals, changing
Git config, redesigning the reseed history model, or moving OPAL to webhooks.
It keeps BUG-4's source contract intact: the local gitserver remains an
authoritative rendered snapshot that can be replaced by a force-pushed
synthetic commit.

### Q2. Bounce location

Lock: option i, add the bounce inside `reseed_gitserver_only` after Flux's
`GitRepository` confirms the new revision.

The current reseed flow is:

1. `render_local_snapshot`
2. `ensure_git_daemon_for_reseed`
3. `seed_git_daemon`
4. `apply_source_crs`
5. `wait_for_source_revision "$SEEDED_REVISION_SHA"`

The OPAL bounce belongs immediately after step 5. That ordering matters:
before the Flux source revision is confirmed, the script only knows that the
bare gitserver ref was moved; after the source revision is confirmed, both
Flux and OPAL are pointed at a gitserver state that has been accepted as the
new source artifact.

Do not add a second operator script. BUG-6 is a missing recovery step in the
existing narrow reseed path, not a separate maintenance workflow.

### Q3. Success condition

Lock: OPAL Client fetches the new bundle, visible in client logs.

The implementation should still wait for the mechanical restart to complete:

- `Deployment/auth-system/opal-server` rollout succeeds.
- the replacement OPAL Server pod reaches `Ready=True`.
- the OPAL Server log shows that the policy clone completed again, using the
  existing "Clone succeeded" signal.

Those checks prove that the server pod was replaced and recloned policy, but
they do not prove Cedar received usable policy. The bounce is successful only
when the downstream OPAL Client observes a fresh bundle fetch after the server
restart. That is the most concrete signal among the available choices because
the user-visible failure is stale or empty Cedar policy at authorization time.

The test plan then closes the loop with a runtime authorization probe:
`authorize_public_intake` must succeed immediately after reseed without a
manual restart.

### Q4. Other in-cluster gitserver consumers

Lock: no other non-Flux in-cluster component was found that polls
`humility-local.git` through a persistent working clone.

Audit results:

- `gitops/channels/local/auth/opal-cedar/render-values.yaml` and the rendered
  OPAL Server Deployment are the only local manifests found with
  `OPAL_POLICY_REPO_URL` pointing at
  `http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git`.
- The user-requested path `gitops/channels/local/auth/opal/` does not exist in
  this checkout; the OPAL deployment is under
  `gitops/channels/local/auth/opal-cedar/`.
- Flux also consumes the same gitserver through
  `GitRepository/flux-system/humility-local`, and several Kustomization CRs
  refer to that source. The RCA explains why Flux is not affected: it resolves
  the current remote revision into temporary shallow checkouts and stores
  artifacts, rather than maintaining a long-lived checked-out branch that must
  reconcile a forced update.
- `git-daemon` serves and stores the bare repo; it is not a polling client of
  the repo it serves.
- Grep found no `git-sync`, `gitsync`, custom Git sidecar, or other manifest
  that directly clones or polls `humility-local.git`.
- Infisical `resyncInterval` resources are external secret synchronization,
  not local gitserver polling.

The only BUG-6 bounce target is therefore `Deployment/auth-system/opal-server`.
BUG-9's content-addressed Job work remains the paired fix for stable completed
Jobs that must rerun after a reseed; BUG-6 should not add imperative Job
deletes or recreate other workloads.

## 3. Substrate

### Modified file

- `infra/scripts/install-flux-for-channel.sh`
  - Extend `reseed_gitserver_only` after
    `wait_for_source_revision "$SEEDED_REVISION_SHA"`.
  - Add focused helpers for the OPAL recovery step:
    - detect whether `Deployment/auth-system/opal-server` exists;
    - restart it with `kubectl rollout restart deployment/opal-server`;
    - wait for `kubectl rollout status deployment/opal-server`;
    - wait for the replacement server pod to be ready;
    - inspect logs after the restart for the OPAL Server clone completion
      signal;
    - inspect OPAL Client logs after the restart for the fresh bundle fetch
      signal.
  - Treat OPAL missing or unavailable as a failed reseed recovery in the local
    channel, not as a warning that still exits successfully. The goal is no
    operator intervention after reseed.
  - Use bounded waits with explicit error messages that name the failing phase:
    source revision wait, server rollout, server clone, client bundle fetch.

### Unmodified substrate

- No production API, Discord daemon, web, repository, service, migration, OPAL
  image, OPAL Helm values, or GitOps manifest changes.
- Do not change `infra/scripts/render-gitops-source.py` for BUG-6. BUG-9 owns
  content-addressed Job naming in the rendered snapshot. BUG-6 only adds the
  OPAL post-reseed recovery step to the installer script.
- Do not change `infra/scripts/bring-up-local-channel.sh` beyond its existing
  delegation to `install-flux-for-channel.sh --reseed-gitserver-only`.

## 4. Test plan

### TG-1: reseed recovers OPAL without manual restart

Run `--reseed-gitserver-only` against a local cluster where OPAL policy is
already loaded and authorization currently succeeds.

Acceptance:

- `GitRepository/flux-system/humility-local` reports the new synthetic
  `main@sha1:<SEEDED_REVISION_SHA>` artifact.
- `Deployment/auth-system/opal-server` is restarted by the reseed path.
- The replacement OPAL Server pod reaches `Ready=True`.
- OPAL Server logs after the restart include "Clone succeeded".
- OPAL Client logs after the restart show that the client fetched a fresh
  bundle from OPAL Server.
- `authorize_public_intake` calls succeed immediately after reseed.
- No manual `kubectl rollout restart deployment/opal-server` or pod deletion
  is needed.

### TG-2: OPAL starting-state matrix

Verify the reseed continues to work when OPAL begins in each relevant state:

- down or missing ready pod;
- healthy with policy already loaded;
- diverged-but-still-running with repeated `git pull` failures.

Acceptance:

- In every state, `--reseed-gitserver-only` exits successfully only after the
  new Flux source revision is confirmed, OPAL Server is running from a fresh
  pod, OPAL Client has fetched policy again, and `authorize_public_intake`
  succeeds.
- If OPAL cannot be made healthy within the bounded waits, the script exits
  non-zero and points to the failing OPAL recovery phase.

### TG-3: paired BUG-9 behavior is not regressed

Run a reseed after BUG-9's content-addressed Job names are present in the
rendered snapshot.

Acceptance:

- BUG-6 does not delete, patch, or recreate any server-manager Job.
- New migration or seed payload content still produces the BUG-9
  content-addressed Job names through the rendered snapshot.
- The OPAL bounce happens after Flux confirms the new source artifact and does
  not mask or replace the BUG-9 Job rerun contract.

## 5. Anti-scope

Do not modify OPAL's image or Git config. The project does not own OPAL's
upstream polling implementation, and no documented OPAL 0.7.12 pull-strategy
setting was found in the RCA.

Do not switch OPAL from polling to webhooks. A webhook would change when OPAL
checks for changes, not prove that OPAL can reconcile a non-fast-forward
remote update into its persistent working clone.

Do not redesign the reseed to do fast-forward-only commits. BUG-4 explicitly
locked the reseed contract as a complete local snapshot force-pushed into the
in-cluster gitserver.

Do not add imperative cleanup for BUG-9 one-shot Jobs. Content-addressed Job
identity and TTL belong to BUG-9; BUG-6 is limited to OPAL recovery.

## 6. Diff budget

Expected implementation size: one script-only change in
`infra/scripts/install-flux-for-channel.sh`.

Budget:

- Add 3-5 small shell helpers for OPAL deployment/pod lookup, rollout wait,
  and log-signal waits.
- Add one call site in `reseed_gitserver_only` after
  `wait_for_source_revision "$SEEDED_REVISION_SHA"`.
- Keep total script churn under roughly 120 lines.
- No GitOps manifest churn.
- No production service code.
- No documentation update required unless implementation discovers a new
  operator-facing command or failure mode.
