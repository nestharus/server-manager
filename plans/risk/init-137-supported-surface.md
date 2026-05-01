# INIT-137 — Supported-surface risk gate

**Verdict:** LOW

INIT-137 (BL-010 β-3) widens the existing `_BaseFormField`
discriminated union with one new variant (`FormFieldFile`),
adds one new public endpoint
(`POST /api/v1/public/applications/upload-url`) under the
existing `/api/v1/public/applications` Kong ingress prefix,
extends `validate_application_responses` for `type == "file"`
fields with a deterministic `head_object` boundary call, and
introduces a new SPA file input in
`ApplicationFormRoute.tsx`. Every infrastructure surface that
β-3 needs (MinIO bucket, MinIO root credentials sync, S3 env
vars on `server-manager-api`) was already provisioned by the
INIT-113 platform-bootstrap landing
(`gitops/channels/local/applications/server-manager/object-storage-bucket-job.yaml`,
`object-storage-bucket-credentials-infisicalsecret.yaml`,
`api-deployment.yaml:123-138`). The slice ships purely as
application-level contract widening, server validator
extension, a new endpoint module, an SPA renderer extension,
and a single `boto3` dependency bump in
`services/api/pyproject.toml`. The HTTP submit wire shape,
the public chapters endpoint, the authenticated chapter-
specific submit path, the Alembic head, the Pomerium
routes, the Authentik blueprint, and the BL-002 seed
fail-closed/no-op invariants are all preserved. Forms
published under β-1 / β-2 (with no `file` field in
`form_definitions.fields` JSONB) round-trip identically and
never reach the new validation, endpoint, or SPA render
branches.

## Surfaces touched

### 1. Existing β-1 / β-2 forms without `file` fields keep working — additive variant

The β-1 / β-2 contract stores fields as a Pydantic
discriminated union over `type` rooted in `_BaseFormField`
(`services/api/app/contracts/applications.py`). Today's
variants — `FormFieldShort`, `FormFieldLong`,
`FormFieldNumber`, `FormFieldSelect`, `FormFieldMultiSelect`,
`FormFieldBoolean`, `FormFieldChapterSelect` — inherit `id`,
`label`, `required`, `page`, `visible_when` from
`_BaseFormField` and carry
`model_config = ConfigDict(extra="forbid")` via
`_ApplicationModel`. INIT-136's `page` default (`1`) and
`visible_when` default (`None`) are preserved verbatim per
`plans/risk/init-136-supported-surface.md`.

| Surface | Pre (β-2) | Post (β-3) | Risk |
|---|---|---|---|
| `_BaseFormField` shape | `id`, `label`, `required`, `page=1`, `visible_when=None` | unchanged — proposal §3 "Contracts" extends only by adding the new variant `FormFieldFile` to the discriminated union; no fields are added on the base | **none** |
| Discriminated union `ApplicationFormField` | seven variants over `Literal["short" \| "long" \| "number" \| "select" \| "multi_select" \| "boolean" \| "chapter_select"]` | adds `Literal["file"]` variant. Pydantic's `Field(discriminator="type")` routes any payload whose `type` is not `"file"` to the existing variants, so legacy parses are byte-identical | **none** — every legacy JSONB row carries one of the seven existing `type` values, all of which dispatch to their existing variant |
| Persisted JSONB shape for legacy rows | `[{"id":..., "type":..., "label":..., "required":..., "page":..., "visible_when":..., ...}]` | unchanged on disk; new published forms may include `{"type":"file", "accept":[...], "max_size_bytes":...}` | **none** — JSONB tolerates the new variant; old rows stay readable |
| `_APPLICATION_FORM_FIELD_ADAPTER` re-parse path | `TypeAdapter(ApplicationFormField).validate_python(raw)` inside `validate_application_responses` | unchanged call site; the adapter routes the new `type=="file"` variant to `FormFieldFile` and continues to route the seven existing types to their variants | **none** |
| `FormDefinitionPublish` publish-time validation | unique field ids, `min_length=1`, `chapter_select` contract, β-2 page/predicate validation | extends with `FormFieldFile` validation (non-empty `accept` list, MIME-shape entries, no duplicates, positive bounded `max_size_bytes`); proposal §4 TG-1 covers the failure cases | **none** — every new check fires only when authored JSON includes a `file` field; legacy authored payloads without any `file` field publish exactly as today |
| `extra="forbid"` regression | each variant inherits `extra="forbid"` from `_ApplicationModel` | unchanged; `FormFieldFile` inherits the same config and only declares `type`, `accept`, `max_size_bytes` on top of base fields | **none** — legacy JSONB rows do not introduce undefined keys; `FormFieldFile` itself declares its keys explicitly |

