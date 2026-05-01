# INIT-136 — Supported-surface risk gate

**Verdict:** LOW

INIT-136 (BL-010 beta-2) widens the existing `_BaseFormField`
contract with two optional attributes — `page: int` (default `1`)
and `visible_when: FormFieldVisibleWhen | None` (default `None`) —
extends `validate_application_responses` with a deterministic
visibility pass, and converts the SPA `ApplicationFormRoute.tsx`
renderer into a single-page-at-a-time wizard with a shared
visibility evaluator. The HTTP submit wire shape, the public
chapters endpoint, the authenticated chapter-specific submit path,
the Alembic head, the Pomerium routes, the Authentik blueprint,
the GitOps seed pattern, the env-var set, and the BL-002 seed
fail-closed/no-op invariants are all preserved. Forms published
under β-1 (with no `page` and no `visible_when` keys in
`form_definitions.fields` JSONB) round-trip identically: the
proposal locks `page` to default `1` and `visible_when` to default
`None` on the shared base, so legacy rows continue to parse, every
field stays "always visible," and the wizard derives a single
implicit page-1 step.

## Surfaces touched

### 1. Existing β-1 v2 forms (no `page` key) keep working — defaults to `page=1`

The β-1 contract stores fields as a Pydantic discriminated union
over `type` rooted in `_BaseFormField` (`services/api/app/contracts/applications.py:80-100`,
`:192-201`). Today's variants — `FormFieldShort`, `FormFieldLong`,
`FormFieldNumber`, `FormFieldSelect`, `FormFieldMultiSelect`,
`FormFieldBoolean`, `FormFieldChapterSelect` — inherit `id`,
`label`, `required` from `_BaseFormField` and carry
`model_config = ConfigDict(extra="forbid")` via `_ApplicationModel`
(`services/api/app/contracts/applications.py:21-22`).

| Surface | Pre (β-1) | Post (β-2) | Risk |
|---|---|---|---|
| `_BaseFormField` shape | `id`, `label`, `required` (`services/api/app/contracts/applications.py:80-100`) | adds `page: int = Field(default=1, ge=1)` and `visible_when: FormFieldVisibleWhen \| None = None` (proposal §3 "Contracts") | **none** — strict additive default-bearing fields. Existing JSONB rows omitting both keys round-trip: `page` defaults to `1`, `visible_when` defaults to `None`; `extra="forbid"` is unaffected because the new keys are *defined* on the base, not "extra" |
| Persisted JSONB shape | `[{"id":..., "type":..., "label":..., "required":..., ...}]` (`services/api/app/services/forms.py:78-110`, seed payload at `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:44`) | unchanged on disk for legacy rows; new published forms may include `page` and `visible_when`, persisted through the existing `field.model_dump(mode="json")` path | **none** — JSONB column tolerates new keys; old rows stay readable |
| `_APPLICATION_FORM_FIELD_ADAPTER` re-parse path | `TypeAdapter(ApplicationFormField).validate_python(raw)` inside `validate_application_responses` (`services/api/app/services/applications.py:496-508`) | unchanged call site; the adapter automatically picks up the new optional attributes on `_BaseFormField` and applies defaults when the keys are absent | **none** — the call site is the same; the adapter behavior on legacy dicts is identical because `page` and `visible_when` have defaults |
| `FormDefinitionPublish` publish-time validation | unique field ids, `min_length=1`, `chapter_select` contract (`services/api/app/contracts/applications.py:215-256`) | adds page-value validation, predicate source existence, earlier-field ordering, supported source field types, and `chapter_select` non-conditional restriction (proposal §3 "Contracts" + §2 Q1, Q2) | **none** — every new check fires only when the authored JSON includes `page > 1` or `visible_when`; legacy authored payloads without those keys publish exactly as today |
| Wizard navigation when `page=1` is the only derived page | n/a | when every field defaults to `page=1` and no `visible_when` is set, the wizard derives one step `Step 1 of 1`, renders all fields on that single step, and `Submit application` appears on it (proposal §2 Q3) | **none** — single-derived-page is functionally equivalent to today's flat render. No `Next`/`Previous` button is reachable when `M=1` |

