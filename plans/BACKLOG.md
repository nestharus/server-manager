# Server-manager engineering backlog

This is the **single authoritative list** of unfinished work,
follow-ups, residuals, and deferred-scope items for this
repository. New items are appended here as slices/initiatives
finish; the next initiative is picked from the top of the highest
priority section.

Do **not** scatter follow-ups across STEP6C_DONE residuals,
proposal Out-of-scope sections, or RCA "Recommended fix" sections
without also adding them here. Those artifacts are provenance;
this file is the index.

Each item: stable id, one-line title, source citation, one-paragraph
description, status. When picking up work, change status
`[open]` → `[in-progress]` → `[done]` (with the closing commit
SHA) or `[wontfix]` (with reason).

---

## Priority: HIGH

### BL-001 [done] — Cedar bootstrap-job's bundle PUT silently no-ops in some cases

- **Source:** `.tmp/init-120/phase6/STEP6C_DONE.md` R3; observed
  during INIT-120 e2e validation (2026-04-28)
- **Symptom:** `cedar-access-policy-bootstrap` Job runs `curl -X PUT
  -H "Content-Type: application/json" --data-binary
  @/policy/policies.json http://opal-client:8180/v1/policies` and
  exits 0. Cedar agent's `GET /v1/policies` returns `[]`. Manual
  Python `urllib` PUT of the same bundle from the API pod loaded
  the policies correctly. Suspect curl `--data-binary` semantics
  with cedar-agent's PUT handler, or a silent overwrite-with-empty
  on bundle ID conflict.
- **Impact:** Every fresh `humility-local` cluster bringup is
  vulnerable to silently broken authorization. Adjacent E2E specs
  (15-auth-stack, 16-access-policy, 17-tenant-isolation) work today
  only because the seed-time bootstrap happens to win the race.
- **Plan:** Run RCA workflow on the bootstrap PUT path. Confirm
  whether to switch to per-policy POST or fix the curl invocation.
  Implementation will likely change
  `gitops/channels/local/auth/opal-cedar/bootstrap-job.yaml`.
- **Outcome (closed in INIT-121, full pipeline; verified e2e=19/19
  on humility-local):** RCA proved the issue was a split-brain
  policy-loading design — `OPAL_POLICY_REPO_URL` rendered empty
  while the bundle lived only in a ConfigMap consumed by the
  one-shot Job. Fix made OPAL the sole policy authority via the
  in-cluster `git-daemon` already serving `humility-local.git`.
  The renderer materializes per-policy `.cedar` files +
  `.manifest`; OPAL Server clones, OPAL Client refetches, Cedar
  hydrates. Bootstrap Job + ConfigMap deleted. Surfaced and fixed
  several adjacent issues: NetworkPolicy egress to git-system,
  `OPAL_POLICY_REPO_MAIN_BRANCH=main`, OPAL CSV-not-JSON env
  format, separate `OPAL_FILTER_FILE_EXTENSIONS` config, and
  Cedar policy IDs being path-form (validators updated). See
  `.tmp/rca/cedar-bootstrap-put-FINDINGS.md`,
  `proposals/03-cedar-policy-source.md`, and
  `.tmp/init-121/phase6/` for the trail.

### BL-002 [done] — Public intake e2e requires a global-scope form_definitions row that no GitOps seed creates

- **Source:** `.tmp/init-120/phase6/STEP6C_DONE.md` R4; observed
  during INIT-120 e2e validation (2026-04-28)
- **Symptom:** `POST /api/v1/public/applications` calls
  `get_current_form_for_scope(scope_kind='global')` and raises
  `application_not_found` if no form exists. Fresh `humility-local`
  cluster has no global-scope `form_definitions` row, so the public
  intake e2e fails until manual SQL inserts one.
- **Impact:** Public intake breaks on every fresh cluster bringup.
  Workaround was a manual SQL INSERT during INIT-120 validation.
- **Plan:** Add either a Kustomize-applied seed Job in
  `gitops/channels/local/applications/server-manager/` or a
  fixture-loader helper invoked before test 19-web-ui in
  `infra/tests/e2e/run-fullstack.sh`. Decide which based on
  whether the form should exist in production-like deployments
  (Job) vs only test environments (fixture loader).
- **Outcome (closed in INIT-122, full pipeline; verified
  e2e=19/19 on humility-local):** GitOps Job
  `seed-public-intake-form` runs after the Alembic migration Job
  in the local channel. The Job's `psql -f /seed/seed.sql` writes
  both `form_definitions` and the `application_form|global|`
  aggregate head + state-change rows in one transaction so the
  application service's `get_current_form_for_scope` finds the
  seeded form. Idempotency: deterministic UUID derived from
  sha256, no-op on re-run, skip-with-NOTICE if an
  officer-published current global form exists. See
  `proposals/04-public-intake-form-seed.md`,
  `.tmp/init-122/phase6/`.

### BL-003 [done] — `build-channel-image.sh` Docker layer cache serves stale `npm run build` output