Risk on §1: **none**. Existing β-1 / β-2 forms (the BL-002
seed v2 and any officer-published global form) preserve their
semantics byte-for-byte. The discriminated-union dispatch
routes every legacy `type` value to its existing variant.

### 2. Existing β-1 / β-2 forms without `file` fields skip the new submit validation branch

The β-1 / β-2 server validator
(`validate_application_responses` in
`services/api/app/services/applications.py`) parses fields,
runs the β-2 visibility pass, rejects unknown response keys,
checks required visible fields, and type-validates submitted
values. INIT-137 extends the per-type validation with a
`type == "file"` branch that calls the new
`file_upload.head_object` boundary against MinIO.

| Surface | Pre (β-2) | Post (β-3) | Risk |
|---|---|---|---|
| Visibility-pass behavior for non-file forms | `visible_when is None` ⇒ visible; required-visible field enforcement; unknown-key rejection | unchanged for forms whose fields all have `type != "file"`; the new `file` branch is dispatched per-field by type and never executed for legacy forms | **none** |
| Per-type validator dispatch | dispatches by field `type`, with each variant's per-type rules (string min/max, number bounds, select option whitelist, etc.) | adds a `file` branch that validates the submitted response object shape (`object_key` / `content_type` / `size_bytes` only, no extras), enforces `content_type ∈ field.accept`, enforces `0 < size_bytes <= field.max_size_bytes`, parses `object_key` against the `applications/<application_id>/<field_id>/<uuid>` prefix, and `HEAD`s the S3 object via `file_upload` | **none** for legacy forms — dispatch on `type` keeps the new branch isolated to `file` fields |
| `_chapter_selector_override` gate | β-1 routing override (`services/api/app/services/applications.py`) | unchanged — proposal §3 "Submit Validator" requires the file-validation branch to live inside the existing per-type pass that runs *after* `_chapter_selector_override` selects the effective form row | **none** — the override gate condition is byte-identical, and `chapter_select` cannot be a `file` field |
| `_submit_application_internal` application-id resolution | generates a fresh UUID at insert time | extends only when visible file responses are present: parses the application id segment from each submitted file response's `object_key`, requires all submitted file responses to agree on the same id, and uses that id as the insert key. If a submit has no file response, behavior is unchanged | **none** for legacy forms — the application-id-from-key path is reached only when visible file responses are submitted, which requires a `file` field in the form, which legacy forms do not have |
| Error mapping | `raise_known_application_error(error)` in `services/api/app/api/v1/endpoints/applications/public.py` | unchanged — new validation paths (missing required file, hidden file response, bad object key, bad content type, oversized, missing object, mismatched HEAD metadata, conflicting application id) raise existing `InvalidApplicationResponseError` and route through the existing error mapper as 422 | **none** |

Risk on §2: **none**. The new file-validation branch is
strictly per-`type` dispatched; forms without any `file`
field never execute it. The application-id-from-key
resolution is similarly guarded by "submitted visible file
responses present."

### 3. Public submit endpoint signature unchanged; new endpoint mounted under existing applications router family

