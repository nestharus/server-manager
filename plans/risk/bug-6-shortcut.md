# BUG-6 — Shortcut risk gate (OPAL divergence after gitserver reseed)

**Verdict:** LOW

Source: `proposals/25-bug-6-opal-divergence.md`,
`research/38-bug-6-opal-divergence-rca.md`,
`infra/scripts/install-flux-for-channel.sh`.

## C1 — Real rollout-status wait, not "sleep 30s"

**Pass.**

The proposal substrate (lines 124-137) names every phase as a bounded
wait with an explicit failing-phase error message, not a fixed sleep:

> - restart it with `kubectl rollout restart deployment/opal-server`;
> - wait for `kubectl rollout status deployment/opal-server`;
> - wait for the replacement server pod to be ready;
> - inspect logs after the restart for the OPAL Server clone completion
>   signal;
> - inspect OPAL Client logs after the restart for the fresh bundle
>   fetch signal.
> ...
> Use bounded waits with explicit error messages that name the failing
> phase: source revision wait, server rollout, server clone, client
> bundle fetch.

This composes onto the script's existing wait helpers, which are real
kubectl waits, not sleeps:

- `wait_for_rollout` at `install-flux-for-channel.sh:311-328` polls
  `kubectl rollout status` with a 10s per-attempt timeout up to 120
  attempts and dumps `kubectl get -o wide` on failure. The proposal's
  rollout-status wait can land directly on this helper or a sibling.
- `wait_for_source_revision` at `install-flux-for-channel.sh:279-299`
  is the model: it spins on `source_artifact_revision` until the
  `main@sha1:${SEEDED_REVISION_SHA}` revision matches and `die`s with
  the YAML dump if it doesn't, rather than sleeping a flat duration.
- `wait_for_git_daemon` at `install-flux-for-channel.sh:156-175` does
  the same for the git daemon's exec-readiness.

The shortcut version of this fix would have been "after force-push,
`sleep 30; kubectl rollout restart deployment/opal-server; sleep 60`"
and called it done — that pattern is the one BUG-4's RCA explicitly
warned about (the manual workaround was bouncing the pod, and a flat
sleep would mask whether the new pod actually completed cloning before
the script exits). The proposal forecloses that by demanding a wait per
named phase and by lifting the existing `kubectl rollout status` /
condition wait pattern that already runs throughout this script.

The proposal also locks the *ordering* (Q2, lines 41-58): the OPAL
bounce runs after `wait_for_source_revision "$SEEDED_REVISION_SHA"` has
confirmed the new artifact, so the server restart is gated on Flux
having accepted the rewritten ref — there is no window where the
restart could happen against a still-stale source artifact. Without
that ordering, even a real rollout-status wait could pass before the
new policy is reachable.

The diff budget (lines 220-230) bounds churn to "3-5 small shell
helpers for OPAL deployment/pod lookup, rollout wait, and log-signal
waits" plus one call site, totalling under ~120 lines — that is
consistent with adding three or four `wait_for_*`-pattern helpers, not
collapsing the recovery into a single sleep+restart.

## C2 — OPAL client policy fetch verified, not just "server pod is Running"

**Pass.**

Q3 (proposal lines 64-83) is the most explicit anti-shortcut paragraph
in the proposal. It enumerates the candidate success conditions and
then *rejects* the "server pod replaced" framing as insufficient:

> The implementation should still wait for the mechanical restart to
> complete:
>
> - `Deployment/auth-system/opal-server` rollout succeeds.
> - the replacement OPAL Server pod reaches `Ready=True`.
> - the OPAL Server log shows that the policy clone completed again,
>   using the existing "Clone succeeded" signal.
>
> Those checks prove that the server pod was replaced and recloned
> policy, but they do not prove Cedar received usable policy. The
> bounce is successful only when the downstream OPAL Client observes a
> fresh bundle fetch after the server restart. That is the most
> concrete signal among the available choices because the user-visible
> failure is stale or empty Cedar policy at authorization time.

That last paragraph is the precise shortcut this gate was looking for.
The cheap fix would have been "rollout status returned 0 → done";
proposal explicitly says no, the success signal must be the *client*
bundle fetch. The substrate (lines 124-131) carries this forward as a
named wait phase: "inspect OPAL Client logs after the restart for the
fresh bundle fetch signal." TG-1 acceptance (lines 156-167) repeats
both signals (server "Clone succeeded" + client fresh bundle fetch) and
adds a runtime probe:

