# Risk audit — BUG-8 Authentik blueprint health check

Inputs:

- Proposal: `proposals/26-bug-8-blueprint-health.md`
- RCA: `research/39-bug-8-blueprint-health-rca.md`
- Substrate verified against the worktree:
  - `infra/scripts/install-flux-for-channel.sh` —
    `reseed_gitserver_only()` at lines 588–600, with
    `bounce_opal_for_reseed()` defined at line 550 and called at
    line 594.
  - `infra/tests/e2e/tests/19-web-ui.sh` — `run_validator
    validate-web-ui infra/tests/validate_web_ui_local.sh ...` at
    line 276; Playwright invocation at line 290; `run_validator`
    helper defined at `infra/tests/e2e/lib/assertions.sh:87–93`.
  - `infra/tests/validate_web_ui_local.sh` — `--static-only` mode
    parsed at lines 66–68, runtime proof block lines 236–297.
  - `infra/tests/validate_auth_stack_local.sh` — pass/fail/skip
    helpers and `RESULT: pass=… fail=… skip=…` summary format
    (the local validator pattern this proposal must follow).
  - `gitops/channels/local/auth/authentik/postgres-cluster.yaml` —
    CNPG `Cluster/auth-system/authentik-postgres` declared with
    container `postgres` and database `authentik`. CNPG primary is
    selected via `cnpg.io/cluster=<cluster>,role=primary` (the same
    selector idiom used at `infra/tests/e2e/tests/19-web-ui.sh:21`
    and `infra/scripts/run-cnpg-restore-drill.sh:113`).

## Verdict

**Risk level: LOW–MEDIUM.** APPROVED WITH REQUIREMENTS — proceed to
implementation, with three implementer requirements and two
observations.

The proposal's structural decisions are sound. It picks the right
intervention point (host-side validator, candidate B), the right
file (`infra/tests/validate_authentik_blueprints_local.sh`, matching
the existing `validate_*_local.sh` family), the right query surface
(direct CNPG psql exec, not REST), the right assertion list
(blueprint instance state PLUS provider-to-scope-mapping binding,
which is precisely the masking shape the BUG-8 RCA names), and the
right call sites (BUG-6 reseed path, e2e test 19 preflight, and
`validate_web_ui_local.sh` runtime proof). The locked CNPG
primary-by-label decision is correct and matches the rest of the
local-channel tooling.

The three requirements below pin down (a) the actual SQL targets so
the validator does not couple to the wrong Authentik table names,
(b) post-bounce sequencing in the reseed path so the validator is
not asserting against state that Flux has not yet had a chance to
apply, and (c) failure-message specificity so the BUG-8 named-error
contract is preserved across all eight assertions. None of these is
a design defect; they are wording and implementer discipline, so the
verdict is APPROVED WITH REQUIREMENTS rather than a hard block.

## Findings

### F-1 SQL targets are the right shape — PASS with REQUIREMENT

Audit check #1: "validator queries the right tables/columns
(`authentik_blueprints_blueprintinstance`, `authentik_core_provider`,
`authentik_core_provider_property_mappings`,
`authentik_core_propertymapping`)".

The proposal §2 Q3 names `authentik_blueprints_blueprintinstance`
explicitly and §2 Q4 enumerates the eight runtime assertions, which
collectively imply queries against:

- `authentik_blueprints_blueprintinstance` — for assertions 1, 2, 3
  (presence, `status='successful'`, non-empty `last_applied_hash`).
- `authentik_core_propertymapping` — for assertions 4, 5 (existence
  of the two custom `discord_user_id` scope mappings).
- `authentik_core_provider` — for the named providers `pomerium` and
  `server-manager-applicant` in assertions 6, 7.
- `authentik_core_provider_property_mappings` — the M2M join table
  binding providers to property mappings, required for assertions
  6 and 7 (provider has the four expected mappings).
- `authentik_core_application` — required for assertion 8 (the
  `pomerium` application links to the `pomerium` provider). This
  is the one table the audit checklist does not enumerate but the
  proposal's assertion 8 needs.

These are standard Authentik Django table names (`app_model`
naming). They do not appear anywhere in the repo (verified — no
prior code queries Authentik internals), so the implementer is
choosing them by convention.

**Required at implementation time:** the validator must reference
the exact table names listed above, including
`authentik_core_application` for assertion 8 even though the audit
checklist names only four tables. The implementer should not
substitute a join through `authentik_outposts_*` or any other
neighboring Authentik schema, and should not collapse assertions
6/7/8 into a single SQL pass that loses per-mapping/per-provider
naming on failure (see F-3).