| Surface | Pre (β-2) | Post (β-3) | Risk |
|---|---|---|---|
| `POST /api/v1/public/applications` route | unchanged (`services/api/app/api/v1/endpoints/applications/public.py`) | unchanged — proposal §1 keeps `responses: dict[str, JSON]`, persists structured file response objects inside `responses` exactly as submitted, no change to status code or response model | **none** |
| Submit request contract `PublicApplicationSubmission` | `{ scope, responses: dict[str, JSONValue], client_application_id }` | unchanged — file responses ride inside the existing `responses` map as `{object_key, content_type, size_bytes}` JSON objects; no new top-level fields | **none** |
| Submit response model `PublicApplicationSubmissionReceipt` | `{ message, application_id }` | unchanged | **none** |
| Submit auth dependencies | `Depends(verify_applicant_receipt)` + `Depends(authorize_public_intake)` | unchanged | **none** |
| New endpoint `POST /api/v1/public/applications/upload-url` | n/a | added in `services/api/app/api/v1/endpoints/applications/public_uploads.py`, mounted under the existing applications router family. Auth dependencies match the public submit endpoint: `verify_applicant_receipt`, `authorize_public_intake`, `get_db`. Returns `{upload_url, object_key, expires_at}` with no S3 credentials in the body | **none** — the new endpoint is additive, sits at a sub-path of the existing applications router, and reuses the receipt + intake authorization chain. It does not write Discord-visible state and does not create an application row |
| Per-page submit / draft API | not introduced | **explicitly not introduced** (proposal §5 "Anti-Scope") | **none** |

Risk on §3: **none**. The submit wire contract is byte-
identical. The new upload-url endpoint adds one new route
under the same router family, reuses the same auth chain
established by β-1, and has no side effects on
application/notification/Discord state.

### 4. Public chapters endpoint and β-2 wizard untouched

The β-1 public chapter list endpoint
(`GET /api/v1/public/chapters`) and the β-2 wizard navigation
in `ApplicationFormRoute.tsx` are not touched at any layer.

| Surface | Pre (β-2) | Post (β-3) | Risk |
|---|---|---|---|
| `GET /api/v1/public/chapters` route | unchanged (`services/api/app/api/v1/endpoints/public_chapters.py:12-20`) | unchanged | **none** |
| `list_public_chapters` service | active-only query, ordered by `name ASC`, capped at 200 | unchanged | **none** |
| SPA fetch of chapters | called only when the loaded form contains a `chapter_select` field | unchanged — file fields never replace `chapter_select` and never reference `chapter_select` | **none** |
| β-2 wizard navigation, page-derivation, `Step N of M` indicator | derives ordered pages from `form.fields`, skips pages with no visible fields, last derived page shows `Submit application` | unchanged — file fields use the existing `_BaseFormField` `page` and `visible_when` attributes and participate in derivation/visibility identically to other field types | **none** — proposal §3 "SPA" places the file input on whatever page the field declares; nothing in the wizard machinery special-cases file fields |
| β-2 visibility evaluator (shared pure helper) | render, navigation, and submit payload assembly all consult one helper | unchanged — file fields are visibility-evaluated via the same helper. When hidden, the SPA does not upload, does not store, does not submit; the server does not require a response and rejects any submitted hidden-file response per the β-2 hidden-key rule | **none** |

Risk on §4: **none**. β-3 is orthogonal to chapter routing
and to wizard navigation. The visibility helper is reused
without modification.

### 5. No DB migration; no GitOps change; env var set unchanged

