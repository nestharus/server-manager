# INIT-135 — Supported-surface risk gate

**Verdict:** LOW

INIT-135 (BL-010 beta-1) ships the public chapter selector on top of
the existing INIT-120 / INIT-127 / INIT-134 public submit substrate:
one new public unauthenticated endpoint
(`GET /api/v1/public/chapters` exposed at `/api/public/chapters`),
one new field-type variant (`chapter_select`) added to the existing
JSONB-backed form-definition fields list as a Pydantic discriminated
union, a public-submit chapter-selector code path that validates a
chapter scope against the current global form, and a SPA renderer that
becomes data-driven for the existing two-field shape and the new
select. The Alembic head, the `notification_envelopes` shape, the
Pomerium routes, the Authentik blueprint, the build pipeline, the
chapter contract, the authority namespace, and the BL-002
seed-public-intake-form fail-closed/no-op invariants are all
preserved. Existing global no-selector forms keep submitting globally;
the chapter-selector path is opt-in by form definition.

## Surfaces touched

### 1. `GET /api/public/chapters` — additive, no route collision

| Surface | Pre | Post | Risk |
|---|---|---|---|
| API mount | `/api/v1/chapters` (authenticated, `services/api/app/api/v1/endpoints/chapters/base.py:35`), `/api/v1/web/admin/chapters` (authenticated, `services/api/app/api/v1/endpoints/web.py:64-69`), `/api/v1/public/applications` (public submit, `services/api/app/api/v1/endpoints/applications/public.py:22-30`) | adds `/api/v1/public/chapters` mounted under the v1 router (`services/api/app/api/v1/router.py:36-58` extension; new `services/api/app/api/v1/endpoints/public_chapters.py`) | additive — distinct path; **no collision** with `/api/v1/chapters/*`, `/api/v1/web/admin/chapters`, or `/api/v1/public/applications` |
| Browser-visible path | `/api/public/applications` proxies to API `/api/v1/public/applications` (`services/api/app/api/v1/endpoints/applications/public.py:22-30`, `containers/server-manager/nginx-web.conf:8-20`-style mapping referenced in `research/15-receipt-required-submit-problem-map.md:84`) | adds `/api/public/chapters` proxying to `/api/v1/public/chapters`; the existing `/api/public/applications` path is unchanged | additive — no collision with `/api/public/applications` |
| Auth | applicant submit requires `verify_applicant_receipt` + `authorize_public_intake` (`services/api/app/api/v1/endpoints/applications/public.py:30-41`) | new endpoint requires no Pomerium principal, no applicant receipt, and no Discord identity; returns only active chapter `id` and `name` (proposal §6, §2 Q2) | none — non-PII, already visible in admin surface (`services/api/app/api/v1/endpoints/web.py:64-69`); does not introduce a new authorization branch |
| Response model | `AdminChapterListRead` exposes `id`, `name`, `state`, `created_at`, `version` (`services/api/app/repositories/web.py:9-21`) | new `PublicChapterListRead` / `PublicChapterSummaryRead` exposes `id`, `name` only (proposal §5) | none — strict subset; admin-only columns (`state`, `version`, `created_at`, templates, configuration, `discord_resources`) intentionally excluded |
| Query | `list_admin_chapters` joins `aggregate_heads` for `version` and orders `created_at DESC, name ASC` capped at 200 (`services/api/app/repositories/web.py:9-21`) | new `services/api/app/services/public_chapters.py` reads `chapters` filtered by `state = 'active'`, ordered by `name ASC`, capped at 200 (proposal §4) | none — read-only; new query; existing `list_admin_chapters` untouched |

Risk on §1: **none** — gate criterion 1 (additive, no collision) holds.
The new path is distinct at every layer: API mount, nginx/proxy mapping,
Pomerium catch-all (see §7 below), and Kong public-intake ingress (see
§7 below). The repository read is a separate query; the existing admin
listing is not reused.

