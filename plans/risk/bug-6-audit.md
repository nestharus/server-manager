# Risk audit — BUG-6 OPAL divergence after gitserver reseed

Inputs:
- Proposal: `proposals/25-bug-6-opal-divergence.md`
- RCA: `research/38-bug-6-opal-divergence-rca.md`
- Substrate:
  - `infra/scripts/install-flux-for-channel.sh` — `reseed_gitserver_only`
    at lines 500-511, with `wait_for_source_revision` at lines 279-299
    and the seed/force-push flow at `seed_git_daemon` lines 188-228.
  - `gitops/channels/local/auth/opal-cedar/kustomization.yaml:3`
    (`namespace: auth-system`).
  - `gitops/channels/local/auth/opal-cedar/rendered/opal-0.0.29.yaml`
    — `Deployment/opal-client` line 56-58, `Deployment/opal-server`
    line 139-141, `OPAL_POLICY_REPO_URL` env at 188-189
    (`http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git`).
  - `gitops/channels/local/auth/opal-cedar/render-values.yaml:5`
    (Helm `policyRepoUrl` set to the same in-cluster URL).
  - OPAL 0.7.12 source already cloned at `.tmp/opal-src/`:
    - `packages/opal-common/opal_common/git_utils/repo_cloner.py:202`
      emits `"Clone succeeded"`.
    - `packages/opal-client/opal_client/policy/fetcher.py:121`
      emits `"Fetched valid bundle, id: {id}"`.

## Verdict

**Risk level: LOW–MEDIUM.** APPROVED WITH REQUIREMENTS — proceed
to implementation, with two implementer requirements:

1. The OPAL Client success-log check MUST match the actual upstream
   log string `"Fetched valid bundle"`
   (`opal_client/policy/fetcher.py:121`), not the proposal's plain-
   English "fresh bundle fetch signal" phrasing.
2. Both log probes (server `"Clone succeeded"` and client
   `"Fetched valid bundle"`) MUST be scoped to log lines emitted
   **after the bounce** — i.e. use `kubectl logs --since-time=`,
   `--since=`, or restrict to the new pod by name. Otherwise stale
   pre-bounce log lines (which exist in healthy starting states)
   would trivially satisfy both checks and the script would exit
   green without ever proving recovery.

The proposal's structural decisions are sound: it correctly
sequences the bounce *after* Flux's `wait_for_source_revision`
(eliminating the race where OPAL would otherwise reclone against an
old gitserver state); it uses `kubectl rollout restart`, not
imperative pod deletion; it keeps the substrate change confined to
the existing `reseed_gitserver_only` path; it does not touch OPAL's
image, OPAL's Helm values, the BUG-4 reseed contract, or BUG-9's
content-addressed Job naming. The Q4 audit of other in-cluster
gitserver polling consumers is correct and reproducible — only
OPAL Server polls `humility-local.git` through a persistent working
clone; Flux source-controller's temporary-shallow-clone model is
not affected, and Infisical's `resyncInterval` is unrelated
external-secret sync.

The two requirements above are wording/implementation discipline,
not design defects, so the verdict is APPROVED WITH REQUIREMENTS
rather than a hard block.

## Findings

### F-1 Bounce ordering eliminates the race — PASS

Audit check #1: "the bounce actually happens AFTER Flux's source
revision confirms (else racy)".

Proposal §2 Q2 explicitly locks the call site to "immediately after
step 5" of the existing flow, where step 5 is
`wait_for_source_revision "$SEEDED_REVISION_SHA"`
(`install-flux-for-channel.sh:505`). `wait_for_source_revision`
asserts `status.artifact.revision == main@sha1:<SEEDED_REVISION_SHA>`
on the local `GitRepository`, which is the proof that
source-controller has fetched and stored the new commit.