Risk on §1: **none**. Existing β-1 forms (the BL-002 seed v2 and
any officer-published global form authored under β-1) preserve
their semantics byte-for-byte. The Pydantic default machinery
keeps `page=1` for any field that omits `page`, so the runtime
visible-page set degenerates to a single implicit page that
matches today's flat render.

### 2. Existing β-1 forms without `visible_when` keep working — field always visible

The proposal locks `visible_when: FormFieldVisibleWhen | None = None`
on `_BaseFormField` and locks the visibility evaluator to treat
`visible_when is None` as "always visible." Both the SPA renderer
(proposal §3 "SPA Renderer") and the server-side validator
(proposal §3 "Submit Validator") share this rule.

| Surface | Pre (β-1) | Post (β-2) | Risk |
|---|---|---|---|
| Server visibility pass | `validate_application_responses` parses fields, rejects unknown response keys, checks required fields, type-validates submitted values (`services/api/app/services/applications.py:496-559`) | **adds** a deterministic visibility pass (proposal §3 "Submit Validator" steps 1-7): parse fields preserving authored order, build response lookup, evaluate `visible_when` referencing only earlier visible source fields, produce visible field map, reject hidden-field response keys, require only visible required fields, type-validate submitted visible values | **none** for legacy forms — when `visible_when is None` on every field the visibility map becomes *all fields visible*, and every step of the new pass collapses to its current behavior: unknown keys still rejected, all `required=true` fields still required, all submitted values still type-validated |
| `chapter_select` always-visible guarantee | `chapter_select` is the routing field for the chapter-selector public submit override (`services/api/app/services/applications.py:780-784`, `_chapter_selector_override` per `plans/risk/init-135-supported-surface.md` §4) | proposal §2 Q6 forbids `visible_when` on `chapter_select` and forbids referencing `chapter_select` as a predicate source (publish-time validation) | **none** — the β-1 chapter-selector override gate stays narrow: current global form contains a required `chapter_select`, request sends `scope_kind=chapter`, submitted chapter response equals `scope.scope_id` (`services/api/app/services/applications.py:780-784`). Conditional visibility cannot hide that routing field |
| SPA visibility evaluation | flat render of `formDefinition().fields.map(...)` (`services/web/src/features/public/ApplicationFormRoute.tsx:172-183`) | shared pure helper used by render, navigation, and submit payload assembly; `visible_when is None` ⇒ visible (proposal §3 "SPA Renderer") | **none** — legacy forms render every field, every page-1 derived step, exactly as today |
| Submit payload assembly | builds responses from every field in `form.fields` | builds responses from visible fields only (proposal §3 "SPA Renderer") | **none** — for legacy forms with no `visible_when`, "visible fields only" equals "every field," so the wire shape of the POST body is identical to β-1 |
| `extra="forbid"` regression | each variant inherits `extra="forbid"` from `_ApplicationModel` (`services/api/app/contracts/applications.py:21-22`) | unchanged; `page` and `visible_when` are defined keys on the base, not "extra" | **none** — legacy JSONB rows do not introduce undefined keys, so `extra="forbid"` continues to admit them |

Risk on §2: **none**. The visibility pass is a strict no-op for
forms whose fields all have `visible_when is None`, which is
every β-1-published form including the BL-002 seed v2.

### 3. Submit endpoint signature unchanged

| Surface | Pre (β-1) | Post (β-2) | Risk |
|---|---|---|---|
| Route | `POST /api/v1/public/applications` (`services/api/app/api/v1/endpoints/applications/public.py:22-25`) | unchanged | **none** |
| Request contract | `PublicApplicationSubmission { scope: ApplicationScope, responses: dict[str, JSONValue], client_application_id: str \| None }` (`services/api/app/contracts/applications.py:296-316`) | unchanged — proposal §1 explicitly states "The submit response shape stays the beta-1 shape: `responses: dict[str, JSON]`. There is no per-page submit API and no draft API in this slice." | **none** |
| Auth dependencies | `Depends(verify_applicant_receipt)` + `Depends(authorize_public_intake)` (`services/api/app/api/v1/endpoints/applications/public.py:30-41`) | unchanged | **none** |
| Response model | `PublicApplicationSubmissionReceipt { message, application_id }` (`services/api/app/contracts/applications.py:319-321`) | unchanged | **none** |
| Status code | `HTTPStatus.CREATED` (201) | unchanged | **none** |
| Endpoint signature `submit_public_application_endpoint` | `(body, identity=Depends(verify_applicant_receipt), db=Depends(get_db), _authz=Depends(authorize_public_intake))` (`services/api/app/api/v1/endpoints/applications/public.py:30-35`) | unchanged | **none** |
| Service-level signature `submit_public_application_with_receipt` | takes `(db, body, *, discord_user_id)` and returns the application UUID | unchanged; visibility-pass logic lands inside `_submit_application_internal` at the existing `validate_application_responses` call site (`services/api/app/services/applications.py:814-819`) | **none** |
| Error mapping | `raise_known_application_error(error)` (`services/api/app/api/v1/endpoints/applications/public.py:42-43`) | unchanged — new validation paths (hidden-field response, missing visible required, stale dependent value) raise existing `InvalidApplicationResponseError` (`services/api/app/contracts/applications.py:534-535`) and route through the existing error mapper | **none** |
| Per-page submit / draft API | not introduced | **explicitly not introduced** (proposal §1, §5 "Anti-Scope") | **none** |

