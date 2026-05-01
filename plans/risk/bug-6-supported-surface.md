# BUG-6 — Supported-surface risk gate

**Verdict:** LOW

BUG-6 (after `--reseed-gitserver-only` force-pushes a new synthetic
root commit into `humility-local.git`, OPAL Server's persistent working
clone at `/opal/regoclone/opal_repo_clone` becomes `ahead 1, behind 1`
relative to the rewritten `origin/main`; with no `pull.rebase`/`pull.ff`
configured, GitPython's `origin.pull()` aborts with `fatal: Need to
specify how to reconcile divergent branches.`, the polling loop catches
and logs the failure, and Cedar policy stays stale until an operator
manually restarts the OPAL Server pod — RCA §"Why force-push breaks
OPAL but not Flux") is repaired by extending
`reseed_gitserver_only()` in
`infra/scripts/install-flux-for-channel.sh` with a fifth phase: after
`wait_for_source_revision "$SEEDED_REVISION_SHA"` confirms Flux has
ingested the new artifact (proposal §2 Q2), the script issues
`kubectl rollout restart deployment/opal-server` against
`Deployment/auth-system/opal-server`, waits for rollout completion and
the replacement pod's readiness, scans server logs for the OPAL "Clone
succeeded" signal, and finally scans `Deployment/auth-system/opal-client`
logs for a fresh bundle-fetch signal (proposal §2 Q3, §3 modified
file). No new operator script, no new flag, no new env var, no OPAL
image or Helm-values change, and no GitOps manifest edit accompanies
this fix (proposal §3 "Unmodified substrate", §5 anti-scope, §6 diff
budget).

## Surfaces touched

### 1. Public API — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| HTTP/gRPC routes exposed by `services/api` | as today | unchanged — proposal §3 "Unmodified substrate": "No production API, Discord daemon, web, repository, service, migration, OPAL image, OPAL Helm values, or GitOps manifest changes" | none |
| Bridge/web endpoints consumed by `services/web` | as today | unchanged — out of the modified-files list (single edit confined to `infra/scripts/install-flux-for-channel.sh`, proposal §3 + §6) | none |
| OPAL Server / OPAL Client HTTP surfaces (`http://opal-server:7002`, `http://opal-client:8180`) | as today | unchanged — the bounce restarts the existing Deployment without altering its Service, container ports, or env block; the rendered `opal-0.0.29.yaml` Service definitions for `opal-server` (port 7002) and `opal-client` (port 8180) are not in the diff budget | none |
| Pomerium → API → OPAL Client authorization probe (`authorize_public_intake`) | currently 403s when Cedar policy is stale post-reseed (RCA §"Symptom + state") | restored to 200 immediately after reseed (proposal §4 TG-1 acceptance: "`authorize_public_intake` calls succeed immediately after reseed") — same endpoint, same payload, same response semantics | none — improved availability without contract change |

Risk on §1: **none.** Gate criterion 1 (no public API change) holds.
The only externally observable behavior change is that the previously
manual `kubectl rollout restart deployment/opal-server` workaround
becomes automatic, restoring an existing API to its working state
faster.

### 2. Operator workflow — `bring-up-local-channel.sh --reseed-gitserver-only` continues to work

`bring-up-local-channel.sh` declares `--reseed-gitserver-only` (line
19, line 88), validates exclusivity against `--force/--repair/--cluster-only`
(lines 105-108), and then delegates verbatim to:

```
bash "$FLUX_INSTALLER" --channel "$CHANNEL_ID" --reseed-gitserver-only
```

(line 451). The wrapper's CLI shape is therefore the property of
`install-flux-for-channel.sh`. In that script `--reseed-gitserver-only`
toggles `RESEED_GITSERVER_ONLY=1` (line 78) and gates entry to
`reseed_gitserver_only()` (lines 539-542); the proposal extends
`reseed_gitserver_only()` *only after* its existing fifth step
`wait_for_source_revision "$SEEDED_REVISION_SHA"` (proposal §2 Q2,
script line 505). The CLI parsing path, the flag name, the resolver
inputs, the resolved channel id, the `KUBECONFIG_PATH`/`SOURCE_NAME`/
`SOURCE_NAMESPACE` resolution, and the delegation chain from
`bring-up-local-channel.sh` are all untouched.

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `bring-up-local-channel.sh --reseed-gitserver-only` resolves and dispatches | works (lines 451-452 of `bring-up-local-channel.sh`) | unchanged — proposal §3 "Unmodified substrate": "Do not change `infra/scripts/bring-up-local-channel.sh` beyond its existing delegation" | none |
| `install-flux-for-channel.sh --reseed-gitserver-only` flag parsing | recognized (line 77-79), gated entry (line 539) | unchanged — proposal §3 modifies only the body of `reseed_gitserver_only()`; argument parsing, dispatch, and resolver block (lines 70-89, 513-542) are not in the diff budget (§6: "one script-only change" with helpers + one call site) | none |
| Existing five reseed phases (`render_local_snapshot`, `ensure_git_daemon_for_reseed`, `seed_git_daemon`, `apply_source_crs`, `wait_for_source_revision`) | run in order (lines 500-505) | unchanged order, unchanged semantics — proposal §2 Q2: "The OPAL bounce belongs immediately after step 5"; the bounce is appended, not interleaved | none |
| `--cluster-only`, `--force`, `--repair`, full bootstrap path (`main` lines 544-571) | as today | unchanged — proposal §3 limits the diff to `reseed_gitserver_only()`; `main()`'s full-install branch (`else`-equivalent after the `RESEED_GITSERVER_ONLY` early return) is not in the diff budget | none |
| Trailing operator hint (`kubectl patch kustomization … {"spec":{"suspend":false}}`) | printed at end of reseed (lines 509-510) | unchanged — proposal §6 budget is additive (helpers + one call site after `wait_for_source_revision`); the existing tail logging is preserved | none |

Risk on §2: **none.** Gate criterion 2 (operator workflow continues
to work) holds. The wrapper's command line and exit conventions are
preserved; only the success-condition stringency tightens — see §5
below for the documented failure-mode shift.

### 3. No new env vars or flags

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `install-flux-for-channel.sh` flag set (`--channel`, `--reseed-gitserver-only`, `-h/--help`) | lines 70-89 | unchanged — proposal §6 "no documentation update required unless implementation discovers a new operator-facing command or failure mode"; the implementation explicitly rejects "a second operator script" (proposal §2 Q2) and "no new env vars or flags" is enumerated as a gate | none |
| `bring-up-local-channel.sh` flag set (`--channel`, `--force`, `--repair`, `--cluster-only`, `--reseed-gitserver-only`) | usage at lines 19, 30-37 | unchanged — wrapper is out of the modified-files list (§3) | none |
| OPAL container env (`OPAL_POLICY_REPO_URL`, `OPAL_POLICY_REPO_POLLING_INTERVAL`, `OPAL_POLICY_REPO_MAIN_BRANCH`, `OPAL_POLICY_REPO_REUSE_CLONE_PATH`, etc., RCA §"OPAL policy polling") | as today, set by Helm-rendered Deployment | unchanged — proposal §5 anti-scope: "Do not modify OPAL's image or Git config"; no `OPAL_POLICY_REPO_*PULL*`/`*REBASE*`/`*RESET*` variable is added (none was found in OPAL 0.7.12 source per RCA §"Configurable pull strategy") | none |
| `git-daemon` container env / config | as today | unchanged — proposal §3 only adds `kubectl rollout restart` + log probing against the existing OPAL Deployments; the gitserver Deployment, Service, and PVC (`gitops/sources/local/git-daemon.yaml`) are not in the diff budget | none |
| Renderer env (`infra/scripts/render-gitops-source.py`) | as today | unchanged — proposal §3 "Unmodified substrate": "Do not change `infra/scripts/render-gitops-source.py` for BUG-6. BUG-9 owns content-addressed Job naming in the rendered snapshot" | none |
| Shell-script timeouts / wait constants (`WAIT_TIMEOUT="180s"`, polling loop counts) | top-of-file (lines 16-31) | the proposal's "bounded waits" reuse the existing `WAIT_TIMEOUT` family or introduce locally-scoped function-level constants; no new exported env var (proposal §3 "Use bounded waits with explicit error messages that name the failing phase"; §6 caps total churn at ~120 lines including helpers) | none |

Risk on §3: **none.** Gate criterion 3 (no new env vars or flags)
holds. The fix is implemented purely as additional shell helpers and
one new call site inside an existing function; the wait limits
piggyback on the existing constants or on locally-scoped values.

### 4. Deployment names referenced are correct (`auth-system/opal-server`, `auth-system/opal-client`)

The target Deployment names are verified against the rendered chart in
this checkout (not just the RCA's live-cluster snapshot):

| Resource | Defined at | Confirms |
|---|---|---|
| `Kustomization` `namespace: auth-system` for the OPAL slice | `gitops/channels/local/auth/opal-cedar/kustomization.yaml:3` | the rendered Deployments below land in namespace `auth-system` |
| `Deployment` `name: "opal-server"` | `gitops/channels/local/auth/opal-cedar/rendered/opal-0.0.29.yaml:141` (selector at line 153, container `name: opal-server` at line 174, image `docker.io/permitio/opal-server:0.7.12` at line 175) | rollout target `Deployment/auth-system/opal-server` resolves |
| `Deployment` `name: "opal-client"` | `gitops/channels/local/auth/opal-cedar/rendered/opal-0.0.29.yaml:58` (selector at line 70, container `name: opal-client` at line 91, image `docker.io/permitio/opal-client-cedar:0.7.12` at line 92) | log-tailing target `Deployment/auth-system/opal-client` resolves |
| Live cluster confirmation (RCA §"Affected paths") | `Deployment/auth-system/opal-server`, `Deployment/auth-system/opal-client`, `Service/auth-system/opal-client` | independently corroborates the namespace/name pair |
| OPAL Server policy-repo URL | `OPAL_POLICY_REPO_URL=http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git` (`rendered/opal-0.0.29.yaml`, RCA §"OPAL policy polling") | the bounce target is the only in-cluster consumer with a persistent working clone of `humility-local.git` (proposal §2 Q4 audit) |

The proposal text uses `Deployment/auth-system/opal-server` (proposal
§3 first bullet, §4 TG-1 acceptance) and `Deployment/auth-system/opal-client`
(implicit in the OPAL Client log probe, proposal §2 Q3 + §3). Both
match the rendered chart and the live cluster.

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `kubectl rollout restart deployment/opal-server` resolves in `auth-system` | n/a (manual workaround today) | matches rendered Deployment name + Kustomization namespace; resolves cleanly under both `kubectl_cmd` (which already wires `--kubeconfig "$KUBECONFIG_PATH"` via line 128-130) | none |
| `kubectl rollout status deployment/opal-server` matches the same Deployment | n/a | same as above; the existing `wait_for_rollout` helper (lines 311-328) and `kubectl_cmd -n <ns> rollout status` pattern (line 145, 161) already handle this signature | none |
| OPAL Client log scan for "fresh bundle fetch" signal | n/a | `Deployment/auth-system/opal-client` confirmed at `rendered/opal-0.0.29.yaml:58`; the Service `opal-client:8180` (line 6) is internal-only, so the log probe avoids cluster-egress assumptions | none — implementation should pin the exact log substring during build, but the resource name target is correct |
| Other in-cluster `humility-local.git` consumers that would also need bouncing | none beyond Flux's own source-controller (proposal §2 Q4 audit: "no other non-Flux in-cluster component was found that polls `humility-local.git` through a persistent working clone") | no expansion of the bounce target list — Flux uses temporary shallow checkouts (RCA §"Flux polling") so it is unaffected | none |

Risk on §4: **none.** Gate criterion 4 (deployment names are correct)
holds. The proposal's resource references match the rendered chart in
this checkout, the Kustomization namespace, the live cluster
inspection captured in the RCA, and the policy-repo URL audit that
proves OPAL Server is the only persistent-clone consumer.

### 5. Bounce's failure mode is documented

The proposal commits to **fail-loud** semantics with named phases and
disallows silent success:

> "Treat OPAL missing or unavailable as a failed reseed recovery in
> the local channel, not as a warning that still exits successfully.
> The goal is no operator intervention after reseed."
> — proposal §3, third bullet under the modified-file changes

> "Use bounded waits with explicit error messages that name the
> failing phase: source revision wait, server rollout, server clone,
> client bundle fetch."
> — proposal §3, fourth bullet

> "If OPAL cannot be made healthy within the bounded waits, the
> script exits non-zero and points to the failing OPAL recovery
> phase."
> — proposal §4 TG-2 acceptance

| Failure mode | Pre (today) | Post (proposed) | How it's surfaced |
|---|---|---|---|
| OPAL Server Deployment absent in `auth-system` (e.g., during a partial bring-up) | reseed exits 0 silently because nothing checks OPAL (script ends at line 510 after Flux source confirmation) | reseed exits non-zero with an error naming the OPAL detection phase ("Treat OPAL missing or unavailable as a failed reseed recovery"); the existing `die "<message>"` pattern (lines 50-53) carries that contract | non-zero exit + named phase |
| OPAL Server Deployment present but new pod fails to roll out within bounded wait | reseed exits 0 (no check) | reseed exits non-zero with "server rollout" phase identifier (proposal §3 phase naming) | non-zero exit + named phase |
| OPAL Server pod ready but never logs "Clone succeeded" within bounded wait (e.g., gitserver unreachable for unrelated reasons, or PVC mount issue) | symptom would only appear later as repeated polling failures (RCA §"Symptom + state") | reseed exits non-zero with "server clone" phase identifier | non-zero exit + named phase |
| OPAL Client never logs a fresh bundle fetch within bounded wait (server reclone succeeded but client did not pick up) | symptom would surface as `authorize_public_intake` 403 long after the operator command returned 0 | reseed exits non-zero with "client bundle fetch" phase identifier | non-zero exit + named phase |
| OPAL is down for *unrelated* reasons (e.g., upstream `humility-local.git` HTTP path broken; Authentik dependency issue holding back pod scheduling) | masked behind the silent-success exit | the script "fails loud" — the operator sees a non-zero exit naming the phase that timed out, which is the documented failure-mode contract | non-zero exit + named phase |
| Healthy steady state (OPAL up, gitserver reachable, divergence resolved by recreated pod) | required manual `kubectl rollout restart` (RCA §"Symptom + state") | reseed exits 0 only after Flux source revision is confirmed AND the OPAL Server pod has recloned AND the OPAL Client has fetched a fresh bundle; `authorize_public_intake` succeeds immediately afterwards (proposal §4 TG-1 acceptance) | exit 0 only on full recovery |

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Exit-code contract for `--reseed-gitserver-only` | 0 once Flux confirms the new artifact, even if OPAL is wedged (the bug condition itself) | 0 only after OPAL Server is recloned and OPAL Client has fetched a fresh bundle within bounded waits; non-zero with a named failing phase otherwise | low — this is a contract tightening; any external tooling that previously treated exit 0 as "GitOps source updated" must now also tolerate exit non-zero meaning "GitOps source updated, but auth plane not yet recovered." This change is *intentional* (proposal §1: "no operator intervention after reseed") and fully documented in proposal §3 + §4 TG-2 |
| stdout/stderr message format | `log()` (line 55-57) writes to stdout; `die()` (lines 50-53) writes "ERROR: …" to stderr and exits 1 | reused — proposal "explicit error messages that name the failing phase" sits naturally on the existing `die "<message>"` helper; no new logging helper is introduced | none |
| Reseed re-runnability (operator can re-invoke the same command after a transient failure) | already idempotent (the seed phase recreates `/tmp/humility-gitops-seed`, force-pushes the same content if rerun) | preserved — `kubectl rollout restart` is itself idempotent (kicks a fresh ReplicaSet rollout each invocation), and the post-restart log probes look for the *latest* "Clone succeeded" / fresh bundle-fetch signal so a rerun against an already-healthy OPAL succeeds | none |

Risk on §5: **none** for documentation-of-failure-mode (which is the
gate criterion); **low, intentional** for the exit-code contract
tightening, which is the documented behavior change and the entire
point of the fix. Gate criterion 5 (failure mode documented) holds.

### 6. Anti-scope items — explicitly held out

| Surface | Status | Source |
|---|---|---|
| OPAL image / `Dockerfile` / `OPAL_POLICY_REPO_REUSE_CLONE_PATH` flip | not modified | proposal §5 anti-scope: "Do not modify OPAL's image or Git config" |
| OPAL Helm chart values (`gitops/channels/local/auth/opal-cedar/render-values.yaml`) | not modified | proposal §3 "Unmodified substrate"; the env-driven OPAL config (RCA §"OPAL policy polling") stays as today |
| Switch from polling to webhook-triggered updates | not introduced | proposal §5 anti-scope: "Do not switch OPAL from polling to webhooks" (would change *when* OPAL checks for changes, not *how it reconciles* a non-fast-forward remote) |
| Redesign reseed to fast-forward commits | not introduced | proposal §5 anti-scope: "Do not redesign the reseed to do fast-forward-only commits. BUG-4 explicitly locked the reseed contract as a complete local snapshot force-pushed into the in-cluster gitserver" |
| Imperative cleanup for one-shot Jobs (alembic, public-intake-seed) | not introduced — owned by BUG-9 (commit `65dde95`) | proposal §3 "Unmodified substrate": "Do not change `infra/scripts/render-gitops-source.py` for BUG-6. BUG-9 owns content-addressed Job naming"; §5: "Do not add imperative cleanup for BUG-9 one-shot Jobs" |
| `bring-up-local-channel.sh` body changes beyond delegation | not modified | proposal §3 "Unmodified substrate": "Do not change `infra/scripts/bring-up-local-channel.sh` beyond its existing delegation to `install-flux-for-channel.sh --reseed-gitserver-only`" |
| GitOps manifest churn (Pomerium, Authentik, OPAL chart, NetworkPolicy, gitserver) | not modified | proposal §6 budget: "No GitOps manifest churn" |
| Production service code (API, Discord daemon, web, repository, service, migration) | not modified | proposal §3 "Unmodified substrate"; §6: "No production service code" |
| New operator script for OPAL recovery | not introduced | proposal §2 Q2: "Do not add a second operator script. BUG-6 is a missing recovery step in the existing narrow reseed path, not a separate maintenance workflow"; §6: implementation is "one script-only change" |
| Bounce of other in-cluster gitserver consumers | not introduced — none exist | proposal §2 Q4 audit: "no other non-Flux in-cluster component was found that polls `humility-local.git` through a persistent working clone"; §1 rationale: Flux uses temporary shallow checkouts so it is unaffected (RCA §"Flux polling") |

## Supported-surface findings summary

| Gate | Verdict |
|---|---|
| 1. No public API change | PASS |
| 2. `bring-up-local-channel.sh --reseed-gitserver-only` continues to work | PASS |
| 3. No new env vars or flags | PASS |
| 4. Deployment names referenced are correct (`auth-system/opal-server`, `auth-system/opal-client`) | PASS |
| 5. Bounce's failure mode is documented (fail-loud with named phase) | PASS |

## Findings

1. **No public API change.** The single edited file is
   `infra/scripts/install-flux-for-channel.sh`; proposal §3
   "Unmodified substrate" excludes API/daemon/web/repository/service/
   migration/OPAL image/OPAL Helm values/GitOps manifest changes.
   Pomerium routes, Authentik blueprints, OPAL/OPA decision endpoints,
   and the `services/api`+`services/web` HTTP/gRPC contracts are not
   in the diff budget. The only externally observable behavior change
   is positive: the previously manual `kubectl rollout restart
   deployment/opal-server` workaround becomes automatic, and
   `authorize_public_intake` returns to 200 without operator
   intervention (proposal §4 TG-1).

2. **Operator workflow preserved.** `bring-up-local-channel.sh`
   delegates to `install-flux-for-channel.sh --reseed-gitserver-only`
   verbatim at line 451; that delegation is left alone (proposal §3
   "Unmodified substrate"). Inside `install-flux-for-channel.sh`, the
   flag-parsing, resolver, and dispatch blocks (lines 70-89, 513-542)
   are untouched, and the existing five reseed phases run in their
   current order; the bounce is appended after step 5 per proposal §2
   Q2. A re-run of the wrapper after a transient failure remains
   idempotent because `kubectl rollout restart` kicks a fresh
   ReplicaSet rollout and the log probes look for the latest
   "Clone succeeded" / fresh bundle-fetch signal.

3. **No new env vars or flags.** The implementation adds 3-5 small
   shell helpers (proposal §6 budget) and one call site inside
   `reseed_gitserver_only()`. The proposal explicitly rules out a
   second operator script (§2 Q2), an OPAL config flip (§5
   anti-scope), and a webhook-mode env var (§5 anti-scope). The
   bounded waits piggyback on the existing `WAIT_TIMEOUT` family or
   on locally-scoped values; no new exported environment variable is
   introduced.

4. **Deployment names correct.** Verified against the rendered chart
   in this checkout: `gitops/channels/local/auth/opal-cedar/kustomization.yaml:3`
   sets `namespace: auth-system`, `gitops/channels/local/auth/opal-cedar/rendered/opal-0.0.29.yaml:141`
   defines `Deployment` `name: "opal-server"`, and the same file at
   `:58` defines `Deployment` `name: "opal-client"`. Both names
   match the live-cluster snapshot the RCA captured under §"Affected
   paths" (`Deployment/auth-system/opal-server`,
   `Deployment/auth-system/opal-client`). The proposal's audit (§2
   Q4) confirms OPAL Server is the only in-cluster consumer of
   `humility-local.git` via a persistent working clone, so no
   additional bounce target is silently missing.