PASS for design intent; REQUIREMENT for table name pinning.

### F-2 CNPG primary selection by label, not by hardcoded name — PASS

Audit check #2: "selects primary pod by CNPG label, not hardcoded
name".

Proposal §2 Q3 explicitly locks: "select the primary pod for
`Cluster/auth-system/authentik-postgres` by label instead of
hard-coding `authentik-postgres-1`". This is the correct CNPG
discipline — the operator re-labels the primary on failover, so
hardcoding `-1` is fragile and would silently target a replica or
a missing pod after a CNPG primary switch.

The label selector idiom already in use across the local channel is
`cnpg.io/cluster=<cluster-name>,role=primary` (verified at
`infra/tests/e2e/tests/19-web-ui.sh:21` for `humility-postgres` and
`infra/scripts/run-cnpg-restore-drill.sh:113`). The Authentik
equivalent is therefore:

```bash
kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system get pod \
  -l "cnpg.io/cluster=authentik-postgres,role=primary" \
  -o jsonpath='{.items[0].metadata.name}'
```

The container name is `postgres` (verified in
`postgres-cluster.yaml`) and the database is `authentik`. The
proposal substrate also correctly notes that the validator should
not require a host-side `psql` client — the `psql` execution lives
inside the `postgres` container via `kubectl exec`, which matches
how every other CNPG-driven local script behaves.

PASS — the locked decision is correct and reproducible.

### F-3 Both blueprint status AND provider mapping bindings asserted — PASS with REQUIREMENT

Audit check #3: "asserts both: blueprint status + provider scope
mapping bindings".

Proposal §2 Q4 locks eight blocking assertions. Mapping to the
audit's two-class requirement:

- **Blueprint status** (assertions 1, 2, 3): every mounted `init-*`
  blueprint is present in `authentik_blueprints_blueprintinstance`,
  has `status='successful'`, and has a non-empty
  `last_applied_hash`. ✓
- **Provider scope mapping bindings** (assertions 4, 5, 6, 7): both
  custom `discord_user_id` scope mappings exist, and both providers
  (`pomerium` and `server-manager-applicant`) have all four expected
  property mappings (default `openid` + `email` + `profile` + the
  custom `discord_user_id`). ✓
- **Application linkage** (assertion 8): the `pomerium` application
  links to the `pomerium` provider. This is a third assertion class
  beyond what the audit checklist names, and is correct: the
  bootstrap masking shape from the RCA depended on the application
  pointing at a host-bootstrapped provider stripped of custom
  mappings, so checking the application→provider FK closes that
  loop.

The proposal correctly anti-scopes warning-only modes:
"Missing custom mappings must fail even if the provider exists and
login would otherwise work with the three default OIDC mappings."
That is exactly the contract that closes the BUG-8 silent-failure
class.

**Required at implementation time:** assertions 6 and 7 must report
the *specific missing mapping name(s)* on failure, not just
"provider X has the wrong number of mappings". The RCA-grade error
message for the BUG-8 incident must read substantially like:

```
FAIL: provider 'pomerium' missing required scope mapping
  'server-manager-pomerium-discord_user_id'
  (has: openid, email, profile)
```

A bare count comparison ("expected 4, got 3") would re-introduce the
debuggability gap the proposal §2 Q3 closes. See F-4.

PASS for design intent; REQUIREMENT for per-mapping failure naming.

### F-4 Failure messages name the specific blueprint/provider/mapping — PASS

Audit check #4: "failure messages name the specific
blueprint/provider/mapping (debuggable)".

Proposal §2 Q3 explicitly contracts the failure output:

> Failure output must include: blueprint `name`; blueprint `path`;
> `status`; `last_applied_hash`; the stored diagnostic
> context/content available on the blueprint instance row, and
> recent Authentik worker log lines for that blueprint when the row
> is in a failing state.

Proposal §4 TG-2 acceptance reinforces this:

> the failure names the exact blueprint, for example
> `init-127-applicant-discord-oauth` or
> `init-133B-pomerium-officer-discord`;
> the failure includes `status`, `path`, `last_applied_hash`, and
> the available apply diagnostic context or worker log excerpt;
> Playwright is not needed to discover the failure.

This is exactly the named-failure contract that closes the
"e2e timeout instead of blueprint failed" symptom from the RCA. The
implementer must preserve this for assertions 4, 5, 6, 7, 8 too —
F-3 covers the mapping case; the same discipline applies to
assertion 8 (name the application and the missing/wrong provider FK
target).

