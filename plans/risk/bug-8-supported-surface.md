# BUG-8 — Supported-surface risk gate

**Verdict:** LOW

BUG-8 (Authentik blueprint apply failures land silently — the worker
records `status='error'` in `authentik_blueprints_blueprintinstance`,
the failed blueprint transaction is rolled back so the custom
`server-manager-pomerium-discord_user_id` and
`server-manager-applicant-discord_user_id` scope mappings never commit,
yet Pomerium login still succeeds via the host-side
`bootstrap_pomerium_oidc_application` helper which patches a viable
Pomerium provider with only the default `openid`/`email`/`profile`
mappings, so the visible failure surfaces much later as missing
`discord_user_id` claims, officer-queue authorization denials, and an
e2e test 19 timeout — RCA §"Symptom + State", §"The second Pomerium
provider writer", §"Why Failures Go Silent Today") is repaired by
adding a host-side runtime validator
`infra/tests/validate_authentik_blueprints_local.sh` that queries
Authentik PostgreSQL directly via `kubectl exec` into the
`Cluster/auth-system/authentik-postgres` primary, asserts every
mounted `init-*` blueprint reports `status='successful'` with a
non-empty `last_applied_hash`, and asserts both custom Discord scope
mappings exist and are bound to their respective OAuth2 providers
(proposal §2 Q1-Q4); the validator is then invoked from three call
sites — `infra/scripts/install-flux-for-channel.sh` after
`bounce_opal_for_reseed`, `infra/tests/e2e/tests/19-web-ui.sh` before
the Playwright browser flow, and `infra/tests/validate_web_ui_local.sh`
as part of runtime validation when not in `--static-only` mode
(proposal §2 Q5, §3 modified files, §6 diff budget). No Authentik
image change, no Helm chart upgrade, no blueprint YAML edit, no
Pomerium/API/web/Discord-daemon/migration churn, no new env var, no
new flag accompanies this fix (proposal §3 "Unmodified substrate",
§5 anti-scope, §6 diff budget).

## Surfaces touched

### 1. Public API — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| HTTP/gRPC routes exposed by `services/api` | as today | unchanged — proposal §3 "Unmodified substrate": "Do not modify API, web, Discord daemon, migrations, or Pomerium manifests" | none |
| Web/SPA endpoints consumed by `services/web` | as today | unchanged — out of the modified-files list (4 files: 1 new validator + 3 caller scripts, proposal §3 + §6) | none |
| Authentik HTTP API (`/api/v3/...`) | as today | not consumed at all — proposal §2 Q3 explicitly chose direct DB query over the REST API: "Use the database rather than the Authentik REST API for BUG-8. The failing condition was stored in `authentik_blueprints_blueprintinstance`"; no token plumbing, no port-forward, no API call paths added | none |
| Authentik OAuth2 provider OIDC flow (`/application/o/pomerium/`, `/application/o/server-manager-applicant/`) | as today (default mappings always present; custom `discord_user_id` mapping present iff blueprint applied successfully) | unchanged — the validator *observes* this state; it does not write to it. The `pomerium` Authentik provider continues to be created/patched by `bootstrap_pomerium_oidc_application` in `bring-up-local-channel.sh` (proposal §3 "Unmodified substrate": "Do not change `bring-up-local-channel.sh`'s host-side Pomerium provider bootstrap in this proposal"); the new validator only reads `authentik_blueprints_blueprintinstance` and provider/scope-mapping tables | none |
| Pomerium → API authorization probe (`/api/me`, `/api/web/officer/applications`) | currently 401/403 when blueprint failure removes the `discord_user_id` claim from the JWT (RCA §"Symptom + State") | unchanged — same endpoint, same payload, same response semantics; the validator simply *fails earlier* (at reseed/preflight) when the upstream condition that would later produce a 401/403 is already present | none — improved early detection without contract change |
| Authentik Postgres cluster surface (`Cluster/auth-system/authentik-postgres`) | already exists per `gitops/channels/local/auth/authentik/postgres-cluster.yaml` (`Cluster` `name: authentik-postgres`, `namespace: auth-system`); app DB credentials via `Secret/authentik-postgres-app`; primary pod selectable by `cnpg.io/cluster=authentik-postgres,role=primary` label | unchanged — proposal §2 Q3 "select the primary pod for `Cluster/auth-system/authentik-postgres` by label instead of hard-coding `authentik-postgres-1`, then execute `psql` inside the `postgres` container against the `authentik` database using the in-cluster application connection details"; this is an *exec*-based read using the existing pod, container, secret, and database — no Service exposure, NetworkPolicy, or RBAC change | none |

Risk on §1: **none.** Gate criterion 1 (no public API change) holds.
The only externally observable behavior change is that the previously
silent runtime blueprint failure now surfaces as a named, blocking
validator FAIL at reseed and at e2e preflight, restoring an existing
identity-claim contract instead of changing it.

### 2. No env vars or DB migrations

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Authentik container env (`AUTHENTIK_*`, `DISCORD_APPLICANT_*`, `DISCORD_OFFICER_*`, `OIDC_CLIENT_*`, `APPLICANT_OIDC_*`) | populated by `Secret/authentik-config` from the InfisicalSecret template (RCA §"Where the blueprints come from") | unchanged — proposal §3 "Unmodified substrate": "Do not modify Authentik blueprint YAML content as part of this proposal"; §5 anti-scope: "Do not change the Authentik image, Helm chart version, or runtime version" | none |
| Authentik Postgres schema (`authentik_blueprints_blueprintinstance`, `authentik_providers_oauth2_oauth2provider`, `authentik_providers_oauth2_scopemapping`, `authentik_core_application`) | as shipped by Authentik 2026.2.2 (rendered `authentik-2026.2.2.yaml`) | unchanged — the validator only `SELECT`s; proposal §2 Q3 explicitly anchors the queries to the existing tables; §5 anti-scope: "This proposal observes the existing Authentik runtime state; it does not upgrade or patch Authentik" | low — the validator couples to Authentik's internal Postgres schema (RCA §"Direct database query" tradeoff). If a future Authentik upgrade renames `authentik_blueprints_blueprintinstance` or its columns, the validator FAILs loudly with a SQL error rather than masking; the schema-coupling risk is bounded to the validator script and is the documented tradeoff for not standing up an Authentik API client (proposal §2 Q3) |
| Server-manager Postgres schema (`applications`, `members`, `application_messages`, `notification_envelopes`, etc.) | unchanged | unchanged — out of scope; proposal §3 "Unmodified substrate" excludes "migrations" | none |
| New env var added to any script | n/a | none — proposal §6 budget: "No GitOps manifest churn", "No production service code", "No migrations"; the validator accepts `--kubeconfig PATH`, `--channel local`, `-h\|--help` (proposal §2 Q2) but introduces no exported env var; the existing `KUBECONFIG_PATH` and `CHANNEL_ID` resolution in caller scripts is reused | none |
| Alembic migration files (`services/server-manager/migrations/`, `services/api/alembic/`) | unchanged | unchanged — out of the diff budget (validator + 3 caller scripts only) | none |
| Authentik Helm chart values (`gitops/channels/local/auth/authentik/render-values.yaml`) | declares the mounted `authentik-init-114-blueprint` ConfigMap | unchanged — proposal §5 anti-scope: "Do not change the Authentik image, Helm chart version, or runtime version" | none |
| Bootstrap blueprint ConfigMap (`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml`) | contains `init-114-local-users.yaml`, `init-127-applicant-discord-oauth.yaml`, `init-133B-pomerium-officer-discord.yaml` | unchanged — proposal §3 "Do not modify the blueprint ConfigMap structure beyond adding the validator and call sites. The validator checks the mounted `init-*` blueprint contract as it exists today" | none |

Risk on §2: **none** for env vars and migrations (no additions, no
schema edits); **low, intentional** for the implicit Authentik schema
coupling, which is the documented tradeoff (RCA §"Authentik Status
Query Surfaces" + proposal §2 Q3) for choosing direct DB query over a
REST API client. Gate criterion 2 (no env vars or DB migrations) holds.

### 3. The 3 callers get a NEW failure mode (validator FAIL is now visible) — that's the goal

The fix is *exactly* a tightening of the success contract on three
existing call sites. Each gains the ability to surface a named
blueprint failure that previously went silent. The proposal commits
to this explicitly:

> "The call should be blocking. A failed blueprint validator exits
> the reseed script non-zero."
> — proposal §2 Q5 #1

> "Run the validator before the Playwright browser flow … the new
> preflight should run before the browser OAuth flow so blueprint
> failures surface as named Authentik errors instead of officer
> queue timeouts."
> — proposal §2 Q5 #2

> "Call the Authentik blueprint validator as part of runtime proof
> when not in `--static-only` mode."
> — proposal §2 Q5 #3

| Caller | Pre — silent failure path | Post — visible failure path | Site of new call |
|---|---|---|---|
| `infra/scripts/install-flux-for-channel.sh` (BUG-4/BUG-6 reseed) | `reseed_gitserver_only()` (lines 588-600) runs `render_local_snapshot` → `ensure_git_daemon_for_reseed` → `seed_git_daemon` → `apply_source_crs` → `wait_for_source_revision` → `bounce_opal_for_reseed` and exits 0 once GitRepository confirms artifact + OPAL Server logs "Clone succeeded" + OPAL Client logs "Fetched valid bundle" — **no observation of Authentik blueprint state** (RCA §"Existing Health Checks": "No existing bootstrap health check queries blueprint status") | exits non-zero with the failed `init-*` blueprint name, `status`, `path`, `last_applied_hash`, and apply diagnostic context whenever the validator detects a failed blueprint or missing custom mapping (proposal §2 Q5 #1, §4 TG-3 acceptance: "if a blueprint is in `error` or missing its hash, reseed exits non-zero and names the failed blueprint; if provider mappings are missing, reseed exits non-zero and names the provider plus missing mapping names") | one new line in `reseed_gitserver_only()` immediately after `bounce_opal_for_reseed` (proposal §3 modified files, ≤20-line budget) |
| `infra/tests/e2e/tests/19-web-ui.sh` (Playwright e2e test 19) | invokes `run_validator validate-web-ui infra/tests/validate_web_ui_local.sh ... --skip-image-build` at line 276 then proceeds to `seed-chapter-fixture.mjs`, `seed-authority-grants.mjs`, `grant_officer_message_authority`, and `run-browser-flow.sh web-ui` — **a missing `discord_user_id` claim manifests as `assert_officer_review_persisted` mismatch or Playwright timeout long after the browser opened** (RCA §"Symptom + State" #6: "the symptom appears as queue gate failure, authorization denial, or a browser e2e timeout rather than as 'blueprint failed.'") | invokes the new blueprint validator as a named preflight before the Playwright run; a blueprint or mapping failure exits the e2e step non-zero with the blueprint/provider name *before* the browser starts, eliminating the multi-minute Playwright timeout as the user-visible failure mode (proposal §2 Q5 #2, §4 TG-2 acceptance: "Playwright is not needed to discover the failure") | one new preflight call ahead of the existing `run_validator validate-web-ui` line and the `run-browser-flow.sh` invocation (proposal §3 modified files, ≤10-line budget) |
| `infra/tests/validate_web_ui_local.sh` (web-UI runtime validator) | `assert_runtime` (lines 236-297) checks Pod Ready, public route 200, admin route requires-auth — **does not prove the source of the `discord_user_id` claim it depends on**; the static-only path skips this validator branch entirely (proposal §2 Q5 #3 rationale; line 237) | calls the new Authentik blueprint validator from runtime validation; skipped under `--static-only` so the existing static-only contract is preserved (proposal §2 Q5 #3: "Skip the Authentik runtime call under `--static-only`") | one new call inside `assert_runtime` (or a sibling runtime helper) gated by the existing `STATIC_ONLY` flag at line 8/237 (proposal §3 modified files, ≤20-line budget) |

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Exit-code contract for `bring-up-local-channel.sh --reseed-gitserver-only` | 0 once Flux confirms the new artifact and OPAL has fetched a fresh bundle, even if the Authentik blueprint that drove the reseed is in `error` (the bug condition itself) | 0 only after Flux + OPAL succeed *and* every mounted `init-*` blueprint reports `status='successful'` with a non-empty `last_applied_hash` *and* both custom `discord_user_id` scope mappings are bound to their providers; non-zero with a named blueprint or provider+mapping otherwise | low — this is a contract tightening; any external tooling that previously treated reseed exit 0 as "GitOps source updated AND OPAL recovered" must now also tolerate exit non-zero meaning "GitOps source updated AND OPAL recovered, but Authentik blueprint apply failed." This change is *intentional* (proposal §1 problem statement, §4 TG-3) and is the deliverable of this bug |
| Exit-code contract for e2e test 19 (`run_e2e_test 19-web-ui`) | non-zero when Playwright/`assert_*_persisted` fails (delayed) | non-zero earlier with a named Authentik error when blueprint runtime state is invalid (preflight) | none — strictly earlier-failure contract; total set of failing scenarios is unchanged |
| Exit-code contract for `validate_web_ui_local.sh` non-static-only run | exits 1 only when web-runtime checks fail | exits 1 when web-runtime checks fail *or* when Authentik blueprint runtime state is invalid; `--static-only` runs are unchanged (proposal §2 Q5 #3) | none — `--static-only` callers (existing fast-path users) see no behavior change; non-static callers see a strictly tighter contract that matches the stated runtime proof |

Risk on §3: **none** for the gate criterion (the entire point of the
fix is to *introduce* the new failure mode at three call sites);
**low, intentional** for the exit-code tightening on the reseed and
non-static `validate_web_ui_local.sh` paths, which is the documented
behavior change. Gate criterion 3 (the 3 callers get a new visible
failure mode) holds.

### 4. Validator failure is loud, not silent

The proposal commits to **fail-loud** semantics with named blueprint
identifiers, structured diagnostic output, and bounded-wait failure
messages. Silent success on a blueprint failure is explicitly
disallowed.

> "Failure output must include: blueprint `name`; blueprint `path`;
> `status`; `last_applied_hash`; the stored diagnostic
> context/content available on the blueprint instance row, and recent
> Authentik worker log lines for that blueprint when the row is in a
> failing state."
> — proposal §2 Q3

> "Missing custom mappings must fail even if the provider exists and
> login would otherwise work with the three default OIDC mappings."
> — proposal §2 Q4

> "Do not add a fallback REST API path, compatibility shim, feature
> flag, or warning-only mode. The selected health gate is direct
> database validation, and failures should fail the calling script."
> — proposal §5 anti-scope

> "Emit failure messages that name the failed blueprint or provider
> and list missing mappings."
> — proposal §3 (validator implementation requirements)

| Failure mode | Pre (today) | Post (proposed) | How it's surfaced |
|---|---|---|---|
| Mounted `init-*` blueprint missing from `authentik_blueprints_blueprintinstance` (e.g., worker never discovered the file) | masked behind reseed/e2e exit 0 (RCA §"Why Failures Go Silent Today") | validator exits non-zero naming the missing blueprint and the expected mounted path | non-zero exit + named blueprint |
| Mounted `init-*` blueprint present but `status` is `error`/unapplied (e.g., wrong model name, schema-incompatible field) | masked — Pomerium login still works via host-side helper with default mappings only (RCA §"The second Pomerium provider writer") | validator exits non-zero with blueprint `name`, `path`, `status`, `last_applied_hash`, and the row's diagnostic context plus worker log excerpt for that blueprint | non-zero exit + structured blueprint diagnostics |
| Blueprint applied but `last_applied_hash` is empty (e.g., partial apply, transaction rolled back) | masked behind exit 0 | validator exits non-zero naming the blueprint and reporting the empty hash | non-zero exit + named blueprint |
| Custom scope mapping `server-manager-pomerium-discord_user_id` missing | masked — Pomerium provider still has default `openid`/`email`/`profile` mappings via `bootstrap_pomerium_oidc_application`, so login completes; downstream `discord_user_id` claim is missing and surfaces as officer-queue 401/403 (RCA §"Symptom + State", §"The second Pomerium provider writer") | validator exits non-zero naming the missing scope mapping and the OAuth2 provider it should be bound to (`pomerium`) | non-zero exit + named provider + named missing mapping |
| Custom scope mapping `server-manager-applicant-discord_user_id` missing | masked behind public-form OAuth flow that may still partially work | validator exits non-zero naming the missing scope mapping and the applicant provider (`server-manager-applicant`) | non-zero exit + named provider + named missing mapping |
| OAuth2 provider `pomerium` exists but is not bound to all 4 expected mappings (default `openid`, default `email`, default `profile`, custom `discord_user_id`) | masked behind successful OIDC login with a subset of mappings | validator exits non-zero listing the provider name and the specific mappings missing from its property-mapping set | non-zero exit + named provider + per-mapping identification |
| OAuth2 provider `server-manager-applicant` not bound to all 4 expected mappings | masked | validator exits non-zero listing the provider name and missing mappings | non-zero exit + named provider + per-mapping identification |
| Authentik application `pomerium` not linked to OAuth2 provider `pomerium` | masked behind partial login flow | validator exits non-zero naming the application/provider link mismatch | non-zero exit + named application + provider link identification |
| Authentik Postgres primary pod absent or not Ready (e.g., during a partial bring-up) | n/a — no validator existed | validator exits non-zero with a clear "primary pod not found" message (proposal §2 Q3: "select the primary pod … by label instead of hard-coding `authentik-postgres-1`"); follows the established `pass`/`fail`/`skip`/`die` style of sibling `validate_*_local.sh` scripts | non-zero exit + named pod-discovery phase |
| Authentik Postgres reachable but `psql` connection fails (e.g., wrong app secret, DB down) | n/a | validator exits non-zero naming the connection failure (existing `pass`/`fail`/`finish`/`die` pattern from sibling validators, e.g., `validate_web_ui_local.sh:45-49`) | non-zero exit + named connection phase |

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Validator pass/fail/skip/result reporting style | n/a (validator is new) | proposal §3 specifies "Follow the pass/fail/skip/result style used by existing local validators" — which `validate_web_ui_local.sh:26-43` defines as `pass()`/`fail()`/`skip()`/`finish()` printing `PASS:`/`FAIL:`/`SKIP:`/`RESULT: pass=X fail=Y skip=Z` and `die()` exiting 1 with the failed assertion message | none |
| Exit code on healthy state | n/a | exits 0 after printing `RESULT: pass=N fail=0 skip=M` once all 8 assertions (proposal §2 Q4) pass | none |
| Exit code on failed state | n/a | non-zero with `FAIL:` lines on stderr naming the failing assertion (blueprint name, provider, missing mapping); the standard `die "..."` shell pattern routes to stderr exit 1 | none |
| Re-runnability after a transient pod restart or reseed | n/a | the validator is read-only (`SELECT`-only against Authentik PG); idempotent — re-invocation against a now-healthy Authentik returns 0 | none |
| Wait-boundary for "blueprint not yet applied after Flux apply" (the RCA's Option A wait-boundary concern: "If Flux remains suspended, Authentik may not have applied the updated ConfigMap yet" — RCA §"Add blueprint health check to `reseed_gitserver_only`") | n/a | proposal §2 Q5 #1 places the validator call **after** `bounce_opal_for_reseed`, which itself runs after `wait_for_source_revision "$SEEDED_REVISION_SHA"`; this gives Flux + Authentik a worker-discovery window before the validator queries; if a blueprint is genuinely not yet applied, the validator FAILs with `status` other than `successful` rather than masking, which is the documented fail-loud contract (proposal §5 anti-scope: "Do not add a fallback REST API path, compatibility shim, feature flag, or warning-only mode") | low, intentional — a transient "not yet applied" race would surface as a named blueprint FAIL instead of a silent pass; operators re-running reseed after a successful Authentik worker apply would get a clean 0. This is the documented contract, not an edge case |

Risk on §4: **none** for the gate criterion (validator failures are
fail-loud with named blueprints, providers, and missing mappings, on
the standard `pass`/`fail`/`skip`/`die` pattern). Gate criterion 4
(validator failure is loud, not silent) holds.

### 5. Anti-scope items — explicitly held out

| Surface | Status | Source |
|---|---|---|
| Authentik image / Helm chart version / runtime version change | not modified | proposal §5 anti-scope: "Do not change the Authentik image, Helm chart version, or runtime version" |
| Authentik blueprint YAML edits (`init-114-local-users.yaml`, `init-127-applicant-discord-oauth.yaml`, `init-133B-pomerium-officer-discord.yaml`) | not modified | proposal §3 "Unmodified substrate": "Do not modify Authentik blueprint YAML content as part of this proposal" |
| `bootstrap-blueprint-configmap.yaml` ConfigMap structure | not modified | proposal §3: "Do not modify the blueprint ConfigMap structure beyond adding the validator and call sites" |
| Host-side Pomerium provider bootstrap (`bootstrap_pomerium_oidc_application` in `bring-up-local-channel.sh`) — the masking helper itself | not modified | proposal §3 "Unmodified substrate": "Do not change `bring-up-local-channel.sh`'s host-side Pomerium provider bootstrap in this proposal. BUG-8 detects the masking behavior; removing or changing that helper is a separate design question" |
| API / Discord daemon / web SPA / repository / service / migration code | not modified | proposal §3 "Unmodified substrate": "Do not modify API, web, Discord daemon, migrations, or Pomerium manifests"; §6: "No production service code", "No migrations" |
| Pomerium manifests (`gitops/channels/local/auth/pomerium/...`) | not modified | proposal §3; §6: "No GitOps manifest churn" |
| Kubernetes Job / webhook / event-pipeline integration for blueprint health (RCA Options C, D) | not introduced | proposal §5 anti-scope: "Do not add a Kubernetes Job or webhook. BUG-8 needs a host-side validator that can be invoked from existing scripts and e2e preflight" |
| REST API path / compatibility shim / feature flag / warning-only mode | not introduced | proposal §5 anti-scope: "Do not add a fallback REST API path, compatibility shim, feature flag, or warning-only mode. The selected health gate is direct database validation, and failures should fail the calling script" |
| Broadened Playwright e2e behavior or new browser scenarios | not introduced | proposal §5 anti-scope: "Do not broaden the web e2e flow or add new Playwright behavior. The point is to fail before Playwright when Authentik runtime state is already invalid" |
| Static-only callers (`validate_web_ui_local.sh --static-only`) gaining a runtime dependency on Authentik | held out | proposal §2 Q5 #3: "Skip the Authentik runtime call under `--static-only`" — the existing static-only contract is preserved verbatim |
| New env var, new operator flag (beyond `--kubeconfig`/`--channel`/`-h`), new exported environment | not introduced | proposal §2 Q2 explicitly enumerates the validator's flag set; §6 budget: "No GitOps manifest churn", "No production service code", "No migrations" |
| Deletion or change of the host-side `bootstrap_pomerium_oidc_application` masking behavior | held out — this is a separate design question (proposal §3) | the BUG-8 fix is *detection*, not removal of the masking helper; the validator surfaces the masked failure but does not redesign the bootstrap path |

## Supported-surface findings summary

| Gate | Verdict |
|---|---|
| 1. No public API change | PASS |
| 2. No env vars or DB migrations | PASS |
| 3. The 3 callers (reseed, e2e, validate_web_ui_local) get a NEW failure mode (validator FAIL is now visible) — that's the goal | PASS |
| 4. Validator failure is loud, not silent | PASS |

## Findings

1. **No public API change.** The diff budget is one new shell script
   plus three small caller edits (proposal §6). API/web/Discord-daemon
   HTTP/gRPC contracts, Authentik OAuth2 provider OIDC flows, Pomerium
   routes, and OPAL decision endpoints are all out of scope (proposal
   §3 "Unmodified substrate", §5 anti-scope). The Authentik REST API
   is *not* used (proposal §2 Q3); the validator queries the existing
   `Cluster/auth-system/authentik-postgres` primary via `kubectl exec`
   + `psql` against the `authentik` database, using the `authentik-
   postgres-app` Secret already produced by the CNPG operator
   (`gitops/channels/local/auth/authentik/postgres-cluster.yaml`). The
   only externally observable behavior change is positive: a previously
   silent runtime failure becomes a named, loud FAIL at three existing
   call sites.

2. **No env vars or DB migrations.** The validator introduces no new
   exported environment variable; it accepts only `--kubeconfig PATH`,
   `--channel local`, and `-h|--help` (proposal §2 Q2). No alembic
   migration is added; no Authentik schema is altered (the validator
   is `SELECT`-only). The Authentik container env, Helm values,
   blueprint ConfigMap, and InfisicalSecret template are all
   explicitly held out (proposal §3 + §5). The implicit Authentik
   Postgres schema coupling is the documented tradeoff for choosing
   direct DB query over a REST API client (RCA §"Authentik Status
   Query Surfaces" + proposal §2 Q3); a future Authentik schema
   migration would surface as a loud SQL error in the validator
   rather than as silent masking — i.e., it preserves the fail-loud
   contract.

3. **The 3 callers get a new visible failure mode — by design.** This
   is the deliverable of the bug, not a regression risk. (a)
   `infra/scripts/install-flux-for-channel.sh`'s
   `reseed_gitserver_only()` (lines 588-600) gains one new blocking
   call after `bounce_opal_for_reseed` (line 594); a failed blueprint
   validator now exits the reseed script non-zero with the named
   blueprint, replacing the prior silent exit 0 (proposal §2 Q5 #1,
   §4 TG-3). (b) `infra/tests/e2e/tests/19-web-ui.sh` gains one new
   preflight call ahead of the existing `run_validator validate-web-ui`
   line at 276 and the Playwright `run-browser-flow.sh` invocation at
   290; blueprint failures surface as named Authentik errors rather
   than as `assert_officer_review_persisted` mismatches or browser
   timeouts (proposal §2 Q5 #2). (c)
   `infra/tests/validate_web_ui_local.sh`'s `assert_runtime`
   (lines 236-297) gains one new call gated by the existing
   `STATIC_ONLY=1` flag (line 8); the static-only contract used by
   fast-path callers is preserved verbatim (proposal §2 Q5 #3). All
   three changes tighten the success contract; none widens what is
   accepted as success.

4. **Validator failure is loud, not silent.** The validator follows
   the existing local-validator pass/fail/skip/result style (proposal
   §3, exemplar `validate_web_ui_local.sh:26-49`); it prints `FAIL:
   <blueprint-name>` lines on stderr with the row's `status`, `path`,
   `last_applied_hash`, stored diagnostic context, and recent worker
   log excerpt (proposal §2 Q3); it lists missing scope mappings and
   the OAuth2 provider they should be bound to by name (proposal §2
   Q4); and it enforces all 8 assertions — including missing custom
   mappings even when default OIDC mappings would let login complete
   (proposal §2 Q4 final paragraph). The "fallback REST API path,
   compatibility shim, feature flag, or warning-only mode" is
   explicitly disallowed (proposal §5 anti-scope), so a partial-
   success exit-0 path cannot be reintroduced. The wait-boundary
   concern that the RCA flagged for Option A ("If Flux remains
   suspended, Authentik may not have applied the updated ConfigMap
   yet") is addressed by ordering: the reseed call site runs the
   validator *after* `bounce_opal_for_reseed`, which itself runs
   after `wait_for_source_revision` confirms Flux has the new
   artifact (proposal §2 Q5 #1).

## Out-of-scope items intentionally not addressed

- **Removing the masking host-side `bootstrap_pomerium_oidc_application`
  helper** — proposal §3 "Unmodified substrate" holds this as a
  separate design question. BUG-8 *detects* the masking behavior; it
  does not redesign the bootstrap path. The validator's missing-
  mapping assertion (proposal §2 Q4 #6) is the load-bearing detection
  for the masking failure mode.

- **Authentik REST API client / token plumbing** — discussed and
  discarded (RCA §"Authentik REST API"; proposal §2 Q3). The failing
  condition is in `authentik_blueprints_blueprintinstance` and the
  provider/scope-mapping relations; direct DB query is the simplest
  factual signal and avoids token plumbing, pagination, and Authentik
  API availability dependencies.

- **`ak shell` worker-exec validator** — discussed and discarded (RCA
  §"`ak shell` inside the worker"). Operationally awkward and less
  portable than the chosen `kubectl exec` + `psql` pattern, which
  matches existing in-cluster Postgres-exec idioms used by e2e test 19
  itself (`19-web-ui.sh:21,57,117`).

- **Kubernetes Job / webhook / event-pipeline integration** — RCA
  Options C and D, both held out by proposal §5 anti-scope. A host-
  side validator is the right unit for BUG-8 because the same failure
  can appear after fresh bootstrap, local e2e setup, or manual
  diagnosis — three host-side surfaces.

- **Authentik image / chart upgrade** — proposal §5 anti-scope. The
  proposal observes the *existing* Authentik runtime state.

- **Blueprint YAML edits** — proposal §3 "Unmodified substrate". The
  validator checks the mounted `init-*` contract as it exists today;
  fixing a future blueprint apply error is a separate change.

- **Documentation churn** — proposal §6 budget caps the change at the
  validator script and three caller edits. The flag set on each
  caller script is unchanged (the validator's flags are internal to
  the new file). No external operator docs land in this fix.

## Verdict

**LOW** — the fix is a new, read-only host-side validator
(`infra/tests/validate_authentik_blueprints_local.sh`) wired into
three existing call sites: `install-flux-for-channel.sh`'s
`reseed_gitserver_only()` after `bounce_opal_for_reseed`,
`19-web-ui.sh` ahead of the Playwright browser flow, and
`validate_web_ui_local.sh`'s runtime path (skipped under
`--static-only`). It changes no public API, no Authentik image, no
Helm chart, no blueprint YAML, no Pomerium manifest, no API/web/
Discord-daemon/migration code, no env var, no operator flag, and no
GitOps manifest. The Authentik Postgres surface
(`Cluster/auth-system/authentik-postgres`, `Secret/authentik-
postgres-app`, the `authentik` database, the
`authentik_blueprints_blueprintinstance` /
`authentik_providers_oauth2_*` / `authentik_core_application` tables)
is consumed read-only via `kubectl exec` + `psql` using the existing
in-cluster CNPG primary, mirroring the exec-based DB pattern already
established in `19-web-ui.sh`. The failure-mode contract is
documented as fail-loud with named blueprints, providers, and missing
mappings, on the standard `pass`/`fail`/`skip`/`die` pattern from
sibling `validate_*_local.sh` scripts; the "fallback / warning-only
mode" path is explicitly disallowed (proposal §5 anti-scope). The
only behavior change for external tooling is the *intentional*
exit-code tightening at the three call sites — which is the
deliverable of this bug. All four supported-surface gates pass.

SUPPORTED_SURFACE_DONE: plans/risk/bug-8-supported-surface.md