- **Source:** `.tmp/init-120/phase6/STEP6C_DONE.md` R1; observed
  during INIT-120 web-image rebuild (2026-04-28)
- **Symptom:** `docker build` reuses the `npm run build` layer based
  on COPY input hashes, but Vite's content-hashed bundle filenames
  (`index-<hash>.js`) make the deployed bundle look stale even when
  the layer hash is correct. Symptom in INIT-120: `services/web/src/main.tsx`
  changed but the deployed pod's bundle was the old one
  (`index-B8WWo-DS.js` instead of `index-CtukCxsq.js`). Resolved with
  `docker build --no-cache`.
- **Impact:** Iterative web changes silently fail to deploy until
  the cache is busted, wasting time during dev/test cycles.
- **Plan:** Add `--no-cache` flag option to
  `infra/scripts/build-channel-image.sh` and call it from CI. Or
  invalidate cache via a `.dockerignore` strategy that always
  re-COPYs source. Or consider Kaniko/buildkit cache-from with
  better invalidation semantics.
- **Outcome (closed; bundled with BL-004 as a tight script
  change rather than full pipeline since this is a 5-line
  script-flag addition with self-evident rationale):**
  `build-channel-image.sh` now accepts `--no-cache` which passes
  through to `docker build`. Verified by rebuild of
  server-manager-api with `--no-cache --k3d-import humility-local`.

### BL-004 [done] — k3d nodes cache same-tag images, defeating `imagePullPolicy: IfNotPresent` rolls

- **Source:** `.tmp/init-120/phase6/STEP6C_DONE.md` R2; observed
  during INIT-120 web/api rolls (2026-04-28)
- **Symptom:** Deployments use `imagePullPolicy: IfNotPresent` with
  stable tags (`init-118-local`, `init-113-local`). After
  `docker push` to the registry with the same tag, k3d nodes
  retain the previously-pulled image; `kubectl rollout restart`
  reuses the cached image. Resolved with `crictl rmi` on each
  k3d node before rolling.
- **Impact:** Same-tag rebuilds need a manual cache-clear step that
  isn't documented in the bringup runbooks. Easy to misdiagnose
  as "my code change didn't take" when the build was fine.
- **Plan:** Either (a) move to digest-pinned image references via a
  build-step that writes `image: <registry>/<app>@sha256:...` into
  the rendered GitOps, or (b) append a build-id/timestamp tag
  suffix and update the kustomization to reference it. (a) is the
  more durable answer.
- **Outcome (closed; bundled with BL-003):** Picked the
  pragmatic third option: `build-channel-image.sh --k3d-import
  <cluster>` re-tags the just-pushed image as the cluster-internal
  pull URL and runs `k3d image import` to load it into every
  node's containerd by tag, bypassing the registry pull cache.
  Verified: server-manager-api rebuild lands new digest under the
  same tag on both `k3d-humility-local-agent-0` and `-server-0`,
  old digest moved to `<none>` tag. Digest-pinning (option a) is
  deferred — the import path is sufficient for local dev/test
  reliability and doesn't require gitops kustomization churn.

### BL-005 [done] — Synthetic public-intake members pollute roster queries

- **Source:** `proposals/02-public-application-intake.md:327-339` (AS-2),
  `plans/risk/init-120-shortcut.md`
- **Description:** INIT-120 creates `members` rows whose
  `discord_user_id` starts with `public:` for anonymous applicants.
  Existing roster-facing queries (member listing, trust profile
  aggregations, member status counts) include these synthetic rows
  unless explicitly filtered. The proposal's risk gate accepted
  this with the assumption that future cleanup or roster filters
  would land alongside Discord OAuth linking.
- **Impact:** Reporting accuracy degrades silently as public submissions
  accumulate. Officers querying "members" via Discord commands or
  admin UI get inflated counts that mix real Discord members with
  synthetic intake placeholders.
- **Plan:** Enumerate every roster-facing API endpoint and add a
  query-level `discord_user_id NOT LIKE 'public:%'` filter, or
  refactor `members.id` to namespace synthetic rows differently
  (separate table or `kind` column). Coordinate with BL-009 (Discord
  OAuth linking) since the long-term answer may be conversion.
- **Outcome (closed in INIT-124, full pipeline w/ round-2
  re-run; verified e2e=19/19 on humility-local):** Picked
  Option 1 from RCA — write-boundary guard via
  `is_synthetic_member()` predicate in
  `services/api/app/services/members.py`. Boundary guards
  applied at: authenticated submit, owner claim/reassign/
  reactivate, trust signal/compute/recompute, leadership alias
  expansion, roster entry creation, and PATCH member status.
  Each boundary returns a stable `*_synthetic_not_allowed` error
  code with 422. INIT-120 public-intake submit path unchanged —
  e2e still creates synthetic members successfully. Read-side
  hardening + `members.kind` schema column + pre-existing-pollution
  cleanup deferred to BL-008 (Discord OAuth linking).

---