Why this matters: if the bounce fired before that wait, the new
OPAL Server pod could conceivably reclone against a gitserver state
that Flux had not yet certified, or — worse, in a degenerate case
where the bounce fires before the force-push completes — reclone
against the *old* state and silently re-establish the same
divergent baseline. After
`wait_for_source_revision` returns, the gitserver has durably
served the new SHA at least once (Flux successfully fetched it),
the bare repo's `update-server-info` has been refreshed by
`seed_git_daemon` (`install-flux-for-channel.sh:223`), and OPAL's
fresh clone over the same dumb-HTTP endpoint will see the same SHA.

PASS — ordering is correct as locked.

### F-2 `kubectl rollout restart` is the right primitive — PASS

Audit check #2: "Bounce uses `kubectl rollout restart`, not
`kubectl delete pod` (cleaner)".

Proposal §3 substrate (lines 124-125): "restart it with
`kubectl rollout restart deployment/opal-server`; wait for
`kubectl rollout status deployment/opal-server`".

Rationale for the choice — `rollout restart` annotates the
Deployment's `spec.template.metadata.annotations
[kubectl.kubernetes.io/restartedAt]`, which causes the Deployment
controller to roll out a replacement ReplicaSet under the standard
`maxUnavailable`/`maxSurge` policy. By contrast, `kubectl delete
pod` bypasses the Deployment controller's ordering and surge
behavior and is awkward when there is more than one replica or
when a PodDisruptionBudget is in play. Both eventually clear the
container filesystem and re-trigger OPAL's clone path, but
`rollout restart` is observable end-to-end via `rollout status`
(matches the proposal's success condition), is idempotent under
re-run, and does not depend on the caller knowing the pod name.

The proposal also correctly avoids `kubectl exec ... rm -rf
/opal/regoclone/opal_repo_clone`-style in-place cleanup. That
shortcut would not require a restart but would interact poorly
with the running watcher loop (the loop holds open file handles
and would race file removal). PASS.

### F-3 Server-side success signal exists in the upstream code — PASS

Audit check #3 part A: "rollout status, OPAL client log
'Fetched valid bundle'".

Proposal expects three server-side checks before the client probe:
rollout status succeeds, replacement pod reaches `Ready=True`,
and the server log contains `"Clone succeeded"`. The string is
real: `packages/opal-common/opal_common/git_utils/repo_cloner.py:202`
emits it via `logger.info("Clone succeeded", repo_path=self.path)`.
This signal fires during the OPAL Server initial clone path,
which is the path the bounced pod takes (the clone path is
configured via `OPAL_POLICY_REPO_REUSE_CLONE_PATH=true` against
the empty `/opal/regoclone/opal_repo_clone` of a fresh container
filesystem; per RCA §"OPAL policy polling", "initial state either
clones into the configured path or reuses an existing valid repo"
— in a fresh pod it falls into the clone branch).

PASS for the existence of the signal. See F-7 for the post-bounce
scoping requirement that applies to *both* probes.

### F-4 Client-side success signal — REQUIREMENT (literal log string) — PASS

Audit check #3 part B: the audit prompt names the concrete signal
as `"Fetched valid bundle"`. The proposal uses softer phrasing —
"the OPAL Client log shows that the client fetched a fresh bundle"
(line 76-78), and "inspect OPAL Client logs after the restart for
the fresh bundle fetch signal" (line 130-131). It does not pin the
exact upstream string.

The exact string in OPAL 0.7.12 is:

```
packages/opal-client/opal_client/policy/fetcher.py:121
    logger.info("Fetched valid bundle, id: {id}", id=bundle.hash)
