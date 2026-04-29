READ:
- proposals/04-public-intake-form-seed.md
- research/06-public-intake-form-seed-problem-map.md
- .tmp/rca/public-intake-form-seed-FINDINGS.md
- ~/ai/workflows/implementation-pipeline.md
- ~/ai/conventions/no-backwards-compatibility.md
- ~/ai/conventions/no-deferred-stubs.md
- plans/risk/init-121-shortcut.md
- plans/risk/init-120-shortcut.md

# INIT-122 Phase 4 — Shortcut Risk Report

## Inputs read

- `proposals/04-public-intake-form-seed.md` (full file)
- `research/06-public-intake-form-seed-problem-map.md` (full file)
- `.tmp/rca/public-intake-form-seed-FINDINGS.md` (full file)
- Pipeline rules (Phase 4 shortcut-risk role) and the no-backwards-compatibility / no-deferred-stubs conventions
- Predecessor shortcut-risk reports (`init-120-shortcut.md`, `init-121-shortcut.md`) for verdict-format and tone

## Root-cause fix vs. relocation

The RCA names the root cause as: INIT-120 made `/api/v1/public/applications` a
supported public submit surface whose day-1 payload targets global scope, but
no durable local-channel bootstrap step creates the required current global
`form_definitions` record, and the only tests exercising the service layer
satisfy the precondition through test-local fixtures rather than the same
fresh-bringup path used by `humility-local`
(`.tmp/rca/public-intake-form-seed-FINDINGS.md:78`). RCA H6 explicitly ruled
out reusing the existing test fixture SQL because it omits the
`application_form|global|` aggregate head and would leave
`get_current_form_for_scope()` 404ing even after public submit recovers.

The proposal fixes the root cause rather than relocating it:

- The seed runs in the local cohort that actually exhibits the failure.
  `gitops/channels/local/applications/server-manager/` is the same surface
  that already runs the Alembic and bucket Jobs
  (`proposals/04-public-intake-form-seed.md:39-41`). The fix lives where the
  bringup happens, not in a test harness that bypasses it.
- The SQL writes BOTH the projection row (`form_definitions`) AND the full
  mutation substrate (`activity_actions`, `activity_state_changes`,
  `aggregate_heads`) in one transaction
  (`proposals/04-public-intake-form-seed.md:184-307`). This is the precise
  gap RCA H6 named — the prior workaround inserted only the projection.
  Both the public-submit raw-fallback query in
  `_get_current_form_for_submit()` and the canonical
  `get_current_form_for_scope()` join become consistent after the seed.
- The proposal does not relocate the failure into the test harness. RCA H3
  (fixture-loader) was POSSIBLE-only-if-product-is-test-only; the proposal
  rejects that framing and seeds the cluster runtime path. The component
  fixture `seed_global_public_application_form()` is left untouched as a
  test-only construct, not promoted to production source of truth.
- The proposal does not relocate into Alembic. RCA's locked direction
  preferred a separate Job; the proposal carries that forward (Q1) so
  schema lifecycle is not coupled to channel-specific operational content.
- The fresh-bringup probe (`infra/tests/e2e/tests/19-web-ui.sh`) is named
  as the e2e signal that the original BL-002 failure is closed
  (`proposals/04-public-intake-form-seed.md:380`). That is the same probe
  the RCA recommended in §Test-intent surface, so the test pressure lands
  on the actual user-reachable path rather than a stub.

Verdict on this question: the design fixes the RCA's named root cause and
addresses the specific completeness gap (aggregate-head consistency) that
ruled out the simpler alternative.

## Implementation choices serve purpose

### Q1 — Separate Job vs. Alembic-coupled

Proposal: a separate local GitOps one-shot Job, not an Alembic seed migration
(`proposals/04-public-intake-form-seed.md:60`).

- Purpose served: schema migrations apply to every database, including
  remote channels that do not yet host application workloads
  (`research/06-public-intake-form-seed-problem-map.md:94`). Coupling the
  global form to Alembic would silently push channel-specific operational
  content to deployments where the public-intake surface is not even
  exposed yet (BL-013 remote).