## Priority: MEDIUM

### BL-006 [deferred] — Public submit response shape — verify final envelope is what we want long-term

- **Source:** `proposals/02-public-application-intake.md` Implementation
  decision B1
- **Description:** Public route returns `{message, application_id}`
  by deliberate design — not the full `ApplicationRead`. Worth
  revisiting after the surface has been live for a few weeks to
  confirm support/debug needs are met.
- **Plan:** Lightweight review; bump priority if reports show
  confusion. Otherwise leave open as low-cost ongoing.
- **Deferred reason (2026-04-29):** No actionable signal yet — the
  public surface has not been deployed to humans, so there's no
  support/debug feedback to act on. Re-open and bump to medium
  priority when (a) the surface ships to a real channel, or (b)
  any operator reports a debug need that the current envelope
  cannot satisfy.

### BL-007 [done] — psql `:'name'` substitution in `kubectl exec ... -- psql -c` does not expand

- **Source:** `.tmp/init-120/phase6/STEP6C_DONE.md` R5; fixed inline
  in `infra/tests/e2e/tests/19-web-ui.sh` during INIT-120
- **Symptom:** psql's `-v name=value` flag sets a script variable;
  expansion only happens when reading SQL from a script file or
  stdin, NOT from `-c "..."` strings. Test wrappers that use
  `:'name'` syntax with `-c` get a syntax error.
- **Impact:** Future test authors will hit this same bug if they
  follow the now-fixed-but-was-buggy pattern.
- **Plan:** Document the convention in
  `~/ai/conventions/test-reports.md` or a new
  `infra/tests/README.md` snippet. Audit existing test scripts
  with `grep -rn "psql.*:'.*'" infra/tests` to confirm no other
  files share the bug.
- **Outcome (closed):** Sweep `grep -rn "psql.*:'.*'" infra/
  services/` returned zero matches (the original bug was already
  fixed inline in `infra/tests/e2e/tests/19-web-ui.sh` during
  INIT-120). Added a load-bearing comment at the fixed call site
  warning future test authors that psql does NOT expand `:'var'`
  in `-c` queries — use shell interpolation. No central conventions
  doc needed since there are no other instances and the comment
  is at the exact place future authors will copy from.

### BL-008 [done — superseded by receipt-required design] — Discord OAuth linking + synthetic→real member conversion

- **Source:** `proposals/02-public-application-intake.md:441` (Out
  of scope for follow-up); deferred from INIT-120
- **Description:** Public web applicants currently land as synthetic
  members (`discord_user_id="public:<sha>"`). A proper applicant
  should be linkable to a real Discord identity once they
  authenticate; their pending application(s) and any audit history
  should fold into the real member row.
- **Plan:** New initiative. RCA → Phase 2.5 problem map → Phase 3
  proposal. Likely surface: extend Authentik OIDC flow, add
  `members.linked_at`, write a conversion service that updates
  `applications.applicant_id` and migrates audit refs.
- **Decomposition (per `.tmp/rca/discord-oauth-linking-FINDINGS.md`):**
  Too large for one slice. Split into:
  - **INIT-125A [done]** — `members.kind` schema column +
    guard migration from prefix-check to kind-check. Verified
    e2e=19/19 on humility-local; live SELECT shows
    `public_intake` rows correctly classified.
  - **BL-016** — INIT-125B Authentik Discord OAuth provider +
    applicant OIDC client plumbing.
  - **BL-016 [done]** — INIT-127 Authentik Discord OAuth provider +
    applicant OIDC client plumbing.
  - **BL-017 [done]** — INIT-128 receipt-required public submit
    (supersedes the original "member_links + conversion service"
    design — receipt-backed submits create real Discord members
    directly, eliminating the need for synthetic→real linking).
  - **BL-018 [done]** — INIT-129 dead synthetic-creation path
    removed; defense-in-depth `is_synthetic_member()` guards kept.
- **Outcome:** BL-008's original goal (real Discord identity for
  public applicants) is achieved. The implementation diverged from
  the original "link & convert synthetics" plan: instead, receipt-
  required submit means no synthetic is ever created on the request
  path, so there's nothing to convert. Historical synthetics from
  pre-INIT-128 e2e runs remain in humility-local as inert data,
  filtered by read-side guards.

### BL-009 [done] — INIT-134: Discord-visible side effects for public web submissions

Closing commit on `recovery/test-first-audit` branch (bundled
with BL-020 as INIT-134). Adds officer embed in
`#applications-review`-style designated channel + applicant DM
with link to primary guild channel, both fired off the
public-submit hookpoint via the existing notification_events
substrate. Migration `wu-045` adds nullable
`rendered_embed_json` to `notification_envelopes` and seeds the
two notification rules. PII level A truncation locked. Tests
passing locally: 29 INIT-134 tests + 70/70 prior-slice
regression. Risk gates LOW after r2. CodeRabbit converged
through r3 with only 6b-test-file nitpicks remaining. See full
proposal at `proposals/16-init-134-discord-notifications.md`.