```

**Required at implementation time:** the helper must grep for the
literal substring `Fetched valid bundle` in OPAL Client logs.
"Fresh bundle" or "policy update" or any synonym is not a real
upstream log line and would either never match (fail-closed —
script always errors) or match by coincidence (fail-open —
silent regression). Pinning the exact upstream string makes the
contract auditable and makes upstream OPAL upgrades a flagged
substrate change rather than a silent breakage.

This is a one-line implementer requirement, not a design defect,
so the finding is logged as a REQUIREMENT but does not block.

### F-5 Both log probes must be scoped to post-bounce — REQUIREMENT

Both `"Clone succeeded"` and `"Fetched valid bundle"` are routine
log lines that already exist in the *current* live OPAL state
*before* any reseed/bounce — the live OPAL Server completed an
initial clone successfully when first deployed (RCA §"Symptom +
State" shows OPAL is happily serving stale policy with
`opal_repo_clone` populated), and the live OPAL Client has fetched
valid bundles many times against that stale clone before the
divergence began.

If the bounce-success helper does:

```bash
kubectl -n auth-system logs deployment/opal-server | grep "Clone succeeded"
```

then in the "OPAL was healthy at start" branch of TG-2 the helper
will exit 0 *before the new pod has even been scheduled*, because
Kubernetes' `logs deployment/...` resolves to whichever pod is
selected by the Deployment label selector — including the
about-to-be-replaced pod that already logged `"Clone succeeded"`
on its own startup. Same hazard for the client probe.

**Required at implementation time:** scope both log searches to
post-bounce window. Acceptable patterns:

- Capture a wall-clock timestamp `t0=$(date -u +%FT%TZ)` immediately
  before `kubectl rollout restart`, then pass `--since-time="$t0"`
  to both `kubectl logs` invocations.
- Or: after `rollout status` succeeds, resolve the new pod by
  selector (`kubectl get pod -l app.kubernetes.io/name=opal-server
  -o jsonpath='{.items[?(@.status.phase=="Running")].metadata.name}'`)
  and tail logs from that specific pod only.
- Or: use `kubectl logs --since=2m` with a window strictly smaller
  than the bounce wait budget.

This finding combines with F-4: the literal string AND the post-
bounce scope are both required for the success signal to actually
prove what the proposal says it proves.

### F-6 Q4 audit of other polling consumers is correct — PASS

Audit check #4: "do other polling consumers exist? (Cedar OPA,
custom sidecars?)".

Reproduced the audit independently:

- `Grep -nE "policyRepoUrl|POLICY_REPO_URL|humility-local\.git"
  gitops/` returns three files, all under
  `gitops/channels/local/auth/opal-cedar/` (Helm values + rendered
  Deployment), plus `gitops/flux/humility-local.yaml:8` which is
  the Flux `GitRepository` source — not a polling client.
- The opal-cedar rendered chart contains exactly two Deployments:
  `opal-client` (line 56-58) and `opal-server` (line 139-141), in
  namespace `auth-system`. Only `opal-server` carries
  `OPAL_POLICY_REPO_URL` (line 188-189); `opal-client` consumes
  policy from `opal-server` over its own client/server channel,
  not directly from gitserver. No separate `cedar-agent` or `opa`
  Deployment is configured.
- `git-sync`/`gitsync`/custom sidecar grep is empty
  (already done in the RCA, reconfirmed: the OPAL deployment has
  no init-container or sidecar that polls git).
- `resyncInterval: 60s` matches at 26 paths, all
  `InfisicalSecret` resources — Infisical Operator polls Infisical
  Cloud / standalone, not the in-cluster git daemon. Unrelated.
- Flux's own consumption is via `GitRepository/flux-system/
  humility-local`, which the RCA correctly characterizes as
  temporary shallow checkouts + artifact storage, not a long-lived
  branch reconcile.

The bounce target list is therefore correctly limited to
`Deployment/auth-system/opal-server`. Bouncing `opal-client` is
unnecessary because the client does not maintain a divergent
working clone of `humility-local.git`; it pulls bundles from
`opal-server` over OPAL's pubsub/HTTP channel and is naturally
re-hydrated when `opal-server` republishes. PASS.

### F-7 No infinite-loop / partial-failure path — PASS

Audit check #5: "no infinite-loop / partial-failure path".

Proposal §3 requires "bounded waits with explicit error messages
that name the failing phase: source revision wait, server rollout,
server clone, client bundle fetch." The existing helpers in
`install-flux-for-channel.sh` already follow this pattern —
`wait_for_source_revision` uses `for attempt in $(seq 1 60); do …
sleep 2; done` then `die`, and `wait_for_rollout` uses
`for attempt in $(seq 1 120); do … sleep 3; done` then `die`. The
script runs under `set -euo pipefail`, so any uncaught failure
exits non-zero rather than silently dropping the recovery step.

TG-2 acceptance is explicit that failure to recover OPAL within
the bounded waits results in `script exits non-zero and points to
the failing OPAL recovery phase`. The proposal also explicitly
removes the soft-warning escape hatch: "Treat OPAL missing or
unavailable as a failed reseed recovery in the local channel, not
as a warning that still exits successfully" (line 132-134). That
is the right call for a local-only operator-facing tool — silent
"OPAL not present, skipping" would re-create the BUG-6 manual-
intervention shape this proposal is meant to remove.

Two partial-failure shapes worth the implementer's attention but
not blocking:

- **Helm install in progress.** If the operator runs
  `--reseed-gitserver-only` while OPAL is mid-rollout from a Flux
  apply (e.g. fresh cluster, OPAL just installed seconds ago), the
  bounce can race the initial rollout. `kubectl rollout status`
  with a bounded timeout will still terminate; the implementer
  should make sure the timeout error message distinguishes "rollout
  was already in progress and did not finish in budget" from "our
  bounce stalled". A simple `kubectl rollout status` after bounce
  is sufficient — it observes the latest revision generation, so
  a still-in-progress rollout from before our annotation will
  block until either it completes or our annotation supersedes it.

- **Two reseeds in fast succession.** If an operator runs the
  reseed twice within seconds, the second bounce will restart a
  pod that is mid-bootstrap from the first bounce. `rollout
  restart` is idempotent in the sense that it just re-annotates;
  a third pod will be rolled. This costs an extra pod cycle but
  does not loop or deadlock, because each `rollout status` call
  observes the latest annotated revision and waits for it.

PASS — no infinite-loop path, partial failures fail loudly with
named phase, no silent exit.

### F-8 Anti-scope is honored — PASS

Proposal §5 (lines 198-213) explicitly anti-scopes:

- No OPAL image change.
- No OPAL Git config change.
- No switch to webhooks.
- No fast-forward redesign of BUG-4 reseed.
- No imperative cleanup for BUG-9 Jobs.

These are the right anti-scopes. Notably, anti-scoping the
fast-forward redesign keeps the BUG-4 contract (force-pushable
synthetic snapshot) intact, which the BUG-4 audit already
ratified. Anti-scoping BUG-9 Job cleanup keeps the rerun contract
in render-time content addressing rather than pulling it into the
bounce path. PASS.

### F-9 Diff budget is realistic — PASS

§6 budget: "roughly 120 lines" of script-only change in
`install-flux-for-channel.sh`, with 3-5 small shell helpers and
one call site. Plausible: detection-of-deployment (~5 lines),
rollout restart + status (~10), wait for replacement pod ready
(~10, can reuse existing wait_for_rollout pattern), since-time
log probe for server "Clone succeeded" (~15), since-time log
probe for client "Fetched valid bundle" (~15), call site (~5),
plus error/log strings. Comes in around 60-80 lines without
golf, well under budget. No GitOps manifest churn; no production
service code; no doc churn. PASS.

## Observations (non-blocking)

1. **opal-client needs no explicit bounce.** The proposal
   correctly does not restart `Deployment/auth-system/opal-client`.
   When `opal-server` publishes a new policy bundle after its
   reclone, OPAL Client receives the update via OPAL's
   server→client channel and writes the new bundle to its policy
   store. The client log line `"Fetched valid bundle"` is the
   downstream proof that this hand-off completed. If a future
   change moves OPAL Client to its own persistent git clone,
   re-audit this assumption.

2. **30-second polling jitter does not affect the bounce.** OPAL
   Server's polling interval is 30s
   (`OPAL_POLICY_REPO_POLLING_INTERVAL: "30"`, RCA line 103-104).
   That cadence is the periodic-pull cadence, not the
   initial-clone cadence. A bounced pod clones immediately on
   startup and republishes; the 30s loop only matters for the
   *next* drift event, not for the post-bounce success path. The
   bounce wait budget therefore does not need to absorb a
   poll-interval window.

3. **The BUG-4 reseed already calls `update-server-info`.** OPAL's
   reclone goes through dumb-HTTP via `git-http`/`httpd` plus
   `git http-backend` (RCA "Local gitserver behavior"); dumb HTTP
   requires `objects/info/packs` and `info/refs` to be current.
   `seed_git_daemon` already runs `git --git-dir='${repo_path}'
   update-server-info` (`install-flux-for-channel.sh:223`) before
   `wait_for_source_revision`, so the reclone payload is correct
   before the bounce ever fires. No additional gitserver-side
   step is needed.

4. **TG-2 "diverged-but-still-running" starting state is the
   live-cluster baseline.** This state is exactly what the RCA
   captured at 2026-05-01: `main` at the old synthetic SHA,
   `origin/main` at the new SHA, `git pull` failing with
   `fatal: Need to specify how to reconcile divergent branches`.
   Once the bounce path lands, the *next* `--reseed-gitserver-only`
   run from this baseline is the live regression test. Worth
   capturing the before/after artifact as part of TG-1 evidence.

5. **Implementer hygiene: do not source the bounce helpers in the
   non-reseed path.** The full-bootstrap branch of `main()`
   (`install-flux-for-channel.sh:544-571`) installs OPAL via Flux
   reconcile and does not need an explicit OPAL bounce — OPAL
   comes up clean against a freshly seeded gitserver. The new
   helpers should be called only from `reseed_gitserver_only()`
   (per proposal Q2). Defining the helpers at top level is fine;
   not call-siting them from `main()` is the requirement.

6. **The `--reseed-gitserver-only` exit message at lines 509-510
   tells the operator to manually `kubectl patch kustomization
   ... suspend:false`.** That instruction is downstream of the
   OPAL bounce in the script's execution order, which means OPAL
   will be republishing policy bundle from the new gitserver
   state *before* the operator has resumed the Kustomization.
   That is fine — the bundle policy is sourced from gitserver
   directly, not from Flux's Kustomization apply — but worth
   noting so the implementer does not invert the order.

## Acceptance check (proposed)

When implementation lands, all of the following must hold:

- `infra/scripts/install-flux-for-channel.sh`'s
  `reseed_gitserver_only()` invokes the OPAL bounce immediately
  after `wait_for_source_revision "$SEEDED_REVISION_SHA"` and
  before any final log message.
- The bounce uses
  `kubectl rollout restart deployment/opal-server -n auth-system`
  and waits with `kubectl rollout status` under a bounded
  timeout, NOT `kubectl delete pod`.
- The replacement OPAL Server pod is verified `Ready=True`.
- The OPAL Server log probe greps for the literal upstream string
  `Clone succeeded` (F-3) and is scoped to log entries emitted
  *after* the bounce by either `--since-time=`, `--since=`, or
  by-pod-name selection (F-5).
- The OPAL Client log probe greps for the literal upstream string
  `Fetched valid bundle` (F-4 — not a paraphrase) and is also
  scoped to post-bounce log entries (F-5).
- Each phase has a bounded timeout and emits an explicit
  `die "OPAL recovery failed at <phase>: <detail>"` message; no
  silent-success branch exists for "OPAL deployment missing" or
  "OPAL pod did not become ready".
- TG-1: a single `--reseed-gitserver-only` against an
  already-loaded cluster causes `Deployment/auth-system/opal-server`
  to be restarted, the new pod becomes ready, both log probes
  match post-bounce entries, and `authorize_public_intake`
  succeeds without any manual intervention.
- TG-2: each starting state (down/missing-pod, healthy-with-policy,
  diverged-but-still-running) reaches the same end state OR the
  script exits non-zero with a phase-specific error.
- TG-3: BUG-9's content-addressed Job naming is not modified;
  `reseed_gitserver_only` does not delete, patch, or recreate any
  Job; the OPAL bounce is purely additive to the rerun contract.
- No edits to OPAL image, OPAL Helm values, GitOps manifests,
  `bring-up-local-channel.sh`, or `render-gitops-source.py`.
- Diff stays within §6 budget (~120 lines, script-only).

AUDIT_DONE: plans/risk/bug-6-audit.md