PASS — the proposal locks the right contract.

### F-5 Reseed integration sequence — PASS with REQUIREMENT

Audit check #5: "reseed integration sequence is correct (after OPAL
bounce, after Flux apply)".

Proposal §2 Q5(1) locks: in `reseed_gitserver_only`, call the
validator after `bounce_opal_for_reseed`. Verified against the
substrate: `reseed_gitserver_only()` at
`infra/scripts/install-flux-for-channel.sh:588–600` runs in the
order render → seed git daemon → apply Flux sources → wait for
`SEEDED_REVISION_SHA` → `bounce_opal_for_reseed` (line 594) →
manual-resume guidance.

This sequencing is **correct for the BUG-6/BUG-8 cascade contract**:
OPAL has clean policy state before the validator fires, so a
validator failure can be cleanly attributed to Authentik blueprint
state and not to OPAL policy divergence.

**However, there is a sequencing nuance the implementer must be
aware of.** In the `--reseed-gitserver-only` path, Flux's
`Kustomization` is intentionally left **suspended** at the point
the OPAL bounce fires; the script's final lines tell the operator
to manually `kubectl patch kustomization … suspend:false` afterward
(this was already noted in the BUG-6 audit, observation 6). What
this means concretely:

- If the reseed is being run because OPAL diverged but the cluster
  was otherwise healthy (the BUG-6 incident shape), Authentik's
  blueprint state is exactly what it was before the reseed, and the
  validator correctly verifies that pre-existing healthy state.
- If the reseed includes new or changed blueprints in the synthetic
  GitOps snapshot, **Flux has not applied them yet** at the
  validator's call site. The validator will see pre-reseed blueprint
  state, not post-reseed state. After the operator manually resumes
  Flux, a subsequent validator call (or rerun of e2e test 19) is the
  thing that proves the new blueprint state.

This is consistent with the proposal's intent (the reseed call site
is named "BUG-6 reseed recovery first confirms the new GitRepository
revision and OPAL bundle refresh, then fails the reseed if Authentik
blueprint runtime state is broken") and is acceptable because the
validator is designed to be runnable independently from any of its
three call sites. But the implementer must not advertise the reseed
call as proving "the reseed's blueprint changes are healthy" — it
proves "Authentik runtime state is healthy at the moment OPAL
finished re-clone, before manual Flux resume".

**Required at implementation time:** the validator failure messages
emitted from the reseed path must not imply that the validator has
verified post-resume Flux state. A neutral message like
`"Authentik blueprint runtime state is invalid (Flux not yet
resumed; rerun validator after `kubectl patch kustomization …
suspend:false`)"` preserves the BUG-6 manual-resume contract without
falsely advertising what was checked.

The Flux **full-bootstrap** path
(`install-flux-for-channel.sh:main()` non-reseed branch) is a
separate concern not modified by this proposal: the validator is
not call-sited from the full-bootstrap path. That is correct —
e2e test 19 and `validate_web_ui_local.sh` cover the
full-bootstrap-and-then-validate flow downstream.

PASS for the chosen call-site ordering; REQUIREMENT for failure
wording in the reseed branch.

### F-6 e2e + `validate_web_ui_local.sh` integrations — PASS with OBSERVATION

Audit check #6: "e2e + validate_web_ui_local.sh integrations don't
introduce flakiness".

**e2e test 19 integration.** Proposal §2 Q5(2) locks the validator
call before the Playwright OAuth flow. Verified:
`infra/tests/e2e/tests/19-web-ui.sh:276` already invokes
`run_validator validate-web-ui infra/tests/validate_web_ui_local.sh
--kubeconfig "$KUBECONFIG_PATH" ...` and Playwright runs at
line 290. The new validator preflight slots in cleanly via the
existing `run_validator` helper
(`infra/tests/e2e/lib/assertions.sh:87–93`); same kubeconfig, same
failure mode, same logging surface.

Flakiness analysis:

- The validator is a synchronous psql query, not a poll loop. Risk
  of "blueprint is mid-apply" transient: low — by the time test 19
  is reached, the cluster has already passed `validate-auth-stack`
  and the BUG-4/BUG-6 reseed path. Authentik's worker discovers
  mounted blueprints during boot and re-checks regularly; the
  steady state is the relevant state.
- CNPG primary failover during the test would cause a transient
  selector-resolution failure. Rare but possible. The validator
  should fail cleanly with the named pod-discovery phase rather
  than dump a kubectl error and exit ambiguously.
