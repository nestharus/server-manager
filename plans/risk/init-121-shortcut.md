# INIT-121 Phase 4 Shortcut-Risk — Cedar policy source

## Inputs read

- `proposals/03-cedar-policy-source.md`
- `research/04-cedar-policy-source-problem-map.md`
- `.tmp/rca/cedar-bootstrap-put-FINDINGS.md`
- `~/ai/conventions/no-backwards-compatibility.md`
- `~/ai/conventions/no-deferred-stubs.md`

## Root-cause fix vs. relocation

The RCA names the root cause as a split-brain policy loading design: OPAL
Server/Client are configured to treat OPAL's policy source as authoritative,
but `OPAL_POLICY_REPO_URL` renders empty while the bundle lives only in a
ConfigMap consumed by a one-shot direct `PUT /v1/policies` Job
(`cedar-bootstrap-put-FINDINGS.md:50-52`).

The proposal fixes this at the cause, not by relocation:

- It populates `OPAL_POLICY_REPO_URL` with the existing in-cluster git daemon
  URL (`humility-local.git`) so OPAL Server can actually clone its declared
  source (`proposals/03-cedar-policy-source.md:80-83`).
- It removes the ConfigMap and the bootstrap Job entirely — they are deleted
  from `kustomization.yaml` and from the repo, with no fallback path
  (`proposals/03-cedar-policy-source.md:138-146`, scope point at
  `proposals/03-cedar-policy-source.md:58`).
- After the change, only one writer remains: OPAL Client's policy updater,
  which is the path OPAL was designed for. There is no second shim
  reproducing the bootstrap-Job race.

The proposal does not introduce a new bootstrap-Job-style step. The seed
flow is pre-existing (`install-flux-for-channel.sh` already force-pushes the
snapshot before Flux applies CRs); adding `policy/` to the snapshot does not
add a new write path into Cedar — it adds a populated source for OPAL to
clone. This eliminates the split-brain rather than relocating it.

## Implementation choices serve purpose

**Q1 (same-repo vs separate-repo):** Same-repo under top-level `policy/`.
The choice serves durability and operator clarity: only one bare repo per
channel to seed and lifecycle-manage, only one source for operators to
audit. The Flux Kustomization path is unchanged
(`./gitops/channels/local`), so adding `policy/` at the repo root does not
disturb Flux reconciliation (assumption A4). The minor cost — two consumers
read different subtrees of one repo — is named explicitly in Q1 and is
preferable to a second repo-lifecycle. No confusing bundling.

**Q2 (snapshot-scope change):** Adding `policy/` to the seed snapshot
preserves a single canonical source. The canonical authoring file remains
`policy/cedar/channels/local/services/server-manager-api/policies.json`
and the `.cedar` files are *generated* into a `generated/policies/`
subdirectory during snapshot rendering
(`proposals/03-cedar-policy-source.md:122-135`). Crucially, the renderer
"remove[s] and recreate[s] the generated policy directory each render so
stale `.cedar` files cannot survive after a policy deletion"
(`proposals/03-cedar-policy-source.md:135`). The generated files are
derived artifacts inside the seeded snapshot, not a second authoring
surface — no duplicate-source-of-truth risk.

**Q3 (.cedar files vs JSON):** `.cedar` files match OPAL's already-rendered
`OPAL_POLICY_REPO_POLICY_EXTENSIONS='[".cedar"]'`
(`render-values.yaml:6-7`) and OPAL's documented Cedar tutorial pattern.
The conversion is lossless: each JSON object's `content` becomes the file
body and `id` becomes the file stem; the materializer fails on duplicate
IDs, missing `id`/`content`, path-unsafe IDs, empty content, or invalid
JSON shape (`proposals/03-cedar-policy-source.md:135`). One newline
trailing convention is fixed, so the equality check is well-defined.

**Q4 (test-equality replacement):** The replacement is two assertions:
static (rendered seed `.cedar` files == canonical `policies.json` by ID
and content) plus runtime (`GET /v1/policies` returns the canonical IDs).
This is strictly stronger than the old ConfigMap-equality assertion: the
old check only compared two GitOps representations, while the new pair
also compares the GitOps representation against effective Cedar state.
Property preserved: canonical bundle == effective Cedar state — and now
checked at runtime, not just at render.

**Q5 (runtime gate replacement):** The new gate is `Deployment/opal-client`
readiness plus a poll of `GET /v1/policies` for canonical IDs
(`proposals/03-cedar-policy-source.md:70`, T3 at line 211). This proves
*current* loading via OPAL's intended path, which is the property the old
Job-completion gate failed to prove. T7 adds a one-polling-interval
re-probe after T3 to catch a pubsub-overwrite-empty-bundle regression
(line 219). Pod-restart durability is *not* exercised; that gap is treated
in `## Pod-restart durability` below.

## Anti-scope deferral honesty

The proposal defers remote-channel apply to BL-013/INIT-124 (scope line
56, supported-surface track at lines 178-179). That deferral is honest for
this cohort:

- `infra/channels/dev.yaml` has access-policy fields but explicitly omits
  any GitOps block; remote Flux wiring does not exist for this channel
  (`research/04-cedar-policy-source-problem-map.md:104`). There is nothing
  on the remote channel for this proposal to break or skip.
