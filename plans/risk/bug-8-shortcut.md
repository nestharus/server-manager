# BUG-8 — Shortcut risk gate (Authentik blueprint health check)

**Verdict:** LOW

Source: `proposals/26-bug-8-blueprint-health.md`,
`research/39-bug-8-blueprint-health-rca.md`,
`gitops/channels/local/auth/authentik/postgres-cluster.yaml`,
`infra/scripts/bring-up-local-channel.sh` (`bootstrap_pomerium_oidc_application`
at line 511).

## C1 — Real SQL queries (not "trust kubectl describe")

**Pass.**

Q3 (proposal lines 61-94) locks the state-query surface to direct PostgreSQL,
not API parsing or describe-output scraping:

> Lock: query Authentik PostgreSQL directly with `kubectl exec` into the local
> CNPG primary pod and `psql`.
>
> The validator should select the primary pod for
> `Cluster/auth-system/authentik-postgres` by label instead of hard-coding
> `authentik-postgres-1`, then execute `psql` inside the `postgres` container
> against the `authentik` database using the in-cluster application connection
> details.

The pod-selection-by-label clause forecloses the obvious shortcut (hardcode
`authentik-postgres-1`) that would silently break on failover or rebuild —
CNPG renumbers the primary on switchover, so a fixed name is exactly the kind
of "looks right today" code that would re-mask the bug.

The data plane is real DB rows, not derived state:

- assertion 1 (line 99-100): `init-*` instance presence in
  `authentik_blueprints_blueprintinstance`;
- assertion 2 (line 101): `status = 'successful'` on every instance;
- assertion 3 (line 102): non-empty `last_applied_hash`;
- assertions 4-7 (lines 103-112): scope-mapping rows + provider-to-mapping
  bindings;
- assertion 8 (line 113-114): application→provider link.

These are columns on the actual Authentik schema documented in RCA section
"Direct database query" (research lines 209-221: `name`, `status`,
`last_applied_hash`, `path` on `authentik_blueprints_blueprintinstance`), and
RCA "What success looks like" (lines 296-322) names the same provider-and-
mapping rows. The validator query surface matches the failing rows from the
incident, not a proxy.

The proposal also explicitly rejects the alternative shortcut surfaces:

> Use the database rather than the Authentik REST API for BUG-8. The failing
> condition was stored in `authentik_blueprints_blueprintinstance`, and the
> provider-to-scope relation is also database state. A REST validator would
> depend on Authentik server API availability, token plumbing, pagination,
> and the same host-side API route that is not needed to observe this failure.

That rules out the "trust the REST API" shortcut. It also rules out — by
implication — the "trust `kubectl describe authentik`" shortcut: there is no
CRD that exposes per-blueprint `status='error'` at the Kubernetes layer
(RCA "Why failures go silent today", lines 274-294). The only way to assert
the failing condition is to query the row that recorded it.

