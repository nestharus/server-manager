# INIT-137 hookpoints

Substrate inventory for INIT-137 / BL-010 β-3 (single-file
upload field on the public application form). Source
proposal: `proposals/28-init-137-file-upload.md` (esp. §2
Decisions Q1–Q7, §3 Substrate, §4 Test Plan, §5 Anti-Scope,
§6 Diff Budget). Risk gates:
`plans/risk/init-137-audit.md`,
`plans/risk/init-137-scope.md`,
`plans/risk/init-137-shortcut.md`,
`plans/risk/init-137-supported-surface.md`. β-2 hookpoint
reference: `research/40-init-136-hookpoints.md`. Problem
map: `research/28-bl-010-problem-map.md`.

## Summary

INIT-137 ships exactly one new field variant
(`FormFieldFile`) on the existing
`ApplicationFormField` discriminated union, exactly one new
public endpoint
(`POST /api/v1/public/applications/upload-url`) under the
existing `/api/v1/public/applications` Kong-rate-limited
prefix, exactly one new service module
(`services/api/app/services/file_upload.py`) that
encapsulates the only `boto3` import in the API, a
`HEAD`-object verification step inside the existing
`validate_application_responses` per-type dispatch, a
single-file `<input type="file">` branch in the existing β-2
wizard inside `ApplicationFormRoute.tsx`, and the upload
helpers in `services/web/src/api/client.ts`. No DB
migration, no Pomerium / Authentik / Cedar / Kong manifest
edits, no new ingress rule, no new GitOps file (MinIO
bucket and `S3_*` env injection were provisioned by
INIT-113). β-1 / β-2 forms without a `file` field round-trip
byte-for-byte and never reach the new branches.
Net change target: +720 / −40 lines (one PR; proposal §6).

## Reuse (call directly)

### Backend (API)

- `app.contracts.applications._BaseFormField`
  (`services/api/app/contracts/applications.py:117-139`).
  Already the shared field base; β-2 added `page` and
  `visible_when` (lines 121-122). `FormFieldFile`
  inherits these, so file fields participate in β-2
  page derivation and conditional visibility without
  duplication.
- `app.contracts.applications.ApplicationFormField`
  discriminated `TypeAlias`
  (`services/api/app/contracts/applications.py:232-241`).
  `Annotated[... | FormFieldChapterSelect, Field(discriminator="type")]`
  — adding the new variant inside the union keeps the
  shape; legacy JSONB rows with one of the existing seven
  `type` literals continue to dispatch to their existing
  variants.
- `app.contracts.applications._ApplicationModel`
  (`services/api/app/contracts/applications.py:24-25`).
  `model_config = ConfigDict(extra="forbid")`. Inherited
  by `FormFieldFile`, the new upload-url request/response
  contracts, and the new file-response model — extra-key
  rejection comes for free at the contract boundary.
- `app.contracts.applications.FIELD_ID_PATTERN`
  (`services/api/app/contracts/applications.py:14`).
  Reused by the new `FormFieldFile` `id` validator and
  by the upload-url request `field_id` validator.
- `app.contracts.applications._APPLICATION_FORM_FIELD_ADAPTER`
  hoisted at
  `services/api/app/services/applications.py:182`
  (`TypeAdapter(ApplicationFormField)`). Reused in
  `validate_application_responses:504` and
  `_chapter_select_field_ids:583`. Adding a discriminated
  variant updates the adapter automatically; no call-site
  change.
- `app.contracts.applications.FormDefinitionPublish`
  (`services/api/app/contracts/applications.py:255-319`)
  with its `validate_unique_field_ids` (lines 270-281),
  `validate_chapter_select_contract` (lines 283-296),
  and β-2 `validate_visible_when_graph` (lines 298-319).
  Reused unchanged; the F3 multi-file-field validator
  (see Modify in place) is added as a sibling
  `model_validator(mode="after")` alongside them.
- `app.contracts.applications.PublicApplicationSubmission`
  (`services/api/app/contracts/applications.py:359-379`)
  and `PublicApplicationSubmissionReceipt`
  (`services/api/app/contracts/applications.py:382-384`).
  Submit body shape and the receipt response stay
  byte-identical; file responses ride inside the existing
  `responses: dict[str, JSONValue]` map as
  `{object_key, content_type, size_bytes}` JSON objects.
- `app.contracts.applications.ApplicationScope`
  (`services/api/app/contracts/applications.py:65-80`).
  Submit `scope` semantics unchanged; β-1
  chapter-selector override remains the only routing
  branch that mutates `target_scope` from `responses`.
- `app.contracts.applications.InvalidApplicationResponseError`
  (`services/api/app/contracts/applications.py:597-598`).
  Raised by every new file-validation rejection
  (missing object, head-mismatch, key-prefix-mismatch,
  cross-field application-id disagreement, oversized
  metadata, hidden-file response, wrong content type,
  malformed object, conflicting application id) so the
  existing 422 mapping in
  `services/api/app/api/v1/endpoints/applications/_shared.py:187-191`
  fires without a new error class.
- `app.services.applications.validate_application_responses`
  (`services/api/app/services/applications.py:497-577`).
  Field-list build (line 504), unknown-key check
  (lines 506-511), β-2 visibility pass (line 512),
  hidden-key rejection (lines 513-519), missing-visible-
  required check (lines 520-528), and per-type dispatch
  (lines 530-577) all reused; β-3 adds a `file` branch
  inside the existing per-type loop (see Modify in
  place).