- Local is the only currently-supported cohort consuming OPAL/Cedar via
  Flux (`infra/channels/local.yaml:20-32`). Local is fully usable after
  this proposal — fresh `install-flux-for-channel.sh` produces a working
  end-to-end Cedar path with policy IDs hydrated.
- The deferred work is named with a tracked work unit ID
  (BL-013/INIT-124), satisfying the no-deferred-stubs convention's
  "name the follow-up work unit" requirement.

No deferral of behavior that local needs. Anti-scope is consistent with
the locked architectural direction.

## Migration / rollback completeness

The proposal targets fresh and reconciled `humility-local` clusters.
Migration order is named (lines 227-234) and is internally consistent:
tests first, renderer changes, manifest changes, deletion of the old
ConfigMap/Job, validator updates, then static-then-runtime verification.

Reconciled-cluster transition: when Flux reconciles the new manifests on
an existing local cluster, the bootstrap Job manifest is gone (Flux will
not delete the completed Job by itself; that is a `kubectl delete job`
operator step or a fresh-cluster artifact, but completed Jobs do not
re-run, so coexistence is benign). The ConfigMap is removed — nothing
mounts it after `bootstrap-job.yaml` is gone. OPAL Server rolls with the
new repo URL and Client reconnects. The seed step must run before Flux
reconciles the OPAL manifest update or OPAL Server will clone an empty
`policy/` subtree; the proposal's migration order (line 230-231) puts
the renderer extension before the manifest change, which addresses this.

Rollback path is described and honestly labeled as
"operationally straightforward but reintroduces the split-brain risk, so
it is only for emergency recovery" (line 189). Aligns with the
no-backwards-compatibility convention: the proposal explicitly forbids a
dual loading path (line 58).

For the named local cohort (project memory: "Local-only verification"
superseded by environment-agnostic-stack but still local-first for this
phase), migration is complete. No transition gap for longer-lived local
clusters that I could identify.

## Pod-restart durability

RCA H2 flagged that Cedar-Agent's in-memory store is wiped on
opal-client restart (`cedar-bootstrap-put-FINDINGS.md:24-28`). The RCA
also documents the OPAL mechanism that compensates: "the client triggers
a full policy refetch on server connection/reconnection, fetches from
`/policy`, and applies a returned bundle to Cedar"
(`cedar-bootstrap-put-FINDINGS.md:14`).

Under the new design, OPAL Server holds the authoritative bundle (cloned
from `humility-local.git`), and OPAL Client refetches on every connect.
A Cedar-Agent restart that occurs alongside an opal-client restart will
result in OPAL Client reconnecting to OPAL Server and re-applying the
bundle. Mechanism-wise, durability across pod restarts is built into
OPAL's design and is correctly leveraged here — the proposal does not
need a new mechanism for restart durability, because the OPAL refetch
path is exactly what the new design uses for *initial* loading too.

However, the **test plan does not exercise restart durability**:

- T7 waits one polling interval but does not restart `opal-client`
  (line 219).
- Out-of-scope explicitly lists "Strong durability proof across arbitrary
  `opal-client` pod crashes if Step 6b does not include a restart probe"
  (line 248).

This is an honest residual: the *mechanism* is sound and matches OPAL's
documented behavior, but the *evidence* that it works in this cluster is
weaker than it could be. A single `kubectl rollout restart
deployment/opal-client` followed by a re-poll of `/v1/policies` would
close this — it is a low-cost addition. T7 already structures the
follow-on probe; the only missing step is forcing the restart. This is
the most consequential gap I see in the proposal.

## Notable observations

- The proposal correctly inverts the previous test surface: the old gate
  ("Job exited 0") proved the wrong property; the new gate
  ("`/v1/policies` returns expected IDs through OPAL") proves the right
  property and is verifiable from outside the bootstrap mechanism.
- The static seeded-source equality check is strictly more useful than
  the prior ConfigMap-equality check because it pins the materializer
  output (the actual file format OPAL consumes) against canonical JSON
  rather than pinning two GitOps representations against each other.
- Project memory note: "channel-template-pattern" — environments are
  channels with parent inheritance. The same-repo choice here keeps
  channel-aware policy paths under
  `policy/cedar/channels/<channel>/services/<service>/`, which preserves
  the channel-template pattern when remote channels later reuse this.
- Validator-text update for `test_public_intake_policy_fixture.py`
  (line 168) is necessary; the current assertion encodes a string the
  new validator does not produce. The proposal flags this explicitly,
  reducing migration-leftover risk.
- The proposal's named acceptance for adding a restart-probe to Step 6b
  ("restart durability can remain follow-up if it is not included in
  Step 6b") leaves room for the implementation phase to close the gap
  cheaply. Recommend Step 6b include the restart probe given it costs
  one `kubectl rollout restart` plus a re-run of T3.

## Verdict

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```

The proposal addresses the RCA's root cause directly, the implementation
choices each serve the underlying purpose, deferrals are honest for the
local cohort, migration is complete, and pod-restart durability is
mechanism-correct. The single material gap is that the test plan does
not force an `opal-client` restart to verify the restart-refetch path.
That is a low-cost addition and is named in out-of-scope as a candidate
for Step 6b inclusion. No invalidated assumptions and no non-positive
value identified.