Risk on §3: **none**. The HTTP wire contract, the receipt
response shape, the auth chain, and the FastAPI signatures remain
byte-identical. The new visibility-pass behavior is reachable only
through legitimate `responses` payloads against forms that
actually contain `visible_when` predicates; without such
predicates, the validator is a strict no-op overlay.

### 4. Public chapters endpoint untouched

The β-1 public chapter list endpoint
(`GET /api/v1/public/chapters`, exposed at
`/api/public/chapters`) is the SPA's substrate for resolving
chapter ids when a `chapter_select` field is present
(`services/api/app/api/v1/endpoints/public_chapters.py:12-20`).
β-2 introduces multi-page wizards and conditional fields; it does
not touch the chapters endpoint at any layer.

| Surface | Pre (β-1) | Post (β-2) | Risk |
|---|---|---|---|
| Route mount | `APIRouter(prefix="/api/v1/public/chapters")`, no auth dependencies (`services/api/app/api/v1/endpoints/public_chapters.py:12-20`) | unchanged | **none** |
| Response model | `PublicChapterListRead` exposing `[{id, name}]` for `state='active'` rows | unchanged | **none** |
| Service `list_public_chapters` | active-only query, ordered by `name ASC`, capped at 200 | unchanged | **none** |
| SPA fetch | `services/web/src/api/client.ts` chapter helpers; called only when the loaded form contains a `chapter_select` field (`plans/risk/init-135-supported-surface.md` §3) | unchanged — proposal §3 "SPA Renderer" preserves the β-1 chapter-select submit behavior including the conditional fetch | **none** |
| Pomerium / Kong ingress | `/api/public/chapters` served via the existing public catch-all and the existing Kong `public-intake-rate-limit` plugin entries (`plans/risk/init-135-supported-surface.md` §7) | unchanged — proposal §3 introduces zero ingress changes | **none** |
| Auth posture | public, no Pomerium principal, no applicant receipt, no Discord identity | unchanged | **none** |

Risk on §4: **none**. The chapters endpoint, its service, its
ingress, and its auth posture are all preserved verbatim.

### 5. No env vars / migrations / GitOps changes