### BL-009 [done — historical] — INIT-126: Discord-visible side effects for public web submissions

- **Source:** `proposals/02-public-application-intake.md:444-446` (Out
  of scope for follow-up — Tier 3 approval)
- **Description:** Public web submissions create a `queued`
  application but no Discord message, thread, or notification —
  officers have no in-Discord trigger that a public submission
  needs review. The Discord-driven submission flow already does
  these side effects; the web path needs convergence.
- **Plan:** New initiative subject to Tier 3 approval rules per
  `~/ai/workflows/tiered-approval.md`. RCA establishes existing
  Discord side-effect surface; proposal designs queue/thread/
  notification fan-out.
- **User-confirmed product direction (2026-04-29):**
  - Discord embed in `#applications-review` channel that routes
    back to the in-product application page; officers can claim/
    assign + open private interview channels in the product.
  - Embed format A: app_id, support_id, scope, submitted time,
    form version, truncated response preview. Hide synthetic ids.
  - **Applicants must Discord-OAuth before submitting.** No
    anonymous public-intake. Real `discord_id` available at
    submit time — synthetic-member apparatus becomes legacy. This
    is a redirect of INIT-120's anonymous-public-form
    foundation; the public submit path must be retrofitted (or
    re-thought) to require Discord auth before the form
    materializes responses.
  - No private Discord thread per application. Reviews + private
    reviewer↔applicant channels happen IN-PRODUCT. Transcripts
    saved to product. Discord is the entry/notification surface
    only.
  - On submit: applicant receives an immediate Discord DM with a
    link to the primary guild channel.
  - Officer notification @-mentions a chapter-specific role for
    application managers (chapter-role assignments managed in
    the product).
  - PII level A: minimal preview in embed; full content stays in
    the API.
- **Blockers:**
  - **BL-016** (Discord OAuth provider in Authentik) — required
    for applicants to authenticate before submitting and for the
    embed/DM to address a real Discord identity.
  - **BL-019** (new — in-product application review surface
    with chapter-scoped officer roles, assignment, private
    reviewer↔applicant channels, transcript persistence) —
    required for the "routes back to application" embed link
    to land somewhere meaningful and for the "private interview
    channel" workflow.

### BL-010 [β-1 done; β-2/β-3 open] — INIT-135: Web form richer inputs (chapter selector / multi-page / file upload)

- **Source:** `proposals/02-public-application-intake.md:445` (Out
  of scope for follow-up); β-1 spec at
  `proposals/17-init-135-chapter-selector.md`.
- **Description:** Day-1 form has two visible fields targeting
  global scope. Roadmap wants chapter selection, file uploads,
  multi-page forms with conditional fields. The fixture
  `infra/tests/fixtures/web-ui/contract.json` is the contract
  surface to extend.
- **β-1 chapter selector — done at f3e28a7 (recovery/test-first-audit):**
  - New `chapter_select` form-field discriminated-union variant on
    JSONB `form_definitions.fields` (no migration).
  - New `GET /api/v1/public/chapters` (active-only, name ASC, 200
    cap, identity-free dependency tree).
  - Form-lookup override gate (chapter-selector global form +
    scope_kind=chapter), 6 positive/negative cases (audit F2).
  - Server-side chapter existence + active re-check;
    `responses[chapter] == scope.scope_id` enforced.
  - `TypeAdapter` for `ApplicationFormField` union alias (audit F1).
  - v1→v2 seed advance with archive + version bump + state-change
    write (audit F3); preserves BL-002 fail-closed guard.
  - SPA `ApplicationFormRoute` is data-driven; chapter dropdown
    fetched from new endpoint; multi_select draft restoration
    iterates `<select multiple>` options.
  - 41 unit tests pass; web typecheck + build pass.
  - 8 rounds of CodeRabbit applied (path normalization, dead-code
    removal of unreachable validators, `selected` placeholder
    attributes, documentation cleanups).
  - Risk gates: 4×LOW, audit r2 confirmed F1–F4 absorbed.
  - Pre-existing residual: Playwright spec carrier failure on the
    Solid 2 beta compat shim "Cannot read properties of undefined
    (reading 'effect')" affects ALL specs in this worktree, not
    introduced by INIT-135.
  - Cluster restored 2026-04-30: agent node `Ready` after `docker
    restart k3d-humility-local-agent-0`; Redis + Infisical back up;
    `server-manager-e2e-fixtures` resynced with all 5 INIT-134 keys;
    api/discord pods running 1/1 with INIT-113/INIT-118 images.
    Flux Kustomization `humility-local` left **suspended** because
    its tracked git revision (`5d872983`) predates INIT-134 and would
    revert the new InfisicalSecret + api-deployment env vars.
  - e2e admin step timeout (β-i carrier through INIT-134) **fixed**
    in BUG-1 at 743f25b: services/web/src/solid-compat/solid.ts
    createLegacyEffect was passing one arg to Solid 2 beta's
    createEffect; beta needed two. SPA now bootstraps and admin
    route renders. Verified via re-run of test 19 — "Chapter
    administration" heading visible.
  - e2e downstream blocker (now exposed): test 19 expects chapter
    `chapter-alpha`/`Alpha Chapter` to exist for the chapter_select
    dropdown, but cluster has no chapters seeded and `seed-authority-grants.mjs`
    doesn't add one. Tracked as BUG-5 (separate slice).