| Surface | Pre (β-2) | Post (β-3) | Risk |
|---|---|---|---|
| Alembic head | β-2 head (`migrations/versions/`) | unchanged — proposal §3 "Contracts" explicitly states "No database migration is needed. `form_definitions.fields` and `applications.responses` are already JSON-backed." | **none** — `FormFieldFile` is a new variant inside the existing JSONB column; structured file responses ride inside the existing `applications.responses` JSONB column |
| `Settings` class | post-INIT-136 set (`services/api/app/core/settings.py`) | adds `s3_endpoint`, `s3_region`, `s3_bucket`, `s3_access_key_id`, `s3_secret_access_key`. Env names match the existing `S3_*` env keys already injected by `api-deployment.yaml:123-138` (Pydantic Settings auto-uppercases the field names). Credentials use `SecretStr` posture established by `applicant_receipt_signing_key` / `applicant_oidc_client_secret` | **none** — env names are reused, not redefined. `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` are already populated from the InfisicalSecret `server-manager-object-storage` (`gitops/channels/local/applications/server-manager/object-storage-bucket-credentials-infisicalsecret.yaml`); `S3_ENDPOINT` / `S3_REGION` / `S3_BUCKET` are static values on the deployment env block |
| MinIO bucket provisioning | INIT-113 set: `mc mb --ignore-existing local/server-manager` (`gitops/channels/local/applications/server-manager/object-storage-bucket-job.yaml:53`) | unchanged — bucket name `server-manager` matches `S3_BUCKET=server-manager` injected at `api-deployment.yaml:128`. No new bucket, no new lifecycle policy is configured in this slice (proposal §2 Q6 explicitly defers the 24h-prefix lifecycle policy as follow-up) | **none** for the slice — the deferred lifecycle policy is documented in §6 "Diff Budget" / proposal §2 Q6 as follow-up work; orphan objects accumulate until the policy lands but cannot affect form-submit correctness |
| MinIO root-credentials sync | InfisicalSecret `server-manager-object-storage` syncs `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` from `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` (`object-storage-bucket-credentials-infisicalsecret.yaml:29-33`) | unchanged | **none** — the API uses the root credentials already exposed; the proposal does not introduce a scoped MinIO user. This matches β-3's anti-scope on lifecycle / storage hardening |
| Pomerium routes | INIT-127 / INIT-134 / INIT-135 / INIT-136 set (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:48-105`) | unchanged — the `web.local.humility.local` route table ends with a catch-all (`secrets-infisicalsecret.yaml:97-100`) `allow_public_unauthenticated_access: true` to `server-manager-web.web.svc.cluster.local:8080`, which proxies `/api/public/...` to the API. The new SPA path `/api/public/applications/upload-url` is matched by that catch-all (no explicit Pomerium rule for `/api/public/applications` exists today; β-1's `/api/public/chapters` ride the same catch-all). Receipt + intake authorization happens in the API, not in Pomerium | **none** — proposal Q3 explicitly preserves "public from a network path perspective but not anonymous from an API authority perspective" |
| Kong ingress for public-intake rate limiting | post-INIT-135 set: `/api/v1/public/applications` and `/api/v1/public/chapters` Prefix paths covered by `public-intake-rate-limit` plugin (`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:37-50`) | unchanged — the new endpoint sits at `/api/v1/public/applications/upload-url`, a strict sub-path of the existing `/api/v1/public/applications` Kong Ingress `pathType: Prefix` rule. The rate-limit plugin (`minute: 5`, `hour: 50`, `policy: local`, `fault_tolerant: true`) automatically applies. The mirror Pomerium-side ingress (`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml:24-37`) similarly covers `/api/public/applications` as Prefix, so the SPA call path is rate-limited identically | **none** — this matches β-1's `/api/public/chapters` pattern in spirit: Kong Prefix ingress + identical plugin posture, except β-3 adds a sub-path under an *existing* Prefix rather than a new top-level path, so it requires zero ingress edits |
| Authentik blueprint | INIT-127 / INIT-134 set (`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml`) | unchanged | **none** |
| BL-002 seed-public-intake-form invariant | seeds deterministic global form, no-ops on officer-published current, fails closed when an aggregate head exists without a current row, no-ops on already-current seed | unchanged — proposal §3 / §5 do not introduce a seed advance; the e2e fixture (deferred to follow-up per TG-5) supplies the file-field form through the test publish path | **none** |
| `notification_envelopes` / `notification_rules` / `notification_events` | INIT-029a / INIT-134 set | unchanged — INIT-137 emits zero new event types and edits zero rules. The upload-url endpoint does not write Discord-visible state | **none** |

Risk on §5: **none**. Every infrastructure surface (database
schema, Pomerium, Authentik, Kong, GitOps seed jobs, MinIO
bucket, MinIO credentials) is preserved verbatim. The S3
env-var set is reused, not redefined. The deferred bucket
lifecycle policy is acknowledged as follow-up and does not
gate β-3 correctness.

### 6. `boto3` is the only dependency change; service module isolates the boundary

| Surface | Pre (β-2) | Post (β-3) | Risk |
|---|---|---|---|
| `services/api/pyproject.toml` runtime deps | `alembic`, `fastapi`, `psycopg`, `pydantic`, `pydantic-settings`, `orjson`, `PyJWT[crypto]`, `python-dotenv`, `sqlalchemy`, `uvicorn[standard]` (`services/api/pyproject.toml:6-17`) | adds `boto3>=...` exactly once. No `aiobotocore`, no `botocore` direct pin, no S3-related dev deps | **low** — `boto3` is a well-maintained synchronous client that supports MinIO via `endpoint_url`. The proposal §2 Q1 explicitly rejects `aiobotocore` to avoid sync/async bridging in `_submit_application_internal`. The single new wheel is acceptable for the slice |
| `services/api/pyproject.toml` dev deps | unchanged | unchanged — proposal §4 mocks the `file_upload.py` boundary or monkeypatches `head_object`; no `moto` / no `testcontainers[minio]` is required for unit/contract coverage | **none** — TG-1 / TG-2 / TG-3 / TG-4 all describe deterministic mocking at the service-module boundary |
| New module `services/api/app/services/file_upload.py` | n/a | constructs `boto3.client("s3", endpoint_url=settings.s3_endpoint, ...)`, generates presigned PUT URLs with `Content-Type` baked in, runs `head_object` on submit, normalizes `ClientError` into `InvalidApplicationResponseError`. Endpoint and submit modules **never** instantiate boto3 directly | **none** — boundary isolation makes the service the only file that imports `boto3`, which keeps the dependency contained and lets tests monkeypatch one place |
| New module `services/api/app/api/v1/endpoints/applications/public_uploads.py` | n/a | thin route handler. Calls `file_upload.py`. Returns `{upload_url, object_key, expires_at}`. No S3 credentials in the response body | **none** |
| `Settings` posture for credentials | `applicant_oidc_client_secret`, `applicant_receipt_signing_key` use `SecretStr(repr=False)` | matches: `s3_access_key_id`, `s3_secret_access_key` use `SecretStr(repr=False)` (proposal §3 reads "no hardcoded endpoint, bucket, or credentials"; the existing `Settings` SecretStr pattern applies) | **none** |

Risk on §6: **low**. The single dependency bump is recorded
only in `services/api/pyproject.toml`. The boundary module
(`services/api/app/services/file_upload.py`) is the only
place that imports `boto3`, so the blast radius of the bump
is one module's surface. No GitOps, no Helm chart, no Docker
base image change is required.

## Verdict reasoning

LOW.

1. **Discriminated-union extension (gate §1)**:
   `FormFieldFile` is added as an additive variant on
   `ApplicationFormField`. Every legacy JSONB row dispatches
   to its existing variant by `type`, so β-1 / β-2 forms
   round-trip byte-for-byte. `extra="forbid"` is unaffected
   because `accept` and `max_size_bytes` are defined keys on
   the new variant.
2. **Per-`type` validator branch (gate §2)**: the new
   `file` validation branch (object-key parse, `accept` /
   size enforcement, `head_object` boundary call) is per-
   `type` dispatched and never reached for legacy forms.
   The application-id-from-`object_key` resolution in
   `_submit_application_internal` is similarly guarded by
   "visible file responses present"; legacy submits keep
   generating a fresh UUID exactly as today.
3. **Public submit signature (gate §3)**: route, request
   body, response model, status code, error mapping, and
   auth dependencies are byte-identical. The new
   upload-url endpoint adds one route under the same
   applications router family, reuses
   `verify_applicant_receipt` + `authorize_public_intake`,
   and produces no Discord-visible side effects.
4. **β-2 chapter / wizard machinery (gate §4)**: zero
   changes at the chapters route, the chapter service, the
   wizard navigation, or the shared visibility evaluator.
   File fields plug into β-2's `page` / `visible_when`
   without special-casing.
5. **No DB / GitOps / env redefinition (gate §5)**: zero
   Alembic head changes (JSONB tolerates the new variant
   and the new response shape), zero Pomerium route
   changes (the `web.local.humility.local` catch-all
   covers the new SPA path; the upload-url is *under* the
   existing `/api/v1/public/applications` Kong Prefix),
   zero Authentik / seed / notification-rule changes. The
   five `S3_*` env keys are *reused*: they were injected
   in INIT-113 platform-bootstrap and are sourced from the
   existing `server-manager-object-storage` InfisicalSecret
   and the static bucket / endpoint values in
   `api-deployment.yaml:123-138`.
6. **`boto3` dependency bump (gate §6)**: recorded only in
   `services/api/pyproject.toml`. Imported only inside
   `services/api/app/services/file_upload.py`. Tests mock
   the service-module boundary, so the dev-dep set does
   not change. The proposal explicitly rejects
   `aiobotocore` to avoid sync/async bridging, which keeps
   the wheel set minimal.

Tier 3 (live Humility guild send) remains explicitly out of
scope per proposal §5; the local Discord deployment stays at
its existing dry-run posture inherited from INIT-134. The
deferred 24h S3 bucket lifecycle policy (proposal §2 Q6) is
acknowledged as follow-up work and does not gate β-3
correctness; orphan objects from never-submitted presigned
URLs accumulate until the policy lands but cannot affect
form-submit validation. The TG-5 e2e MinIO-backed browser
flow is similarly deferred per the proposal; β-3 ships API +
SPA component coverage without an e2e expansion.

The slice has **zero** tracked findings against the seven
β-3 gate criteria. The single supported-surface property to
keep an eye on during implementation is the discriminated-
union dispatch contract: every β-1 / β-2 JSONB row that
currently round-trips through `FormFieldShort | FormFieldLong
| FormFieldNumber | FormFieldSelect | FormFieldMultiSelect |
FormFieldBoolean | FormFieldChapterSelect` must continue to
round-trip with its existing variant once the union grows by
one. Pydantic's `Field(discriminator="type")` machinery
guarantees this property as long as the new variant declares
`type: Literal["file"]` distinct from the seven existing
literals — which proposal §2 Q2 does.

Verdict: **LOW**.

## Findings

None. All seven β-3 gate criteria pass:

1. ✓ Existing forms without `file` fields keep working —
   `FormFieldFile` is a strictly additive discriminated-union
   variant; legacy `type` values dispatch to their existing
   variants; the new server `file` validation branch and the
   new application-id-from-key path are guarded by "visible
   file responses present" and never reached for legacy
   submits.
2. ✓ S3 env vars (`S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`,
   `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`) are reused
   — they are already injected by
   `gitops/channels/local/applications/server-manager/api-deployment.yaml:123-138`
   and sourced from the existing
   `server-manager-object-storage` InfisicalSecret. The new
   `Settings` fields read the same env names; no rename, no
   new env key, no new InfisicalSecret.
3. ✓ No DB schema changes — `FormFieldFile` lives inside
   the existing `form_definitions.fields` JSONB column and
   structured file responses live inside the existing
   `applications.responses` JSONB column. No Alembic head
   advance.
4. ✓ No GitOps changes — MinIO is provisioned by INIT-113
   (`object-storage-bucket-job.yaml`,
   `object-storage-bucket-credentials-infisicalsecret.yaml`).
   No new GitOps file, no edit to existing GitOps files.
5. ✓ New endpoint goes through existing public-intake Kong
   rate-limit ingress — `/api/v1/public/applications/upload-url`
   is a strict sub-path of the existing
   `/api/v1/public/applications` `pathType: Prefix` rule in
   `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:37-44`,
   which carries the `public-intake-rate-limit` Kong plugin
   (`minute: 5`, `hour: 50`, `policy: local`,
   `fault_tolerant: true`). The mirror Pomerium-side
   ingress in
   `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml:24-30`
   covers `/api/public/applications` as Prefix and
   automatically rate-limits the SPA call path. This
   matches β-1's `/api/public/chapters` pattern with the
   advantage that no ingress edit is needed.
6. ✓ Pomerium config: new public path covered by catch-all
   — the `web.local.humility.local` route table in
   `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:48-100`
   ends with a catch-all
   (`allow_public_unauthenticated_access: true`) to
   `server-manager-web.web.svc.cluster.local:8080`. No
   explicit Pomerium rule exists today for
   `/api/public/applications`; β-1 chapters and β-3
   upload-url ride the same catch-all. Receipt + intake
   authorization happens in the API.
7. ✓ `boto3` deps bump is recorded in
   `services/api/pyproject.toml` only — no Helm chart,
   no Docker base image change, no GitOps edit, no dev-dep
   change. The boundary module
   `services/api/app/services/file_upload.py` is the only
   place that imports `boto3`, keeping the dependency blast
   radius to one file.

SUPPORTED_SURFACE_DONE: plans/risk/init-137-supported-surface.md