### 2. Migration — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Alembic head | `wu_045_application_public_submit_notifications` (`migrations/versions/wu-045_application_public_submit_notifications.py`) | unchanged — proposal §3 explicitly states "No Alembic schema migration" | none |
| `form_definitions.fields` JSONB column | persists `[{"id":..., "type":..., ...}]` shape (`services/api/app/services/forms.py:78-110`, seed payload `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:44`) | unchanged — `chapter_select` is a new variant in the JSONB blob, not a new column or table; serialized via the existing `field.model_dump(mode="json")` path | none — JSONB tolerates new keys; existing rows continue to round-trip |
| `chapters.state` column | already supports `active` filter (read site at `services/api/app/repositories/web.py:9-21`) | unchanged | none |
| `applications.target_scope_kind` / `target_scope_id` | already accept `chapter` + chapter id (`services/api/app/contracts/applications.py:62-77`, `services/api/app/services/applications.py:733-744` referenced in proposal) | unchanged at the schema level; the public-submit code now persists `chapter` instead of `global` for chapter-selector forms | none |
| `notification_envelopes` / `notification_rules` | INIT-029a + INIT-134 shape | unchanged — INIT-135 emits no new event type and edits no rule | none |
| Other tables | unchanged | unchanged | none |

If implementation later discovers a forced schema migration (e.g., a
constraint that cannot be expressed in JSONB validation), proposal §3
requires it to chain off the current head
`wu_045_application_public_submit_notifications` and remain additive
(no destructive `ALTER TABLE`, no column drops, no renames). The
beta-1 path explicitly has no migration.

Risk on §2: **none** — gate criterion 2 (additive only) holds vacuously
because no migration is introduced.

### 3. Form definition contract — extending the field-type discriminated union with `chapter_select` is backwards-compatible

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `ApplicationFormField` | single Pydantic class with `type: Literal["short", "long", "number", "select", "multi_select", "boolean"]`, `id`, `label`, `required`, `max_length`, `options`, `extra="forbid"`, `FIELD_ID_PATTERN`, label trim/length validation (`services/api/app/contracts/applications.py:80-141`) | becomes a Pydantic discriminated union over `type` preserving every existing variant verbatim plus `FormFieldChapterSelect` (proposal §5). JSON keys remain `id`/`type`. | additive — every currently-accepted field shape continues to validate. Existing JSONB rows with `type` ∈ `{short, long, number, select, multi_select, boolean}` round-trip identically |
| `FormFieldChapterSelect` shape | n/a | **new**: `id: str`, `type: Literal["chapter_select"]`, `label: str`, `required: Literal[True] = True`, `placeholder: str \| None = None` (proposal §5). Reuses `FIELD_ID_PATTERN` and label trim/length rules. | additive |
| `FormDefinitionPublish.fields` discriminator | `list[ApplicationFormField]`, `min_length=1`, unique-id validator (`services/api/app/contracts/applications.py:155-181`) | `list[ApplicationFormField]` where `ApplicationFormField` is the discriminated union; same `min_length`, same unique-id validator | none — type-list extension, not a removal or rename |
| Seed payload | `[{"id":"character_name","label":"Character name","type":"short","required":true},{"id":"application_text","label":"Application text","type":"long","required":true}]` (`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:44`) | seed payload v2 includes a `chapter_select` field plus the existing two text fields; existing seed v1 row remains a valid form definition under the new union (proposal §3 / §11) | additive |
| Existing in-flight forms | text-only fields, `routing_rules` defaults applied via `_effective_routing_rules` (`services/api/app/services/forms.py:55-59`) | continue to validate, publish, and read with no contract changes | none |

The discriminator extension is a **strict superset** of the current
field-type set: every currently-stored or currently-published form
definition without a `chapter_select` field continues to parse,
serialize, persist, and submit identically. The opt-in property is
holistic — only forms that contain a `chapter_select` field activate
the new chapter-selector submit path; every other form follows the
existing global submit path (proposal §4 / §11).

Risk on §3: **none** — gate criterion 3 (text-only field forms still
parse) holds. The discriminated union widening is backwards-compatible
because (a) the JSON shape `{id, type, label, ...}` is preserved, (b)
the discriminator key (`type`) and existing values are preserved, (c)
no field is renamed or removed, and (d) the seed migration only
upgrades the deterministic seed row when the current global form is
still the prior seed (`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:193-211`,
proposal §3).

