# Proposal 28 - INIT-137 / BL-010 beta-3: file upload

## 1. Problem Statement

INIT-137 ships BL-010 beta-3: public application forms can include a single-file upload field for applicant-supplied artifacts such as character sheets and screenshots. This follows the BL-010 decomposition in `research/28-bl-010-problem-map.md`: beta-1 delivered chapter selection, beta-2 delivered multi-page forms plus conditional fields, and beta-3 owns file upload.

The public unauthenticated application endpoint must not accept browser file payloads directly. Large multipart uploads through FastAPI would expand the DDoS and malware surface on the mutation gateway, tie API worker capacity to untrusted file transfer, and bypass object-storage controls already present in local GitOps. The locked architecture is a presigned PUT URL flow: an applicant with a valid receipt asks the API for an upload URL, uploads directly to S3-compatible MinIO, then submits the application with a file reference in `responses`.

The server remains authoritative. The upload-url endpoint validates the requested file against the published form field contract before minting a presigned URL, and final submit verifies the object exists in S3 with the expected content type and size before the application is persisted. Virus scanning, image manipulation, content extraction, thumbnails, multi-file fields, and officer download/readback are follow-up work, not part of this slice.

## 2. Decisions

### Q1. S3 client library: use `boto3`

Add `boto3` to `services/api/pyproject.toml` and use the synchronous S3 client. The submit path in `services/api/app/services/applications.py` is synchronous inside `_submit_application_internal`, and the object existence check belongs inside that transaction-adjacent validation path. `boto3` also directly supports S3-compatible endpoints, MinIO, presigned PUT generation, and `head_object` without adding an async dependency stack.

Do not use `aiobotocore` in this slice. It would only benefit the new async FastAPI endpoint while leaving submit verification needing either sync bridging or duplicate S3 client paths.

### Q2. New form field type: `FormFieldFile`

Extend the existing `ApplicationFormField` discriminated union in `services/api/app/contracts/applications.py` with:

```python
class FormFieldFile(_BaseFormField):
    type: Literal["file"]
    accept: list[str]
    max_size_bytes: int = 10 * 1024 * 1024
```

The serialized field shape is:

```json
{
  "id": "character_sheet",
  "type": "file",
  "label": "Character sheet",
  "required": true,
  "accept": ["image/png", "application/pdf"],
  "max_size_bytes": 10485760
}
```

`id`, `label`, `required`, `page`, and `visible_when` come from the existing `_BaseFormField` contract established by beta-1 and beta-2. `accept` is a non-empty list of MIME types. `max_size_bytes` defaults to 10 MiB and must be a positive bounded integer. File fields may use beta-2 `page` and `visible_when`; when hidden, the browser does not upload or submit the reference and the server does not require it.

### Q3. Presigned-URL endpoint contract

Add `POST /api/v1/public/applications/upload-url`, exposed to the SPA as `/api/public/applications/upload-url`.

Request body:

```json
{
  "form_definition_id": "uuid",
  "field_id": "character_sheet",
  "content_type": "application/pdf",
  "size_bytes": 420000
}
```

Response body:

```json
{
  "upload_url": "https://...",
  "object_key": "applications/<application_id>/<field_id>/<uuid>",
  "expires_at": "2026-05-01T12:00:00Z"
}
```

Authority is receipt-required, matching public submit. The endpoint must depend on `verify_applicant_receipt` and `authorize_public_intake`; it is public from a network path perspective but not anonymous from an API authority perspective. It validates:

- `form_definition_id` is the current public form definition being answered.
- `field_id` exists on that form and has `type == "file"`.
- The field is not author-hidden by contract; runtime conditional visibility is still rechecked at submit.
- `content_type` is exactly in `field.accept`.
- `size_bytes <= field.max_size_bytes`.
- `size_bytes > 0`.

Presigned URLs expire quickly; use 10 minutes to align with the current applicant receipt TTL default. The API must include the expected `Content-Type` in the presigned PUT parameters so the later `head_object` metadata can be checked against the contract.

### Q4. Submit response shape

File fields in `responses` carry structured references, not raw URLs:

```json
{
  "character_sheet": {
    "object_key": "applications/<application_id>/<field_id>/<uuid>",
    "content_type": "application/pdf",
    "size_bytes": 420000
  }
}
```

The application row persists that object exactly in `responses`. Do not persist the presigned URL; it is temporary bearer authority and should never become application state. Officer readback is intentionally not solved here, so this slice stores an object key that a later officer attachment-serving endpoint can authorize.

### Q5. Server-side verification at submit time

Extend `validate_application_responses` in `services/api/app/services/applications.py` for `file` fields:

- Required visible file fields must have a response object.
- Optional visible file fields may be omitted.
- The response must contain only `object_key`, `content_type`, and `size_bytes`.
- `content_type` must be in `field.accept`.
- `size_bytes` must be positive and `<= field.max_size_bytes`.
- `object_key` must match the application-upload prefix format and the submitted field id.
- The service must `HEAD` the S3 object.
- `ContentLength` must equal `size_bytes`.
- `ContentType` must equal `content_type`.

