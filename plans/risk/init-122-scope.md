READ:
- proposals/04-public-intake-form-seed.md
- research/06-public-intake-form-seed-problem-map.md
- .tmp/rca/public-intake-form-seed-FINDINGS.md
- ~/ai/workflows/implementation-pipeline.md (Phase 4)
- ~/ai/conventions/no-backwards-compatibility.md
- ~/ai/conventions/no-deferred-stubs.md
- plans/risk/init-121-scope.md (format reference)
- plans/BACKLOG.md (BL-002, BL-013)

# INIT-122 Scope-Risk Report

## Inputs read

- Proposal: `proposals/04-public-intake-form-seed.md`.
- Problem map: `research/06-public-intake-form-seed-problem-map.md`.
- RCA: `.tmp/rca/public-intake-form-seed-FINDINGS.md`.
- Conventions: `~/ai/conventions/no-backwards-compatibility.md`,
  `~/ai/conventions/no-deferred-stubs.md`.
- Phase-4 rules: `~/ai/workflows/implementation-pipeline.md` §Phase 4.
- Backlog: `plans/BACKLOG.md` BL-002 (this slice) and BL-013 (deferred
  remote channel apply).
- Locked direction confirmed in problem map line 53 and RCA line 81:
  Option A — local GitOps idempotent seed Job under
  `gitops/channels/local/applications/server-manager/`, after the
  Alembic Job, that writes both projection and aggregate substrate.

## Scope ↔ Anti-scope check

Each design change below is paired with the Scope clause it satisfies
and the Anti-scope clause it must not violate.

1. **Add `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`
   with a ConfigMap-mounted seed payload and a one-shot Job, then
   wire it into the local Kustomization** (proposal §Scope lines 38-39;
   §Design lines 70-78).
   - Scope: "Add `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`
     containing a ConfigMap-mounted seed payload and a one-shot Job"
     and "Add that manifest to `gitops/channels/local/applications/server-manager/kustomization.yaml`."
   - Anti-scope guard: "No remote-channel apply; remote remains
     deferred to BL-013" (line 53). The new file lives only under
     `gitops/channels/local/...`; no edit to
     `infra/channels/dev.yaml` or any remote/template overlay.
   - Anti-scope guard: "No migration-based seed and no Alembic
     downgrade hook for this form" (line 55). The Job is a separate
     Kubernetes resource, not a new Alembic revision.
   - Verdict: in scope; the surface stays inside the named local
     channel directory.

2. **Use the already-mirrored Bitnami legacy `psql` image and read
   `DATABASE_URL` from the existing `server-manager-postgres-url`
   Secret** (proposal §Scope lines 40-41; §Design line 70).
   - Scope: "Use a tiny image with `psql`, preferably the already
     mirrored local e2e Postgres image
     `mirror.gcr.io/bitnamilegacy/postgresql:16.2.0-debian-11-r16`"
     and "Read `DATABASE_URL` from the existing
     `server-manager-postgres-url` Secret, matching the Alembic Job."
   - Anti-scope guard: anti-scope does not introduce a new image
     mirror, registry mirror, or new Secret. The proposal reuses the
     image the e2e bringup already pulls
     (`infra/tests/e2e/lib/bringup.sh`) and the Secret the Alembic
     Job already consumes
     (`gitops/channels/local/applications/server-manager/alembic-migration-job.yaml`).
   - Verdict: in scope; no new infrastructure dependency.

3. **Seed the canonical INIT-120 two-field global form using fixture-
   visible labels and max lengths** (proposal §Scope line 42;
   §Design lines 82-95).
   - Scope: "Seed the canonical INIT-120 global form with fields
     `character_name` short required and `application_text` long
     required, using the fixture-visible labels and max lengths from
     `services/api/tests/public_intake_fixtures.py` and
     `infra/tests/fixtures/web-ui/contract.json`."
   - Anti-scope guard: "No INIT-120 public route or public
     request/response contract change" (line 51). The seed mirrors
     the contract under test in `infra/tests/fixtures/web-ui/contract.json`
     and the component fixture in
     `services/api/tests/public_intake_fixtures.py`; it does not
     introduce a third "shape of public form" to converge on.
   - Anti-scope guard: "No YAML `forms/` runtime source of truth.
     Postgres remains the runtime form source" (line 54). Content is
     inline ConfigMap data feeding Postgres, not
     `forms/dark-nemesis.yaml`. RCA H5 (lines 70-72) is honored:
     YAML may be authoring input, not runtime source of truth.
   - Verdict: in scope; the seed converges on the existing public
     contract rather than redefining it.