- Reversibility: a Job can be added/removed via Kustomization edit; an
  Alembic seed needs a downgrade, and the proposal's rollback section
  honestly documents why a downgrade hook is not the right shape because
  `applications.form_definition_id` is `ON DELETE RESTRICT`
  (`proposals/04-public-intake-form-seed.md:391`). Coupling to Alembic
  would have made this restriction pollute every migration cycle.
- Honesty: existing migration seed patterns (read-models, SLA triggers)
  intentionally keep their service grants on downgrade
  (`research/06-public-intake-form-seed-problem-map.md:71`). A form-content
  seed does not match that "operational reference data, never removed"
  pattern — form content is channel/product configuration that may evolve
  with officer authoring. The proposal correctly does not extend the
  migration-seed pattern to a domain it does not fit.
- Risk: LOW. The choice serves the cohort scoping and does not couple
  unrelated lifecycles.

### Q2 — Direct SQL vs. API publish

Proposal: direct SQL, with the seed writing both `form_definitions` and the
`application_form|global|` aggregate substrate in one transaction
(`proposals/04-public-intake-form-seed.md:61`, design at lines 99-307).

- Purpose served: the API publish path requires actor headers and an active
  DB authority grant for `application_form.publish`
  (`research/06-public-intake-form-seed-problem-map.md:100`). Routing the
  seed through the API would force the proposal to add a service-actor
  authority grant (and, optionally, Cedar surface) just to bootstrap, and
  that grant would persist as a live writer authority after the bootstrap
  succeeds. Direct SQL avoids creating a long-lived "anyone with
  Postgres credentials can publish forms via API" identity.
- Honesty about the cost: the proposal explicitly acknowledges that direct
  SQL "must write the projection and mutation substrate together because
  `get_current_form_for_scope()` joins `form_definitions` to
  `aggregate_heads`" (line 61). That is exactly the H6 failure mode the
  RCA ruled out. The SQL design enumerates the four required row shapes
  (lines 347-350) and structures them as a single transaction with
  `FOR UPDATE` on the relevant probe rows.
- Audit substrate fidelity: the seed inserts an `activity_actions` row
  (`action_type='form.publish'`, `status='accepted'`,
  `actor_kind='service'`, `actor_id='public-intake-seed'`,
  `request_surface='gitops:local/server-manager/seed-public-intake-form'`,
  `reason_text='init-122 public-intake form seed'`) and an
  `activity_state_changes` row whose `payload_json` mirrors the publish
  payload shape from `services/api/app/services/forms.py`
  (`proposals/04-public-intake-form-seed.md:347-350`). The seed
  identifies itself in the audit trail rather than impersonating the
  public-submit service identity, so post-incident review can distinguish
  seeded state from officer-published state.
- Drift residual: future changes to `mutate_entity()`'s row shape would
  not automatically propagate to the seed SQL. The proposal does not
  hand-wave this — it pins the observable behavior contract and lets
  Step 6c factor the SQL for maintainability while preserving the
  contract (line 343). Acceptable as a localized residual.
- Risk: LOW. The choice serves the "do not add a long-lived authority"
  purpose, and the proposal carries the consequence (full substrate
  write) honestly rather than papering over it.

### Q3 — Inline ConfigMap vs. YAML file

Proposal: keep the seed payload inline in a ConfigMap mounted by the Job;
Postgres remains the runtime source of truth
(`proposals/04-public-intake-form-seed.md:62`).

- Purpose served: v1 strategy explicitly says forms are versioned in
  Postgres and YAML/JSON attachments are import artifacts, not runtime
  source of truth (RCA H5). A separate `forms/`-style YAML consumed at
  runtime would re-create the import-vs-runtime ambiguity that
  `services/api/tests/test_application_boundaries.py` already guards
  against. Inline ConfigMap keeps the bootstrap content self-contained
  and visible inside the GitOps surface, where operators read other
  Job-mounted configuration.
- Anti-scope honesty: the proposal anti-scope explicitly forbids
  "YAML `forms/` runtime source of truth" (line 54) and forbids
  "Importing or reconciling `forms/dark-nemesis.yaml` into the runtime
  database" (line 400). The Q3 choice is consistent with both.