5. **Failure mode documented.** Proposal §3 commits to fail-loud
   semantics with phase-named errors ("source revision wait, server
   rollout, server clone, client bundle fetch"), explicitly disallows
   the previous silent-success exit ("Treat OPAL missing or
   unavailable as a failed reseed recovery in the local channel, not
   as a warning that still exits successfully"), and §4 TG-2
   acceptance encodes the contract: "If OPAL cannot be made healthy
   within the bounded waits, the script exits non-zero and points to
   the failing OPAL recovery phase." The OPAL-down-for-unrelated-
   reasons case (gate question 5) is therefore explicitly covered:
   the script will exit non-zero naming the rollout, server-clone,
   or client-bundle-fetch phase that timed out, rather than masking
   the situation. This is a *tightening* of the previous exit-code
   contract — exit 0 used to mean "GitOps source updated"; it now
   means "GitOps source updated AND OPAL Server recloned AND OPAL
   Client has fetched a fresh bundle." Any external tooling that
   wrapped the reseed must tolerate the new non-zero exits, which
   is the entire purpose of the fix and is fully documented.

## Out-of-scope items intentionally not addressed

- **OPAL upstream pull-strategy/rebase support** — discussed and
  discarded (RCA Option A; proposal §5 anti-scope: "Do not modify
  OPAL's image or Git config"). RCA §"Configurable pull strategy"
  found no documented OPAL 0.7.12 env var for this behavior, and the
  implementation lives in OPAL's GitPython call which would require
  upstream changes.

- **Webhook-triggered updates** — discussed and discarded (RCA
  Option D; proposal §5 anti-scope). Would change *when* OPAL
  checks but not *how* it reconciles a non-fast-forward remote, so
  it would not prove the fix.

- **Fast-forward reseed history** — discussed and discarded (RCA
  Option C; proposal §5 anti-scope). Locked by BUG-4: the reseed is
  authoritative snapshot replacement by force-push.

- **Imperative Job cleanup in `reseed_gitserver_only`** — owned by
  BUG-9 (commit `65dde95`, content-addressed Job names). Proposal
  §3 + §5 explicitly bar BUG-6 from deleting/patching/recreating
  any server-manager Job; §4 TG-3 verifies BUG-9's contract is not
  regressed.

- **Bouncing other in-cluster consumers of `humility-local.git`** —
  proposal §2 Q4 audit established that no other non-Flux consumer
  maintains a persistent working clone; Flux's source-controller
  uses temporary shallow checkouts (RCA §"Flux polling") and is
  unaffected. Adding pre-emptive bounces for unrelated workloads
  would expand blast radius without addressing a real failure mode.

- **`bring-up-local-channel.sh` body edits** — proposal §3 holds
  the wrapper at its current delegation contract; no usage line,
  flag, or pre-flight check changes.

- **Documentation updates** — proposal §6: "No documentation update
  required unless implementation discovers a new operator-facing
  command or failure mode." The flag set is unchanged and the
  failure-mode shift is internal to an already-documented operator
  command, so no external docs land in this fix.

## Verdict

**LOW** — the fix is a self-contained shell change confined to
`infra/scripts/install-flux-for-channel.sh`'s
`reseed_gitserver_only()`, appending a `kubectl rollout restart
deployment/opal-server` plus bounded-wait health probes after the
existing `wait_for_source_revision` step. It changes no public API,
no env var, no operator flag, no GitOps manifest, no OPAL image, no
OPAL Helm values, and no other script or service. The Deployment
names (`Deployment/auth-system/opal-server`,
`Deployment/auth-system/opal-client`) are verified against both the
rendered chart in this checkout and the RCA's live-cluster snapshot.
The failure-mode contract is documented as fail-loud with phase-named
errors, the OPAL-down-for-unrelated-reasons case is explicitly
covered by TG-2 acceptance, and the only behavior change for
external tooling is the *intentional* exit-code tightening that is
the deliverable of this bug. All five supported-surface gates pass.

SUPPORTED_SURFACE_DONE: plans/risk/bug-6-supported-surface.md