4. **Insert mutation rows for `aggregate_type='application_form'`,
   `aggregate_id='application_form|global|'`, `aggregate_seq=1`,
   `change_type='form.published'`** (proposal §Scope line 43; §Design
   lines 217-307; §Design lines 345-350).
   - Scope: "Insert the corresponding accepted mutation rows for
     aggregate type `application_form`, aggregate id
     `application_form|global|`, aggregate sequence `1`, and
     `form.published` state."
   - Anti-scope guard: "No change to authenticated
     `/api/v1/application-forms/*` endpoint behavior" (line 52). The
     seed writes the same row contract used by
     `services/api/app/services/forms.py` and
     `services/api/app/services/mutations.py`, which is exactly the
     shape the authenticated form API already produces. The endpoint
     code, authority check
     (`RequireAuthority("application_form.publish", "global")`), and
     ETag/optimistic-locking semantics are not edited.
   - Anti-scope guard: "No change to Discord application form flows
     or Discord-visible behavior" (line 49). Discord submission
     posts to authenticated `/api/v1/applications` with command-
     provided scope (`services/discord/app/handlers/application_submission.py`).
     Adding a current global form does not edit Discord code,
     channel routing, or Discord commands.
   - Verdict: in scope; aggregate substrate is consistent with the
     existing form authoring contract, not a new contract.

5. **Idempotency rule: insert when no current global form, no-op when
   the deterministic seed row already exists, skip when a different
   current global form exists** (proposal §Implementation decisions
   line 63; §Design lines 308-343).
   - Scope: "Q4, conflict behavior: insert only when no current
     global form exists; no-op when the deterministic seed row
     already exists; skip when any different current global form
     exists. This prevents a seed rerun from overwriting officer-
     published state."
   - Anti-scope guard: "No replacement, archiving, or mutation of a
     different current global form" (line 56) and "No form-authoring
     UI or officer workflow change" (line 53). The SQL emits
     `officer-published form present; skipping seed` and exits 0 in
     that case (lines 322-329); it does not call the archive/insert
     logic that the authenticated publish path uses
     (`services/api/app/services/forms.py:78-166`).
   - Verdict: in scope; the rule operationalizes the anti-scope.

## Implementation decisions inside scope?

Q1..Q4 from `## Implementation decisions taken in proposal`
(lines 60-66). Each must be implementable within the touched surface
named in the problem map (lines 42-50).

- **Q1 — Seed as a separate local GitOps one-shot Job, not an
  Alembic migration** (line 60). Touched surface:
  `gitops/channels/local/applications/server-manager/`. The
  problem map lines 42-43 names this directory and the existing
  Alembic Job as the ordering anchor. No `migrations/versions/`
  edit; no Alembic revision id is asserted. The decision is
  consistent with anti-scope line 55. **In touched surface.**

- **Q2 — Direct SQL, not the authenticated form API** (line 61).
  Touched surface: the new ConfigMap SQL only. Problem map lines
  47-48 enumerated the API publish path
  (`services/api/app/api/v1/endpoints/applications/forms.py`,
  `services/api/app/services/forms.py`,
  `services/api/app/repositories/forms.py`) as adjacent surfaces
  inside blast radius, not as edit targets. The decision explicitly
  preserves them by writing the same projection + aggregate row
  shape they expect. The proposal also names the load-bearing
  reason direct SQL must seed the aggregate head: the canonical
  repository lookup joins `form_definitions` to `aggregate_heads`
  (`services/api/app/repositories/forms.py:10-30`,
  problem map line 66, RCA H6 lines 73-74). **In touched surface.**

- **Q3 — Inline ConfigMap-mounted seed payload, not a separate
  YAML in `forms/` or repo root** (line 62). Touched surface: the
  new manifest only. Problem map open question 3 (line 101) named
  this exact decision; the proposal commits to inline data. No
  edit to `forms/dark-nemesis.yaml`, `containers/server-manager/Containerfile.web`,
  or `services/web/src/features/forms/schema.ts`. **In touched
  surface.**

- **Q4 — Idempotency rule: insert / no-op deterministic seed /
  skip non-seed current global form** (line 63). Touched surface:
  the SQL in the new ConfigMap only. Problem map lines 68-69 named
  the `ux_form_definitions__current_per_scope` and
  `ux_form_definitions__scope_version` invariants the SQL must
  respect; the proposal's CTE chain
  (`current_global`, `existing_seed`, `inserted_form`,
  `inserted_action`, `inserted_change`, `inserted_head`) honors
  both. **In touched surface.**