> - OPAL Server logs after the restart include "Clone succeeded".
> - OPAL Client logs after the restart show that the client fetched a
>   fresh bundle from OPAL Server.
> - `authorize_public_intake` calls succeed immediately after reseed.

The runtime probe is what closes the loop: even if both server and
client log signals are read correctly, the proposal demands the actual
authorization path that produced the user-visible BUG-6 symptom (per
RCA "Symptom + State", `research/38…rca.md:75-80`: 403 from
`authorize_public_intake` while OPA/Cedar has no usable policy bundle)
must succeed without manual intervention. That is the same probe the
RCA lists in "Affected Paths" alongside `services/api/.../authorization.py`
and `infra/tests/test_access_policy_runtime_gate.py`.

The RCA's solution candidates B and C made the comparable shortcut
explicit (`research/38…rca.md:284-298`):

> A restart is a recovery action, not a git semantics fix.
> OPAL Client/Cedar hydration timing would need to be accounted for; an
> `opal-server` restart alone may not prove Cedar policy availability
> unless runtime policy probes are included elsewhere.

The proposal answers that risk by including the runtime probe in TG-1
and the client log-signal wait in the substrate. There is no
intermediate "we'll add the probe in a follow-up" step.

## C3 — No "TODO: handle multi-replica OPAL"

**Pass.**

No TODO, deferral, or multi-replica caveat appears anywhere in the
proposal text. The narrowing is structural rather than papered-over:

- The script is local-channel-only by construction
  (`install-flux-for-channel.sh:524`:
  `[[ "$target" == "k3d-local" ]] || die "channel '${CHANNEL_ID}' target is '${target}', expected k3d-local"`).
  `--reseed-gitserver-only` is reachable only when target is k3d-local,
  so the bounce never executes against staging/production OPAL
  topologies.
- The local OPAL Helm values pin both server and client to
  `replicas: 1` (`gitops/channels/local/auth/opal-cedar/render-values.yaml:1-2`
  and `:23-24`), and the rendered manifest confirms it
  (`gitops/channels/local/auth/opal-cedar/rendered/opal-0.0.29.yaml:67`,
  `:150`). Within the BUG-6 perimeter, "the replacement OPAL Server
  pod" is unambiguously a single pod.
- Q4 (lines 84-115) audits other in-cluster gitserver consumers and
  concludes the only BUG-6 bounce target is
  `Deployment/auth-system/opal-server`. That audit incidentally
  confirms there is no second OPAL Server replica or sibling
  long-lived clone the proposal would need to extend to.
- Anti-scope (lines 198-214) explicitly forbids changing OPAL's image,
  Helm values, Git config, or polling/webhook mode. A multi-replica
  caveat would necessarily live in those files, and the proposal
  forecloses touching them. So a "TODO: handle multi-replica" comment
  in the script would have nowhere to land — the design constrains the
  scope to single-replica local OPAL.

The shortcut version of this fix would have been to write
`# TODO: handle multi-replica OPAL` next to a hard-coded
`kubectl get pods -l opal.ac/role=server -o name | head -n1` and move
on. Instead, Q4's audit converts the single-target assumption into a
documented design fact about the local channel, not an unresolved
ticket.