Failure-output requirements (lines 81-93) are also concrete — `name`, `path`,
`status`, `last_applied_hash`, plus the stored diagnostic context and recent
worker log excerpt for failing rows. That's enough for the operator to act
without bouncing back into the cluster to gather context, which the BUG-8
incident report (RCA lines 27-53) shows was the slow part of diagnosis
("the visible failure emerged much later as authorization denials and e2e
timeout behavior").

## C2 — Validator catches BOTH failure modes

**Pass.**

BUG-8 had two distinct failure surfaces that have to be caught simultaneously
for the validator to actually unmask the bug class:

1. **Blueprint-instance-level failure** — RCA lines 31-49 / 42-49: e.g.,
   `init-127-applicant-discord-oauth` and `init-133B-pomerium-officer-discord`
   recorded as `status='error'` in
   `authentik_blueprints_blueprintinstance` with rolled-back transactions.
2. **Provider-mapping-binding-level failure** — RCA lines 151-170: the
   host-side `bootstrap_pomerium_oidc_application` helper still creates or
   patches a viable `pomerium` OAuth2 provider with only the three default
   scope mappings (`openid`, `email`, `profile`) **even when the officer
   blueprint failed**. Login completes; the custom `discord_user_id` claim is
   silently absent.

Q4 (proposal lines 96-118) covers both:

- Failure mode 1 → assertions 1, 2, 3:
  - Every mounted `init-*` blueprint instance is present in
    `authentik_blueprints_blueprintinstance`.
  - Every `init-*` blueprint has `status = 'successful'`.
  - Every `init-*` blueprint has a non-empty `last_applied_hash`.
- Failure mode 2 → assertions 4, 5, 6, 7, 8:
  - Custom `server-manager-pomerium-discord_user_id` scope mapping exists.
  - Custom `server-manager-applicant-discord_user_id` scope mapping exists.
  - OAuth2 provider `pomerium` has at least the four mappings: default
    `openid`, default `email`, default `profile`, **and**
    `server-manager-pomerium-discord_user_id`.
  - OAuth2 provider `server-manager-applicant` has the corresponding four
    mappings including `server-manager-applicant-discord_user_id`.
  - Authentik application `pomerium` links to OAuth2 provider `pomerium`.

The Q4 closing clause (lines 117-118) is the explicit close on the masking
shortcut:

> Missing custom mappings must fail even if the provider exists and login
> would otherwise work with the three default OIDC mappings.

That is exactly the regression the host-side bootstrap helper produces.
Cross-checked against the live helper at
`infra/scripts/bring-up-local-channel.sh:511-591`: the `provider_payload`
binds only `[scope_openid, scope_email, scope_profile]` (line 589), with no
custom-mapping enrichment. So the masking pathway is a present, code-level
fact today, not a hypothetical — and assertions 4 + 6 will fail closed against
that helper's output if the officer blueprint did not commit.

A naive shortcut variant — assert only the blueprint rows or only the
provider mappings — would let one failure mode leak past the gate. For
example, if the blueprint applied successfully but a future schema change
caused the provider patch to fail to bind the custom mapping, only the
provider-mapping checks would catch that. Conversely, if the host-side
bootstrap were ever extended to bind the custom mapping itself (papering
over a blueprint failure), only the blueprint-instance checks would catch
that. The proposal locks both legs.

## C3 — TG-2 actually inserts a known-bad blueprint and verifies validator fails

**Pass.**

TG-2 (proposal lines 210-224) is structured as:

1. **Trigger:** "Manually corrupt a mounted blueprint in a local test branch
   or temporary cluster state, for example by injecting an invalid Authentik
   model name into one `init-*` blueprint, then reconcile Authentik and run
   the validator."
2. **Acceptance:**
   - the validator exits non-zero;
   - the failure names the exact blueprint, e.g.
     `init-127-applicant-discord-oauth` or
     `init-133B-pomerium-officer-discord`;
   - the failure includes `status`, `path`, `last_applied_hash`, and the
     available apply diagnostic context or worker log excerpt;
   - Playwright is not needed to discover the failure.

That is a real corruption + reconcile + observe-the-fail loop, not a
"validator should fail in this case, trust me" assertion. The corruption
shape ("invalid Authentik model name") is the exact incident from RCA
lines 44-52: `init-127-applicant-discord-oauth` "used an invalid model name
and failed", `init-133B-pomerium-officer-discord` "had the same model issue"
— so TG-2 reproduces the actual bug surface, not an adjacent fault that
would happen to surface a similar error.

The acceptance leaves cover the chain end-to-end:

- *Validator exits non-zero* is the contract for the call sites
  (Q5 lines 120-146) — `install-flux-for-channel.sh`'s reseed flow,
  e2e test 19, and `validate_web_ui_local.sh` all rely on a non-zero exit
  to fail closed; an "exit zero with warnings" shortcut would defeat the
  blocking-gate semantics.
- *Names the exact blueprint* validates the failure-output contract from Q3
  (lines 81-93), not just "something failed" — the BUG-8 incident report
  shows the slow part was identifying *which* blueprint, so an unnamed
  failure would re-create the diagnosis time.
- *Includes status/path/last_applied_hash/diagnostic context* ties the
  failure message to the actual row state, which means a test that reports
  "validator failed but didn't surface enough context" catches a
  gold-plated-error-message shortcut.
- *Playwright not needed* is the negative assertion against the original
  symptom path — the whole point of the validator is to stop relying on
  e2e timeout behavior to discover blueprint failures (RCA lines 39-41:
  "the visible failure emerged much later as authorization denials and
  e2e timeout behavior, specifically the officer queue bootstrap gate
  never reaching the expected row in e2e test 19").

The "for example, by injecting an invalid Authentik model name" framing
gives the implementer freedom to pick the corruption shape, but the
acceptance criteria are concrete enough that any corruption that produces
an Authentik-side `status='error'` would satisfy the test. That's the right
pairing — the trigger is generic (any failing blueprint), the observable
contract is specific.

TG-1 (lines 192-208) covers the inverse direction (a healthy cluster
passes), and TG-3 (lines 226-244) covers the integration into the BUG-4/BUG-6
reseed flow with the same level of named acceptance ("if a blueprint is in
`error` or missing its hash, reseed exits non-zero and names the failed
blueprint; if provider mappings are missing, reseed exits non-zero and names
the provider plus missing mapping names"). Together TG-1/TG-2/TG-3 pin all
three corners of the contract — pass, fail-on-blueprint, fail-on-mapping —
without leaving any of them as "we'll trust the implementation."

## C4 — No "TODO: also check Authentik flows later" stubs

**Pass.**

`grep -in 'TODO|TBD|FIXME|XXX|later|defer' proposals/26-bug-8-blueprint-
health.md` returns no matches. Every assertion in Q4 is committed; no
assertion is parked to a follow-up.

The closest thing to a deferred decision is in Anti-scope (lines 247-265) /
Q3 substrate (lines 181-186):

> Do not change `bring-up-local-channel.sh`'s host-side Pomerium provider
> bootstrap in this proposal. BUG-8 detects the masking behavior; removing
> or changing that helper is a separate design question.

That reads like a "later" stub on first scan, but it is *bounded scope*, not
deferred validator coverage. The masking helper is the *cause* of failure
mode 2 going silent; the BUG-8 fix is to *detect* the resulting state, not
to remove the helper. Assertions 4 + 6 already fail closed when the helper
leaves the provider with only default mappings (regardless of whether the
helper itself is later removed or rewritten). So the gating contract is
complete with the helper unchanged — removing the helper is a separate
engineering question that does not weaken BUG-8's detection.

Other anti-scope clauses (lines 247-265) are also bounding rather than
parking:

- "Do not add a Kubernetes Job or webhook" — rules out option C/D from RCA
  in this scope; the host-side validator is sufficient for the bug class.
- "Do not change the Authentik image, Helm chart version, or runtime
  version" — rules out the upgrade-our-way-out shortcut.
- "Do not modify the blueprint ConfigMap structure beyond adding the
  validator and call sites" — keeps the validator at the observation layer.
- "Do not add a fallback REST API path, compatibility shim, feature flag,
  or warning-only mode" — closes the soften-the-gate shortcut: a
  warning-only mode would let the validator log a problem without exiting
  non-zero, which would re-create the masking behavior at the validator
  layer.
- "Do not broaden the web e2e flow or add new Playwright behavior" — the
  point is to fail *before* Playwright, not to add more Playwright
  coverage.

Each of these is a "do not do this at all in this scope," not a "do this
later." Diff budget (lines 268-284) reinforces that bundling — one new
validator script plus three call-site edits, no follow-up file referenced.

Substrate (lines 148-178) enumerates every change with concrete file paths
and bounded edit shapes (validator script ~140-220 lines; reseed call site
under 20 lines; e2e test 19 under 10 lines; web-UI validator under 20
lines). No "stub here, fill in later" placeholders.

The Q5 invocation list also does not park any call site:

1. `infra/scripts/install-flux-for-channel.sh` — concrete location
   (`reseed_gitserver_only`, after `bounce_opal_for_reseed`), blocking exit.
2. `infra/tests/e2e/tests/19-web-ui.sh` — preflight before Playwright.
3. `infra/tests/validate_web_ui_local.sh` — call from runtime validation,
   skip under `--static-only`.

All three are wired in the same proposal; none are gated behind "we'll
also do this in a future PR."

## Findings worth carrying into implementation

Not blockers — verdict is LOW — but the implementer should preserve:

1. **Pod selection by label, not by ordinal name.** Q3 says "select the
   primary pod for `Cluster/auth-system/authentik-postgres` by label
   instead of hard-coding `authentik-postgres-1`." The CNPG-canonical label
   is `cnpg.io/cluster=authentik-postgres,role=primary` (or
   `cnpg.io/instanceRole=primary` on newer charts). The validator should
   query both labels (or use `kubectl cnpg status` / the
   `cnpg.io/instanceName` annotation) and fail loudly if zero or more than
   one pod matches, rather than picking the first match silently — a
   silent pick would mask a failover-in-progress condition that is itself
   diagnostic.

2. **`psql` exit-code propagation.** A naive `kubectl exec ... -- psql -c
   "SELECT ..."` with a single pipe to a count check could swallow `psql`
   errors (auth failure, missing DB, missing table). The validator should
   use `psql -v ON_ERROR_STOP=1` and check both the exec exit code and
   the row count; an "empty result" must be distinguished from "query
   errored." That guards against a future schema rename
   (`authentik_blueprints_blueprintinstance` → some new table) silently
   passing the validator with zero failing rows.

3. **`init-*` discovery source must match the mounted file set, not a
   hardcoded list.** The proposal says assertion 1 covers "every mounted
   `init-*` blueprint instance" — the implementer should derive the
   expected set from `kubectl get cm authentik-init-114-blueprint -n
   auth-system -o jsonpath='{.data}'` (or by listing keys on the
   ConfigMap), not from a hardcoded array of three names. Otherwise a
   future fourth blueprint added to the ConfigMap that fails on apply
   would be missed by an unchanged validator. The query side
   (`SELECT name FROM authentik_blueprints_blueprintinstance WHERE name
   LIKE 'init-%'`) gives Authentik's view; the diff against the
   ConfigMap-data set gives the "missing" case (assertion 1's "is
   present").

4. **Worker-log excerpt extraction.** The Q3 failure-output spec includes
   "recent Authentik worker log lines for that blueprint when the row is
   in a failing state." The implementer should grep the worker pod logs
   for the specific blueprint name with a bounded window (e.g.,
   `kubectl logs -n auth-system deploy/authentik-worker --tail=2000 |
   grep -F "$blueprint_name" | tail -30`). Don't `--tail=-1` against a
   long-running worker — that can produce megabytes of output and make
   the validator output unreadable. Bound the lines and bound the
   grep window.

5. **Reseed-call-site ordering.** Q5.1 says "after `bounce_opal_for_reseed`."
   The implementer should ensure the validator runs *after* the OPAL
   bounce completes (RCA lines 139-148: reseed mode currently waits for
   GitRepository artifact revision and OPAL log signals, then prints the
   manual Flux resume command). The proposal acknowledges in
   RCA "Tradeoffs" that "if Flux remains suspended, Authentik may not
   have applied the updated ConfigMap yet." The implementer should
   either (a) only invoke the validator if a Flux reconcile path is
   wired into reseed by then, or (b) document clearly that reseed's
   validator call assumes blueprint state is current as of the previous
   apply, which is the normal case for `--reseed-gitserver-only` (the
   reseed refreshes git source, not blueprint content). A halfway-state
   call that runs before Authentik has had a chance to apply changed
   blueprint content would produce false negatives.

6. **`--static-only` skip semantics in `validate_web_ui_local.sh`.** Q5.3
   says "Skip the Authentik runtime call under `--static-only`." The
   implementer should skip with a clear `SKIP:` line in the result
   summary (matching the existing pass/fail/skip pattern noted in the
   substrate) — a silent skip would give the operator a false sense of
   coverage when running static-only.

7. **e2e test 19 preflight error path.** Q5.2 says "the new preflight
   should run before the browser OAuth flow so blueprint failures
   surface as named Authentik errors instead of officer queue
   timeouts." The implementer should ensure the preflight failure
   output is captured into the e2e test log and the run aborts before
   Playwright. A preflight that logs but doesn't abort would re-create
   the masking. The existing `run_validator` helper pattern (proposal
   lines 138-141 reference) is the right model.

8. **Provider-mapping assertion must check membership, not equality.**
   Q4 says "OAuth2 provider `pomerium` has **at least** these four
   property mappings" (line 109). The validator should use a set-
   membership check (`{openid, email, profile, server-manager-pomerium-
   discord_user_id} ⊆ provider.property_mappings`), not equality. A
   future addition of a fifth mapping should pass; only the absence of
   a required one should fail. The "at least" wording is intentional and
   the implementer should not tighten it to equality.

## Verdict

LOW. No shortcuts. The proposal:

- Locks the state-query surface to direct PostgreSQL via `kubectl exec` +
  `psql` against `authentik_blueprints_blueprintinstance` and the related
  provider/mapping/application tables, with the primary pod resolved by
  label. Real SQL on the rows where the failing condition is recorded —
  not a `kubectl describe` parse, not a REST-API proxy, not a static
  YAML re-check.
- Q4 commits eight blocking assertions that cover both failure modes
  simultaneously — blueprint instance status (assertions 1-3) and
  provider-mapping bindings including the custom `discord_user_id`
  scope (assertions 4-7) plus the application→provider link (8) — with
  the explicit "missing custom mappings must fail even if login would
  otherwise work" close on the masking shortcut.
- TG-2 reproduces the actual incident shape (invalid Authentik model
  name on a mounted `init-*` blueprint), reconciles, and runs the
  validator with named-output acceptance: non-zero exit, exact blueprint
  name, status/path/last_applied_hash plus diagnostic context, and no
  Playwright dependency. TG-1 and TG-3 pin the pass case and the reseed-
  integration case with similarly concrete acceptance.
- No TODO/TBD/FIXME/later/deferred stubs in the proposal. Anti-scope is
  bounding rather than parking — the host-side
  `bootstrap_pomerium_oidc_application` helper stays in place because
  BUG-8 is a *detection* fix and assertions 4 + 6 close the gate against
  the helper's output regardless of whether the helper is later removed.
  All three call sites (reseed, e2e test 19, web-UI validator) are wired
  in the same proposal with concrete file paths and a bounded diff
  budget.

SHORTCUT_DONE: plans/risk/bug-8-shortcut.md
