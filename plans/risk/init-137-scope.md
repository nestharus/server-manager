# INIT-137 — Scope risk gate

**Verdict:** LOW

INIT-137 ships BL-010 β-3 only: one new `file` field type
in the existing discriminated union, one new presigned-URL
endpoint (`POST /api/v1/public/applications/upload-url`), and
direct-to-MinIO PUT from the browser with server-side
`HEAD`-based verification at submit. The proposal explicitly
defers multi-file fields, virus scanning, image manipulation
/ thumbnailing / OCR / EXIF / content extraction, the
officer file-served-back endpoint, the officer attachment
review UI, S3 bucket lifecycle policy implementation, raw
URL persistence, and direct multipart upload through FastAPI
(`proposals/28-init-137-file-upload.md` §1, §2 Q7, §5). Diff
budget +720 / -40 stays under the 1,000-line single-PR
threshold (§6). One new field variant, one new endpoint, one
new service module, one new dependency (`boto3`, sync only —
no `aiobotocore`), zero database migrations, zero Cedar /
Pomerium / Authentik policy changes.

## Gate checks

### 1. Only one new field type (`file`) — not multi-file

**PASS.** §2 Q2 adds exactly one new variant to the
`ApplicationFormField` discriminated union in
`services/api/app/contracts/applications.py`:

```python
class FormFieldFile(_BaseFormField):
    type: Literal["file"]
    accept: list[str]
    max_size_bytes: int = 10 * 1024 * 1024
```

The `id`, `label`, `required`, `page`, and `visible_when`
attributes come from the β-2 `_BaseFormField` shared base —
no duplication, no parallel field-shape branch. The serialized
field carries one object reference per submission, not a list:

```json
{
  "character_sheet": {
    "object_key": "applications/<application_id>/<field_id>/<uuid>",
    "content_type": "application/pdf",
    "size_bytes": 420000
  }
}
```

§2 Q4 fixes the response-value shape to a single object with
exactly three keys (`object_key`, `content_type`,
`size_bytes`); §2 Q5 enforces "the response must contain only
`object_key`, `content_type`, and `size_bytes`" at submit
validation, rejecting array values, extra keys, or repeated
references. §5 (Anti-Scope) reinforces: "Multi-file fields.
Each `file` field accepts one object reference."