| Surface | Pre (β-1) | Post (β-2) | Risk |
|---|---|---|---|
| Alembic head | `wu_045_application_public_submit_notifications` (`migrations/versions/wu-045_application_public_submit_notifications.py`) | unchanged — proposal §3 introduces no migration. `form_definitions.fields` is JSONB; `page` and `visible_when` are new keys inside the existing column shape, not new columns/indexes/constraints | **none** |
| `Settings` class | post-INIT-134 set (`services/api/app/core/settings.py`) | unchanged — proposal introduces zero new env keys, zero new optional/required settings | **none** |
| GitOps Pomerium routes | INIT-127 / INIT-134 / INIT-135 set (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:48-105`) | unchanged | **none** |
| GitOps Authentik blueprint | INIT-127 / INIT-134 set (`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml`) | unchanged | **none** |
| Kong ingress | post-INIT-135 set with `/api/public/applications` + `/api/public/chapters` rate-limited paths (`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`, `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`) | unchanged — no new public route to rate-limit | **none** |
| BL-002 seed-public-intake-form invariant | seeds deterministic global form, no-ops on officer-published current, fails closed when an aggregate head exists without a current row, no-ops on already-current seed (`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:14-31`, `:193-211`) | unchanged — proposal §2 Q5 explicitly preserves "the beta-1 seed discipline: deterministic JSON form payloads, no schema migration for JSONB field expansion, and no officer-published form overwrite" | **none** — proposal does not require an additional seed advance to demonstrate `page`/`visible_when`; the e2e fixture in TG-5 supplies the multi-page form directly through publish |
| `gitops/channels/local/applications/server-manager/api-deployment.yaml` env injection | INIT-134 / INIT-135 set | unchanged | **none** |
| `gitops/channels/local/applications/server-manager/discord-deployment.yaml` | INIT-134 dry-run posture | unchanged | **none** |
| `notification_envelopes` / `notification_rules` / `notification_events` | INIT-029a / INIT-134 set | unchanged — INIT-136 emits zero new event types and edits zero rules | **none** |

Risk on §5: **none**. The slice ships purely as application-level
contract widening, server validator extension, and SPA wizard
state. Every infrastructure surface (database schema, env vars,
Pomerium, Authentik, Kong, GitOps seed jobs) remains byte-
identical.

### 6. Authenticated chapter-specific submit path unchanged

The β-1 substrate has two distinct public-submit dispatch paths
inside `_submit_application_internal`
(`services/api/app/services/applications.py:780-792`):

1. **Chapter-selector override** (β-1 addition): when the current
   global form contains a required `chapter_select` and the
   request sends `scope_kind=chapter` with a matching response,
   `_chapter_selector_override` returns the global form row
   plus a target-scope override.
2. **Exact-scope lookup** (existing pre-β-1 path): when the
   override does not fire,
   `_get_current_form_for_submit(scope_kind=..., scope_id=...)`
   resolves the form by exact scope. Authenticated chapter-
   specific submits — those targeting a chapter-published form
   directly — flow through this branch.

β-2 must not let conditional visibility leak into either gate.

| Surface | Pre (β-1) | Post (β-2) | Risk |
|---|---|---|---|
| `_chapter_selector_override` gate | fires only when current global form contains a required `chapter_select` and `scope_kind=chapter` matches the response (`services/api/app/services/applications.py:780-784`) | unchanged — proposal §3 "Submit Validator" requires the visibility pass to run *after* `_chapter_selector_override` selects the effective form row, and proposal §2 Q6 forbids `visible_when` on `chapter_select` plus forbids referencing it as a predicate source | **none** — the override gate condition is byte-identical, and `chapter_select` cannot be hidden or used as a conditional source |
| `_get_current_form_for_submit` exact-scope lookup | resolves chapter-specific forms by `(scope_kind=chapter, scope_id)` (`services/api/app/services/applications.py:786-790`) | unchanged | **none** |
| Authenticated chapter submit path (`scope_kind=chapter` against a chapter-published form, no `chapter_select` in the form) | resolves the chapter form via exact-scope lookup, runs `validate_application_responses` against its fields, persists `target_scope_kind=chapter` | unchanged — the visibility pass is a no-op for chapter-published forms whose fields have no `visible_when`. If a chapter officer later publishes a chapter form with `visible_when` predicates, the new pass applies uniformly without changing dispatch | **none** — dispatch order, form lookup, and target-scope persistence are preserved |
| Form lookup error path | `FormDefinitionNotFoundError(scope)` raised when neither the override nor the exact-scope lookup yields a form (`services/api/app/services/applications.py:791-792`) | unchanged | **none** |
| `_require_submit_authority` chain | runs against `(form_row["scope_kind"], form_row["scope_id"])` (`services/api/app/services/applications.py:803-809`) | unchanged | **none** |
| Form snapshot construction | `build_form_snapshot(form_row)` then `target_scope_override` is applied if present (`services/api/app/services/applications.py:811-813`) | unchanged | **none** — the visibility pass operates on `snapshot["fields"]`, not on `target_scope`, so the snapshot's chapter-target semantics for chapter-selector forms remain intact |
| `chapter_select` predicate source ban | n/a (β-1 has no `visible_when`) | publish-time `FormDefinitionPublish` validation rejects `visible_when` on `chapter_select` and rejects `chapter_select` as a predicate source (proposal §2 Q1 + §2 Q6) | **none** — protects the routing-only contract of `chapter_select` |

Risk on §6: **none**. Both authenticated chapter-specific submit
dispatch (exact-scope lookup) and the β-1 chapter-selector
override gate are preserved. The visibility pass cannot reroute,
hide, or conditionalize `chapter_select`, and it runs after form-
row selection rather than altering it.

## Verdict reasoning

LOW.

1. **`page` default (gate §1)**: `_BaseFormField` gains
   `page: int = Field(default=1, ge=1)`. Pydantic applies the
   default whenever the key is absent in the input dictionary,
   so legacy JSONB rows from β-1 (which omit `page` entirely)
   parse with `page=1`. The wizard's derived-page algorithm
   (proposal §2 Q2) sorts distinct page values, yielding a single
   `[1]` step set, which renders flat — functionally identical to
   the current renderer. `extra="forbid"` is unaffected because
   `page` is defined on the base, not "extra."
2. **`visible_when` default (gate §2)**: `_BaseFormField` gains
   `visible_when: FormFieldVisibleWhen | None = None`. The shared
   visibility evaluator (used by both the SPA renderer and the
   server validator) treats `visible_when is None` as "always
   visible," so the new server-side visibility pass is a strict
   no-op for any form authored without `visible_when`. Legacy
   forms see exactly the same unknown-key rejection, required-
   field enforcement, and per-type validation as today.
3. **Submit endpoint signature (gate §3)**: route, request body,
   response model, status code, error mapping, auth dependencies,
   FastAPI endpoint signature, and the
   `submit_public_application_with_receipt` service-level
   signature are byte-identical. Proposal §1 explicitly preserves
   `responses: dict[str, JSON]` and explicitly bans a per-page
   submit API and a draft API in this slice.
4. **Public chapters endpoint (gate §4)**: zero changes at the
   route, response model, service, ingress, or auth-posture
   layer. The SPA's β-1 conditional `chapter_select` fetch
   behavior is preserved verbatim by proposal §3 "SPA Renderer."
5. **No env / migration / GitOps (gate §5)**: zero new env vars,
   zero Alembic head changes (the JSONB column tolerates the new
   keys), zero Pomerium route changes, zero Authentik blueprint
   changes, zero Kong ingress changes, zero new notification
   rules/events. The BL-002 seed fail-closed/no-op invariants are
   preserved; proposal §2 Q5 explicitly bans schema migrations
   for JSONB field expansion. The TG-5 e2e multi-page fixture is
   supplied through the test publish path, not through a seed
   advance.
6. **Authenticated chapter-specific submit (gate §6)**:
   `_chapter_selector_override` and the exact-scope
   `_get_current_form_for_submit` branch in
   `_submit_application_internal` are preserved verbatim. The
   visibility pass runs *after* form-row selection at the
   existing `validate_application_responses` call site
   (`services/api/app/services/applications.py:814-819`); it can
   reject hidden-field responses but cannot influence dispatch,
   form lookup, target-scope override, or `chapter_select`
   semantics. Publish-time validation forbids `visible_when` on
   `chapter_select` and forbids referencing `chapter_select` as a
   predicate source, protecting its routing-only role.

Tier 3 (live Humility guild send) remains explicitly out of scope
per proposal §5; the local Discord deployment stays at its
existing dry-run posture inherited from INIT-134; the e2e suite
extends test 19 with a multi-page fixture path but the suite
count and the live-guild fixture guard from INIT-134 are
unchanged.

The slice has **zero** tracked findings against the six β-2 gate
criteria. The single supported-surface property to keep an eye on
during implementation is the discriminated-union default
preservation: every β-1 JSONB row that currently round-trips
through `FormFieldShort | FormFieldLong | FormFieldNumber |
FormFieldSelect | FormFieldMultiSelect | FormFieldBoolean |
FormFieldChapterSelect` must continue to round-trip with `page=1`
and `visible_when=None` materialized by the Pydantic defaults on
`_BaseFormField`. Proposal §3 places the new attributes on the
shared base (not on each variant individually), so this property
holds uniformly across every existing variant — including
`FormFieldChapterSelect`, whose β-1 always-visible/routing-only
contract is further protected by proposal §2 Q6's publish-time
bans.

Verdict: **LOW**.

SUPPORTED_SURFACE_DONE: plans/risk/init-136-supported-surface.md