- `app.services.applications._chapter_selector_override`
  (`services/api/app/services/applications.py:589-624`).
  Reused unchanged. `chapter_select` cannot become a
  `file` field; the existing override gate's invariant
  ("global form contains exactly one required
  `chapter_select` field") is preserved by the contract
  validators.
- `app.services.applications._get_current_form_for_submit`
  (`services/api/app/services/applications.py:627-665`)
  and `app.services.applications.build_form_snapshot`
  (`services/api/app/services/applications.py:477-494`).
  Reused as-is. `form_snapshot.fields` already carries
  the JSON-serialized field list, so `FormFieldFile`
  round-trips through JSONB without snapshot-shape edit.
- `app.services.applications._submit_application_internal`
  (`services/api/app/services/applications.py:752-919`)
  and `submit_public_application_with_receipt`
  (`services/api/app/services/applications.py:935-986`).
  Reused as the single submit pipeline. The
  application-id derivation point (line 769:
  `application_id = uuid4()`) becomes the modify-in-place
  hookpoint that switches between "generate fresh UUID"
  and "parse from submitted file `object_key`s" (see
  Modify in place).
- `app.services.applications.PUBLIC_SUBMIT_SURFACE`
  (`services/api/app/services/applications.py:181`).
  Reused; the new upload-url endpoint is not a submit
  surface (it does not write Discord-visible state and
  does not create application rows) so it does not need
  a parallel surface name.
- `app.services.form_visibility.evaluate_visibility`
  (`services/api/app/services/form_visibility.py:8-35`).
  Pure visibility helper; reused by the new file-field
  branch through the existing `validate_application_responses`
  call. Hidden file fields are filtered before the
  HEAD pass (proposal §2 Q5; risk gate A6).
- `app.services.applicant_discord_auth.verify_applicant_receipt`
  (`services/api/app/services/applicant_discord_auth.py`)
  — already wired on the public submit endpoint at
  `services/api/app/api/v1/endpoints/applications/public.py:32`.
  Reused as the upload-url dependency; same applicant-
  must-be-receipt-bound rule.
- `app.services.applicant_discord_auth.RECEIPT_TTL_SECONDS = 600`
  (`services/api/app/services/applicant_discord_auth.py:23`).
  Reused as the bound for the presigned-URL expiry
  (Q3 locks 10-minute presign expiry to align).
- `app.services.authorization.authorize_public_intake`
  (`services/api/app/services/authorization.py:24-39`)
  with `PUBLIC_INTAKE_ACTION` /
  `PUBLIC_INTAKE_RESOURCE` (lines 13-14). Reused as the
  Cedar gate on the new upload-url endpoint; same
  posture as the public submit endpoint.
- `app.api.v1.endpoints.applications._shared.get_db`
  (`services/api/app/api/v1/endpoints/applications/_shared.py:34-35`)
  and `raise_known_application_error`
  (`services/api/app/api/v1/endpoints/applications/_shared.py:68-202`).
  Reused on the new upload-url endpoint exactly as on
  the public submit endpoint
  (`services/api/app/api/v1/endpoints/applications/public.py:33,42-43`)
  so `InvalidApplicationResponseError → 422`,
  `ValueError → 422`, and `PermissionError → 403`
  mappings already exist.
- `app.api.v1.endpoints.applications.public.router`
  (`services/api/app/api/v1/endpoints/applications/public.py:22`)
  with `prefix="/api/v1/public/applications"`. The new
  upload-url endpoint mounts as a sibling
  `APIRouter(prefix="/api/v1/public/applications")` and
  is included in
  `services/api/app/api/v1/endpoints/applications/__init__.py`
  alongside `public_routes` (see Modify in place).
- `app.api.v1.endpoints.public_application_forms` router
  (`services/api/app/api/v1/endpoints/public_application_forms.py:12-30`).
  Reused without signature or response-model change;
  `FormDefinitionRead` serializes the new `FormFieldFile`
  variant naturally because it inherits
  `_BaseFormField`.
- `app.api.v1.endpoints.public_chapters` router (β-1
  surface). Untouched.

### Frontend (SPA)

- `services/web/src/api/client.ts:33-47`
  (`basePublicFormFieldSchema`) — already carries
  `id`, `label`, `required`, `page`, `max_length`,
  `visible_when`. The new `file` variant extends it.
- `services/web/src/api/client.ts:49-78`
  (`publicFormFieldSchema` discriminated union over
  `type`). Extension point: add the seventh+1 variant
  for `Literal["file"]` (see Modify in place).
- `services/web/src/api/client.ts:80-95`
  (`publicFormDefinitionSchema`). Reused; reads
  `fields: z.array(publicFormFieldSchema)` so the new
  variant flows through automatically.
- `services/web/src/api/client.ts:230-231`
  (`PublicFormDefinition` / `PublicFormField` type
  aliases). Reused; `z.infer` picks up the new variant
  without a manual edit.
- `services/web/src/api/client.ts:282-298` (`getJson<T>`),
  `services/web/src/api/client.ts:344-347`
  (`fetchPublicChapters`),
  `services/web/src/api/client.ts:349-351`
  (`fetchPublicApplicationForm`),
  `services/web/src/api/client.ts:362-375`
  (`submitPublicApplication`),
  `services/web/src/api/client.ts:353-360`
  (`fetchApplicantDiscordIdentity`). All five helpers
  used as-is. `submitPublicApplication` already POSTs
  JSON to `/api/public/applications` with same-origin
  cookies, which is exactly what the upload-url helper
  needs; the new `requestPublicApplicationUploadUrl`
  is a thin sibling of `submitPublicApplication`.
- `services/web/src/api/client.ts:243-257` (`ApiError`)
  and `services/web/src/api/client.ts:259-275`
  (`readErrorPayload` / `isJsonContentType`). Reused
  for upload-url failure surfacing and (separately)
  for any non-2xx response from the presigned PUT.
- `services/web/src/features/public/ApplicationFormRoute.tsx:299-326`
  (component opening with `formDefinition`,
  `currentPageIndex`, `responses`, `visibility`,
  `visiblePages`, `currentVisibleFields` signals).
  Reused without restructuring; the new file-field
  upload state is a sibling per-field map.
- `services/web/src/features/public/ApplicationFormRoute.tsx:328-345`
  (`pruneHiddenResponses` / `setResponseValue`).
  Reused; the file-response object
  `{object_key, content_type, size_bytes}` is a value
  written into `responses` exactly like other field
  values, so prune-hidden semantics already cover it.
- `services/web/src/features/public/ApplicationFormRoute.tsx:347-369`
  (`applyResponsesToForm`),
  `services/web/src/features/public/ApplicationFormRoute.tsx:371-385`
  (`onFormInput`),
  `services/web/src/features/public/ApplicationFormRoute.tsx:387-394`
  (`goNext` / `goPrevious`),
  `services/web/src/features/public/ApplicationFormRoute.tsx:396-415`
  (`responseForField` / `responsesWithDraftDefaults`),
  `services/web/src/features/public/ApplicationFormRoute.tsx:417-445`
  (`refreshPublicFormDefinition`),
  `services/web/src/features/public/ApplicationFormRoute.tsx:447-467`
  (`refreshApplicantDiscordState`),
  `services/web/src/features/public/ApplicationFormRoute.tsx:511-556`
  (`onSubmit`). Reused; the file branch hooks into the
  existing `responses()` signal without restructuring
  the wizard.
- `services/web/src/features/public/ApplicationFormRoute.tsx:145-147`
  (`chapterSelectField`). Reused unchanged.
- `services/web/src/features/public/ApplicationFormRoute.tsx:180-297`
  (`renderFormField` per-type dispatch). Reused; the
  new `file` branch is appended into the same dispatch.
- `services/web/src/features/public/ApplicationFormRoute.tsx:30-31`
  (`CLIENT_APPLICATION_ID_KEY` / `DRAFT_KEY` and the
  `getClientApplicationId` / `preserveApplicationDraft`
  / `restoreApplicationDraft` helpers, lines 71-143).
  Reused. The proposal §3 SPA constraint applies: a
  `File` object must not be put into sessionStorage;
  uploaded `{object_key, content_type, size_bytes}`
  references may live in the existing draft map.
- `services/web/src/features/public/formVisibility.ts`
  (`evaluateVisibility` / `derivePages` /
  `pageVisibleFields`, lines 1-55). Reused; β-2
  visibility helpers already cover `file` fields by
  virtue of operating on the discriminated union's
  shared `_BaseFormField` `page` and `visible_when`
  attributes.
- `services/web/src/components/primitives/Button` —
  reused for the file-field's per-field "Choose file"
  / "Replace file" / retry affordances.

### Tests / e2e

- `services/api/tests/public_intake_fixtures.py` —
  `applicant_receipt_token`, `audit_context`,
  `seed_global_public_application_form`,
  `create_real_member`, `public_application_payload`
  helpers. Reused as the receipt + audit + member
  plumbing for TG-2 and TG-3.
- `services/api/tests/test_forms.py` — reused as the
  publish/read round-trip suite; TG-1 file-field rows
  add alongside without restructuring.
- `services/api/tests/test_public_intake_submit.py`
  and `services/api/tests/test_chapter_selector_submit.py`
  — reused as the submit-time test surfaces. The β-1
  six-case `chapter_select` matrix and the β-2
  `visible_when` cases must continue to pass; TG-3
  rows add alongside.
- `services/api/tests/test_public_application_contracts.py`
  — reused as the API contract suite where new
  upload-url request/response models and the
  file-response model land.
- `services/api/tests/test_public_application_route.py`
  — reused as the public-route auth-posture test
  surface; TG-2 cases for the new upload-url endpoint
  live alongside.
- `services/web/tests/ApplicationFormRoute.spec.tsx`
  fixture builders and `mockVerifiedApplicant` helper.
  Reused; TG-4 cases add a `fileForm` fixture
  alongside `selectorForm` / `multiPageForm` /
  `conditionalForm`.
- `services/web/tests/formVisibility.spec.ts` — β-2
  predicate-evaluator tests. Reused; β-3 adds no new
  predicate semantics (file fields participate in
  visibility through `_BaseFormField`).
- `services/web/tests/compat.spec.ts` (Contract type
  and `publicSubmitApi` route stub). Reused; TG-4
  payload coverage extends the contract type with the
  file response object.

### Infrastructure (S3 / MinIO / GitOps)

- `gitops/channels/local/applications/server-manager/object-storage-bucket-job.yaml`
  — INIT-113 platform-bootstrap creates the
  `server-manager` MinIO bucket via
  `mc mb --ignore-existing local/server-manager`.
  Reused; the bucket name matches the
  `S3_BUCKET=server-manager` value injected at
  `gitops/channels/local/applications/server-manager/api-deployment.yaml:127-128`.
- `gitops/channels/local/applications/server-manager/object-storage-bucket-credentials-infisicalsecret.yaml`
  — InfisicalSecret `server-manager-object-storage`
  syncs `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY`
  from `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`
  (lines 29-33). Reused.
- `gitops/channels/local/applications/server-manager/api-deployment.yaml:123-138`
  — `S3_ENDPOINT` (`http://minio.minio-system.svc.cluster.local:9000`),
  `S3_REGION` (`us-east-1`), `S3_BUCKET`
  (`server-manager`), `S3_ACCESS_KEY_ID` /
  `S3_SECRET_ACCESS_KEY` (from
  `server-manager-object-storage` secretKeyRef). Reused
  exactly. The new `Settings` fields read these env
  names; no rename, no new env key, no new
  InfisicalSecret.
- `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
  Kong plugin (`minute: 5`, `hour: 50`,
  `policy: local`, `fault_tolerant: true`) attached
  via Ingress on `pathType: Prefix`
  `/api/v1/public/applications` (and
  `/api/v1/public/chapters`). Reused — the new
  endpoint at `/api/v1/public/applications/upload-url`
  is a strict sub-path and inherits the plugin without
  ingress edit.
- `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`
  mirror Kong plugin on the SPA-facing path
  `/api/public/applications` Prefix. Reused — the
  SPA-facing path `/api/public/applications/upload-url`
  is a strict sub-path.
- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml`
  `web.local.humility.local` route table catch-all to
  `server-manager-web.web.svc.cluster.local:8080`
  (`allow_public_unauthenticated_access: true`).
  Reused — receipt + intake authorization happens in
  the API, not in Pomerium; the new public path rides
  the same catch-all as β-1 chapters and β-2 submit.

## New (write fresh)

### Backend (API)

- `app.contracts.applications.FormFieldFile` (new class
  in `services/api/app/contracts/applications.py`,
  inserted alongside the existing variants around
  `FormFieldChapterSelect:211-229`). Shape locked at
  proposal §2 Q2:

  ```python
  class FormFieldFile(_BaseFormField):
      type: Literal["file"]
      accept: list[str]
      max_size_bytes: int = 10 * 1024 * 1024
      max_length: None = None
      options: None = None
  ```

  Validators on the new variant:
  - `accept` non-empty, all entries fully-qualified
    `type/subtype` MIME (regex
    `^[a-z]+/[a-z0-9.+-]+$`), no duplicates, no
    wildcards (F1 below — strict equality alignment
    with the presign-time `content_type ∈ accept`
    rule).
  - `max_size_bytes` strictly positive and bounded
    (e.g., `<= 100 * 1024 * 1024` — pick a contract
    cap inside the implementation that is at least the
    default, well below S3 single-PUT 5 GiB).
  Add to `__all__` (alongside the existing
  `FormFieldChapterSelect`, `FormFieldShort`, etc.).
- `app.contracts.applications.FileUploadUrlRequest`
  (new model in
  `services/api/app/contracts/applications.py`).
  Shape locked at proposal §2 Q3:

  ```python
  class FileUploadUrlRequest(_ApplicationModel):
      form_definition_id: UUID
      field_id: str
      content_type: str
      size_bytes: int
  ```

  With validators: `field_id` matches
  `FIELD_ID_PATTERN`; `content_type` is a
  fully-qualified MIME; `size_bytes > 0` (upper bound
  is enforced against the resolved field's
  `max_size_bytes` inside the service, not the
  contract).
- `app.contracts.applications.FileUploadUrlResponse`
  (new model). Shape locked at proposal §2 Q3:

  ```python
  class FileUploadUrlResponse(_ApplicationModel):
      upload_url: str
      object_key: str
      expires_at: datetime
  ```

  No S3 credentials in the body; `upload_url` is the
  short-lived bearer (TG-2 line: "does not expose S3
  credentials").
- `app.contracts.applications.FormFileResponse` (new
  model used by submit-time validation). Shape locked
  at proposal §2 Q4:

  ```python
  class FormFileResponse(_ApplicationModel):
      object_key: str
      content_type: str
      size_bytes: int
  ```

  Strict three keys; `extra="forbid"` from
  `_ApplicationModel` rejects any other keys at
  parse time. The submit validator parses each visible
  file field's response value through this model
  before evaluating accept/size/HEAD.
- `app.services.file_upload` (new module at
  `services/api/app/services/file_upload.py`).
  Exports:
  - `build_s3_client(settings) -> "boto3.client('s3', ...)"`
    — single owner of the
    `boto3.client("s3", endpoint_url=..., region_name=..., aws_access_key_id=..., aws_secret_access_key=...)`
    call (proposal §3 "API service": "Do not let
    callers construct S3 clients directly in endpoint
    or application-submit modules").
  - `reserve_application_id() -> UUID` — the upload-url
    endpoint reserves a UUID4 namespace before
    persistence.
  - `build_object_key(application_id, field_id) -> str`
    — `applications/<application_id>/<field_id>/<uuid4>`.
  - `parse_object_key(object_key)
    -> tuple[UUID, str, UUID]` — returns
    `(application_id, field_id, object_uuid)` or
    raises `InvalidApplicationResponseError` for a
    malformed prefix.
  - `generate_presigned_put_url(*, object_key,
    content_type, size_bytes, expires_in_seconds=600)
    -> tuple[str, datetime]` — calls
    `s3.generate_presigned_url("put_object",
    Params={"Bucket": ..., "Key": object_key,
    "ContentType": content_type,
    "ContentLength": size_bytes}, ExpiresIn=600)` so
    S3 enforces the size at upload time (F2 below).
  - `head_object(object_key)
    -> tuple[int, str]` — returns
    `(content_length, content_type)` or raises
    `InvalidApplicationResponseError` for not-found
    / access-denied / metadata mismatch. Normalizes
    boto3 `ClientError` → `InvalidApplicationResponseError`
    (proposal §3: "Normalize boto3 `ClientError`
    failures into application validation errors
    instead of leaking S3 internals"; risk gate A5).
  - `validate_upload_request(*, fields, request,
    visibility) -> tuple[ApplicationFormField, UUID]`
    — pure validator: looks up `field_id` in `fields`;
    rejects if missing or `type != "file"`; rejects if
    author-hidden by contract or runtime-hidden by
    visibility (proposal §2 Q3: "The field is not
    author-hidden by contract; runtime conditional
    visibility is still rechecked at submit");
    rejects if `request.content_type not in
    field.accept`; rejects if
    `request.size_bytes > field.max_size_bytes` or
    `<= 0`. Returns `(file_field, reserved_application_id)`.
  This module is the only file that imports `boto3`
  (risk gate A9: centralized client construction).
- `app.api.v1.endpoints.applications.public_uploads`
  (new module at
  `services/api/app/api/v1/endpoints/applications/public_uploads.py`).
  Mounts
  `APIRouter(prefix="/api/v1/public/applications")`
  matching `public.py:22`. One handler:

  ```python
  @router.post("/upload-url",
      response_model=FileUploadUrlResponse,
      status_code=HTTPStatus.OK)
  async def request_upload_url_endpoint(
      body: FileUploadUrlRequest,
      identity: DiscordIdentity = Depends(verify_applicant_receipt),
      db: PostgresDatabase = Depends(get_db),
      _authz: None = Depends(authorize_public_intake),
  ) -> FileUploadUrlResponse:
      ...
  ```

  Loads the current public form for the requesting
  scope, parses fields through
  `_APPLICATION_FORM_FIELD_ADAPTER`, runs
  `evaluate_visibility` against an empty response map
  (author-hidden check), runs
  `validate_upload_request`, reserves an
  `application_id`, builds the object key, generates
  the presigned PUT URL with `ContentType` and
  `ContentLength` bound, returns the response. No
  application row is created; no Discord-visible state
  is written. Errors normalize through
  `raise_known_application_error`.
- `services/api/tests/test_file_upload.py` (new) —
  unit tests for `parse_object_key`,
  `build_object_key`, `validate_upload_request`,
  and the boto3-mocked `head_object` /
  `generate_presigned_put_url` boundary. No live MinIO
  required (proposal §4 "Mock `file_upload.py` or the
  boto3 client boundary").
- `services/api/tests/test_public_uploads_endpoint.py`
  (new, or extend
  `test_public_application_route.py`) — TG-2 cases
  (see Tests below).

### Frontend (SPA)

- `services/web/src/api/client.ts` — three new exports:
  - `publicFormFileFieldSchema` (added as the eighth
    branch in `publicFormFieldSchema` discriminated
    union; see Modify in place).
  - `fileUploadUrlRequestSchema` and
    `fileUploadUrlResponseSchema` (new Zod schemas
    mirroring the API models).
  - `requestPublicApplicationUploadUrl(payload:
    FileUploadUrlRequest):
    Promise<FileUploadUrlResponse>` — sibling of
    `submitPublicApplication`, POSTs JSON to
    `/api/public/applications/upload-url` with
    same-origin credentials, parses the response
    through `fileUploadUrlResponseSchema`. ApiError on
    non-2xx (so the SPA can surface receipt-missing as
    a redirect to Discord login through the existing
    onSubmit handler shape).
- `services/web/tests/file-upload.spec.ts` (new) —
  Zod schema acceptance/rejection cases for the
  `file` variant and for the upload-url request /
  response shapes (TG-1 SPA half).

### Tests

- **TG-1 publish/read round-trip + invalid shapes**
  (`services/api/tests/test_forms.py`):
  - publish/read round-trip with a `file` field
    carrying `accept`, `max_size_bytes`, `page`,
    `visible_when`;
  - reject empty `accept`;
  - reject non-MIME `accept` entry
    (e.g., `pdf`, `application`, `image/`);
  - reject duplicate `accept` entries;
  - reject wildcard `accept` (`image/*`, `*/*`) — F1
    strictness;
  - reject `max_size_bytes <= 0`;
  - reject duplicate field ids when one is a `file`
    field;
  - reject a form with two `file` fields — F3 stopgap
    (one file field per form for β-3, see Modify in
    place: `validate_single_file_field`).
- **TG-2 upload-url endpoint**
  (`services/api/tests/test_public_uploads_endpoint.py`
  or `test_public_application_route.py`):
  - receipt-required positive: a current public form
    with a `file` field returns
    `{upload_url, object_key, expires_at}`;
  - missing/invalid receipt → auth failure through
    the existing receipt path (TG-2 line 235);
  - unknown `form_definition_id` / stale id → 404
    via `FormDefinitionNotFoundError`;
  - unknown `field_id` → 422;
  - `field_id` of a non-file type → 422;
  - `content_type` outside `field.accept` → 422
    (TG-2 line 237);
  - `content_type` is a wildcard (e.g., `image/*`)
    → 422 (F1 alignment);
  - `size_bytes > max_size_bytes` → 422 (TG-2 line
    238);
  - `size_bytes <= 0` → 422;
  - response body excludes S3 credentials (TG-2 line
    240);
  - the boto3 client is mocked at the
    `file_upload.generate_presigned_put_url`
    boundary; the mock asserts that
    `Params["ContentType"]` and
    `Params["ContentLength"]` are bound (F2
    alignment);
  - the rate-limit ingress applies — implicit, exercised
    by the existing public-intake harness; no new
    ingress test.
- **TG-3 submit + HEAD chain**
  (`services/api/tests/test_public_intake_submit.py`):
  - required visible file field with matching S3
    object → 201, file response persisted as
    `{object_key, content_type, size_bytes}`;
  - missing required file response → 422;
  - hidden file response → 422 (β-2 hidden-key
    rejection in
    `validate_application_responses:513-519`);
  - object not found → 422 (HEAD raises
    `InvalidApplicationResponseError`);
  - `head_object` `ContentType` mismatch → 422;
  - `head_object` `ContentLength` mismatch → 422;
  - object-key wrong prefix → 422 (parse_object_key);
  - object-key wrong field id segment → 422;
  - object-key invalid `application_id` segment → 422;
  - object-key with a different `application_id`
    than another submitted file field → not exercised
    in β-3 because the F3 stopgap pins single file
    field per form; flag as a follow-up TG-3 case
    when β-3+1 lifts the stopgap;
  - oversized response metadata
    (`size_bytes > max_size_bytes`) → 422 even if S3
    exists;
  - response object with extra keys → 422 via
    `FormFileResponse` `extra="forbid"`;
  - β-1 chapter-selector matrix (Positive 1–3,
    Negative 1–3) re-asserted alongside the new file
    branch;
  - β-2 visibility cases (hidden non-file response
    rejection, hidden required not required) re-
    asserted.
- **TG-4 SPA file input**
  (`services/web/tests/ApplicationFormRoute.spec.tsx`,
  with a `fileForm` fixture):
  - a file field renders as a single
    `<input type="file">` on its page;
  - selecting an accepted file calls
    `requestPublicApplicationUploadUrl` with
    `{form_definition_id, field_id, content_type,
    size_bytes}`;
  - the browser performs a `fetch(upload_url,
    {method: "PUT", headers: {"Content-Type":
    file.type}, body: file})` to the returned URL;
  - per-field upload state transitions
    `idle → uploading → uploaded` (visible to the
    user via aria-live status);
  - on success, `responses[field_id]` is
    `{object_key, content_type, size_bytes}`;
  - submit POSTs the file response object inside
    `responses` (not the presigned URL);
  - upload failure transitions to `failed` and
    blocks submit with a retryable error (TG-4
    "Upload failure blocks submit");
  - hidden file field is not uploaded and not
    submitted (TG-4 "Hidden file fields are not
    uploaded or submitted");
  - on refresh after a successful upload, the
    `{object_key, content_type, size_bytes}`
    reference is preserved in the existing
    `DRAFT_KEY` sessionStorage path; a `File`
    object is never written to sessionStorage.
- **TG-5 e2e** — explicitly deferred (proposal §4.5
  / §5; risk gate C6). Backlog entry required at
  slice landing (no MinIO-backed browser e2e in
  this slice).

## Modify in place (additive only)

### Backend (API)

- `services/api/app/contracts/applications.py:232-241`
  (`ApplicationFormField`) — extend the discriminated
  union with `FormFieldFile`:

  ```python
  ApplicationFormField: TypeAlias = Annotated[
      FormFieldShort
      | FormFieldLong
      | FormFieldNumber
      | FormFieldSelect
      | FormFieldMultiSelect
      | FormFieldBoolean
      | FormFieldChapterSelect
      | FormFieldFile,
      Field(discriminator="type"),
  ]
  ```

  Pydantic dispatches by `type`; legacy JSONB rows are
  unaffected (risk gate §1).
- `services/api/app/contracts/applications.py:283-296`
  (`validate_chapter_select_contract`) — no change.
  `chapter_select` cannot become a `file` field; the
  existing `len(chapter_select_fields) > 1` and
  `routing_rules.review_scope` invariants stand.
- `services/api/app/contracts/applications.py:298-319`
  (`validate_visible_when_graph`) — no body change.
  `_VISIBLE_WHEN_SCALAR_SOURCE_TYPES` (line 19-21) is
  `{"short", "long", "number", "select", "boolean"}`
  — `file` is not added (a structured object cannot
  be a predicate source). Add an explicit reject if
  a `file` field tries to *be* a predicate source; the
  existing scalar-source check already covers it
  because `field.type == "file"` will not be in the
  scalar set, so no edit is required. But the
  `FormFieldFile` variant *can* set `visible_when`
  (β-2 plumbing applies; risk gate A6).
- `services/api/app/contracts/applications.py:255-319`
  (`FormDefinitionPublish`) — add a fourth
  `model_validator(mode="after")` named
  `validate_single_file_field` (sibling of
  `validate_chapter_select_contract` and
  `validate_visible_when_graph`):

  ```python
  @model_validator(mode="after")
  def validate_single_file_field(self) -> "FormDefinitionPublish":
      file_fields = [f for f in self.fields if f.type == "file"]
      if len(file_fields) > 1:
          raise ValueError("forms may contain at most one file field")
      return self
  ```

  This is the F3 stopgap — option (c) from the audit:
  "Limit β-3 to one file field per form." Removes the
  multi-file-field application-id coordination problem
  by construction. Add a TG-1 case for the rejection
  (see Tests).
- `services/api/app/services/applications.py:530-577`
  (per-type dispatch inside
  `validate_application_responses`) — extend the
  `if/elif` chain with a `file` branch placed
  alongside the existing scalar-type branches:

  ```python
  elif field.type == "file":
      file_response = FormFileResponse.model_validate(value)
      if file_response.content_type not in field.accept:
          raise InvalidApplicationResponseError(
              f"{field_id} content_type not in field.accept"
          )
      if file_response.size_bytes <= 0 or file_response.size_bytes > field.max_size_bytes:
          raise InvalidApplicationResponseError(
              f"{field_id} size_bytes out of range"
          )
      key_app_id, key_field_id, _key_uuid = file_upload.parse_object_key(
          file_response.object_key
      )
      if key_field_id != field_id:
          raise InvalidApplicationResponseError(
              f"{field_id} object_key field segment mismatch"
          )
      content_length, content_type = file_upload.head_object(
          file_response.object_key
      )
      if content_length != file_response.size_bytes:
          raise InvalidApplicationResponseError(
              f"{field_id} HEAD ContentLength mismatch"
          )
      if content_type != file_response.content_type:
          raise InvalidApplicationResponseError(
              f"{field_id} HEAD ContentType mismatch"
          )
  ```

  Function signature stays unchanged. Hidden file
  fields are filtered before this loop by the existing
  hidden-key rejection (lines 513-519) and the
  visibility-gated required check (lines 520-528).
- `services/api/app/services/applications.py:752-919`
  (`_submit_application_internal`) — change the
  `application_id = uuid4()` line at line 769 to
  derive from submitted file responses when present.
  Approximate shape:

  ```python
  application_id = _resolve_application_id(
      validated.responses, snapshot["fields"]
  )
  ```

  where `_resolve_application_id` is a private helper
  that:
  - parses each visible-file-response `object_key`
    via `file_upload.parse_object_key`;
  - if there are no file responses → returns
    `uuid4()` (current behavior);
  - if there is exactly one file response → returns
    that response's `application_id` segment;
  - if there are multiple → raises
    `InvalidApplicationResponseError` (would be
    impossible under the F3 stopgap, but defensive).
  The lookup must run after `build_form_snapshot`
  (line 816) and before `validate_application_responses`
  (line 819) so the application id is known when
  inserting at lines 826-846. The existing
  `client_application_id` dedupe (lines 799-806) and
  `errors.UniqueViolation` recovery (lines 893-904)
  handle conflicting / stale submits as
  `DuplicateApplicationCreateError` exactly as today.
- `services/api/app/api/v1/endpoints/applications/__init__.py:5-19`
  — add the new sub-router:

  ```python
  from .public_uploads import router as public_upload_routes
  ...
  router.include_router(public_upload_routes, tags=["applications"])
  ```

  Single-line additive change.
- `services/api/app/core/settings.py:13-60` (`Settings`)
  — add five fields with env-name alignment to the
  existing `S3_*` keys injected by
  `api-deployment.yaml:123-138`:

  ```python
  s3_endpoint: str = Field(...)
  s3_region: str = Field(default="us-east-1")
  s3_bucket: str = Field(...)
  s3_access_key_id: SecretStr = Field(..., repr=False)
  s3_secret_access_key: SecretStr = Field(..., repr=False)
  ```

  `SecretStr(repr=False)` matches the
  `applicant_receipt_signing_key` /
  `applicant_oidc_client_secret` posture. No new env
  key, no new InfisicalSecret.
- `services/api/pyproject.toml:6-17` — add `boto3` to
  the runtime dependency list:

  ```toml
  "boto3>=1.35.0",
  ```

  No `aiobotocore` (proposal §2 Q1: "Do not use
  `aiobotocore` in this slice"). No new dev dep —
  TG-2 / TG-3 mock the
  `file_upload.generate_presigned_put_url` and
  `file_upload.head_object` boundaries.

### Frontend (SPA)

- `services/web/src/api/client.ts:49-78`
  (`publicFormFieldSchema`) — add the eighth branch:

  ```typescript
  basePublicFormFieldSchema.extend({
    type: z.literal("file"),
    accept: z.array(z.string()).min(1),
    max_size_bytes: z.number().int().positive(),
  }),
  ```

  `PublicFormField` type alias picks it up via
  `z.infer`.
- `services/web/src/api/client.ts` (after the existing
  `publicFormDefinitionSchema`) — add the new request
  / response schemas and helper:

  ```typescript
  export const fileUploadUrlRequestSchema = z.object({
    form_definition_id: z.string(),
    field_id: z.string(),
    content_type: z.string(),
    size_bytes: z.number().int().positive(),
  });
  export const fileUploadUrlResponseSchema = z.object({
    upload_url: z.string(),
    object_key: z.string(),
    expires_at: z.string(),
  });
  export type FileUploadUrlRequest = z.infer<typeof fileUploadUrlRequestSchema>;
  export type FileUploadUrlResponse = z.infer<typeof fileUploadUrlResponseSchema>;
  export async function requestPublicApplicationUploadUrl(
    payload: FileUploadUrlRequest,
  ): Promise<FileUploadUrlResponse> {
    const path = "/api/public/applications/upload-url";
    const response = await fetch(path, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new ApiError({
        status: response.status,
        path,
        statusText: response.statusText,
        payload: await readErrorPayload(response),
      });
    }
    return fileUploadUrlResponseSchema.parse(await response.json());
  }
  ```

  No change to the existing `submitPublicApplication`
  helper; the file response object is embedded inside
  the existing `responses` map at submit time.
- `services/web/src/features/public/ApplicationFormRoute.tsx:180-297`
  (`renderFormField`) — append a `file` branch
  alongside the existing per-type branches:

  ```tsx
  if (field.type === "file") {
    return <FileFieldInput field={field}
                            value={value as FormFileResponse | undefined} />;
  }
  ```

  Where `FileFieldInput` is a small inline component
  (or co-located helper) inside the same file that:
  - renders `<input type="file" accept={field.accept.join(",")}>`;
  - tracks per-field upload state in a sibling
    Solid signal map keyed by field id
    (`idle | uploading | uploaded | failed`);
  - on `change`, validates client-side that
    `file.type ∈ field.accept` and
    `file.size <= field.max_size_bytes` (cheap
    UX gate; server is authoritative);
  - calls `requestPublicApplicationUploadUrl` with
    `{form_definition_id, field_id, content_type,
    size_bytes}`;
  - on success, performs `fetch(upload_url, {method:
    "PUT", headers: {"Content-Type": file.type},
    body: file})`;
  - on PUT success, calls `setResponseValue(field,
    {object_key, content_type, size_bytes})` so the
    existing `responses` signal carries the
    structured reference;
  - on any failure, transitions to `failed` and
    surfaces a retry affordance; the existing
    `onSubmit` checks the upload-state map and
    blocks submit when any visible file field is
    not in `uploaded`.
- `services/web/src/features/public/ApplicationFormRoute.tsx:511-556`
  (`onSubmit`) — add a guard before the existing
  `submission = await submitPublicApplication(payload)`
  call: if any visible file field is not in
  `uploaded` state, set `submitStatus` to a
  retryable error and return without POSTing. The
  existing `pruneHiddenResponses(...)` and
  `responsesWithDraftDefaults(...)` calls do not
  change — file response objects ride inside
  `responses` exactly like other field values.
- `services/web/src/features/public/ApplicationFormRoute.tsx:31-61`
  (`FALLBACK_FORM`) — no change. The fallback form
  has no file fields and is unaffected by β-3.
- `services/web/src/features/public/ApplicationFormRoute.tsx:80-143`
  (`preserveApplicationDraft` /
  `restoreApplicationDraft`) — no body change. The
  `responses()` signal already contains the
  structured file reference object on success; the
  existing serialization (`JSON.stringify`) handles
  the new shape. The proposal §3 SPA constraint is
  honored by the implementation discipline ("The
  SPA must not place `File` objects in
  sessionStorage") rather than by a code edit; the
  new `FileFieldInput` component never writes a
  `File` to the responses signal — only the
  upload-completed reference object — so the
  existing draft serialization is automatically
  safe.

### GitOps / e2e

- No GitOps file edits. The new endpoint sits at
  `/api/v1/public/applications/upload-url`, a strict
  sub-path of the existing
  `/api/v1/public/applications` Kong `pathType: Prefix`
  rule and the mirror Pomerium
  `/api/public/applications` Prefix rule. The MinIO
  bucket, the `server-manager-object-storage`
  InfisicalSecret, and the five `S3_*` env keys on
  `api-deployment.yaml` are all already provisioned.
- `infra/tests/fixtures/web-ui/contract.json` — TG-5
  e2e is deferred; no fixture extension lands in this
  slice. When the e2e backlog ticket lands, the
  fixture extension and the `19-web-ui.sh`
  `assert_public_submit_persisted` extension will
  follow the β-2 pattern.
- `gitops/channels/local/applications/server-manager/object-storage-bucket-job.yaml`
  — no edit. The 24h prefix lifecycle policy is
  explicitly deferred (proposal §2 Q6, §5; risk
  gate A10/F6) and tracked as a follow-up backlog
  item, not landed in this slice.

## Audit findings (F1–F6) hookpoint mapping

- **F1 — `accept` entry strictness (wildcards vs.
  fully-qualified MIME).** Hookpoint:
  `FormFieldFile.accept` field validator inside the
  new variant in
  `services/api/app/contracts/applications.py`. Lock
  the regex to `^[a-z]+/[a-z0-9.+-]+$` and reject
  wildcards (`image/*`, `*/*`) at publish time so the
  presign-time `content_type ∈ field.accept` strict
  equality (Q3) and the publish-time validator agree.
  TG-1 wildcard rejection case is added to
  `services/api/tests/test_forms.py`.
- **F2 — Presigned URL must bind `Content-Length`.**
  Hookpoint: `file_upload.generate_presigned_put_url`
  in `services/api/app/services/file_upload.py` —
  pass `Params={"Bucket": ..., "Key": ...,
  "ContentType": content_type, "ContentLength":
  size_bytes}` to
  `s3.generate_presigned_url("put_object", ...)` so
  S3 enforces the size at upload time (S3 aborts
  oversized PUTs before they consume bandwidth /
  produce orphans). TG-2 boto3-mock case asserts
  both `ContentType` and `ContentLength` are in the
  signed `Params` dict.
- **F3 — Multi-file-field `application_id`
  coordination.** Hookpoint: new
  `validate_single_file_field` `model_validator` on
  `FormDefinitionPublish` in
  `services/api/app/contracts/applications.py` —
  option (c) from the audit, "Limit β-3 to one file
  field per form." Removes the cross-field
  application-id coordination problem by construction.
  TG-1 rejection case lands in
  `services/api/tests/test_forms.py`. When β-3+1
  needs multi-file fields, lift the validator and
  switch to option (a) (extend
  `FileUploadUrlRequest` with optional
  `application_id` field for SPA-side reuse).
- **F4 — Future officer-readback no-raw-URL
  discipline.** Hookpoint: this slice introduces no
  officer-readback surface (anti-scope, proposal §5).
  Hookpoint for the future slice: open a backlog
  item naming the constraint — the future readback
  must either byte-stream through a server-authorized
  handler or return very short-lived presigned `GET`
  URLs with `Content-Disposition: attachment` and no
  caching, scoped to a per-request officer-authority
  check. No code edit in this slice.
- **F5 — `S3_ENDPOINT` deployment-config trust
  boundary.** Hookpoint: none in this slice. The
  endpoint URL is already settings-driven via
  `api-deployment.yaml:123-128` and the Infisical
  trust chain established by INIT-113. The
  observation belongs in the GitOps deployment-PR
  review checklist.
- **F6 — Lifecycle-policy deferral must precede
  production.** Hookpoint: none in this slice
  (proposal §2 Q6 explicitly defers the 24h prefix
  lifecycle rule to a follow-up). Implementation must
  open a backlog entry referencing Q6 scoped to
  "configure 24h lifecycle policy on the
  `applications/` prefix in the `server-manager`
  MinIO bucket" before β-3 ships to a production-
  like deployment.

## Anti-scope — do NOT touch

- **Multi-file fields per `file` field.** Each `file`
  field accepts exactly one
  `{object_key, content_type, size_bytes}`
  reference (proposal §2 Q7, §5). The
  `validate_single_file_field` validator further
  caps the form at one file field for β-3 (F3
  stopgap).
- **SPA file preview before upload.** No thumbnail
  render, no preview pane, no client-side
  byte-introspection beyond the native `accept`
  attribute (proposal §5).
- **Virus scanning / malware verdict storage.** No
  ClamAV / clamd / virus-scan worker, no
  `applications.malware_verdict` column, no
  quarantine bucket, no async scan pipeline
  (proposal §1, §2 Q7, §5).
- **Officer file-served-back endpoint.** No
  `GET /api/v1/applications/{id}/attachments/{...}`,
  no admin attachment-list endpoint, no Cedar action
  like `application:download_attachment`, no proxy
  download handler (proposal §2 Q7, §5).
- **Officer review UI for applicant uploads.** Admin
  / officer SPA surfaces are untouched (proposal §5).
- **Image manipulation, thumbnailing, OCR, EXIF
  stripping, content extraction.** No `pillow` /
  `ffprobe` / `pdf-extract` import; submit
  verification is metadata-only `head_object`
  (proposal §1, §2 Q7, §5).
- **Direct multipart upload to FastAPI.** No
  `POST /api/v1/public/applications/upload`
  multipart fallback, no
  `request.files`-style handler (proposal §1, §5).
- **Raw URL persistence in `applications.responses`.**
  Only `{object_key, content_type, size_bytes}` is
  stored; the presigned URL is bearer authority and
  never becomes application state (proposal §2 Q4,
  §5).
- **S3 bucket lifecycle policy implementation.** The
  24h orphan-cleanup rule on
  `applications/<application_id>/...` is documented
  as deferred operator follow-up; the proposal does
  not modify `object-storage-bucket-job.yaml`, does
  not call `put_bucket_lifecycle_configuration` from
  the API, and does not add a janitor job (proposal
  §2 Q6, §5; risk gate A10/F6).
- **Object promotion / rename from a temporary key
  to an application-id key.** The application-id is
  reserved before the row, embedded in the object
  key at presign time, and used at submit
  persistence; no `copy_object` + `delete_object`
  dance (proposal §5).
- **`aiobotocore` async S3 client.** The single
  `boto3` sync client is the only S3 path
  (proposal §2 Q1, §5).
- **Custom drop-zone / drag-and-drop / paste-from-
  clipboard / chunked / resumable upload UI.** Plain
  native `<input type="file">` only (proposal §3
  SPA, §5).
- **Byte-level upload progress.** Deterministic
  `idle | uploading | uploaded | failed` state from
  `fetch` only; XHR-based progress is "later
  refinement" (proposal §3 SPA).
- **New public auth posture / receipt model.** The
  upload-url endpoint reuses
  `verify_applicant_receipt` +
  `authorize_public_intake` exactly (proposal §2
  Q3; risk gate A1).
- **New ingress / Kong / Pomerium manifest.** The
  new endpoint sits under existing Prefix rules; no
  edit to
  `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
  or
  `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`
  or `secrets-infisicalsecret.yaml` (risk gate A8).
- **New Cedar action / policy.** Upload authority is
  enforced via FastAPI dependency injection
  (`verify_applicant_receipt` +
  `authorize_public_intake`), not a new Cedar
  action; no `application:upload_attachment` (risk
  gate A1, scope §3).
- **Authentik blueprint changes.** Untouched
  (supported-surface §5).
- **Database migration.** `form_definitions.fields`
  and `applications.responses` are JSONB; the new
  variant and the file response object live inside
  the existing columns. No Alembic head bump
  (proposal §3 Contracts; supported-surface §5).
- **Backwards-compatibility aliases / deprecated
  field names / parallel field unions / dual
  `visible_when` shapes / feature flags / transitional
  code paths / placeholder stubs / `// TODO: validate
  later` shortcuts.** Banned by proposal §5; risk
  gate C4.
- **β-2 visibility extensions.** No new predicate
  ops, no `file`-as-source predicates (file
  responses are structured objects, not scalars), no
  page-level `visible_when` (proposal §5; β-2
  hookpoints anti-scope at
  `research/40-init-136-hookpoints.md`).
- **`_chapter_selector_override` body changes.**
  `chapter_select` cannot be a `file` field; the
  existing override gate's invariant stands (risk
  gate §2).
- **Live Discord-visible writes / messages / channel
  changes / role / permission edits / kicks / bans.**
  Tier 3, separate user-approved action; INIT-137
  emits zero new event types (supported-surface §5).
- **Officer review surfaces** (`web.py:172-408`,
  officer queue / detail / transcript / messages
  routes). Read `responses` and `form_snapshot` as
  opaque maps; no β-3 edit (supported-surface §5).
- **`emit_application_public_submitted_event`**
  (`services/api/app/services/notifications.py`).
  Submit-time notification fan-out unchanged
  (supported-surface §5).
- **`infra/tests/fixtures/web-ui/contract.json` /
  `infra/tests/e2e/lib/playwright/browser-flow.mjs` /
  `infra/tests/e2e/tests/19-web-ui.sh`.** TG-5 e2e
  deferred; no fixture or harness edit lands in this
  slice (proposal §4.5).

HOOKPOINTS_DONE: research/41-init-137-hookpoints.md