- Network-namespace path through `kubectl exec` is the same shape
  used by the existing `cnpg-restore-drill.sh`; no new failure
  mode introduced.

**`validate_web_ui_local.sh` integration.** Proposal §2 Q5(3) locks
the validator as part of runtime proof and explicitly skips it
under `--static-only`. Verified: `--static-only` is parsed at lines
66–68; runtime proof at lines 236–297. The new call hooks into the
runtime block, which is the correct path — the runtime proof
already depends on identity claims being present, so checking their
Authentik source first is logically ordered.

The web UI validator is itself called from e2e test 19, so this
introduces a transitive call: 19-web-ui.sh →
validate_web_ui_local.sh → validate_authentik_blueprints_local.sh.
That is the same shape the proposal authorizes, and is fine because
each invocation is idempotent (read-only psql query, no side
effects). The proposal's separate top-level call from
19-web-ui.sh (Q5(2)) **plus** the call from
validate_web_ui_local.sh (Q5(3)) means the blueprint check will
run twice in the e2e flow — once explicitly at line ~276 area and
once transitively from validate-web-ui. This is acceptable but
worth noting.

**Required at implementation time:** the validator must be
idempotent and side-effect-free (read-only SQL only; no writes,
no admin API calls, no port-forward). It already is by §3 substrate
("require kubectl and psql through the in-cluster Postgres pod"),
but the implementer should not introduce a "fix on detect" mode or
any mutation that would make the double-call behavior in
19-web-ui.sh non-trivial.

PASS for design intent; OBSERVATION on double-invocation.

### F-7 Anti-scope is honored — PASS

Proposal §5 anti-scopes:

- No Kubernetes Job or webhook (the host-side validator is the
  intervention).
- No Authentik image, Helm chart, or runtime version change.
- No blueprint ConfigMap structure change.
- No fallback REST API path, compatibility shim, feature flag, or
  warning-only mode.
- No broadening of e2e Playwright behavior.

These are the right anti-scopes. Notably, the proposal does *not*
remove or change `bring-up-local-channel.sh`'s
`bootstrap_pomerium_oidc_application` helper — the host-side helper
that masks blueprint failure. That is correctly anti-scoped: BUG-8
is about *detection* of the masking shape; *removing* the masker is
a separate design question. The validator's detection-without-removal
posture means a failed blueprint will fail loudly rather than be
silently papered over by the helper.

PASS.

### F-8 Diff budget — PASS

Proposal §6 budget: roughly 140–220 lines for the new validator
script and under ~50 lines combined for the three call-site edits.
Plausible:

- Arg parsing + helpers: ~25 lines.
- Pod discovery via CNPG label: ~10 lines.
- psql exec wrapper: ~15 lines.
- 8 assertions × ~10–15 lines each (SQL + name extraction +
  pass/fail message): ~100–120 lines.
- `RESULT:` summary: ~5 lines.

Comes in around 160–180 lines without golf, well within the upper
bound. Call-site edits are each under 10–20 lines:

- `install-flux-for-channel.sh`: one constant + one blocking call
  after `bounce_opal_for_reseed` at line 594 (~10 lines including
  guard).
- `19-web-ui.sh`: one `run_validator` call before line 276 (~5
  lines).
- `validate_web_ui_local.sh`: one runtime-block call gated on
  `STATIC_ONLY=0` (~10–15 lines).

No GitOps manifest churn, no production service code, no
migrations, no Authentik image change. PASS.

## Observations (non-blocking)

1. **Authentik table coupling is durable but not free.** This
   proposal pins to Authentik's internal Django table names
   (`authentik_blueprints_blueprintinstance`,
   `authentik_core_provider`, `authentik_core_propertymapping`,
   the M2M join `authentik_core_provider_property_mappings`, and
   `authentik_core_application`). Authentik historically renames
   internal tables only across major upgrades (the BUG-8 RCA pins
   the project at Authentik 2026.2.2). Worth flagging the validator
   as part of the Authentik upgrade checklist when the channel
   moves off 2026.2.x.

2. **Worker log excerpt for failure context.** Q3 promises that
   failure output includes "recent Authentik worker log lines for
   that blueprint when the row is in a failing state". The
   implementer should bound this excerpt to a small line count
   (~20 lines, scoped via `kubectl logs --since=10m` or `--tail`)
   and to the worker pod selected by label, not the whole
   namespace. An unbounded `kubectl logs` of the worker
   Deployment in a long-running cluster will dump tens of MB,
   which obscures the named-blueprint failure rather than
   debugging it. This is an implementer hygiene point; the
   proposal does not specify the bound, but the spirit of "named,
   focused failure message" requires it.