The β-2 page / `visible_when` plumbing is reused verbatim
("File fields may use beta-2 `page` and `visible_when`; when
hidden, the browser does not upload or submit the reference
and the server does not require it") — no new visibility
language, no per-field upload-state model in the form
contract, no fan-out across multiple file fields.

### 2. Only one new endpoint (presigned URL)

**PASS.** §2 Q3 adds exactly one new public API endpoint:

- `POST /api/v1/public/applications/upload-url` (browser path
  `/api/public/applications/upload-url`).

The endpoint depends on the existing `verify_applicant_receipt`
+ `authorize_public_intake` + `get_db` dependency stack
("Authority is receipt-required, matching public submit"),
i.e., reuses the β-1 / β-2 public-submit auth posture. No
new auth dependency, no new principal kind, no new ingress
prefix family — `/api/v1/public/applications/...` is the
existing β-1 / β-2 public submit prefix and the new path
sits under it.

§3 (API endpoint) confirms: "Mount it under the existing
applications router family so the final path is
`POST /api/v1/public/applications/upload-url`. The endpoint
... does not write Discord-visible state and does not create
application rows."

§5 (Anti-Scope) bans the obvious second-endpoint creep:

- "File-served-back endpoint for officers" — no GET / file
  / read-back endpoint for the uploaded object.
- "Officer review UI for applicant uploads" — no admin
  attachment-listing endpoint behind the SPA.
- "Direct upload through FastAPI multipart bodies" — no
  fallback `POST .../upload` multipart endpoint that would
  duplicate the upload path.

The submit endpoint itself stays at the existing
`POST /api/v1/public/applications` (`_submit_application_internal`
in `services/api/app/services/applications.py`). No second
submit shape, no per-field upload-confirmation endpoint, no
draft-with-attachments API.

### 3. Server-side bucket lifecycle policy is ANTI-SCOPE (operator concern)

**PASS.** §2 Q6 explicitly defers it: "Orphaned objects from
presigned URLs that were never submitted are handled by S3
bucket lifecycle policy with a 24h expiry on the
application-upload prefix. **Configuring that lifecycle
policy is deferred and must be called out in the
implementation notes or follow-up backlog.**"

§5 (Anti-Scope) reinforces: "S3 lifecycle policy
implementation; document the needed 24h cleanup rule as
deferred."

§3 (Substrate / Dependencies and settings) keeps the bucket
provisioning side untouched: "Object storage is already
provisioned for local" via the existing
`object-storage-bucket-credentials-infisicalsecret.yaml`,
`object-storage-bucket-job.yaml`, and `api-deployment.yaml`
GitOps manifests. INIT-137 reads from those settings —
"The new upload service reads only through settings; no
hardcoded endpoint, bucket, or credentials" — but does not
add lifecycle rules to the `object-storage-bucket-job.yaml`
manifest, does not call `put_bucket_lifecycle_configuration`
from the API service, and does not add a janitor / sweeper
job to delete orphans.

The orphan-cleanup deferral is structurally safe because (a)
no application-row is created when the object-key namespace
is reserved (§2 Q5: "The endpoint does not create an
application row when it reserves that namespace"), so
orphaned objects do not leak into `applications.responses`,
and (b) the namespace prefix is fixed and addressable
(`applications/<application_id>/<field_id>/<uuid>`), so a
follow-up lifecycle rule can target it precisely without
re-discovering object layout.

### 4. Officer file-review endpoint is ANTI-SCOPE (separate slice)

**PASS.** §5 (Anti-Scope) bans both halves of the
officer-readback surface:

- "File-served-back endpoint for officers."
- "Officer review UI for opening applicant uploads."

§1 reinforces: "Virus scanning, image manipulation, content
extraction, thumbnails, multi-file fields, **and officer
download/readback** are follow-up work, not part of this
slice."

§2 Q4 caps the persisted shape at the object-key reference,
not a downloadable URL: "The application row persists that
object exactly in `responses`. Do not persist the presigned
URL; it is temporary bearer authority and should never become
application state. **Officer readback is intentionally not
solved here**, so this slice stores an object key that a
later officer attachment-serving endpoint can authorize."

The officer / admin endpoint set is untouched in §3
(Substrate). No `services/api/app/api/v1/endpoints/.../officer`
attachment route is added, no admin-side download proxy is
added, no Cedar action like `application:download_attachment`
is introduced. The officer-side application-detail view stays
at whatever the existing INIT-133 / INIT-134 review surface
provides — INIT-137 does not extend it.

### 5. No virus scanning, image manipulation, thumbnailing

**PASS.** §1 and §5 list every adjacent surface and rule
each one out:

- §1: "Virus scanning, image manipulation, content
  extraction, thumbnails, multi-file fields, and officer
  download/readback are follow-up work, not part of this
  slice."
- §2 Q7 (Anti-scope decisions): "Virus scanning. ...
  Image manipulation, thumbnailing, OCR, EXIF stripping, or
  content extraction."
- §5 (Anti-Scope): "Virus scanning or malware verdict
  storage." / "Image manipulation, thumbnails, OCR, EXIF
  stripping, or content extraction."

The submit-time verification path in §2 Q5 is metadata-only,
not content-aware: it `HEAD`s the object and compares
`ContentLength` and `ContentType` to the submitted
`size_bytes` and `content_type` against `field.accept` and
`field.max_size_bytes`. There is no `get_object`, no MIME
sniffing of bytes, no clamav / ClamD / virus-scan call, no
ffprobe / pillow / pdf-extract path, no thumbnail-generation
job, no malware-verdict column on `applications`, no
quarantine bucket, no async malware-scan worker.

The `accept` list is a contract-level whitelist (§2 Q3:
"`content_type` is exactly in `field.accept`"), not a
content-introspection result — it constrains what an officer
publishing the form will accept by declared type, with no
attempt to verify byte content matches the declared type.
That's a deliberate scope choice in §1 ("Virus scanning ...
content extraction ... are follow-up work"); the structural
mitigation is the officer-readback anti-scope in check 4
(no one downloads it in this slice).

### 6. `boto3` added; no `aiobotocore`

**PASS.** §2 Q1 makes the call explicitly:

- "Add `boto3` to `services/api/pyproject.toml` and use the
  synchronous S3 client."
- "Do not use `aiobotocore` in this slice. It would only
  benefit the new async FastAPI endpoint while leaving submit
  verification needing either sync bridging or duplicate S3
  client paths."

§3 (Substrate / Dependencies and settings) restates:
"Add `boto3` to `services/api/pyproject.toml`."

§3 (API service) restates the sync-client construction:
"Build a MinIO-compatible
`boto3.client(\"s3\", endpoint_url=..., region_name=...,
aws_access_key_id=..., aws_secret_access_key=...)`."

The single-client posture is enforced by service
encapsulation: §3 says "Do not let callers construct S3
clients directly in endpoint or application-submit modules" —
both the upload-url endpoint and the submit verifier go
through `services/api/app/services/file_upload.py`, so the
`boto3.client(...)` call lives in exactly one module. No
parallel `aiobotocore.session.AioSession` path, no
`asyncio.to_thread(boto3_call)` bridge, no `botocore` low-level
direct usage, no `s3fs` / `minio-py` / alternative client.

This keeps the dependency footprint on the API service
small (one new top-level dep, `boto3`, plus its transitive
`botocore`/`urllib3` already pinned by the existing
SDK ecosystem) and avoids dragging an async S3 stack into
the submit path that is itself synchronous inside
`_submit_application_internal` (§2 Q1).

### 7. SPA file input is plain native, not a custom drop-zone

**PASS.** §3 (SPA) specifies a vanilla
`<input type="file">`:

- "Render `type === \"file\"` as a single file input."
- "On file selection, request a presigned URL with
  `form_definition_id`, `field_id`, `content_type`, and
  `size_bytes`."
- "Upload directly with `fetch(upload_url, {method: \"PUT\",
  headers: {\"Content-Type\": file.type}, body: file})`."

No third-party drop-zone library is named, no
`@solidjs/file-upload` style component, no `react-dropzone`
analogue, no custom paste-from-clipboard handler, no
drag-and-drop overlay, no chunked / resumable / tus.io
upload protocol, no client-side thumbnail-preview path. §5
(Anti-Scope) explicitly bans the obvious creep: "File preview
in the SPA before upload."

Upload-state UX is intentionally minimal (§3): "Track upload
state per field: idle, uploading, uploaded, failed." The
proposal degrades the progress story to whatever `fetch`
gives ("Show upload progress where the browser can provide
it; if the implementation uses `fetch`, show deterministic
uploading/uploaded state and **leave byte-level progress to
a later XHR refinement**"), which keeps β-3 from drifting
into XHR-based progress reporting, ETA estimation, or
animated progress UI.

The SPA contract change is correspondingly minimal (§3
SPA): one schema addition (`file` literal in
`publicFormFieldSchema` plus upload-url request/response
schemas), one client helper (`requestPublicApplicationUploadUrl`),
and the renderer extension inside the existing
`ApplicationFormRoute.tsx` β-2 wizard. No new SPA route.

A safety constraint is also pinned (§3 SPA): "The SPA must
not place `File` objects in sessionStorage. Draft restoration
can preserve uploaded file references after a successful
upload, but it cannot resurrect a local file handle after
refresh." This is in-scope hardening of the existing β-2
draft-restore path, not a new persistence surface.

## In scope (justified)

- **No Alembic migration.** `applications.responses` is
  already JSON-shaped (β-1 / β-2 discipline); a file response
  serializes as `{object_key, content_type, size_bytes}`
  inside the same JSON column. `form_definitions.fields` is
  already JSONB and absorbs the new `FormFieldFile` variant.
  §3: "No database migration is needed."
- **`FormFieldFile` variant** in
  `services/api/app/contracts/applications.py` with `accept:
  list[str]` and `max_size_bytes: int = 10 * 1024 * 1024`,
  added to the `ApplicationFormField` discriminated union.
  Inherits `id` / `label` / `required` / `page` /
  `visible_when` from `_BaseFormField` (β-2).
- **Upload-URL request / response contracts** added in
  `services/api/app/contracts/applications.py` —
  `{form_definition_id, field_id, content_type, size_bytes}`
  in, `{upload_url, object_key, expires_at}` out.
- **File-response model** for submit-time validation, again
  in the same contracts module. Strictly three keys
  (`object_key`, `content_type`, `size_bytes`) — extra-field
  rejection is part of TG-3.
- **Single new endpoint:**
  `POST /api/v1/public/applications/upload-url`, mounted
  under the existing public-applications router family,
  receipt-required via the existing
  `verify_applicant_receipt` + `authorize_public_intake`
  dependencies. Implemented in
  `services/api/app/api/v1/endpoints/applications/public_uploads.py`.
- **`file_upload.py` service** in
  `services/api/app/services/file_upload.py` —
  encapsulates the boto3 sync client, presigned-PUT
  generation with `Content-Type` parameter, `head_object`
  verification at submit, and `ClientError` → validation-error
  normalization. Single owner of the `boto3.client(...)`
  call (§3: "Do not let callers construct S3 clients
  directly in endpoint or application-submit modules").
- **`boto3` dependency** in `services/api/pyproject.toml`
  (sync only, no `aiobotocore`).
- **Five S3 settings** in `services/api/app/core/settings.py`:
  `s3_endpoint`, `s3_region`, `s3_bucket`,
  `s3_access_key_id`, `s3_secret_access_key`. Names align
  with existing GitOps env injection in `api-deployment.yaml`
  (§3: "Keep the existing GitOps env names unchanged because
  `api-deployment.yaml` already provides them"); no new
  `Infisical` secret-sync manifest, no new `Job`-type bucket
  bootstrapper, no new ConfigMap.
- **Submit validator extension** in
  `validate_application_responses`
  (`services/api/app/services/applications.py`) so file
  fields participate in the β-2 visibility / required /
  unknown-field / per-type pass: required visible file fields
  must have a response, optional may be omitted, response
  must have only the three keys, `content_type` must be in
  `field.accept`, `size_bytes <= field.max_size_bytes`,
  `size_bytes > 0`, object key must match the
  `applications/<application_id>/<field_id>/<uuid>` prefix
  format and the submitted field id, and a
  `head_object`-derived `ContentLength` and `ContentType`
  must equal the submitted metadata. Validation failures
  surface as 422 through the existing public-submit error
  mapping. Re-uses the β-2 visibility pass (hidden file fields
  are not required and hidden file submissions are rejected).
- **Application-id reservation** moved from
  `_submit_application_internal` to the upload-url endpoint
  for forms that contain a visible file field. The endpoint
  reserves a UUID and embeds it in the object key. Submit
  derives `application_id` from submitted file object keys,
  requires all submitted file responses to share the same
  `application_id`, and persists with that id. If no file
  responses are present, `_submit_application_internal`
  generates the id itself as before. Conflicting / stale
  submits surface as the existing insert-uniqueness /
  duplicate validation failure with the object left as an
  orphan for lifecycle cleanup (deferred, check 3).
- **SPA Zod schema** mirror in `services/web/src/api/client.ts`
  — `file` added to `publicFormFieldSchema`, plus
  upload-url request / response schemas, plus
  `requestPublicApplicationUploadUrl` client helper. Single
  mirror, no parallel old/new schemas.
- **SPA renderer extension** in
  `services/web/src/features/public/ApplicationFormRoute.tsx`
  — render `type === "file"` as a single `<input type="file">`,
  request a presigned URL on file-select, `fetch` PUT to
  the URL, track per-field upload state
  (`idle` / `uploading` / `uploaded` / `failed`), store
  `{object_key, content_type, size_bytes}` in the existing
  β-2 visible-only `responses` signal, submit visible
  responses exactly like β-2. β-2 wizard navigation, β-2
  visibility evaluation, and β-1 chapter-selector submit
  semantics all preserved.
- **SPA draft-restore safety** — `File` objects must not be
  placed in `sessionStorage`; the existing draft path may
  preserve uploaded file *references* (object-key tuples)
  after a successful upload but cannot resurrect a local
  file handle after refresh.
- **Test wiring.** TG-1 file-field contract round-trip plus
  invalid-shape rejection (empty / non-MIME / duplicate
  `accept`, `max_size_bytes <= 0`, duplicate field ids);
  TG-2 upload-URL endpoint receipt / form-id / field-id /
  field-type / content-type / size validation, no S3
  credentials in response, mocked at the boto3-client
  boundary (no real MinIO required); TG-3 submit
  verification with mocked / monkeypatched `head_object` for
  required-visible-with-object success, missing-required,
  hidden-response-rejected, object-not-found,
  content-type-mismatch, size-mismatch, wrong-prefix,
  wrong-field-id, invalid-application-id-segment,
  cross-field-application-id-disagreement, oversized-metadata;
  TG-4 SPA file-input render, presigned-URL request, PUT
  upload, response state, hidden-field-not-uploaded,
  failure-blocks-submit; TG-5 e2e deferred until the test
  harness has a stable way to inspect MinIO and intercept
  presigned PUTs.
- **Diff budget +720 / -40** (~+760 net) under the 1,000-line
  single-PR ceiling (§6) with documented split fallback at
  the API-then-SPA boundary.

## Out of scope (deferred / explicit anti-scope §5)

- **Multi-file fields.** Each `file` field accepts one
  object reference. β-N if needed.
- **SPA file preview before upload** — no thumbnail render,
  no preview pane, no client-side validation beyond `accept`
  attribute on the input.
- **Virus scanning / malware verdict storage.** No
  ClamAV / clamd / virus-scan worker, no
  `applications.malware_verdict` column, no quarantine bucket,
  no async scan-and-mark pipeline.
- **Officer file-served-back endpoint** — no GET attachment
  proxy in the API.
- **Officer review UI for applicant uploads** — admin / SPA
  officer surface untouched.
- **Image manipulation, thumbnailing, OCR, EXIF stripping,
  content extraction** — none of these touch the upload or
  submit path.
- **Direct upload through FastAPI multipart bodies** — no
  fallback `POST .../upload` multipart endpoint that would
  duplicate the presigned-PUT path.
- **Raw URL persistence in application responses** — only
  the structured `{object_key, content_type, size_bytes}`
  reference is stored; the presigned URL is bearer authority
  and never becomes application state (§2 Q4).
- **S3 bucket lifecycle policy implementation.** The 24h
  orphan-cleanup rule on `applications/<application_id>/...`
  is documented as deferred operator follow-up. The proposal
  does not modify `object-storage-bucket-job.yaml`, does not
  call `put_bucket_lifecycle_configuration` from the API,
  and does not add a janitor job.
- **Object promotion / rename from a pending key to an
  application-id key.** §5 explicitly bans the rename path;
  the application-id is reserved before the row, embedded in
  the object key at presign time, and used at submit
  persistence — no `copy_object` + `delete_object` dance.
- **Live Discord-visible writes / messages / channel changes
  / role changes / kicks / bans / permission edits** — Tier
  3, separate user-approved action.
- **Backwards-compatibility aliases / deprecated field names
  / feature flags / transitional code paths / placeholder
  stubs** — §5 bans all of them.
- **`aiobotocore` async S3 client** — §2 Q1 explicit "Do
  not."
- **Custom drop-zone / drag-and-drop / paste-from-clipboard
  / chunked / resumable upload UI.** Plain native
  `<input type="file">` only.
- **Byte-level upload progress.** Deterministic
  uploading / uploaded state from `fetch` only; XHR-based
  progress is "later refinement" (§3).
- **New public auth posture / receipt model.** Upload-url
  reuses `verify_applicant_receipt` +
  `authorize_public_intake`.
- **No e2e MinIO-backed browser test in this slice.** TG-5
  is explicitly deferred until the e2e harness can inspect
  MinIO objects and intercept presigned PUTs.

## Risk surface

| Area | Pre (β-2) | Post (INIT-137 β-3) | Justification |
|---|---|---|---|
| Migration head | β-2 head | Identical — no Alembic migration | `applications.responses` and `form_definitions.fields` are JSON-shaped; a file response and the `FormFieldFile` variant fit the existing JSON columns |
| Field-type set | 7 (`short`, `long`, `number`, `select`, `multi_select`, `boolean`, `chapter_select`) | 8 (+ `file`) | One new variant in the `ApplicationFormField` discriminated union; inherits `_BaseFormField` (β-2) attributes |
| File-field shape | none | `{id, type: "file", label, required, accept: list[str], max_size_bytes: int = 10 MiB, page, visible_when}` | Single-file per field; `accept` is non-empty MIME list; `max_size_bytes` is a positive bounded integer |
| File-response shape | none | `{object_key, content_type, size_bytes}` (exactly three keys) | No raw URL persisted; extra keys rejected by validator (TG-3) |
| Upload language | none | Presigned PUT with explicit `Content-Type` parameter; 10-minute expiry aligned with applicant-receipt TTL | `head_object`-derived `ContentLength` / `ContentType` must equal submitted metadata at submit time |
| Object-key namespace | none | `applications/<application_id>/<field_id>/<uuid>` | Application-id reserved by the upload-url endpoint before row creation; submit derives `application_id` from object keys |
| Public form endpoint | `GET /api/v1/public/application-forms/current` (β-2) | Identical | Existing endpoint serializes the extended `FormFieldFile` variant naturally |
| Public submit endpoint | `POST /api/v1/public/applications` (β-1 / β-2, auth: `verify_applicant_receipt`) | Identical path / auth; service adds file-field validation pass and `head_object` step | No new submit endpoint, no per-field upload-confirmation endpoint |
| New endpoint | none | `POST /api/v1/public/applications/upload-url` (deps: `verify_applicant_receipt` + `authorize_public_intake` + `get_db`) | Mounts under the existing β-1/β-2 public-applications router prefix; reuses existing receipt auth dependency |
| API S3 client | none | Single `boto3` sync client encapsulated in `services/api/app/services/file_upload.py` | Endpoint and submit verifier go through this module; no parallel client construction; no `aiobotocore` |
| API service modules | β-2 set | + `services/api/app/services/file_upload.py` | One new module |
| API endpoint modules | β-2 set | + `services/api/app/api/v1/endpoints/applications/public_uploads.py` | One new module |
| API dependencies | β-2 set | + `boto3` (sync only) in `services/api/pyproject.toml` | Single new top-level dep; transitive `botocore` / `urllib3` already in the stack |
| API settings | β-2 set | + `s3_endpoint`, `s3_region`, `s3_bucket`, `s3_access_key_id`, `s3_secret_access_key` | Names align with existing GitOps env injection in `api-deployment.yaml`; secrets already synced via `object-storage-bucket-credentials-infisicalsecret.yaml` |
| Submit validator | β-2 visibility / required / unknown-field / per-type pass | + file-field per-type validation (`accept`, `max_size_bytes`, key whitelist, `object_key` prefix and field-id checks, cross-field application-id agreement) + `head_object` `ContentLength` / `ContentType` check | Single deterministic pass; runs after β-1 chapter-selector override and β-2 visibility eval; failures map to 422 |
| Application-id source | `_submit_application_internal` generates UUID | If visible file responses present: derived from object keys (must agree across file fields); otherwise: generated as before | Object-key namespace is reserved before row creation; conflicting / stale submit surfaces as the existing insert-uniqueness / duplicate failure |
| Application-row creation | At submit only | Identical | Upload-url endpoint does not create application rows |
| SPA renderer | β-2 wizard with data-driven field dispatch in `ApplicationFormRoute.tsx` | + `type === "file"` branch with single `<input type="file">`, presigned-URL request on file-select, `fetch` PUT to URL, per-field upload-state, `{object_key, content_type, size_bytes}` written to existing visible-only `responses` signal | One-file extension; no new route; no chunked / resumable / drop-zone library |
| SPA draft restore | β-2 `sessionStorage` draft restore | + must not place `File` objects in `sessionStorage`; uploaded reference may be preserved post-success but local file handle cannot be revived after refresh | Existing path with hardening constraint, not a new persistence mechanism |
| SPA Zod schema | `publicFormFieldSchema` (β-2) | + `file` literal + upload-url request / response schemas + `requestPublicApplicationUploadUrl` helper | Single mirror in `services/web/src/api/client.ts` |
| Permission surface | Unchanged | Unchanged | No new permission name; receipt auth is reused |
| Actor kinds | Resolved Discord member from receipt (β-1 / β-2) | Identical | No new auth branch; presigned-URL bearer authority is short-lived (10 min) and scoped to a single object |
| Pomerium auth | Public submit + public chapters via existing posture | Unchanged — new path sits under the existing `/api/public/applications/...` prefix family | No new policy file, no new principal, no new prefix root |
| Cedar policies | Application submit / officer review (existing) | Unchanged | Upload authority is enforced via FastAPI dependency injection, not Cedar; no `application:upload_attachment` action introduced; no officer-side download action introduced (officer readback is anti-scope) |
| Authentik | Unchanged | Unchanged | Not in §3 modified files |
| Kong ingress / rate-limit | β-1 / β-2 public paths enumerated | + `/api/public/applications/upload-url` (under existing public prefix) | Ingress shape inherits the existing public-applications prefix policy; no new dedicated rate-limit class |
| Object-storage GitOps | β-1 / β-2 (bucket + credentials already provisioned via `object-storage-bucket-job.yaml` + `object-storage-bucket-credentials-infisicalsecret.yaml`) | Unchanged | INIT-137 reads from existing settings; does not modify the bucket-job manifest, does not add lifecycle rules, does not add a separate bucket-bootstrap job |
| Bucket lifecycle policy | none | none — documented as deferred 24h orphan-cleanup follow-up | Anti-scope (§5); structurally safe because no row is created until submit succeeds |
| Discord daemon | Existing INIT-134 surface | Untouched | No new Discord surface |
| Discord-visible writes | β-1 submit notification preserved (β-2) | Identical | Upload-url endpoint does not write Discord-visible state (§3) |
| Idempotency | Existing public-submit dedupe by `client_application_id` | Identical | Upload-url is not idempotent in itself but is recoverable: a fresh request mints a fresh URL + UUID, and a stale UUID becomes a lifecycle-cleanup orphan |
| Officer review UI | Existing INIT-133 / INIT-134 review surface | Untouched | Officer attachment readback is explicit anti-scope |
| E2e (test 19) | β-2 multi-page + conditional path | Unchanged in this slice (TG-5 deferred) | Real-MinIO browser e2e is documented follow-up |
| Diff budget | — | +720 / -40 (under 1,000 single-PR ceiling, documented split fallback at >1,000) | One PR; split boundary is API contract + upload-url + submit validation, then SPA upload wiring |

## Splittable concerns

- **API contract additions (`FormFieldFile`, upload-url
  request / response, file-response model) + upload-url
  endpoint + `file_upload.py` service + submit validator
  extension** are the API half. **SPA Zod mirror + file
  input + upload-state in `ApplicationFormRoute.tsx`** are
  the SPA half. §6 documents this as the split boundary if
  the diff exceeds ~1,000 net lines. Bundling is the right
  call at the +760 estimated diff because the SPA cannot
  exercise the upload flow without the contract / endpoint /
  validator changes, and the contract changes would otherwise
  sit dormant behind a feature gate (banned in §5: "No ...
  feature flags").
- **Submit-time `head_object` verification is not splittable
  from the upload-url endpoint** — without server-side
  metadata verification at submit, a malicious client could
  upload a file and then submit a falsified `content_type` /
  `size_bytes` reference, or reference an object that does
  not exist (TG-3 explicitly tests these).
- **Application-id reservation is not splittable from the
  upload-url endpoint** — the object-key namespace must
  include the application-id before the row exists, otherwise
  uploaded objects could not be reattached at submit. The
  alternative — creating the row at upload-url time — would
  proliferate empty / abandoned application rows on every
  presigned request and is implicitly banned by §3 ("The
  endpoint does not write Discord-visible state and does not
  create application rows").
- **Object-promotion / rename from a temporary key to an
  application-id key is not a valid future split** — §5 bans
  it as anti-scope. The current namespace already includes
  the application-id, so no rename is required.
- **Bucket lifecycle policy** (operator follow-up) is the
  deliberate split. The slice does not silently ship without
  cleanup: §2 Q6 and §5 instruct that the 24h orphan-cleanup
  rule must be called out as a follow-up so the operator
  side knows to apply it.

## Verdict reasoning

LOW. Every gate check passes:

1. **Only one new field type (`file`)** — added as exactly
   one variant in the `ApplicationFormField` discriminated
   union, single-object response shape, single-upload per
   field. Multi-file fields are explicit anti-scope. ✅
   check 1.
2. **Only one new endpoint
   (`POST /api/v1/public/applications/upload-url`)** —
   mounted under the existing public-applications router
   family with the existing receipt auth posture; no
   officer-side, no fallback multipart, no per-field
   confirmation endpoint. ✅ check 2.
3. **S3 bucket lifecycle policy is anti-scope** — deferred
   to operator follow-up; no `put_bucket_lifecycle_configuration`
   call, no manifest change, no janitor job. Structurally
   safe because no application row is created until submit.
   ✅ check 3.
4. **Officer file-review endpoint is anti-scope** — no
   download proxy, no admin attachment-list endpoint, no
   officer review UI. The persisted shape is an object-key
   reference that a future officer attachment-serving
   endpoint can authorize. ✅ check 4.
5. **No virus scanning, image manipulation, thumbnailing**
   — all explicitly anti-scope; submit verification is
   metadata-only `head_object`, no `get_object`, no MIME
   sniffing, no clamav / pillow / ffprobe / pdf-extract
   path. ✅ check 5.
6. **`boto3` added; no `aiobotocore`** — `boto3` is the
   single S3 client, encapsulated in `file_upload.py`,
   constructed once for both presigned-PUT generation and
   submit-time `head_object`. The async client is explicitly
   refused. ✅ check 6.
7. **SPA file input is plain native** — `<input type="file">`
   in the existing β-2 wizard inside
   `ApplicationFormRoute.tsx`, `fetch` PUT to the presigned
   URL, deterministic uploading / uploaded state, no
   drop-zone library, no chunked / resumable / preview path.
   ✅ check 7.

Three judgment calls worth naming explicitly — all LOW-risk:

- **Application-id reservation in the object-key namespace
  before submit** is the right way to attach uploaded objects
  to the eventual application row without (a) creating empty
  application rows on every presigned-URL request, (b) doing
  a `copy_object` + `delete_object` rename at submit, or (c)
  persisting a separate "pending uploads" table. The submit
  validator extracts `application_id` from object keys,
  enforces cross-field agreement, and surfaces conflicting /
  stale submits as the existing insert-uniqueness failure
  with the object left as a lifecycle-cleanup orphan. This
  is bounded — the application-id source switches only when
  visible file responses are present; otherwise the existing
  `_submit_application_internal` UUID-generation path is
  preserved unchanged.
- **Submit-time `head_object` metadata check** is the right
  anti-bypass posture (TG-3 explicitly tests it). The
  alternative — trusting the SPA-submitted
  `content_type` / `size_bytes` — would let a client smuggle
  arbitrary references, falsify size, or reference
  nonexistent objects. The `HEAD` is a single S3 round-trip
  per submitted file field, runs inside the existing
  synchronous validator (which is why §2 Q1 picks `boto3`
  over `aiobotocore`), and surfaces failures as 422 through
  the existing public-submit error mapping.
- **Bucket lifecycle policy deferred to operator follow-up**
  is the right scope cut for β-3 because the cleanup rule is
  a single S3 lifecycle configuration on the
  `applications/<application_id>/...` prefix. No application
  state leaks (the upload-url endpoint doesn't create rows;
  unsubmitted objects are pure storage orphans), and the
  prefix is fixed so the future rule can target it precisely.
  Shipping the lifecycle rule inside this slice would expand
  the GitOps surface (`object-storage-bucket-job.yaml`) and
  require lifecycle-policy verification in tests, both of
  which are operator concerns rather than form-engine
  concerns.

No "while we're at it" cleanups. No audits of pre-existing
form / submit logic. No officer-side attachment surface
sneaking in. No drop-zone / chunked-upload / preview UI
expansion. No virus-scan / thumbnailer / EXIF-stripping
worker. No `aiobotocore` async client. No raw-URL
persistence. No object promotion / rename. No
backwards-compatibility shims, feature flags, or transitional
code paths (§5 explicitly bans them).

SCOPE_DONE: plans/risk/init-137-scope.md