All four Q-decisions are implementable inside the local GitOps
manifest plus the inline SQL named in the problem map. None require
a new external dependency, a new endpoint, a new authority grant, a
new Cedar policy, a new Pomerium route, or a new Alembic migration.

## Out-of-scope discipline

The proposal lists these as `## Out of scope for follow-up`
(lines 397-401). Cross-checked against `## Design`:

- **Chapter scope or chapter-specific forms (BL-010 territory)**
  (line 398): not implemented. The seed targets `scope_kind='global'`,
  `scope_id=NULL`, aggregate id `application_form|global|`. No
  chapter loop, no chapter selector, no chapter-scoped form
  definition row. The anti-scope clause "No INIT-120 public route
  or public request/response contract change" (line 51) reinforces
  that the public web fixture has no chapter selector
  (problem map line 55).
- **Remote channel apply / BL-013** (line 399): not implemented;
  `infra/channels/dev.yaml` still has no application workload
  block (problem map line 95). The Design references only the
  `local` channel directory and reuses the local-channel Secret;
  the rendered manifest never appears under
  `gitops/channels/dev/...` or any shared template surface. No
  silent dev/remote enablement.
- **Officer-driven form authoring UI** (line 400): not in §Design.
  The anti-scope clause "No form-authoring UI or officer workflow
  change" (line 53) is mirrored. No web component edit, no
  authenticated `POST /api/v1/application-forms` change, no Cedar
  policy change for form publish authority.
- **Importing or reconciling `forms/dark-nemesis.yaml`** (line
  401): not in §Design. The anti-scope clause "No YAML `forms/`
  runtime source of truth" (line 54) is mirrored. The proposal's
  inline ConfigMap data is the seed source; `forms/dark-nemesis.yaml`
  is left untouched.
- **Reworking the authenticated publish API or authority model**
  (line 402): not in §Design. Anti-scope line 52 is mirrored. The
  endpoint guard `RequireAuthority("application_form.publish", "global")`
  (problem map line 47) is unchanged; no Cedar policy edit for
  form publish; no `service-identities.json` row added for
  `public-intake-seed`. The `public-intake-seed` actor is only a
  string written into `published_by_id`/`actor_id` columns by the
  seed SQL, not a new Cedar service identity or DB authority grant.

None of the listed follow-ups are silently in scope.

## Convention compliance

`~/ai/conventions/no-backwards-compatibility.md`:

- Anti-scope line 55 forbids a parallel migration path: "No
  migration-based seed and no Alembic downgrade hook for this form."
  This rules out a transitional dual seed (one in Alembic, one in
  GitOps). The proposal commits to a single owning surface.
- Anti-scope line 56 forbids replacement of a different current
  global form. The proposal does not introduce a "fall back to
  bootstrap if officer state missing" branch; the SQL exits 0 with
  a `WARNING` line and makes no mutation
  (proposal lines 322-337).
- The proposal does not introduce a deprecated alias or a
  feature-gated branch for "old fixture seed vs new GitOps seed."
  The component-test fixture
  `seed_global_public_application_form()` in
  `services/api/tests/public_intake_fixtures.py` remains a
  test-only fixture and is not used at runtime (problem map
  line 56). The proposal does not add a runtime caller of that
  fixture and does not add a transitional shim that mirrors its
  archive-then-insert behavior.
- Rollback path (proposal lines 388-393): rollback removes the
  new manifest from the local Kustomization; database cleanup is
  a manual operator action with `ON DELETE RESTRICT` guard, not
  an automated reverse migration. This is reverse-the-resource
  rollback, not a transitional dual-path.

`~/ai/conventions/no-deferred-stubs.md`:

- The Job command is fully specified (proposal lines 70-80,
  97-341): wait for required tables, then execute one
  transactional SQL file with deterministic outcomes. No
  `# TODO` placeholder, no `NotImplementedError`, no empty SQL
  branch.