### 4. Submit endpoint signature/response — unchanged

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Route | `POST /api/v1/public/applications` (`services/api/app/api/v1/endpoints/applications/public.py:22`) | unchanged | none |
| Request body | `PublicApplicationSubmission { scope: ApplicationScope, responses: dict[str, JSONValue], client_application_id: str \| None }` (`services/api/app/contracts/applications.py:221-241`) | unchanged at the contract level — chapter-selector forms set `scope.scope_kind="chapter"`, `scope.scope_id=<chapter id>`, and put the same id in `responses[chapterFieldId]`; both are already valid under the existing schema (`ApplicationScope` accepts `scope_kind ∈ {global, chapter, member}`, `services/api/app/contracts/applications.py:62-77`) | none |
| Auth dependencies | `Depends(verify_applicant_receipt)` + `Depends(authorize_public_intake)` (`services/api/app/api/v1/endpoints/applications/public.py:30-41`) | unchanged | none |
| Response model | `PublicApplicationSubmissionReceipt { message, application_id }` (`services/api/app/contracts/applications.py:244-247`) | unchanged | none |
| Status code | `HTTPStatus.CREATED` (201) | unchanged | none |
| Error mapping | `raise_known_application_error(error)` (`services/api/app/api/v1/endpoints/applications/public.py:42-43`) | unchanged | none — additional 422 validation paths (missing chapter response, inactive chapter, response/scope mismatch) raise existing `InvalidApplicationResponseError` (`services/api/app/contracts/applications.py:459-460`) and route through the existing error mapper |
| Endpoint signature `submit_public_application_endpoint` | unchanged | unchanged | none |
| Service-level signature `submit_public_application_with_receipt` | takes `(db, body, *, discord_user_id)` and returns the application UUID | unchanged signature; body extends `_submit_application_internal` flow with chapter-selector form-scope resolution and target-scope override (proposal §4 / §5) | none on the public function shape |
| Notification emit relative to commit | post-commit, wrapped in `try/except` (INIT-134, `services/api/app/services/applications.py:870-885` per `plans/risk/init-134-supported-surface.md`) | unchanged | none |

Risk on §4: **none** — gate criterion 4 (signature/response unchanged)
holds. The HTTP wire contract and the receipt response shape are
byte-identical. The new chapter-selector behavior is reachable only
through legitimate `scope_kind="chapter"` + matching `responses` from
forms that contain a `chapter_select` field; without such a form, the
existing global submit path applies unchanged.

### 5. Existing global-scope public form (BL-002 seed) keeps working

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Seed job semantics | inserts deterministic global form when no current global form exists, no-ops when the seed row is current, fails closed when an aggregate head exists without a current row, skips when an officer-published form is current (`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:14-31`, `:193-211`) | unchanged contract; the seed payload is bumped to a new `(form_id, version)` derivation (proposal §3) but only inserts when (a) no current global form exists or (b) the prior seed row is still current and the seed advances forward in the same fail-closed/no-op pattern | none — the BL-002 fail-closed invariant is preserved |
| Existing officer-published global forms | `seed_public_intake_form_outcome` returns `'officer-published form present; skipping seed'` (`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:204-208`) | unchanged | none |
| Existing non-selector global form submit path | reads current global form, submits with `scope_kind="global"`, persists `target_scope_kind="global"` (`services/api/app/services/applications.py:708-714` referenced in proposal) | unchanged when the current global form contains no `chapter_select` field; only forms that contain `chapter_select` activate the chapter-scoped target-scope override (proposal §4 / §11) | none — opt-in by form definition |
| `form_snapshot.scope_kind` / `form_snapshot.scope_id` for chapter-selector submits | n/a | remain `global` / `null` (the form definition is global); `target_scope_kind` / `target_scope_id` move to the selected chapter (proposal §4 "Persisted application behavior") | none — preserves the form definition's actual scope source while routing to the selected chapter |
| Submit `request_surface` | `api:/api/v1/public/applications` | unchanged | none |
| Public submit notification emit (INIT-134) | post-commit `application.public_submitted` event, isolated by `try/except` | unchanged — INIT-135 introduces no new event type and edits no allowlist | none |

