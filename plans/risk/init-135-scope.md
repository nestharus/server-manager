# INIT-135 — Scope risk gate

**Verdict:** LOW

INIT-135 ships BL-010 β-1 only: chapter selector field type
plus chapter-scoped public submit. The proposal explicitly
defers multi-page (β-2), conditional fields (β-2), and file
upload (β-3) to future slices (`proposals/17-init-135-chapter-selector.md` §1, §8).
Diff budget +820 / -70 stays well below the 1000-line single-PR
threshold and the 1200-line split threshold (§9). One new field
type, one new public endpoint, one renderer migration, zero auth
or permission changes.

## Gate checks

### 1. Only one new field type (`chapter_select`) — not a blanket field-type system overhaul

**PASS — with intentional contract restructure.** §3 / §5
add exactly one new variant:

- `FormFieldChapterSelect` (Pydantic), `type="chapter_select"`,
  `required=Literal[True]`, optional `placeholder` (§5).
- The contract restructures `ApplicationFormField` from a
  monolithic shape to a Pydantic discriminated union over the
  existing `type` discriminator (`short`, `long`, `number`,
  `select`, `multi_select`, `boolean`, `chapter_select`).

The discriminated-union refactor is necessary substrate for
introducing any new field variant — without it, validation
cannot distinguish `chapter_select` from existing variants. It
preserves existing `id` / `type` JSON keys verbatim (§2 Q3:
"using the existing `id`/`type` naming, not new
`field_id`/`field_type` keys"), so on-the-wire shape and
persisted JSONB are unchanged for current variants. This is
not a blanket overhaul; the existing variants keep their fields,
labels, and validation rules untouched (§5: "The contract keeps
current `FIELD_ID_PATTERN` and label validation rules").

Form-definition constraints in §3 also bound the new variant:
at most one `chapter_select` per form, only allowed on global
forms, `required` locked to `true`. These constraints prevent
the new variant from leaking into chapter-scoped forms or
multi-select use cases this slice doesn't handle.

### 2. One new public endpoint (`GET /api/public/chapters`) — no other public endpoints

**PASS.** §4 enumerates exactly one new public surface:

- `GET /api/public/chapters` — unauthenticated, active-only,
  wrapped `{"chapters": [{"id", "name"}]}` response.

Everything else is reused:

- `POST /api/public/applications` is the existing public submit
  endpoint; auth (`verify_applicant_receipt`) is unchanged (§6).
- No second public endpoint, no chapter-detail endpoint, no
  draft-save endpoint, no file-upload endpoint.
- Admin chapter endpoint (`/api/v1/web/admin/chapters`) is
  explicitly NOT reused for public callers (§11 "Delete or
  avoid": "Do not reuse `/api/v1/web/admin/chapters` for public
  applicants").

The wrapped response shape is locked to `{chapters: [...]}`
(§2 Q2) and intentionally omits admin-only columns (`state`,
`version`, `created_at`, templates, configuration, Discord
resources). This minimizes the public attack surface and
cannot become a backdoor for admin metadata.

### 3. SPA form renderer: switches to data-driven rendering ONLY for the `chapter_select` field type

**PASS — with intentional renderer migration.** §3 modifies
`services/web/src/features/public/ApplicationFormRoute.tsx` to
"replace the current hardcoded two-field renderer with
data-driven field rendering, including a chapter select
populated from `/api/public/chapters`". §11 (New) describes
this as a "SPA data-driven renderer for current form fields
and active chapter options".

The gate language explicitly permits this: *"if migrated,
that's still β-1 scope."* The renderer cannot conditionally
mix hardcoded text fields with a data-driven `chapter_select`
without becoming structurally worse than a uniform data-driven
loop, so migrating the existing two text fields to the same
data path is the smaller change. Existing field semantics
(label, required, placeholder for `short`/`long`) are
preserved; this is not a redesign of the form UI.

Crucially, the renderer change is bounded by the field-type
union — only field types in the API contract render. Since
the contract adds only `chapter_select` (check 1), the renderer
gains exactly one new branch. Any future variant requires both
contract and renderer work, so the seam is correctly placed.

The renderer does NOT add:

- Multi-page navigation, progress indicators, or step state.
- `visible_when` evaluation or any conditional field logic.
- File / attachment input rendering.
- Draft persistence beyond the existing `DRAFT_KEY` session-storage.

### 4. No multi-page navigation. No conditional visibility. No file upload. No chapter-creation UI.

**PASS.** §8 (Anti-scope) explicitly excludes all four:

- "No multi-page forms, progress model, or page schema."
- "No conditional visibility, dependency graph, or
  `visible_when` contract."
- "No file upload, object storage, presigned URLs, malware
  scanning, or attachment response type."
- "No chapter creation/deletion/admin UI changes."

§1 reinforces: "Out of scope: multi-page forms, conditional
fields, and file upload, which remain beta-2/beta-3". §11
("Delete or avoid") additionally bans:

- Chapter-specific copies of the public intake form.
- `field_type` / `field_id` aliases.
- Hardcoded chapter options in the SPA or fixture-only code.
- Schema migration for JSONB field-type expansion.

Form-definition constraints (§3) also prevent a `chapter_select`
field from being multiplied (max 1 per form) or made optional
(required=true locked), so the field cannot become the seed of
a multi-step or conditional flow within β-1.

### 5. No new permissions, no new actor kinds, no Pomerium changes (only confirms existing public catch-all covers the new route)

**PASS — with one operational ingress addition.**

**Permissions:** unchanged. §6: "GET /api/public/chapters is
public and requires no Pomerium principal, officer authority,
applicant receipt, or Discord identity." No new permission
name appears anywhere in §3, §4, §6, or §11.

**Actor kinds:** unchanged. §6: "Submit auth is unchanged...
the applicant can submit only as the receipt Discord identity."
The chapter selector "does not allow browser-supplied identity
headers and does not create a new authorization branch." Submit
actor remains the resolved Discord member from
`verify_applicant_receipt`.

**Pomerium auth:** unchanged. The new route is unauthenticated
public and does not introduce a new policy, prefix, or principal.
§6 confirms public catch-all coverage.

**Operational ingress note:** §3 modifies
`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
and `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`.
These are Kong-Ingress + rate-limit-plugin yamls (verified at
the file: `kind: Ingress` with `konghq.com/plugins:
public-intake-rate-limit`), not Pomerium auth policies. The
existing file enumerates `/api/public/applications` and
`/api/applications` as Kong ingress paths; the new
`/api/public/chapters` path must be added there to be routable
and rate-limited. This is path enumeration / rate-limit
operational config, not a permission, actor, or auth-policy
change. It satisfies the gate's intent (no new auth surface)
while exposing the new route through the same operational
chain as the existing public submit endpoint.

## In scope (justified)

- **No Alembic migration.** `form_definitions.fields` is JSONB
  and absorbs the new variant; chapter table shape is unchanged;
  applications table shape is unchanged. Confirmed against
  current head `wu_045_app_public_submit_notify` (verified
  consistent with the just-shipped INIT-134 migration head).
- **`FormFieldChapterSelect` + discriminated union** in
  `services/api/app/contracts/applications.py`. Existing
  variants preserved with identical JSON shape.
- **One new public endpoint** (`GET /api/public/chapters`) with
  contract / service / endpoint / tests in
  `services/api/app/contracts/public_chapters.py`,
  `services/api/app/services/public_chapters.py`,
  `services/api/app/api/v1/endpoints/public_chapters.py`,
  `services/api/tests/test_public_chapters.py`. Active-only
  filter. 200-row cap matches admin-listing cap.
- **Public-submit chapter-scope handling.** §3 / §4 add: when a
  global public form contains `chapter_select`, accept
  `scope_kind=chapter` from the SPA, validate
  `scope.scope_id == responses[chapter_field_id]`, validate
  the chapter is active, persist `target_scope_kind=chapter`
  + `target_scope_id=<selected>`. Form lookup remains global
  (Q5 lock). This is the minimum surgery to route a
  globally-defined form to a chapter-scoped application
  without forking the seed form per chapter.
- **SPA data-driven renderer.** Replaces hardcoded two-field
  block with field-type dispatch. Loads chapters only when
  ≥ 1 `chapter_select` field is present (avoids needless
  fetch on plain forms).
- **Seed-job v2.** Updates the deterministic
  `seed-public-intake-form` SQL to seed a global form
  containing `chapter_select` while preserving BL-002's
  no-op-when-officer-published and fail-closed invariants
  (§3, §11).
- **Local-channel ingress / rate-limit yamls.** Add the new
  path next to the existing public submit path. Kong /
  rate-limit operational only; no Pomerium auth policy change.
- **Test wiring.** API contract tests, SPA compat tests,
  fixtures, e2e test 19 extension to assert
  `target_scope_kind='chapter'` in Postgres. No live Discord
  send (Tier 3 untouched).

## Out of scope (deferred / explicit anti-scope §8)

- **Multi-page forms / page schema / progress model** — β-2.
- **Conditional fields / `visible_when` / dependency graph** — β-2.
- **File upload / object storage / presigned URLs / attachment
  response type** — β-3.
- **Chapter creation / deletion / admin UI** — separate slice.
- **Officer review workflow changes** beyond the existing
  test-19 reads of the chapter-scoped application.
- **Live Humility Discord writes / sends / role changes** —
  Tier 3, separate user-approved action.
- **Backwards-compatibility aliases** — none. §8: "No
  backwards-compatibility aliases, deprecated field names,
  feature flags for old behavior, or placeholder stubs."
- **`field_type` / `field_id` aliases** — explicitly banned
  in §11 ("Delete or avoid"). Existing `id` / `type` keys
  are kept.
- **Chapter-specific copies of the public intake form** —
  banned in §11.
- **Reuse of `/api/v1/web/admin/chapters` for public callers** —
  banned in §11.
- **Hardcoded chapter options in SPA or fixture-only code** —
  banned in §11.
- **JSONB field-type schema migration** — banned in §11
  (none needed; JSONB absorbs the variant).

## Risk surface

| Area | Pre | Post (INIT-135) | Justification |
|---|---|---|---|
| Migration head | `wu_045_app_public_submit_notify` (INIT-134) | Identical — no Alembic migration | `form_definitions.fields` is JSONB; field-type addition is contract/validation only |
| Field type set | `short`, `long`, `number`, `select`, `multi_select`, `boolean` | + `chapter_select` (one variant) | Discriminated union restructure preserves existing JSON shape |
| Form-definition contract | Monolithic `ApplicationFormField` | Pydantic discriminated union over `type` | Required substrate for any new variant; preserves wire-shape for existing variants |
| Public endpoints | `POST /api/public/applications` | + `GET /api/public/chapters` (active-only, wrapped) | One new public surface; admin chapter endpoint NOT reused |
| Public submit auth | `verify_applicant_receipt` | Identical | §6 preserves auth verbatim; selected chapter is routing target, not identity claim |
| Public submit scope handling | `global` only (today's hardcoded SPA submits global) | + `chapter` accepted when global form contains `chapter_select` and selected chapter id matches scope id | One control-flow branch in the existing service; form lookup remains global |
| Application target scope | Global today | `target_scope_kind=chapter`, `target_scope_id=<selected>` when `chapter_select` present | Reuses existing `target_scope_kind` / `target_scope_id` columns (no schema change) |
| Form snapshot scope | `global` / `null` | Identical (form definition source remains global); `target_scope` carries selected chapter | Snapshot source vs application target separated cleanly |
| SPA renderer | Hardcoded `character_name` + `application_text` | Data-driven dispatch over field types from current form definition | Migration permitted by gate; bounded by field-type union |
| SPA chapter fetch | None | Loads `/api/public/chapters` only when ≥ 1 `chapter_select` field present | Avoids unnecessary fetch on plain forms |
| Permission surface | Unchanged | Unchanged | No new permission name in §3 / §4 / §6 / §11 |
| Actor kinds | Unchanged | Unchanged | Submit actor remains resolved Discord member |
| Pomerium auth | Public catch-all covers public paths | Unchanged auth policy; route is public via existing catch-all (§6) | No new principal, prefix, or policy |
| Kong ingress / rate-limit | `/api/public/applications`, `/api/applications` enumerated | + `/api/public/chapters` enumerated alongside | Operational path enumeration; not an auth change |
| Authentik | Unchanged | Unchanged | Not in §3 modified files |
| Discord daemon | INIT-134 surface (embed delivery) | Untouched | No new Discord surface in §3 |
| Discord-visible writes | INIT-134 emits at submit | Identical | Chapter selector is data on the form/payload; does not introduce a new event or notification |
| Idempotency | Existing public-submit dedupe by `client_application_id` | Identical | No new dedupe key system |
| Seed job | BL-002 global public form (2 text fields) | + `chapter_select` field; preserves no-op-when-officer-published + fail-closed | Deterministic seed advance only when current form is the prior seed |
| E2e test 19 | Asserts existing public submit + officer queue | + Postgres assertions for `target_scope_kind='chapter'`, `target_scope_id=<selected>`, snapshot source remains global | No live Discord write |
| Diff budget | — | +820 / -70 (under 1000 single-PR ceiling, well under 1200 split threshold) | One PR; documented split fall-back along deployability boundary if exceeded |

## Splittable concerns

- **`FormFieldChapterSelect` contract + public chapter endpoint
  + public submit chapter-scope handling** are mechanically
  shippable as a first PR with the SPA / e2e wiring as a
  follow-up — this is the documented split boundary in §9 if
  diff exceeds 1200 net lines. Bundling them into one PR is
  the right call at the +820 estimated diff because the SPA
  cannot exercise the chapter selector without the API
  endpoints, and the API endpoints would otherwise sit dormant
  behind feature gating (which §8 forbids: "No feature flags
  for old behavior").
- **Seed-job v2 update** is bundled with the SPA wiring because
  shipping the contract + endpoint without seeding a form that
  uses `chapter_select` would leave β-1 unverifiable end-to-end.
  The seed update is mechanically small (data/config change,
  not a migration) and gated by BL-002's no-op-when-officer-
  published invariant, so it cannot regress already-customized
  guilds.
- **Discriminated-union refactor** is not splittable from the
  new variant — without the union, `chapter_select` cannot be
  validated separately from existing variants.
- **Kong ingress / rate-limit yaml updates** are not splittable
  from the public chapter endpoint — the route is unreachable
  without ingress path enumeration.

## Verdict reasoning

LOW. Every gate check passes:

1. **One new field type** (`chapter_select`), with a
   discriminated-union refactor that preserves existing JSON
   shape. No blanket overhaul. Constraints (max 1 per form,
   global forms only, required=true) bound the variant
   tightly. ✅ check 1.
2. **One new public endpoint** (`GET /api/public/chapters`),
   active-only, wrapped, minimal `{id, name}` shape. Admin
   chapter endpoint explicitly NOT reused. ✅ check 2.
3. **SPA renderer migrated to data-driven dispatch.** Permitted
   by gate language ("if migrated, that's still β-1 scope").
   Bounded by the field-type union, so it cannot grow new
   surfaces without contract work. No multi-page, conditional,
   or upload rendering added. ✅ check 3.
4. **Anti-scope explicitly excluded** in §8: no multi-page,
   no conditional, no file upload, no chapter-creation UI.
   §11 adds further "delete or avoid" bans on aliases,
   chapter-specific form copies, and admin-endpoint reuse. ✅
   check 4.
5. **No new permissions, no new actor kinds, no Pomerium auth
   changes.** Public submit auth verbatim (§6); public chapter
   list is unauthenticated under existing public catch-all.
   Kong-Ingress + rate-limit yaml updates are operational path
   enumeration, not auth/permission changes. ✅ check 5.

Three judgment calls worth naming explicitly — all LOW-risk:

- **Discriminated-union restructure of `ApplicationFormField`**
  is a substrate change required by introducing any new field
  variant. The proposal preserves wire-shape for existing
  variants (`id`/`type` keys, `FIELD_ID_PATTERN`, label rules)
  and persistence (JSONB absorbs the new variant). The
  alternative — open-ended `dict` validation — would be
  strictly worse for type safety and future variants.
- **Public-submit form-lookup divergence** (Q5 lock): the
  existing service code looks up forms by submitted scope,
  which would miss a global-scoped seed form when the SPA
  submits with `scope_kind=chapter`. The proposal narrowly
  changes the lookup path so chapter-selector submits
  validate against the current global form while overriding
  application target scope to the selected chapter. This is
  a single targeted branch in the public-submit path; it does
  not affect authenticated chapter-specific submits, which
  retain their exact-scope form-lookup. Cleaner than forking
  the seed form per chapter (banned in §11).
- **Renderer broadening to data-driven dispatch** is the most
  expansive single change in the slice but is gate-permitted
  and structurally cleaner than a hybrid renderer. It cannot
  grow new field surfaces without corresponding API contract
  work, which acts as the natural scope guardrail for β-2 / β-3.

No "while we're at it" cleanups, no audits of pre-existing
form / submit logic, no scope leakage outside the chapter-
selector surface, no β-2 / β-3 features sneaking in ahead of
their separate BL slices.

SCOPE_DONE: plans/risk/init-135-scope.md