- The idempotency outcome set is bounded and exhaustive
  (proposal lines 308-338): insert / officer-skip / drift-warning /
  no-op / fail-closed. The fail-closed branch ("WARNING: seed made
  no change and found no current form" — line 337) makes
  unexpected aggregate-head-without-projection state surface
  as an explicit error rather than as a silent stub. Assumption A5
  (lines 366-367) authorizes the fail-closed branch with an
  invalidating-input that returns to research.
- Test-intent track (proposal lines 371-381) names a real
  observable signal for each item. The deferred residual surface
  is bounded by the residual-risk artifact `plans/risk/init-122-test-residuals.md`
  (proposal line 385), which is the authorized-deferral pattern:
  a follow-up artifact captures unverified residuals rather than
  leaving a silent stub.
- Operationally, the proposal does not introduce a "tomorrow we'll
  add a Cedar grant for `public-intake-seed`" stub: the actor
  string is written only into audit/projection columns, no new
  authority grant row, no new Cedar service identity. The decision
  is final, not deferred.

Both conventions are met by the proposal text.

## Adjacent-path discipline

Cross-check of proposal §Supported-surface track (lines 354-359),
§Anti-scope (lines 47-56), and §Out-of-scope follow-up (lines
397-402) against problem-map adjacents (lines 73-89).

- **Discord submission service**: anti-scope line 49 explicit. No
  edit in §Design. Discord posts `ApplicationSubmission` to
  `/api/v1/applications` with command-provided scope and user actor
  headers (`services/discord/app/handlers/application_submission.py:47-93`,
  problem map line 60). Adding a current global form does not
  affect chapter-scoped form lookup, Discord command routing,
  Discord-visible messages, review embeds, private threads, or
  applicant notifications.
- **Authentik flows**: not named in §Design or problem-map blast
  radius. No identity provider, OIDC client, or Authentik flow
  resource is touched. The seed Job runs inside the cluster as a
  service workload using a database secret, not as a user
  identity.
- **Pomerium ingress**: not named in §Design. The public-intake
  rate-limit manifests
  (`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`,
  `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`)
  are not edited. The seed Job has no externally exposed route,
  no Service, no Ingress.
- **INIT-120 public route**: anti-scope line 51 explicit. The seed
  preserves INIT-120 audit semantics — public submit and route
  actions remain stamped as service actor `public-intake` on
  `api:/api/v1/public/applications` (problem map line 75). The
  seed actor is `public-intake-seed` on
  `gitops:local/server-manager/seed-public-intake-form` (proposal
  lines 121-122), which is a distinct request surface and a
  distinct actor identity, so seed audit rows do not collide with
  or impersonate INIT-120 public submit audit rows.
- **Authenticated `/api/v1/application-forms/*`**: anti-scope line
  52 explicit. The endpoint code, the
  `application_form.publish` authority check, and ETag/optimistic-
  locking semantics are unchanged. The seed simply makes `GET
  /api/v1/application-forms/current?scope_kind=global` return 200
  on fresh local bringup where it previously 404'd, which is the
  intended consistency repair (problem map lines 88-89, RCA H6).
- **Authenticated `/api/v1/applications`**: not named in §Design.
  Problem-map line 78 noted that adding a current global form
  could make global-scope authenticated submissions possible for
  actors with `application.submit` at global scope. The proposal
  treats that as adjacent existing capability, not a new public
  route, which is consistent with the supported-surface
  framing — no new authority grant is added, no new endpoint is
  exposed, and the gating still requires existing
  `application.submit` authority at global scope, which the
  proposal does not modify.
- **`form_definitions` uniqueness invariants**: the seed CTE chain
  inserts at most one row, gated on
  `NOT EXISTS (SELECT 1 FROM current_global)` and
  `NOT EXISTS (SELECT 1 FROM existing_seed)`
  (proposal lines 213-214). This honors
  `ux_form_definitions__current_per_scope` and
  `ux_form_definitions__scope_version` (problem map line 68).
- **Audit/optimistic-locking substrate**: aggregate id
  `application_form|global|`, `aggregate_seq=1`, accepted action
  with `action_type='form.publish'`, state change with
  `change_type='form.published'`, head with `current_seq=1`. This
  is the same row contract `services/api/app/services/forms.py`
  and `services/api/app/services/mutations.py` produce, so a later
  officer publish through the API will see expected version 1 and
  archive-then-insert version 2 normally (problem map line 80).

The seed adds local channel runtime state required for an existing
supported public surface; it does not silently mutate Discord,
Authentik, Pomerium, INIT-120 public route semantics, or the
authenticated form/application APIs.

## Notable observations

1. **Job ordering relies on a runtime readiness loop, not Kustomize
   resource order alone.** The proposal explicitly says file order
   is not the only ordering control and that the Job's shell loop
   should poll Postgres until `form_definitions`, `activity_actions`,
   `activity_state_changes`, and `aggregate_heads` exist with the
   post-migration text `aggregate_id` shape (proposal lines 78-80).
   This matches the problem-map observation that plain Kustomize
   inclusion is not a completion-order guarantee (problem map
   line 65). The readiness loop is in scope and fully specified,
   not a deferred stub. **Phase 6 should verify the loop also
   guards against an `aggregate_id`-pre-widening database (i.e.
   pre-`wu-003a`) that would accept the SQL with the wrong column
   type.**

2. **The supported-surface track and the §Out-of-scope follow-up
   both name BL-013, but the §Anti-scope clause is the binding
   one.** Proposal line 53 ("No remote-channel apply; remote
   remains deferred to BL-013") is mirrored in the supported-
   surface track (line 354) and §Out-of-scope follow-up (line
   399). The Anti-scope clause is binding for Phase 6: no
   `gitops/channels/dev/...` edit, no `infra/channels/dev.yaml`
   edit, no shared template extraction, no
   `gitops/flux/dev-*.yaml` edit. **This is enumeration tightness,
   not scope creep — the anti-scope is unambiguous.**

3. **The seed's `actor_id='public-intake-seed'` is distinct from
   INIT-120's `actor_id='public-intake'`.** Proposal lines 121,
   348 use `public-intake-seed`, while INIT-120 stamps
   `public-intake` for public submit and route actions
   (problem map line 75). Distinct actor strings keep audit
   provenance clean: a future operator querying
   `activity_actions WHERE actor_id='public-intake-seed'` sees
   only seed runs; a query for `actor_id='public-intake'` sees
   only public submissions. This is good adjacent-path discipline,
   not scope creep.

4. **The `request_surface='gitops:local/server-manager/seed-public-intake-form'`
   string is a new audit-surface label.** Existing INIT-120
   public-intake audit rows use
   `api:/api/v1/public/applications` (problem map line 75). The
   seed introduces a new label namespaced as `gitops:local/...`,
   which is consistent with the existing API-surface convention
   and does not collide with any other request surface in the
   audit substrate. **This is in scope; the convention is `<surface-kind>:<surface-id>`,
   not a runtime route.**

5. **Assumption A5 explicitly authorizes a fail-closed branch
   rather than inventing a repair path.** Proposal lines 366-367
   commit that an existing `application_form|global|` head
   without a current form and without the seed row "should fail
   closed and return to research rather than guessing a repair."
   The SQL implements that as the final ELSE branch returning
   `WARNING: seed made no change and found no current form`
   (proposal line 337). This is the no-deferred-stubs-compliant
   pattern: the unhandled state surfaces a visible warning and
   exits the slice, rather than being silently auto-repaired.

6. **The `forms/dark-nemesis.yaml` legacy YAML stays untouched.**
   §Out-of-scope follow-up line 401 keeps YAML import out of this
   slice; §Anti-scope line 54 keeps Postgres as the runtime
   source of truth. RCA H5 (lines 70-72) and v1 strategy
   (`proposals/01-v1-scope.md:227-240, :735-738`) both back this.
   The two-field seed content matches the live web contract under
   test (`infra/tests/fixtures/web-ui/contract.json`), not the
   richer Dark Nemesis YAML schema. **No legacy-form import is
   smuggled in.**

## Verdict

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```

No assumption invalidates the supported surface: the local channel
contract still installs `gitops/channels/local/applications/server-manager/`
through Flux, the Alembic Job still creates the post-`wu-003a`
schema the seed depends on, the canonical INIT-120 public submit
path is the surface being repaired, and the day-1 web contract is
the two-field global form already under test in
`services/api/tests/public_intake_fixtures.py` and
`infra/tests/fixtures/web-ui/contract.json`. The proposal stays
cleanly within Scope, honors the locked Option A direction (local
GitOps Job, not Alembic-coupled and not API-publish), keeps every
Anti-scope item out of §Design (no Discord/Authentik/Pomerium edit,
no INIT-120 route or contract edit, no authenticated form-API
edit, no officer UI, no remote-channel apply, no YAML runtime
source, no migration-based seed, no replacement of officer state),
complies with `no-backwards-compatibility` (single owning surface,
no transitional dual seed, no fallback branch) and
`no-deferred-stubs` (full SQL spec, fail-closed final branch,
residual-risk artifact for unverified test intents), and does not
silently mutate Discord application form flows, Authentik flows,
Pomerium ingress, INIT-120 public-route audit semantics, or the
authenticated `/api/v1/application-forms/*` endpoint behavior. The
ordering and `aggregate_id`-shape verification points in notable
observations 1, 2, and 4 are Phase-6 implementation guards bounded
by the proposal text, not scope-gate failures.