Risk on §5: **none** — gate criterion 5 (existing global-scope public
form keeps working) holds. The seed remains a global public form
source, the BL-002 fail-closed invariant is preserved, and the public
submit flow without `chapter_select` follows the existing global path
unchanged.

### 6. Existing tests + e2e continue passing

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `services/api/tests/test_forms.py` | publishes/reads text-field forms (`services/api/tests/test_forms.py:88-175`) | additive — extends with `chapter_select` round-trip plus invalid-shape coverage (duplicate `chapter_select`, `required=false`, non-global scope, blank id/label, conflicting `routing_rules.review_scope`) (proposal §7 TG-1). Existing assertions preserved verbatim. | additive |
| `services/api/tests/test_public_intake_submit.py` + `services/api/tests/public_intake_fixtures.py` | existing receipt/audit/notification assertions for global no-selector path (`:48-139`, `:91-170` referenced in INIT-134 surface) | additive — adds chapter-selector submit tests (target_scope assertions, missing chapter response, inactive chapter, scope/response mismatch) (proposal §7 TG-3). Existing global-no-selector assertions preserved verbatim. | additive |
| `services/api/tests/test_public_chapters.py` | n/a | **new** — endpoint contract + active-only filter coverage (proposal §3, §7 TG-2). Does not reuse `/api/v1/web/admin/chapters` tests | additive |
| `services/api/tests/test_notification_materialization.py` (INIT-134) | preserved per INIT-134 gate | unchanged — INIT-135 adds zero notification rules and zero events | none |
| `services/discord/tests/test_notifications.py` (INIT-134) | preserved per INIT-134 gate | unchanged — INIT-135 ships zero discord daemon changes | none |
| `services/web/tests/compat.spec.ts` | β-i / β-ii / β-iii applicant compat (`:18-30`, `:115-140`, `:278-299`) | additive — mocks `/api/public/chapters`, asserts the chapter select renders, blocks submit on empty required value, and posts `scope.scope_kind="chapter"` with matching `responses[chapterFieldId]` (proposal §7 TG-4). Existing applicant compat assertions preserved verbatim. | additive |
| `services/web/tests/officer-queue.spec.ts` / `officer-detail.spec.ts` | β-iii officer flows | unchanged — INIT-135 touches zero officer routes / components | none |
| `services/api/tests/test_web_officer_applications.py` (incl. dependency-tree guard `:1110-1147`) | β-iii officer endpoint contract | unchanged — INIT-135 introduces zero officer endpoints; dependency-tree guard remains satisfied because no new officer route is added | none |
| `infra/tests/test_applicant_discord_pomerium.py` | INIT-127 / INIT-134 Pomerium static-route assertions | unchanged — INIT-135 introduces zero Pomerium route changes (see §7 below) | none |
| `infra/tests/fixtures/web-ui/contract.json` | β-i / β-iii two-field hardcoded shape (`:99-141`, `:117`) | additive — extends contract to data-driven fields + chapter endpoint fixture + selected chapter fixture + chapter-scoped submit payload (proposal §3) | additive |
| `infra/tests/validate_web_ui_local.sh` | asserts current two-field shape (`:118-124`, `:155-156`) | additive — assertions updated to match the richer contract and require `/api/public/chapters` coverage; the `/api/public/applications` rendered ingress assertion (`infra/tests/validate_application_workloads_local.sh:212`) is preserved | additive |
| `infra/tests/e2e/lib/playwright/browser-flow.mjs` (`:91-129`) | β-iii browser flow fills two text fields | additive — extended to fill select fields from the web contract and persist the selected chapter id in the submit session record. Existing fill behavior preserved. | additive |
| `infra/tests/e2e/tests/19-web-ui.sh` (β-i / β-iii / INIT-134 e2e: `assert_public_submit_persisted`, `assert_officer_review_persisted`, `assert_officer_detail_checked`, INIT-134 notifications/envelopes assertions) | preserved per INIT-134 gate (`:8-80`, `:18-38`, `:238-268`) | additive — `assert_public_submit_persisted` extended to read `target_scope_kind='chapter'`, `target_scope_id=<selectedChapterId>`, and confirm `form_snapshot.scope_kind='global'`. Officer queue/detail assertions unchanged. INIT-134 notification assertions unchanged. Suite count stays at 19. | additive |
| Live-guild fixture guard (INIT-134 TG-2b) | preserved per INIT-134 gate | unchanged — INIT-135 introduces no new fixture channel/role/guild ids | none |