3. **CNPG primary failover during validator run.** The label
   `cnpg.io/cluster=authentik-postgres,role=primary` resolves to
   whichever pod the operator currently labels primary. During an
   in-flight failover this label is briefly absent or transitions.
   Risk is low (failovers are seconds), but the implementer
   should fail fast with a clear message
   (`die "could not resolve authentik-postgres primary pod"`)
   rather than retry forever. The existing
   `wait_for_rollout`/`die` patterns in the script family are the
   right model.

4. **Double-invocation in the e2e flow is acceptable.** With both
   Q5(2) and Q5(3) call sites in place, the blueprint validator
   runs twice during a single e2e test 19 invocation (once
   directly from `19-web-ui.sh` before Playwright, once
   transitively via `validate_web_ui_local.sh`'s runtime proof).
   Both invocations are read-only SQL; cost is on the order of
   one extra `kubectl exec` and a few SELECTs, which is
   negligible. The proposal could collapse these to a single call
   by removing one of the call sites, but the redundancy buys
   "validate-web-ui can be run standalone and still proves the
   blueprint contract", which is the stated reason for Q5(3).
   Keep both.

5. **The reseed call site does not validate post-Flux-resume
   state.** Documented in F-5. The validator is a generic local
   gate; an operator who reseeded a blueprint change should
   manually rerun it (or run e2e test 19) after `kubectl patch
   kustomization … suspend:false`. The proposal §4 TG-3 implicitly
   captures this by stating "the reseed still renders and seeds
   the local GitOps snapshot" — i.e. the reseed produces the
   GitOps state, and the validator confirms current Authentik
   state, which are different things in this branch.

## Acceptance check (proposed)

When implementation lands, all of the following must hold:

- `infra/tests/validate_authentik_blueprints_local.sh` exists,
  follows the local validator pattern (pass/fail/skip helpers,
  `RESULT: pass=… fail=… skip=…` summary, `--kubeconfig` arg),
  runs read-only SQL only, and exits zero on success / non-zero on
  any blocking assertion fail.
- The validator selects the CNPG primary pod by label
  `cnpg.io/cluster=authentik-postgres,role=primary` in namespace
  `auth-system`, container `postgres`, database `authentik`. No
  hardcoded pod suffix (F-2).
- The validator queries the four named tables —
  `authentik_blueprints_blueprintinstance`,
  `authentik_core_provider`,
  `authentik_core_provider_property_mappings`,
  `authentik_core_propertymapping` — plus
  `authentik_core_application` for assertion 8 (F-1).
- All eight blocking assertions from §2 Q4 are present, and
  failures name the specific blueprint, provider, missing mapping
  by name, and application FK target — not bare counts (F-3, F-4).
- The reseed call site is one blocking
  `validate_authentik_blueprints_local.sh` invocation in
  `reseed_gitserver_only()` immediately after
  `bounce_opal_for_reseed` (line 594 area), with a failure
  message that does not falsely advertise post-Flux-resume
  validation (F-5).
- The e2e call site is one `run_validator` invocation in
  `infra/tests/e2e/tests/19-web-ui.sh` before the existing
  `validate-web-ui` call near line 276 (F-6).
- The `validate_web_ui_local.sh` call site is gated on the
  non-`--static-only` runtime branch (F-6).
- TG-1: validator passes against the current healthy local
  cluster, all eight assertions pass, exit zero, summary line
  reports `fail=0`.
- TG-2: a deliberately corrupted `init-*` blueprint causes
  non-zero exit, names the exact blueprint, and includes
  `status`, `path`, `last_applied_hash`, and a bounded worker log
  excerpt (Observation 2).
- TG-3: the BUG-4/BUG-6 reseed flow with the validator wired up
  exits non-zero and names the specific blueprint or
  provider/mapping when broken; otherwise reaches the manual Flux
  resume guidance with the same final-line shape as today.
- No edits to Authentik image, Authentik Helm values, blueprint
  YAML, `bring-up-local-channel.sh`'s
  `bootstrap_pomerium_oidc_application`, or the Pomerium/web/api
  service code (F-7).
- Diff stays within §6 budget (~160–180 line validator + ~30–40
  lines of call-site edits, script-only).

AUDIT_DONE: plans/risk/bug-8-audit.md