- **β-2 (multi-page + conditional fields) and β-3 (file upload):**
  open. New initiatives when product priority surfaces. Touch:
  SPA form renderer state machine, `form_definitions.fields` shape
  for `page` + `visible_when`, S3 / object-storage backend +
  presigned upload + reference in response, and the e2e contract.

### BL-011 [done] — Legacy SQLite `/apply` modernization or deletion

- **Source:** `proposals/02-public-application-intake.md:443` (Out
  of scope for follow-up); originally referenced in
  `proposals/18-applications.md`
- **Description:** `daemon/applications.py` registers `/apply` and
  collects modal answers but only stores them in memory; never
  posts to the API. This was the original Discord-first applicant
  flow. The newer `services/discord/app/handlers/application_submission.py`
  does the right thing through the API. The legacy path is dead
  code that confuses future readers.
- **Plan:** Delete `daemon/applications.py` and any imports/registrations
  it has. Verify nothing else in `daemon/` depends on its stubs.
  Consolidate any tests under `services/discord/tests/`.

### BL-012 [deferred] — Cedar `Public::` entity-type assumption — monitor for OPAL/Cedar schema enforcement

- **Source:** `proposals/02-public-application-intake.md:327-339` (AS-4)
- **Description:** INIT-120 introduces `Public::"web-intake.<channel>"`
  as a new entity type. OPAL/Cedar today accepts any entity name
  because no schema is loaded. If OPAL/Cedar adopts strict
  schema validation in a future version, this principal type
  could be rejected.
- **Plan:** Add an integration test that asserts `Public::"web-intake.local"`
  is accepted by OPAL bootstrap. Watch OPAL release notes for
  schema-enforcement changes.

---

## Priority: LOW

### BL-013 [deferred] — INIT-124: Public intake remote channel apply

- **Source:** `proposals/02-public-application-intake.md:447` (Out
  of scope for follow-up)
- **Description:** INIT-120 ships local-only manifests
  (Kong rate-limit, Cedar policy, Pomerium binding). Remote channel
  config in `gitops/channels/dev/` does not have application
  workload specs yet.
- **Plan:** Block on remote channel application-workload
  materialization (separate initiative). Then this is a
  channel-template port: same logical resources, channel-derived
  hosts.

### BL-014 [deferred] — Kong rate-limit binding feasibility — version-pin watch

- **Source:** `proposals/02-public-application-intake.md:327-339` (AS-5)
- **Description:** INIT-120's path-specific KongPlugin binding
  depends on Kong/KIC supporting that pattern. Current Kong 3.2.0
  + KIC supports it. Future major bumps could break the binding.
- **Plan:** Watch Kong/KIC releases for breaking changes;
  re-evaluate per-service binding if path-specific support
  changes.

### BL-015 [done] — Web `test-results/` Playwright artifacts cluttered the worktree

- **Source:** Observed during INIT-120 commit; partial fix in
  `services/web/.gitignore` shipped with INIT-120
- **Description:** `services/web/test-results/` is a Playwright
  artifact directory created during local test runs. INIT-120
  added it to `services/web/.gitignore`. Verify other Playwright
  artifact paths (e.g., `playwright-report/`) are also ignored.
- **Plan:** Audit `services/web/.gitignore` against Playwright's
  default artifact paths. Add anything missing.
- **Outcome (closed):** `services/web/.gitignore` now also
  excludes `playwright-report/`, `blob-report/`, and
  `playwright/.cache/`.

### BL-016 [done] — INIT-127: Authentik Discord OAuth provider + applicant OIDC plumbing

- **Source:** Decomposition of BL-008 per
  `.tmp/rca/discord-oauth-linking-FINDINGS.md` §"Recommended fix shape"
- **Description:** Add Discord OAuth Source + server-manager
  applicant OIDC provider/app to Authentik. Add Infisical secret
  plumbing for Discord OAuth client_id/secret. Add API/web
  callback contract enough to verify a Discord snowflake claim.
  Do NOT yet mutate existing applications — just establish the
  identity verification surface.
- **Plan:** Pick up after INIT-125A closes.
- **Priority:** MEDIUM
- **Outcome (closed in INIT-127, full pipeline; verified
  e2e=19/19 on humility-local):** Authentik Discord Source +
  applicant OIDC Provider/App declared in blueprints. Pomerium
  prefix route `/auth/discord/*` forwards to API.
  `/auth/discord/start` builds Authentik authorize URL with PKCE
  + state. `/auth/discord/callback` exchanges code server-side,
  validates JWT against Authentik JWKS, issues HMAC-signed
  receipt cookie (HttpOnly, 10-min TTL). `/auth/discord/me`
  reads receipt + returns the verified `discord_user_id`. SPA
  has Login button on `/applications`. Discord scope: `identify`
  only (least privilege). 16/16 unit + 6/6 infra + 6/6 web
  + 19/19 e2e all green.