Risk on §6: **none** — gate criterion 6 (existing tests + e2e continue
passing) holds. INIT-135 preserves every existing assertion verbatim
and only **adds** assertions and fixtures. Suite count remains 19.

### 7. Pomerium / Authentik / Kong public-intake ingress

**No new Pomerium routes. No new Authentik blueprint. No identity-header
changes.**

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Pomerium `routes:` (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:48-105`) | eight specific web-host routes (`/api/me`, `/api/web/admin/`, `/api/web/officer/`, `/applications/queue`, `/applications/queue/`, `/applications/`, `/admin`, `/auth/discord/`), the public catch-all `from: https://web.local.humility.local … allow_public_unauthenticated_access: true`, and the protected-api host | **unchanged** — `/api/public/chapters` does not match any of the more-specific routes (none are prefixed `/api/public/...`) and falls through to the public catch-all, exactly as `/api/public/applications` does today (proposal §6, supported-surface check criterion 7) | none — explicitly the gate criterion 7 case |
| Pomerium `pass_identity_headers` / `idp_*` config | unchanged from INIT-127/INIT-134 (`:32-47`) | unchanged | none |
| Authentik blueprint (`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml`) | INIT-127 + INIT-134 | unchanged — no new application, provider, source, scope mapping, or property mapping | none |
| `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml` (Kong Ingress on `web.local.humility.local`, attaching the `public-intake-rate-limit` plugin to `/api/public/applications` + `/api/applications`, `:24-37`) | two paths routed to `pomerium-proxy` | additive — adds `/api/public/chapters` path entry to the same Kong Ingress so the public chapter list is rate-limited alongside the existing public submit (proposal §3). This is a **Kong ingress path entry**, not a Pomerium route; Pomerium continues to handle `/api/public/chapters` via its existing public catch-all | additive Kong ingress path; **no new Pomerium route** |
| `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml` (Kong Ingress on `api.local.humility.local`, `:33-43`) | one path `/api/v1/public/applications` to `server-manager-api:8000` | additive — adds `/api/v1/public/chapters` path entry so direct API host requests are rate-limited alongside the existing public submit (proposal §3) | additive Kong ingress path; no new auth surface |
| `infra/tests/test_applicant_discord_pomerium.py` | β-iii Pomerium static route assertions | unchanged — every existing assertion holds because the Pomerium config is byte-identical | none |

Risk on §7: **none** — gate criterion 7 (no new Authentik blueprints,
no new Pomerium routes; existing public catch-all covers
`/api/public/chapters`) holds. The two Kong ingress path additions
attach the existing `public-intake-rate-limit` plugin to the new path
in the same channel-local pattern as the existing public submit; they
introduce no new Pomerium route, no new Authentik object, no new
identity-header path, and no new auth dependency.

### 8. Environment variables / settings — none new

| Setting | Pre | Post | Required? | Risk |
|---|---|---|---|---|
| `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `SUPABASE_DB_URL`, `SUPABASE_SERVICE_KEY` | required (`services/api/app/core/settings.py:21-30`) | unchanged | required (existing) | none |
| `WEB_PUBLIC_BASE_URL` (INIT-134 F-7-A) | required (`services/api/app/core/settings.py:24`) | unchanged | required (already wired in `local`) | none — already in place |
| `GLOBAL_APPLICATIONS_REVIEW_CHANNEL_ID`, `GLOBAL_APPLICATION_MANAGERS_ROLE_ID`, `GLOBAL_PRIMARY_GUILD_CHANNEL_URL` (INIT-134) | optional (`services/api/app/core/settings.py:25-27`) | unchanged | optional | none |
| Applicant OIDC / receipt settings (`:39-60`) | INIT-127 set | unchanged | unchanged | none |
| Discord daemon settings | INIT-134 set | unchanged | unchanged | none |
| `gitops/channels/local/applications/server-manager/api-deployment.yaml` env injection | INIT-134 set | unchanged — no new env keys to wire | n/a | none |
| `gitops/channels/local/applications/server-manager/discord-deployment.yaml` | INIT-134 dry-run posture | unchanged | n/a | none |
| Fixture / Infisical secrets | INIT-134 set | unchanged — no new fixture values; chapter id/name come from already-seeded test chapter rows | n/a | none |

Risk on §8: **none** — gate criterion 8 (no new env vars) holds. The
`Settings` class (`services/api/app/core/settings.py:13-67`) is
unchanged; `load_settings` and `_missing_env_vars_from_error` keep
their existing behavior.

### 9. Database schema — no new schema

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Alembic head | `wu_045_application_public_submit_notifications` | unchanged | none |
| `form_definitions.fields` JSONB | persists `[{"id":..., "type":..., ...}]` (`services/api/app/services/forms.py:78-110`) | unchanged — `chapter_select` is a new JSON shape inside the existing JSONB column. No new column, no new index, no new constraint, no enum widening at the DB level (the `type` field is application-level Pydantic discriminator, not a Postgres enum) | none |
| `form_definitions` table | INIT-122 baseline | unchanged | none |
| `chapters` table | INIT-019 + INIT-042 governance | unchanged — `state` column already supports `active` filter | none |
| `applications` table | accepts `target_scope_kind ∈ {global, chapter, member}` and `target_scope_id` (`services/api/app/contracts/applications.py:62-77`) | unchanged at the schema level; chapter-selector submit persists `chapter` instead of `global` for the affected rows | none |
| `aggregate_heads` / `activity_actions` / `activity_state_changes` | INIT-120 substrate | unchanged | none |
| `notification_envelopes` / `notification_rules` / `notification_events` | INIT-029a / INIT-134 | unchanged | none |
| `application_messages` (INIT-133B-iii) | unchanged | unchanged | none |

Risk on §9: **none** — gate criterion 9 (`chapter_select` reuses
existing `form_definitions.fields` JSONB) holds. Proposal §3 requires
no Alembic migration; if implementation discovers an unavoidable
schema constraint, it must remain additive and chain off the current
head (`wu_045_application_public_submit_notifications`).

### 10. Authority / permission namespace — none new

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Permission namespace | INIT-104 / INIT-128 / INIT-131 / β-iii names (`application.{review, claim, route, message, withdraw, reassign, request_interview, waitlist, approve, deny, reactivate}`) | unchanged | none |
| New grants issued by the slice | none | **none** — proposal §6 "no new authorization branch": the public chapter list is an unauthenticated read of a non-PII subset of an existing admin-visible field set; the public submit auth chain (`verify_applicant_receipt` + `authorize_public_intake`) is unchanged | none |
| `authorize_public_intake` policy surface | INIT-120 / INIT-127 | unchanged | none |
| Officer authority surface (`_build_officer_actor`, β-iii authority requirements) | unchanged | unchanged | none |
| Cedar policy bundles | INIT-127 / INIT-134 | unchanged — INIT-135 adds no new Cedar policy entry | none |
| Live Discord-visible writes (Tier 3, AGENTS.md:18-26) | not introduced | not introduced — proposal §8 explicitly excludes any live Discord write/send/channel/role change | none |

Risk on §10: **none** — gate criterion 10 (no new permission namespace)
holds. The new public chapter list endpoint adds zero authority/grant
surface; the chapter-selector submit reuses the existing applicant
receipt + Cedar `authorize_public_intake` chain.

## Verdict reasoning

LOW.

1. **Public chapter list (gate §1)**: `/api/public/chapters` is a
   distinct path at every layer (API mount, nginx/proxy mapping,
   Pomerium catch-all, Kong public-intake ingress). It does not
   collide with `/api/v1/chapters/*`, `/api/v1/web/admin/chapters`, or
   `/api/v1/public/applications`. It exposes only `id` and `name` for
   `state='active'` rows — a strict subset of the admin field set —
   and uses no auth dependency, no Discord identity, and no applicant
   receipt.
2. **Migration (gate §2)**: zero. Proposal §3 explicitly requires "No
   Alembic schema migration." The Alembic head remains
   `wu_045_application_public_submit_notifications`.
3. **Form definition contract (gate §3)**: discriminated union
   widening over `type`. Existing variants (`short`, `long`, `number`,
   `select`, `multi_select`, `boolean`) preserved verbatim with the
   same JSON keys (`id`, `type`, `label`, `required`, `max_length`,
   `options`), the same `FIELD_ID_PATTERN`, and the same label
   trim/length validation. Existing JSONB rows continue to round-trip
   identically; existing forms without `chapter_select` continue to
   parse and submit identically.
4. **Submit endpoint (gate §4)**: route, request body shape, response
   model, status code, error mapping, auth dependencies, endpoint
   signature, and service-level signature are byte-identical. The
   chapter-selector behavior is reachable only through legitimate
   `scope_kind="chapter"` + matching `responses[chapterFieldId]` from
   forms that contain a `chapter_select` field; without such a form,
   the existing global submit path applies unchanged.
5. **Existing global form (gate §5)**: BL-002 seed fail-closed and
   no-op invariants are preserved
   (`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:14-31`,
   `:193-211`). The seed advance is gated on the prior seed row being
   current; officer-published forms are skipped. Forms without
   `chapter_select` continue to submit globally with
   `target_scope_kind='global'`.
6. **Existing tests (gate §6)**: every existing assertion in
   `test_forms.py`, `test_public_intake_submit.py`,
   `test_notification_materialization.py`, `test_notifications.py`,
   `compat.spec.ts`, `officer-queue.spec.ts`,
   `officer-detail.spec.ts`, `test_web_officer_applications.py` (incl.
   the dependency-tree guard), `test_applicant_discord_pomerium.py`,
   `validate_web_ui_local.sh`, and `19-web-ui.sh` is preserved
   verbatim or extended additively. Suite count stays at 19.
7. **Pomerium / Authentik / Kong (gate §7)**: zero Pomerium route
   changes — `/api/public/chapters` falls through to the existing
   public catch-all (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:97-100`)
   exactly as `/api/public/applications` does today. Zero Authentik
   blueprint changes, zero identity-header changes. Two additive Kong
   ingress path entries attach the existing `public-intake-rate-limit`
   plugin to the new path in the same per-channel pattern as the
   existing public submit; this introduces no new auth surface.
8. **Env vars (gate §8)**: zero new env vars. The `Settings` class is
   unchanged; INIT-134's `WEB_PUBLIC_BASE_URL` and the GLOBAL_* trio
   remain in their post-INIT-134 state and are already wired in the
   `local` channel.
9. **Database schema (gate §9)**: zero schema changes.
   `form_definitions.fields` is JSONB and accommodates the new field
   variant via Pydantic discriminator widening only. No new column, no
   new index, no new constraint, no Postgres enum widening, no new
   table.
10. **Authority namespace (gate §10)**: zero. The public chapter list
    has no auth dependency; public submit reuses the existing
    `verify_applicant_receipt` + `authorize_public_intake` chain. No
    new Cedar policy entry, no new permission name, no new actor kind.

Tier 3 (live Humility guild send) remains explicitly out of scope per
proposal §8; the local Discord deployment stays at its existing
dry-run posture inherited from INIT-134; the e2e suite uses fixture
test chapters and is bolstered by the INIT-134 live-guild fixture
guard, which INIT-135 does not weaken.

The slice has **zero** tracked findings against the ten gate criteria.
The single audit-relevant property to keep an eye on during
implementation is the discriminated-union JSON-shape preservation:
existing JSONB rows must round-trip without an `extra="forbid"` regression
on legacy field shapes. The proposal §5 contract preview keeps
`extra="forbid"` on each variant individually rather than widening it,
so existing rows that match an existing variant continue to validate;
new keys only appear under `type="chapter_select"`.

Verdict: **LOW**.

SUPPORTED_SURFACE_DONE: plans/risk/init-135-supported-surface.md