- Diffability concern: a separate YAML would be easier to diff in PR
  review, but the seed payload is two fields and a routing-rule object —
  small enough that ConfigMap inline diff is comparable. The cost of a
  separate YAML (a second authoring surface inside the repo) outweighs
  the diff convenience.
- Risk: LOW. The choice serves the "Postgres is the runtime source"
  invariant and avoids manufacturing a competing source.

### Q4 — Idempotency rule

Proposal: insert only when no current global form exists; no-op when the
deterministic seed row already exists; skip when any different current
global form exists; emit a WARNING when the seed row exists but its content
has drifted (`proposals/04-public-intake-form-seed.md:63`, SQL at lines
308-338).

- Purpose served: the rule protects officer-published state from being
  silently overwritten by a Job rerun (assumption A4) and prevents
  duplicate-current rows that would violate
  `ux_form_definitions__current_per_scope`
  (`research/06-public-intake-form-seed-problem-map.md:68`). The
  deterministic UUID derived from `sha256("init-122:public-intake-global:v1")`
  ensures the same row identity across reruns, so the "seed already
  present" case is detectable without a content-hash collision risk.
- Honesty about non-mutating outcomes: every non-insert path exits 0
  without modifying state. That makes the Job rerun-safe but does mean a
  successful Job exit does not by itself prove the public-intake gap is
  closed. The proposal compensates by emitting a discriminating
  `seed_outcome` log line for each path (lines 359), so post-bringup
  observability can distinguish "inserted", "no-op", "skipped (officer)",
  and "warned (drift)". Honest, but log retention is a residual the
  proposal acknowledges in the test-intent track ("Warning visibility
  depends on log collection retention").
- Material gap — fail-closed prose vs. SQL ELSE branch: the design prose
  says "If the implementation detects an existing aggregate head without
  a current global form and without the seed row, it should fail closed
  rather than invent a version rewrite in this seed slice" (line 343).
  Assumption A5 names the same condition: "a database state has an
  existing `application_form|global|` head but no current form or seed
  row, which should fail closed and return to research rather than
  guessing a repair" (line 367). However, the SQL CASE statement at
  lines 308-338 maps this case to the ELSE branch:
  `'WARNING: seed made no change and found no current form'` and then
  COMMITs successfully. The SQL does not actively probe for the
  "head-exists-without-seed-or-current" condition and does not raise.
  This is a real prose-vs-implementation discrepancy and a candidate
  shortcut: it allows the Job to silently exit 0 when the precondition
  cannot be safely repaired. Closing this is low cost in Step 6c — add
  an explicit probe and `RAISE EXCEPTION` when the impossible state is
  detected. It is named here so Step 6a contract definition can pin it
  before Step 6b writes tests.
- Drift behavior: when the deterministic seed row exists with mutated
  content, the seed emits WARNING and makes no mutation. This protects
  against the seed-rerun-overwrites-manual-edit case but does mean
  drift can persist silently if logs are not collected. The
  drift-warning test (`Drift warning test` in the proposal test-intent
  track) catches the no-mutation property at component level; the
  visibility residual is honestly documented.
- Risk: LOW with one named Step-6c-actionable gap (the ELSE-vs-fail-closed
  discrepancy). Not a verdict-changing finding because the prose contract
  is correct and the SQL fix is mechanical; flagged so the contract
  definition step pins it.

## Aggregate head consistency

The seed writes the four-row shape required for both the canonical
repository lookup and the raw fallback query to behave consistently
(`proposals/04-public-intake-form-seed.md:347-350`):

- `form_definitions` row with the deterministic UUID, `scope_kind='global'`,
  `scope_id=NULL`, `version=1`, `status='current'`, two-field `fields`
  jsonb, global `routing_rules`, and `published_by_kind='service'`,
  `published_by_id='public-intake-seed'`.
- `activity_actions` row tying the seed event to `aggregate_type='application_form'`,
  `aggregate_id='application_form|global|'`, `action_type='form.publish'`,
  `status='accepted'`.
- `activity_state_changes` row at `aggregate_seq=1` with `change_type='form.published'`,
  payload mirroring `services/api/app/services/forms.py` publish payload
  fields, and a diff_json of `{version: null->1, status: null->current}`.
- `aggregate_heads` row at `current_seq=1` with `latest_change_id` linked
  to the inserted state change.

Cross-checking against the consuming code:

- `services/api/app/repositories/forms.py` `get_current_form_for_scope()`
  joins `form_definitions` to `aggregate_heads` on
  `aggregate_id='application_form|{scope_kind}|{scope_id or ""}'`
  (`research/06-public-intake-form-seed-problem-map.md:48`). The seed's
  aggregate id `application_form|global|` matches the canonical key shape
  exactly.
- `services/api/app/services/applications.py` `_get_current_form_for_submit()`
  prefers the repository lookup and falls back to a raw projection query
  (`research/06-public-intake-form-seed-problem-map.md:66`). With the seed
  writing both shapes, the canonical path succeeds and the fallback
  becomes redundant rather than load-bearing.
- `migrations/versions/wu-021_forms.py` enforces one current row per
  `(scope_kind, scope_id)` with NULL-equality. The seed inserts a single
  current global row; reruns are guarded by the `current_global` and
  `existing_seed` CTEs. No double-current risk.
- `migrations/versions/wu-002_activity_substrate.py` requires non-null
  actor fields. The seed populates `actor_kind`, `actor_id`,
  `correlation_id`, `request_surface`. No null-violation risk.

Aggregate head consistency is the strongest single property of the
proposal: it is the precise property RCA H6 said the prior workaround
lacked, and the SQL design enumerates each row that must exist rather
than waving at "plus the audit substrate". Risk: LOW.

## Replace-vs-skip officer-published forms

The rule is: when a current global form exists whose id differs from the
deterministic seed UUID, the seed exits 0 and logs `officer-published form
present; skipping seed` (`proposals/04-public-intake-form-seed.md:328`).
No mutation, no archive, no version rewrite of the officer's row.

Honesty checks:

- The skip is unconditional with respect to officer content shape — the
  seed does not try to detect "officer's form is broken, so I should
  override it". That is the right boundary: officer publication semantics
  belong to the authoring API, not to a bootstrap Job.
- The skip case path: when the officer-published form coexists with an
  archived seed row (e.g., officer published, archiving the seed),
  `existing_seed` matches by id and `current_global` matches a different
  id. Both branches are reachable. The CASE precedence at lines 308-338
  evaluates the officer-present branch before the existing-seed-no-op
  branch, so the operator-visible outcome is the more informative
  "officer-published form present; skipping seed" rather than "seed
  already present; no-op". That ordering matches the expected operator
  mental model.
- Aggregate head divergence: if the officer published their form via the
  authenticated API, the `application_form|global|` aggregate head
  current_seq advanced past 1. The seed never tries to mutate that head
  on the skip path, so optimistic-locking invariants are preserved.
- Reapply after rollback: the proposal's rollback documents that
  reapplying after officer publication "logs the officer-published skip
  and exits 0" (line 393). That is the right rerun shape.
- Pseudo-officer concern: a sufficiently malicious operator could
  manually insert a `form_definitions` row whose id collides with the
  deterministic seed UUID. SHA-256 truncated to 16 bytes makes accidental
  collision astronomically unlikely; deliberate collision requires direct
  DB write authority, in which case the operator has already bypassed
  the seed Job by definition.

The replace-vs-skip rule is honest about what it does and does not own.
The seed's job is to ensure a working public form exists when none does,
not to police the operator's form content. Risk: LOW.

## Anti-scope deferrals — BL-013 remote and BL-010 chapter scope

Both deferrals are named with backlog work-unit IDs, satisfying the
no-deferred-stubs convention's "name the follow-up work unit"
requirement.

### BL-013 remote channel apply

- Deferral evidence: `proposals/04-public-intake-form-seed.md:53` and
  supported-surface track at line 354 explicitly say "Remote channel
  apply is deferred to BL-013 and must not be introduced by this slice."
- Honesty for this cohort: `infra/channels/dev.yaml` does not yet host
  application workloads; remote application GitOps does not exist for
  the seed to break or skip
  (`research/06-public-intake-form-seed-problem-map.md:94`). The
  deferral is honest because there is nothing on the remote channel
  for this proposal to skip — the dependency runs the other way (BL-013
  needs to materialize remote application workloads first).
- Channel-template consistency: the seed lives under
  `gitops/channels/local/applications/server-manager/`, which is the
  channel-aware path remote channels would mirror once BL-013 lands. No
  channel-template anti-pattern is introduced.

### BL-010 chapter scope

- Deferral evidence: `proposals/04-public-intake-form-seed.md:397`
  ("Extending the seed to chapter scope or chapter-specific application
  forms; that belongs to BL-010 territory.").
- Honesty for the day-1 contract: INIT-120's day-1 web payload uses
  global scope only because the public web fixture has no chapter
  selector (`infra/tests/fixtures/web-ui/contract.json`,
  `research/06-public-intake-form-seed-problem-map.md:55`). A
  chapter-scope seed is therefore not required to make the public-intake
  surface functional; chapter scope only matters when the SPA gains a
  chapter selector or when Discord submission targets chapter scope
  (which already works against existing chapter-scoped form authoring).
- No skipped behavior: deferring chapter scope does not leave any
  currently-supported user-reachable path broken. Discord submission
  remains adjacent and unaffected (problem map line 60).

Both deferrals are honest because each names a real follow-up work unit
and identifies the missing precondition (remote application GitOps;
chapter selector in the SPA) that the deferred work itself must address.
Risk: LOW.

## Notable observations

- The proposal correctly inverts the test surface from the INIT-120
  residual: the prior R4 workaround (manual SQL) proved only that the
  service layer could submit if the projection existed. The seed test
  matrix (rendered GitOps, fresh-DB seed, idempotency rerun, officer
  skip, drift warning, e2e fresh bringup) exercises the actual
  fresh-bringup path that BL-002 names as broken.
- The proposal preserves the v1 invariant that Postgres is the runtime
  source of truth for form definitions. Inline ConfigMap content is the
  bootstrap input, not a runtime read. `services/api/tests/test_application_boundaries.py`'s
  guard against importing legacy form YAML remains untouched.
- The seed actor identity (`public-intake-seed`) is deliberately distinct
  from the public-submit service actor (`public-intake`), so audit-trail
  consumers can distinguish bootstrap state from real submissions
  without parsing `request_surface` strings. Honest disambiguation
  rather than impersonation.
- Migration-rollback honesty: the proposal documents that database
  rollback is not automatic and explains why
  (`applications.form_definition_id` is `ON DELETE RESTRICT`,
  `migrations/versions/wu-022_applications.py`). It does not promise a
  clean reversible path it cannot deliver.
- The single material Step-6c-actionable gap is the prose-vs-SQL
  discrepancy in the impossible-state branch (Q4 above). Contract
  definition in Step 6a should pin "fail closed when aggregate head
  exists without seed row and without current global form" so Step 6b
  can encode a test for it before Step 6c writes the SQL.

## Verdict

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```

The proposal addresses the RCA's named root cause directly (closes the
fresh-bringup public-intake gap by writing both projection and aggregate
substrate), each Q-decision serves the underlying purpose (cohort scoping,
no long-lived seed authority, single runtime source of truth, rerun-safe
idempotency), aggregate head consistency is the precise completeness gap
RCA H6 identified and the proposal addresses it explicitly, the
replace-vs-skip rule honestly bounds the seed's authority versus officer
publication, and BL-013/BL-010 deferrals are named with follow-up work
units that own the missing preconditions. The single material gap — an
ELSE branch in the SQL CASE statement that warns instead of failing
closed when the assumption-A5 impossible state is detected — is
mechanically closable in Step 6c and is named here so Step 6a contract
definition can pin it. No invalidated assumptions and no non-positive
value signal on the local supported surface.