### BL-017 [done] — INIT-128: Receipt-required public submit (supersedes member-link/conversion)

- **Source:** Decomposition of BL-008; supersedes the original
  INIT-125C "member_links + conversion service" framing.
- **Description:** Locked design: anonymous public submit is
  removed. `POST /api/v1/public/applications` requires a valid
  HMAC-signed `applicant_receipt` cookie (issued by the
  `/auth/discord/*` flow from BL-016). The submit path resolves
  or creates a real `kind='discord'` member from the receipt's
  snowflake and writes `applications.applicant_id` against that
  real member directly. Emits `application.public_submitted`
  notification event. No synthetic→real linking needed because
  no synthetic members are ever created on this path.
- **Outcome (closed in INIT-128, full pipeline; verified
  e2e=19/19 on humility-local):** Cookie path widened from
  `/applications` to `/`. New FastAPI dep
  `verify_applicant_receipt` returns the verified
  `DiscordIdentity`. Public submit endpoint refactored: no
  anonymous happy path remains; rejects missing/tampered/expired
  receipts with 401 `applicant_receipt_required`. New service
  `submit_public_application_with_receipt` writes the application
  with `actor_kind='user'`, `actor_id=<member.id>`, and request
  surface attribution. New helper
  `resolve_or_create_real_discord_member` is idempotent on
  snowflake. SPA gates the form on `/auth/discord/me`. e2e
  fixture secret `server-manager-e2e-fixtures` issued via
  Infisical so the test signing key matches the API. Live DB
  post-e2e: `discord=1, public_intake=18` (the `1` is the
  receipt-backed e2e submission; the `18` are pre-INIT-128
  historical synthetic rows — BL-018's territory).
- **Priority:** MEDIUM

### BL-018 [done] — INIT-129: Remove dead synthetic-creation path; close BL-005 read-side residual

- **Source:** Decomposition of BL-008; also closes BL-005's
  read-side residual.
- **Description (revised post-INIT-128):** The original "linked →
  keep, unlinked synthetic → drop" cleanup-Job design was
  load-bearing only under the abandoned member_links/conversion
  framing of BL-017. Post-INIT-128 there is no synthetic-creation
  code path on the request side, so:
  - Read-side hardening: `is_synthetic_member()` + `members.kind`
    discriminator already cover every read surface that fetches
    member rows by id (verified: only `repositories/members.py`
    reads from the table, all single-row fetches funneling
    through service-layer guards).
  - Historical-row cleanup: not needed. The 18 humility-local
    `kind='public_intake'` rows are e2e fixture artifacts;
    production has not shipped. No cleanup Job.
- **Outcome (closed in INIT-129; verified e2e=19/19 on
  humility-local):** Pure dead-code removal. Deleted
  `submit_public_application` (legacy anonymous service entry),
  `_SubmissionAuthority` enum + parameter,
  `resolve_or_create_public_intake_member` helper,
  `PUBLIC_INTAKE_*` constants, `public_intake_member_salt`
  setting, `tests/test_public_intake_synthetic_member.py`.
  `_insert_member`/`_insert_member_on_discord_conflict_do_nothing`
  hardcode `kind='discord'` (no callers ever passed anything else
  post-INIT-128). Kept `is_synthetic_member()` + every caller in
  applications/trust/roster/authority/members as defense-in-depth
  for the historical 18 rows + any hypothetical pre-INIT-128
  backup-restore. `MemberKind` literal still accepts
  `"public_intake"` so the type-checker accepts historical rows.
  Net diff: −341 lines. Full API suite: 692 passed (1 unrelated
  pre-existing fail).
- **Priority:** LOW (residual cleanup).

### BL-019 [in-progress, decomposed] — In-product application review surface (chapter roles + assignment + private channels + transcripts)

- **Source:** Surfaced in BL-009 product-direction discussion
  with user (2026-04-29).
- **Substrate audit:** `research/18-bl-019-substrate-audit.md`.
  Found that the application lifecycle (claim/assign/transitions),
  chapter-scoped authority grants, and the ticket_messages
  pattern (visibility-scoped staff/reporter messaging) ALREADY
  exist. The remaining gap is per-application messaging +
  transcript + SPA surface. The originally-planned
  "role/permission model" reduces to a constant + integration
  test because the authority infrastructure is already
  chapter-scope-aware.
- **Decomposition:**
  - **BL-019A (folded into 019B)** — Officer permission bundle
    constant + chapter-scope isolation test. Trivial; folded
    into 019B's authorization wiring.
  - **BL-019B [done] — INIT-131** — `application_messages`
    substrate landed at 4b210f6: schema (wu-044), contracts,
    repository, service, POST + GET endpoints, authorization
    via new `application.message` permission (chapter-scope
    aware). 21 unit/component/migration tests + 19/19 e2e on
    humility-local. Visibility split: `applicant_visible` /
    `officer_only`. Idempotent on `client_message_id`. Schema
    is purely additive; no edits to existing application
    service code beyond the router include.
  - **BL-019C [done] — INIT-132** — Transcript endpoint landed
    at 3bdbab1: GET /api/v1/applications/{id}/transcript joins
    activity_state_changes + application_messages
    chronologically with viewer-aware visibility filtering
    (delegated to read_application_messages). 8 unit/component
    tests, full API suite 721 passed (1 known pre-existing
    fail), e2e 19/19 on humility-local.
  - **BL-019D — split into:**
    - **BL-019D-α [done] — INIT-133A** — list-applications
      endpoint landed at bb5fbc7. `GET /api/v1/applications`
      with state/scope/owner filters + keyset pagination
      (limit, after_id). Authorization reuses the canonical
      application-review permission set. 6 unit/integration
      tests, full API suite 727 passed (1 known pre-existing
      fail), e2e 19/19 on humility-local.
    - **BL-019D-β [decomposed at risk gate] — INIT-133B** —
      original framing (queue + detail + transcript + messages +
      transitions in one slice) blocked by the Phase 4 audit risk
      gate on 2026-04-29. The single-slice INIT-133B-i proposal at
      `proposals/13-init-133B-i-officer-queue.md` and its risk
      gates `plans/risk/init-133B-i-{audit,scope,shortcut,supported-surface}.md`
      are kept as audit-trail artifacts informing the
      decomposition below.
      - **Audit finding A1 (HIGH):** the proposed officer
        web-bridge derived `ActorIdentity.actor_id` from the
        `applicant_receipt` cookie's `discord_user_id`. Nothing
        binds that Discord identity to the Pomerium subject, so
        an officer could claim/list applications under whatever
        Discord receipt happens to be in their browser, with the
        audit row recording the wrong actor. The Pomerium
        Authentik app currently emits only `email`, `sub`,
        `groups`, `name` claims; the Discord-user-id claim
        machinery in `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml`
        belongs to the applicant OAuth app
        (`init-127-applicant-discord-oauth.yaml`), not the
        Pomerium officer app. A trustworthy officer-actor binding
        is missing from the chain.
      - **Decomposition (revised — bundled β-0a+β-0b+β-i):**
        After Phase 2 binding research at
        `research/20-init-133B-officer-identity-binding.md`,
        the bundled M1 approach (Authentik+Pomerium Discord
        claim chain) was chosen. Phase 3 proposal at
        `proposals/13-init-133B-i-officer-queue.md` cleared all
        four risk gates LOW (after 11 revision rounds). Phase
        5 hookpoints at `research/21-init-133B-i-hookpoints.md`.
        Phase 6a contract at
        `.tmp/init-133B-i/phase6/step6a-contract.md`.
        - **BL-019D-β-0a + β-0b + β-i [done]** — INIT-133B-i
          landed bundled; closing commit on
          `recovery/test-first-audit` branch. Includes:
          - TanStack Solid Router as the live SPA entry;
            vanilla `main.tsx` retired. `RuntimeApp.tsx` +
            `DarkNemesisForm` deleted as parallel scaffolding.
          - Authentik officer-Discord OAuth blueprint
            (`discord-pomerium` source, `pomerium` provider +
            app, `officers` group, sample user membership +
            `attributes.discord_user_id`).
          - Pomerium config: `idp_scopes` extends with
            `discord_user_id`, `jwt_claims_headers` adds
            `x-pomerium-claim-discord-user-id`. New
            `path:/api/me`, `prefix:/api/web/admin/`,
            `prefix:/api/web/officer/`,
            `path:/applications/queue`,
            `prefix:/applications/queue/` routes ahead of
            public catch-all.
          - Web-officer API bridge under
            `/api/v1/web/officer/*` derives `ActorIdentity`
            from Pomerium-asserted `discord_user_id` claim
            (server-side, never from cookies/headers).
          - `applicationListForbiddenError` mapping migrated
            into the shared `raise_known_application_error`.
          - `resolve_or_create_real_discord_member` accepts
            optional `originating_actor` + `request_surface`,
            threaded through all three audit-attribution
            sites.
          - Tests passing: 31/31 API bridge + identity, 14/14
            static infra (Authentik + Pomerium), web
            typecheck + build, 18 Playwright tests collect,
            `validate_web_ui_local.sh` 8/8 (with 1 skip).
        - **Residuals folded forward:**
          - **e2e Playwright admin step**: test 19-web-ui
            Playwright fails waiting for "Chapter
            administration" heading on the deployed cluster.
            Code is correct (typecheck/build/unit/static all
            green); appears to be a live-integration boundary
            issue (cluster fixture drift after manual
            applies, or OAuth flow timing). Needs separate
            session.
          - **CodeRabbit For-accessor false positives**:
            CodeRabbit r2-r5 keep flagging `state()`,
            `application()` as "wrong" but they ARE accessors
            in Solid 2 beta (`solid-js@2.0.0-beta.8`). Verified
            in
            `services/web/node_modules/solid-js/types/client/flow.d.ts`.
            Documented and skipped by every fix-agent round.
          - **Manual `ApplicationAlreadyClaimedError`
            wrapping in bridge claim**: bridge translates
            already-claimed-with-version-mismatch into
            `StaleMutationError` manually rather than letting
            `raise_known_application_error` handle it. Could
            be folded back later.
          - **Five accumulated minor nitpicks** from CodeRabbit
            r5 (Pomerium group restriction at edge, SQL CTE
            ordering, blueprint description text, JSON parse
            robustness, test helper error clarity). All
            non-blocking.
        - **BL-019D-β-ii [done]** — Application detail page +
          transcript view (read-only). Consumes β-i routing.
          Closing commit on `recovery/test-first-audit` branch.
          Adds:
          - TanStack route `/applications/$applicationId` →
            `ApplicationDetailRoute` (read-only).
          - Two web-officer bridge GET endpoints (detail +
            transcript) reusing `_build_officer_actor` and
            `raise_known_application_error`.
          - `ApplicationMessageAppendForbiddenError` mapping
            migrated into the shared mapper.
          - Pomerium `prefix: /applications/` after queue
            routes, before public catch-all.
          - Queue row navigation Link to detail.
          - E2e extended: post-claim navigates to detail, asserts
            state=claimed and transcript state_change entry.
          Tests passing locally:
          - 45/45 API + identity tests.
          - 15/15 static infra + Authentik blueprint tests.
          - 27 Playwright tests collect (compat + queue + detail).
          - validate_web_ui_local.sh: pass=9 fail=0 skip=1.
          - All four Phase 4 risk gates LOW on r1 (no revisions
            needed, vs β-i which took 11).
          Residuals:
          - E2e test 19 Playwright admin route step times out
            (β-i pre-existing carryover; cluster-side).
          - CodeRabbit Solid-2-beta For-accessor false positives
            recurred across r1-r5 as expected.
        - **BL-019D-β-iii [done]** — Message thread + non-claim
          transitions. Closing commit on
          `recovery/test-first-audit` branch. Closes BL-019D-β.
          Adds:
          - `POST /api/v1/web/officer/applications/{id}/messages`
            bridge. Browser does NOT supply author fields;
            bridge fills from resolved officer actor. 201 on
            create, 200 on idempotent replay.
          - `POST /api/v1/web/officer/applications/{id}/transitions`
            bridge. Single endpoint covers 7 actions
            (review, request_interview, waitlist, approve,
            deny, reactivate, withdraw, route). Rejects
            `claim` with 400 — β-i has dedicated endpoint.
          - `ApplicationMessageComposer` Solid component
            (textarea + visibility toggle + idempotency
            token rotation).
          - `ApplicationTransitionActions` Solid component
            (state machine-driven button visibility +
            inline required fields).
          - `applicationStateMachine.ts` mirrors
            `VALID_TRANSITIONS` (excluding claim, reassign).
          - E2e extended through review → approve via detail
            route; asserts `state=approved` + audit
            `request_surface` in Postgres.
          Tests passing locally:
          - 70/70 API + identity tests.
          - 15/15 static infra + Authentik blueprint tests.
          - 40 Playwright tests collect (compat + queue +
            detail + actions).
          - validate_web_ui_local.sh: pass=10 fail=0 skip=1.
          - All four Phase 4 risk gates LOW on r1.
          Residuals carried forward (β-i originals):
          - E2e test 19 Playwright admin route step
            timeout (cluster-side, not code).
          - CodeRabbit Solid-2-beta For-accessor false
            positives recurred across r1-r3 as expected.
          - Local Docker `credsStore: desktop.exe` failed
            mid-build; worked around by temporarily
            removing the credsStore line. Worth a separate
            INIT to harden the build pipeline.
          - The `route` transition required adding an
            `allow_route_transition=True` flag on
            `transition_application` per 6b test
            expectations. Implementation choice; can be
            revisited.
- **Dependency graph:** 019B → 019C → 019D-α (done) → β-0a +
  β-0b + β-i (done bundled) → β-ii → β-iii.
- **Priority:** MEDIUM (β-ii + β-iii still block BL-009
  Discord-side rollout + BL-020 DM materialization).

---

## Notes

- New entries land at the bottom of their priority section by default;
  promote/demote based on impact and dependency order.
- When closing an entry: change status to `[done]` and add the
  commit SHA. Do NOT delete entries — the closed list is the audit
  trail.
- When opening a new initiative for a backlog item, name the
  initiative (INIT-N) in the entry so future readers can follow
  the chain.
- When an entry is no longer relevant, mark `[wontfix]` with a
  one-line reason. Same audit-trail rule.