The one *implementation-time* care item that lives adjacent to this
concern (and is worth surfacing in TG, not as a blocker): the
"replacement server pod" wait must read the *new* pod after the
rollout-status wait completes, not the pre-restart pod. The proposal's
wording at line 127 ("wait for the replacement server pod to be
ready") and the existing pod-lookup pattern at
`install-flux-for-channel.sh:149-154` (`git_daemon_pod` filters on
`status.phase=Running`) both push toward this naturally — but the
implementer should verify the helper resolves the post-rollout pod by
labelSelector + ready-condition rather than by caching a name from
before the restart. This is a single-pod correctness issue, not a
multi-replica one.

## C4 — TG-1 actually exercises full chain, not "trust me bounce works"

**Pass.**

TG-1 acceptance criteria (lines 156-167) trace the full chain end-to-end
and assert at every link:

| Chain link                                          | TG-1 assertion                                                                            |
|-----------------------------------------------------|-------------------------------------------------------------------------------------------|
| Reseed force-push lands a new revision in gitserver | `GitRepository/flux-system/humility-local` reports `main@sha1:<SEEDED_REVISION_SHA>` artifact |
| Reseed path actually triggers the OPAL bounce       | `Deployment/auth-system/opal-server` is restarted by the reseed path                      |
| Replacement pod reaches readiness                   | The replacement OPAL Server pod reaches `Ready=True`                                       |
| OPAL Server reclones policy from current head       | OPAL Server logs after the restart include "Clone succeeded"                              |
| OPAL Client refetches the bundle                    | OPAL Client logs after the restart show that the client fetched a fresh bundle           |
| Cedar/OPA actually has usable policy                | `authorize_public_intake` calls succeed immediately after reseed                          |
| No manual intervention                              | No manual `kubectl rollout restart deployment/opal-server` or pod deletion is needed     |

Each row corresponds to a real artifact in this codebase or live
cluster, not a "trust me" assertion:

- The Flux artifact revision is the same field
  `wait_for_source_revision` (`install-flux-for-channel.sh:279-299`)
  already polls; TG-1 just inherits that wait.
- The OPAL Server "Clone succeeded" log signal is the same one the RCA
  identifies at `research/38…rca.md:113-124` (OPAL 0.7.12
  `git_policy_source.py` paths) — i.e. the literal line OPAL emits when
  its `BranchTracker` succeeds in cloning. Not a fabricated grep.
- The OPAL Client "fresh bundle fetch" signal is the documented
  client-side bundle fetch behavior; the RCA's "Impact" paragraph
  (`research/38…rca.md:75-80`) ties this directly to whether Cedar has
  a usable policy.
- `authorize_public_intake` is the production authorization path
  surfaced in the RCA's "Affected Paths" list
  (`research/38…rca.md:357-358`,
  `services/api/app/services/authorization.py`,
  `services/api/app/infrastructure/authz.py`). The RCA's symptom
  section identifies it explicitly as the user-visible failure
  (lines 75-80: "the observed application symptom is that
  `authorize_public_intake` returns 403"). TG-1 closing on the same
  call is genuinely closing the same defect loop.

The shortcut version of TG-1 would have stopped at row 3 ("the
replacement pod is Ready") or row 4 ("Clone succeeded in server logs")
— either of which Q3 explicitly rejects as insufficient. By landing
acceptance at row 6 (runtime authorization probe), TG-1 enforces that
the entire policy plane has rehydrated, not just that the bounce
mechanic ran.

TG-2 (lines 169-184) further hardens this by running the same chain
across an OPAL starting-state matrix:

> - down or missing ready pod;
> - healthy with policy already loaded;
> - diverged-but-still-running with repeated `git pull` failures.
>
> Acceptance:
>
> - In every state, `--reseed-gitserver-only` exits successfully only
>   after the new Flux source revision is confirmed, OPAL Server is
>   running from a fresh pod, OPAL Client has fetched policy again, and
>   `authorize_public_intake` succeeds.
> - If OPAL cannot be made healthy within the bounded waits, the script
>   exits non-zero and points to the failing OPAL recovery phase.

The third state ("diverged-but-still-running with repeated `git pull`
failures") is the *exact* live state captured in the RCA at
`research/38…rca.md:42-51` — the `ahead 1, behind 1` checkout with
`fatal: Need to specify how to reconcile divergent branches.` polling
errors. So TG-2 reproduces the actual incident state and gates the
recovery path against it, not just a green-field cluster.

TG-3 (lines 186-196) checks the cross-bug contract: BUG-6 must not
delete or recreate Jobs, and BUG-9's content-addressed Job rerun
contract must still drive Job execution through the rendered snapshot
— preventing a future shortcut where someone "fixes" a missed Job by
adding an imperative `kubectl delete job` to the OPAL recovery path.

## Findings worth carrying into implementation

Not blockers — verdict is LOW — but the implementation phase should
preserve:

1. **Resolve the replacement pod by labelSelector after rollout, not
   by caching a name from before the restart.** The existing
   `git_daemon_pod` helper at `install-flux-for-channel.sh:149-154`
   is the right pattern — `kubectl get pods -l … --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}'`,
   resolved *after* `kubectl rollout status` returns. A naive helper
   that captures the OPAL pod name once at function entry and then
   re-uses it after the restart would tail logs from a deleted pod and
   either return empty output (false negative) or hang.

2. **Tail OPAL Client logs from a window starting at restart time, not
   from log start.** The "fresh bundle fetch" signal will appear in
   OPAL Client logs every time the client polls (it has its own
   polling loop), so a `kubectl logs … | grep` over the entire log
   stream will match a *previous* fetch and report success without
   proving anything happened after the server restart. The wait must
   either use `--since-time=<server-restart-timestamp>`, or capture
   the post-restart log offset and grep only the new tail. Same
   consideration applies to the OPAL Server "Clone succeeded" wait,
   though server logs are wiped by the rolling pod replacement so the
   risk is smaller there.

3. **Distinguish `Deployment/auth-system/opal-server missing` from
   `available but unhealthy`.** Substrate (lines 132-134) says:
   > Treat OPAL missing or unavailable as a failed reseed recovery in
   > the local channel, not as a warning that still exits successfully.
   The two failure modes deserve distinct error messages so an operator
   can tell "OPAL was never installed in this channel" from "OPAL is
   installed but its rollout never completed." TG-2's first row
   ("down or missing ready pod") covers the latter; the implementer
   should verify the helpers also surface the former with a clear
   message rather than crashing on an empty `kubectl get` result.

4. **`authorize_public_intake` probe in TG-1 must hit the real API
   pod, not bypass authorization through a test fixture.** The RCA's
   "Affected Paths" list at lines 357-358 names
   `infra/tests/validate_access_policy_local.sh` and
   `infra/tests/test_access_policy_runtime_gate.py` as existing runtime
   gates. The TG-1 probe should reuse one of those paths (or the same
   call shape) so the gate exercises the real auth chain
   `request → API → OPAL Client → Cedar`, not an in-process unit-test
   shortcut. The RCA confirms this is the call that returns 403 in the
   failure mode (lines 75-80), so reusing the existing validator script
   is both faithful to the symptom and avoids re-implementing the
   probe.

5. **The post-bounce wait sequence should be: rollout → pod ready →
   server clone log → client bundle fetch log → runtime probe, in that
   order with bounded timeouts each.** The proposal lists the phases
   in this order at lines 124-131 and the success conditions at lines
   64-83 in the same order. Implementing them in any other order risks
   the runtime probe firing before the client has refetched, producing
   a flaky pass at the gate. Substrate's "explicit error messages that
   name the failing phase" requirement implicitly demands the phases be
   sequential with their own waits, not collapsed into one
   `until authorize_public_intake; do sleep; done` super-loop.

6. **Do not import a `pull.rebase` / git-config workaround into the
   reseed path.** The RCA explored this in Option A
   (`research/38…rca.md:266-282`) and noted no documented OPAL config
   for it. A shortcut implementation could try `kubectl exec` into the
   OPAL container to set `git config pull.rebase true` instead of
   bouncing the pod — that would defeat the proposal's locked decision
   (Q1, candidate B) and the anti-scope rule "Do not modify OPAL's
   image or Git config." The implementation must use the bounce path,
   not the in-container config tweak.

7. **TG-3's "no imperative Job delete" assertion must be checked
   against the actual implementation diff, not just the proposal text.**
   BUG-9's content-addressed Job rerun contract is paired with this
   bug; if the BUG-6 implementer reaches for `kubectl delete job` to
   "help" reseed scenarios where Jobs need to rerun, it would silently
   undermine BUG-9. The risk-gate should verify the post-implementation
   diff contains zero `kubectl delete job` or `kubectl patch job`
   invocations against the auth-system or migration namespaces.

## Verdict

LOW. No shortcuts. The proposal:

- Composes onto real `kubectl rollout status` waits (the existing
  `wait_for_rollout` and `wait_for_source_revision` helpers at
  `install-flux-for-channel.sh:279-328`) and explicitly demands "bounded
  waits with explicit error messages that name the failing phase"
  rather than flat sleeps.
- Names the OPAL Client fresh-bundle-fetch log signal *and* the
  `authorize_public_intake` runtime probe as the binding success
  conditions, and explicitly rejects the "server pod is Running"
  framing as insufficient (Q3, lines 64-83).
- Carries no multi-replica TODO because the design is structurally
  single-pod: local channel only (`install-flux-for-channel.sh:524`),
  `replicas: 1` for both OPAL server and client in the local Helm
  values, and Q4 audited that no other in-cluster gitserver consumer
  needs a parallel bounce.
- Encodes TG-1 and TG-2 against the full chain — gitserver write →
  Flux source artifact → OPAL Server restart → server clone signal →
  client bundle fetch signal → runtime authorization probe — and
  reproduces the live divergent-checkout state from the RCA in TG-2's
  starting-state matrix, so the gate exercises the actual incident
  rather than asserting "trust me, the bounce works."

SHORTCUT_DONE: plans/risk/bug-6-shortcut.md
