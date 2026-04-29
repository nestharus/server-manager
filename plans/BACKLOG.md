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

### BL-008 [in-progress, sub-slice A done] — Discord OAuth linking + synthetic→real member conversion

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
  - **BL-017** — INIT-125C member link/conversion service +
    application re-pointing.
  - **BL-018** — INIT-125D historical cleanup / read-hardening
    for roster/trust synthetic pollution.

### BL-009 [paused — blocked on BL-016 + BL-019] — INIT-126: Discord-visible side effects for public web submissions

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

### BL-010 [open] — INIT-123: Web form richer inputs (chapter selector, multi-page, file upload)

- **Source:** `proposals/02-public-application-intake.md:445` (Out
  of scope for follow-up)
- **Description:** Day-1 form has two visible fields targeting
  global scope. Roadmap wants chapter selection, file uploads,
  multi-page forms with conditional fields. The fixture
  `infra/tests/fixtures/web-ui/contract.json` is the contract
  surface to extend.
- **Plan:** New initiative when product priority surfaces. Touch:
  SPA form renderer, `form_definitions.fields` shape, validator,
  and the e2e contract.

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

### BL-017 [open] — INIT-125C: Member link/conversion service + application re-pointing

- **Source:** Decomposition of BL-008
- **Description:** Add `member_links` (or equivalent supersession)
  table + conversion service. On verified Discord OAuth handshake,
  link synthetic→real member, re-point `applications.applicant_id`
  with per-application audit/version updates, emit notification
  event(s). Handle conflict cases for duplicate
  `client_application_id` across synthetic and real submissions.
- **Plan:** Pick up after BL-016 lands the OAuth surface.
- **Priority:** MEDIUM

### BL-018 [open] — INIT-125D: Historical cleanup + read-hardening for roster/trust synthetic pollution

- **Source:** Decomposition of BL-008; also closes BL-005's
  read-side residual.
- **Description:** Explicit read filters for any roster/trust
  surfaces that still need them post-INIT-124. One-shot cleanup
  Job that scans `roster_entries`, `trust_profiles`, etc. for
  synthetic refs and either removes or annotates them. In current
  `humility-local` the job should report zero rows since INIT-124
  guards landed before any synthetic pollution leaked.
- **Plan:** Pick up after BL-017 (conversion service) so cleanup
  has a "linked → keep, unlinked synthetic → drop" rule.
- **Priority:** LOW (residual; no known leaked rows in
  humility-local).

### BL-019 [open] — In-product application review surface (chapter roles + assignment + private channels + transcripts)

- **Source:** Surfaced in BL-009 product-direction discussion
  with user (2026-04-29).
- **Description:** The user-confirmed BL-009 design depends on
  an in-product (NOT Discord-mediated) application review
  surface that doesn't yet exist. Required capabilities:
  - Chapter-scoped officer roles for "application managers"
    (assigned + managed from the product, not Discord roles).
  - Application assignment / claim flow (an officer claims an
    application from the queue).
  - Private reviewer↔applicant channels per application
    (in-product chat/messaging — Discord is not the surface).
  - Transcript persistence for those private channels.
  - The "routes back to application" link in the BL-009 Discord
    embed lands here.
- **Plan:** Substantial new initiative. Likely decomposes into:
  - role/permission model for chapter-scoped officers
  - application claim/assign flow
  - in-product messaging substrate (or reuse of existing
    notification/event substrate)
  - transcript schema + retention policy
- **Priority:** MEDIUM (blocks BL-009 Discord-side rollout).

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