Reject validation failures as 422 via the existing public submit error mapping. Missing objects, mismatched metadata, oversized objects, wrong content type, unknown response keys, hidden file responses, and malformed file response objects are validation errors.

Because the presigned URL is created before the final submit call, the upload-url endpoint generates a UUID that is reserved as the application object namespace and embeds it in the object key:

```text
applications/<application_id>/<field_id>/<uuid>
```

The endpoint does not create an application row when it reserves that namespace. On submit, file validation extracts the application id from submitted file object keys, requires all submitted file responses to use the same application id, and `_submit_application_internal` persists the application with that id. If a submit has no file response, `_submit_application_internal` keeps the current behavior and generates the id itself. If a malicious or stale submit references a conflicting application id, the normal insert uniqueness failure is treated as validation/duplicate failure and the object remains an orphan for lifecycle cleanup.

### Q6. S3 object lifecycle

Object storage is already provisioned for local:

- `object-storage-bucket-credentials-infisicalsecret.yaml` syncs `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY`.
- `object-storage-bucket-job.yaml` creates the `server-manager` MinIO bucket.
- `api-deployment.yaml` injects `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, and `S3_SECRET_ACCESS_KEY`.

Add matching fields to `services/api/app/core/settings.py`. The new upload service reads only through settings; no hardcoded endpoint, bucket, or credentials.

Objects are not tied to an application until submit succeeds. Orphaned objects from presigned URLs that were never submitted are handled by S3 bucket lifecycle policy with a 24h expiry on the application-upload prefix. Configuring that lifecycle policy is deferred and must be called out in the implementation notes or follow-up backlog.

### Q7. Anti-scope decisions

Do not include:

- Multi-file fields. Each `file` field accepts one object reference.
- SPA file preview before upload.
- Virus scanning.
- File-served-back endpoint for officers.
- Officer review UI for opening applicant uploads.
- Image manipulation, thumbnailing, OCR, EXIF stripping, or content extraction.
- Direct multipart upload to FastAPI.
- Raw URL persistence in application responses.

## 3. Substrate

### Dependencies and settings

- Add `boto3` to `services/api/pyproject.toml`.
- Add S3 settings to `services/api/app/core/settings.py`: `s3_endpoint`, `s3_region`, `s3_bucket`, `s3_access_key_id`, and `s3_secret_access_key`.
- Keep the existing GitOps env names unchanged because `api-deployment.yaml` already provides them.

### API service

Create `services/api/app/services/file_upload.py`.

Responsibilities:

- Build a MinIO-compatible `boto3.client("s3", endpoint_url=..., region_name=..., aws_access_key_id=..., aws_secret_access_key=...)`.
- Validate a requested upload against the current form and file field.
- Generate object keys under `applications/<application_id>/<field_id>/<uuid>`, where `application_id` is a UUID reserved by the upload-url service before submit.
- Generate presigned PUT URLs with expected content type and short expiry.
- `HEAD` objects during submit validation.
- Normalize boto3 `ClientError` failures into application validation errors instead of leaking S3 internals.

Do not let callers construct S3 clients directly in endpoint or application-submit modules.

### API endpoint

Create `services/api/app/api/v1/endpoints/applications/public_uploads.py`.

Mount it under the existing applications router family so the final path is `POST /api/v1/public/applications/upload-url`. The endpoint accepts the upload-url request contract, depends on `verify_applicant_receipt`, `authorize_public_intake`, and `get_db`, delegates to `file_upload.py`, and returns the response contract.

The endpoint does not write Discord-visible state and does not create application rows.

### Contracts

Modify `services/api/app/contracts/applications.py`:

- Add `FormFieldFile`.
- Include it in `ApplicationFormField`.
- Add request/response contracts for upload URL generation.
- Add a file-response model or TypeAlias used by submit validation.
- Keep `PublicApplicationSubmission.responses` as JSON-shaped data, but validate file response shape in `validate_application_responses` because validity depends on the current form field.

No database migration is needed. `form_definitions.fields` and `applications.responses` are already JSON-backed.

### Submit validation

Modify `validate_application_responses` in `services/api/app/services/applications.py` so file fields participate in the existing visibility, required-field, unknown-field, and per-type validation pass. The validation must happen after beta-1 chapter-selector form selection and beta-2 visibility evaluation, using the same effective form snapshot that is persisted.

`_submit_application_internal` should resolve the application id before persistence. If visible file responses are present, it uses the shared application id parsed from their `object_key` values; otherwise it generates a new UUID as it does today. File validation must reject object keys that do not match the current field id, do not match the `applications/<application_id>/<field_id>/<uuid>` prefix, or disagree on the application id across multiple file fields.

### SPA

Modify `services/web/src/api/client.ts`:

- Add `file` to `publicFormFieldSchema`.
- Add upload-url request/response schemas.
- Add `requestPublicApplicationUploadUrl`.

Modify `services/web/src/features/public/ApplicationFormRoute.tsx`:

- Render `type === "file"` as a single file input.
- On file selection, request a presigned URL with `form_definition_id`, `field_id`, `content_type`, and `size_bytes`.
- Upload directly with `fetch(upload_url, {method: "PUT", headers: {"Content-Type": file.type}, body: file})`.
- Track upload state per field: idle, uploading, uploaded, failed.
- Show upload progress where the browser can provide it; if the implementation uses `fetch`, show deterministic uploading/uploaded state and leave byte-level progress to a later XHR refinement.
- Store the resulting `{object_key, content_type, size_bytes}` in the existing `responses` signal.
- Submit visible responses exactly like beta-2, with file fields represented by structured objects.

The SPA must not place `File` objects in sessionStorage. Draft restoration can preserve uploaded file references after a successful upload, but it cannot resurrect a local file handle after refresh.

## 4. Test Plan

### TG-1: contract - file field round-trips

Extend API form contract tests so a published form containing `type: "file"` round-trips through publish/read with `accept`, `max_size_bytes`, `page`, and `visible_when` preserved. Cover invalid field shapes:

- Empty `accept`.
- Non-MIME `accept` entries.
- Duplicate MIME entries.
- `max_size_bytes <= 0`.
- Duplicate field ids still rejected through the existing validator.

Extend SPA schema coverage so `publicFormFieldSchema` accepts `file` and rejects malformed file field fixtures.

### TG-2: presigned URL endpoint - content type and size validation

Add endpoint tests for `POST /api/v1/public/applications/upload-url`:

- Receipt-required request succeeds for a current public form file field.
- Missing/invalid receipt returns auth failure through the existing receipt path.
- Unknown form id, stale form id, unknown field id, and non-file field id fail.
- `content_type` outside `field.accept` returns 422.
- `size_bytes > max_size_bytes` returns 422.
- Successful response contains `upload_url`, `object_key`, and `expires_at`, and does not expose S3 credentials.

Mock `file_upload.py` or the boto3 client boundary; do not require a real MinIO service for these contract tests.

### TG-3: submit with file response - server verifies S3 object exists

Add submit validation tests around public submit:

- A required visible file field with a matching S3 object succeeds and persists the structured response.
- Missing required file response returns 422.
- Hidden file response returns 422, preserving beta-2 conditional semantics.
- Object not found returns 422.
- Object content type mismatch returns 422.
- Object size mismatch returns 422.
- Object key with the wrong prefix, wrong field id, invalid application id segment, or a different application id than another submitted file field returns 422.
- Oversized response metadata returns 422 even if S3 exists.

Use a fake file-upload service or monkeypatched S3 `head_object` boundary so tests are deterministic.

### TG-4: SPA - file input upload flow

Extend `services/web/tests/compat.spec.ts` or add a focused public form test:

- A file field renders as a file input on its page.
- Selecting an accepted file calls `/api/public/applications/upload-url`.
- The browser performs a PUT to the returned presigned URL.
- Uploaded metadata is stored in local response state.
- Submit includes `{object_key, content_type, size_bytes}` for the file field.
- Upload failure blocks submit and shows a retryable error state.
- Hidden file fields are not uploaded or submitted.

### TG-5: e2e - deferred

Defer full MinIO-backed browser e2e. The local e2e suite can add this after the test harness has a stable way to inspect MinIO objects and intercept presigned PUTs. This proposal requires API and SPA component coverage in beta-3, with e2e tracked as a follow-up.

## 5. Anti-Scope

- Multi-file fields.
- File preview in the SPA before upload.
- Virus scanning or malware verdict storage.
- File-served-back endpoint for officers.
- Officer review UI for applicant uploads.
- Image manipulation, thumbnails, OCR, EXIF stripping, or content extraction.
- Direct upload through FastAPI multipart bodies.
- S3 lifecycle policy implementation; document the needed 24h cleanup rule as deferred.
- Object promotion/rename from pending key to application-id key.
- Live Discord-visible writes, messages, channel changes, role changes, kicks, bans, or permission edits.
- Backwards-compatibility aliases, deprecated field names, feature flags, transitional code paths, or placeholder stubs.

## 6. Diff Budget

Estimated net: +720 / -40 lines.

- API dependency/settings/S3 upload service: +170.
- Contracts and upload-url endpoint: +140.
- Submit file-response validation and tests: +170 / -20.
- SPA schema, file input, upload state, and client helper: +150 / -20.
- SPA component tests and fixtures: +90.

This should remain one PR. If implementation exceeds roughly 1,000 net lines, split only along deployable boundaries: first API contract plus upload-url/submit validation, then SPA upload wiring. Do not split by adding old/new field names, compatibility shims, feature flags, or direct-upload fallback paths.
