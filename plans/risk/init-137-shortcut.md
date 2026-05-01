# INIT-137 — Shortcut risk gate (BL-010 β-3)

**Verdict:** LOW

Scope: BL-010 β-3 — public application file-upload field. The
slice extends the β-2 ground state (multi-page + conditional
visibility) with a `FormFieldFile` variant on the discriminated
`ApplicationFormField` union, a presigned-PUT URL endpoint at
`POST /api/v1/public/applications/upload-url`, a server-side
S3 `HEAD` re-verification on submit, a structured file-response
shape (`{object_key, content_type, size_bytes}`) persisted in
`applications.responses`, and a SPA file input that uploads
directly to MinIO via presigned PUT.

The shortcut gate inspects whether INIT-137 ships a real
S3-side verification at submit (not "trust the SPA"), re-checks
content_type and size against the live S3 object metadata (not
just the request body), avoids "TODO: validate later" stubs,
makes the SPA actually upload via `fetch` PUT to the presigned
URL (not "skip upload, fake reference"), and has tests that
genuinely exercise the upload → presign → submit → HEAD chain.

Source: `proposals/28-init-137-file-upload.md`,
`research/28-bl-010-problem-map.md`,
`proposals/27-init-136-multi-page-conditional.md`.

## C1 — Real S3 HEAD verification at submit (not "trust the SPA")

**Pass.**

Q5 (proposal lines 97-119) locks the submit validator contract:
the service must `HEAD` the S3 object as part of public submit
validation, not merely accept a structured reference from the
client.

> - Required visible file fields must have a response object.
> - Optional visible file fields may be omitted.
> - The response must contain only `object_key`, `content_type`,
>   and `size_bytes`.
> - `content_type` must be in `field.accept`.
> - `size_bytes` must be positive and `<= field.max_size_bytes`.
> - `object_key` must match the application-upload prefix format
>   and the submitted field id.
> - **The service must `HEAD` the S3 object.**
> - `ContentLength` must equal `size_bytes`.
> - `ContentType` must equal `content_type`.

§3 (Substrate → API service, lines 156-166) gives the
implementation contract: `file_upload.py` owns "`HEAD` objects
during submit validation" and "Normalize boto3 `ClientError`
failures into application validation errors instead of leaking
S3 internals." The HEAD lives behind the service module, not as
an opportunistic check inside the endpoint — every public submit
goes through `validate_application_responses` and through that
service module.

§3 (Substrate → Submit validation, lines 190-194) places the
HEAD pass in the canonical submit path, not a parallel
trusted-client fast path:

> Modify `validate_application_responses` in
> `services/api/app/services/applications.py` so file fields
> participate in the existing visibility, required-field,
> unknown-field, and per-type validation pass. The validation
> must happen after beta-1 chapter-selector form selection and
> beta-2 visibility evaluation, using the same effective form
> snapshot that is persisted.

The β-2 visibility pass runs first, so a "hidden" file field
cannot smuggle in a HEAD-check bypass: hidden file responses
are rejected as unknown response keys before the HEAD layer
runs (Q5 line 111: "hidden file responses … are validation
errors"). And the application-id resolution is binding (Q5
lines 113-119): the upload-url endpoint reserves a UUID, embeds
it in the object key, and `_submit_application_internal` reuses
that id at insert time, so a crafted client cannot mint an
object key for application X and then submit it as application
Y — the application id segment of the key is parsed and
required to match across all submitted file fields.

TG-3 (proposal lines 242-255) is the submit-side HEAD test
group, with both positive and negative cases:

> - A required visible file field with a matching S3 object
>   succeeds and persists the structured response.
> - Missing required file response returns 422.
> - Hidden file response returns 422, preserving beta-2
>   conditional semantics.
> - Object not found returns 422.
> - Object content type mismatch returns 422.
> - Object size mismatch returns 422.
> - Object key with the wrong prefix, wrong field id, invalid
>   application id segment, or a different application id than
>   another submitted file field returns 422.
> - Oversized response metadata returns 422 even if S3 exists.

The "Object not found returns 422" case is the explicit guard
against the "trust the SPA" shortcut: a client that fabricates
a plausible `{object_key, content_type, size_bytes}` triple
with no actual upload must be rejected, not silently persisted.

**Risk:** the natural shortcut would be to (a) accept the SPA's
structured file response verbatim and only validate the
contract shape (`object_key` looks right, `content_type` ∈
`field.accept`, `size_bytes ≤ max`) without ever talking to S3,
or (b) HEAD the object only on the upload-url endpoint and
trust the submit response to refer to "some object that was
uploaded earlier." Either bypass would let a crafted client
persist application rows pointing at non-existent or attacker-
controlled object keys.

**Mitigation:** server-side `HEAD` against the live S3 object
inside the canonical submit validator, with named TG-3
negative cases (object not found, content-type mismatch, size
mismatch, application-id-segment mismatch) and a service-module
boundary that prevents endpoint or submit modules from
constructing S3 clients ad-hoc.

**Verdict:** Not a shortcut.

## C2 — content_type re-check at submit (S3 stored vs presigned contract)

**Pass.**

The proposal binds the presigned PUT contract to the later
HEAD re-check explicitly. Q3 (proposal lines 78-79) on the
upload-url endpoint:

> The API must include the expected `Content-Type` in the
> presigned PUT parameters so the later `head_object` metadata
> can be checked against the contract.

That sentence is the load-bearing one: the `Content-Type` is
not just sent on the request body, it is part of the **signed**
presigned PUT, so the SPA cannot upload an object whose stored
`Content-Type` differs from what the upload-url request
declared. Then Q5 (line 110) closes the loop on submit:

> `ContentType` must equal `content_type`.

Where `content_type` here is the value in the submitted file
response object — which itself must be in `field.accept` (Q5
line 105). The chain is:

1. Upload-url request declares `content_type` ∈ `field.accept`
   (else 422 from the upload-url endpoint, TG-2 line 237: "
   `content_type` outside `field.accept` returns 422").
2. Presigned PUT signs that exact `Content-Type`, so a stored
   object that mismatches the contract cannot be produced
   under the same presigned URL.
3. Submit's `head_object` re-reads `ContentType` from S3 and
   demands equality with the submitted `content_type`, which
   itself must match `field.accept`.

The SPA implementation contract enforces the matching upload
header, §3 (Substrate → SPA, line 207):

> Upload directly with `fetch(upload_url, {method: "PUT",
> headers: {"Content-Type": file.type}, body: file})`.

So the browser sends the same `Content-Type` it asked the API
to sign, which the API will then reject if the live object
metadata differs at submit.

TG-2 (proposal lines 232-240) and TG-3 (line 250: "Object
content type mismatch returns 422") name the negative cases at
both endpoints.

**Risk:** the shortcut would be (a) re-check `content_type`
only against the request body field of the submit payload,
ignoring what S3 actually stored, or (b) sign the presigned
PUT without binding `Content-Type`, so the SPA can upload an
arbitrary content-type body and then declare anything it likes
in the submit response. Either bypass would let a content-type
spoofed object reach `applications.responses` and be served
back later as a different MIME than the field author allowed.

**Mitigation:** `Content-Type` is part of the presigned PUT's
signature so a mismatched upload cannot be produced under that
URL, and submit re-reads `ContentType` from `head_object` and
demands equality with the response object's `content_type`,
which itself must be in `field.accept`. Three layers, all
named in TG-2 and TG-3.

**Verdict:** Not a shortcut.

## C3 — size re-check at submit (HEAD content_length)

**Pass.**

Q5 (line 109) locks the size re-check at the live-object level:

> `ContentLength` must equal `size_bytes`.

This is `head_object`'s `ContentLength`, not the submit
payload's `size_bytes` field. The submit payload's `size_bytes`
must additionally satisfy Q5 line 106 ("`size_bytes` must be
positive and `<= field.max_size_bytes`"), and the upload-url
endpoint enforces the same bound at presign time (Q3 line 77:
"`size_bytes <= field.max_size_bytes`", Q3 line 78: "`size_bytes
> 0`"). The `<= max_size_bytes` bound is therefore checked
twice (presign + submit) and the equality between submitted
`size_bytes` and stored `ContentLength` is verified once at
submit. A client that cheats either by (a) declaring a tiny
`size_bytes` and uploading a huge file, or (b) declaring an
honest `size_bytes` and tampering with the field's
`max_size_bytes` bound, fails:

- (a) the presigned PUT is bound to a `Content-Type`-and-key
  signed contract, but more importantly submit's
  `ContentLength == size_bytes` check rejects the lie at submit.
  TG-3 line 251 ("Object size mismatch returns 422") covers
  this.
- (b) `max_size_bytes` is read from the published form
  definition, not the submit payload. The contract's
  `max_size_bytes` is set at form publish time and validated
  positive (Q2 line 27: "`max_size_bytes: int = 10 * 1024 *
  1024`", and TG-1 lines 224 covers "`max_size_bytes <= 0`"
  rejection at publish).

TG-2 (line 238: "`size_bytes > max_size_bytes` returns 422")
covers the presign-time bound. TG-3 line 254 ("Oversized
response metadata returns 422 even if S3 exists") covers the
submit-time bound, and TG-3 line 251 covers the live-object
mismatch.

**Risk:** the shortcut would be (a) trust the submitted
`size_bytes` and never call `head_object`, so a small declared
size with a huge stored object passes — and later officer
download or readback would deliver a payload the field's
contract never authorized — or (b) call `head_object` but only
log the result without rejecting on mismatch.

**Mitigation:** `ContentLength` from live `head_object` must
equal submitted `size_bytes`; submitted `size_bytes` must be
≤ `field.max_size_bytes`; presign also enforces ≤
`max_size_bytes`. TG-3 names the live-object mismatch case
and the metadata-only oversize case as separate 422 paths.

**Verdict:** Not a shortcut.

## C4 — No "TODO: validate later" stubs

**Pass with one documented deferral.**

The proposal does not carry "validate later" stubs in the
authoritative path. The two layers of validation (presign and
submit) are both implemented in this slice, with named TG-2
and TG-3 negative cases and named publish-time checks in TG-1.
§5 (Anti-Scope, lines 274-286) closes the placeholder-stub
door explicitly:

> - Backwards-compatibility aliases, deprecated field names,
>   feature flags, transitional code paths, or placeholder
>   stubs.

Three concerns deserve specific examination.

**(a) `field.accept` MIME validation.** Q2 (line 28) says
"`accept` is a non-empty list of MIME types." TG-1 (lines
220-224) names the publish-time negative cases:

> - Empty `accept`.
> - Non-MIME `accept` entries.
> - Duplicate MIME entries.

So unsupported MIME-type strings fail at publish, not at
upload-url with a "TODO: better MIME parser later" branch.
The author cannot publish a form whose `accept` contains
non-MIME strings, so the upload-url endpoint never has to
decide what to do with an unparseable `accept` entry at
runtime.

**(b) Upload-url uses receipt + form-current authority, not a
parallel "anonymous" path.** Q3 (lines 70-72) binds the
upload-url endpoint to the same authority the public submit
uses:

> Authority is receipt-required, matching public submit. The
> endpoint must depend on `verify_applicant_receipt` and
> `authorize_public_intake`; it is public from a network path
> perspective but not anonymous from an API authority
> perspective.

There is no TODO-shape "skip authorization for the upload-url
endpoint, we'll add it later" path. TG-2 line 235 names the
auth negative case: "Missing/invalid receipt returns auth
failure through the existing receipt path."

**(c) S3 lifecycle policy.** Q6 (proposal lines 122-131) is the
one explicitly deferred item:

> Orphaned objects from presigned URLs that were never
> submitted are handled by S3 bucket lifecycle policy with a
> 24h expiry on the application-upload prefix. Configuring that
> lifecycle policy is deferred and must be called out in the
> implementation notes or follow-up backlog.

This is a documented deferral, not a hidden stub: orphan
cleanup does not gate the security or correctness of the
upload → presign → submit → HEAD chain (orphans never enter
`applications.responses`), and the proposal makes the deferral
visible to BACKLOG so it cannot silently rot. This is the same
shape as INIT-136 deferring full e2e to a follow-up — declared,
not a hidden stub. **The implementation notes / BACKLOG entry
is mandatory, not optional**, because without it the 24h
cleanup invariant has no owner. Flagged to implementation, not
the proposal gate.

**Risk:** the shortcut would be (a) write a presign endpoint
that accepts any MIME against `field.accept` without validating
the field's `accept` is well-formed, with a TODO to "tighten
the MIME validator later," (b) sign presigned URLs without
binding `Content-Type` so the upload-url endpoint becomes a
catch-all "give me a PUT URL" anonymous oracle with a "TODO:
tighten content-type binding," or (c) leave the orphan-object
problem completely undocumented so 24h cleanup never lands and
MinIO grows unbounded.

**Mitigation:** publish-time `accept` validation in
`FormDefinitionPublish` covers (a) per TG-1; presigned PUT
content-type binding (Q3 line 79) plus submit HEAD re-check
covers (b); explicit deferral with a "must be called out" note
covers (c) but is flagged to implementation as a mandatory
followup.

**Verdict:** Not a shortcut. One deferral (S3 lifecycle policy)
is explicitly documented and must be tracked to BACKLOG.

## C5 — SPA actually uploads via fetch PUT to presigned URL (not "skip upload, fake reference")

**Pass.**

§3 (Substrate → SPA, lines 196-213) locks the SPA upload flow
as a real PUT to the presigned URL, not a fake reference:

> - On file selection, request a presigned URL with
>   `form_definition_id`, `field_id`, `content_type`, and
>   `size_bytes`.
> - **Upload directly with `fetch(upload_url, {method: "PUT",
>   headers: {"Content-Type": file.type}, body: file})`.**
> - Track upload state per field: idle, uploading, uploaded,
>   failed.
> - Show upload progress where the browser can provide it; if
>   the implementation uses `fetch`, show deterministic
>   uploading/uploaded state and leave byte-level progress to a
>   later XHR refinement.
> - Store the resulting `{object_key, content_type, size_bytes}`
>   in the existing `responses` signal.

The ordering is binding: the SPA must (i) request a presigned
URL, (ii) PUT the file body to it, (iii) only then place the
returned `{object_key, content_type, size_bytes}` into the
submit payload. There is no documented path where the SPA
"skips upload and fakes a reference" — and even if a malicious
client tried that, the C1 server-side HEAD re-verification
would reject the submit with TG-3's "Object not found returns
422".

§3 (line 213) explicitly closes the sessionStorage-bypass door:

> The SPA must not place `File` objects in sessionStorage.
> Draft restoration can preserve uploaded file references after
> a successful upload, but it cannot resurrect a local file
> handle after refresh.

This rules out a "save the File and pretend the upload happened
across reloads" shortcut. The reference is only stored after
the upload returns success, and after refresh the user has to
re-select and re-upload — there is no trusted-client cache of
"already uploaded" without the actual S3 object existing.

The submit response shape (Q4 lines 82-95) carries only
`{object_key, content_type, size_bytes}`, never the presigned
URL itself:

> The application row persists that object exactly in
> `responses`. Do not persist the presigned URL; it is
> temporary bearer authority and should never become application
> state.

So the persisted state is not a replay-attackable URL but an
object key the server has already validated against live S3.

TG-4 (lines 258-267) names the SPA upload flow as a tested
behavior, including the actual PUT and the failure path:

> - A file field renders as a file input on its page.
> - Selecting an accepted file calls
>   `/api/public/applications/upload-url`.
> - **The browser performs a PUT to the returned presigned URL.**
> - Uploaded metadata is stored in local response state.
> - Submit includes `{object_key, content_type, size_bytes}` for
>   the file field.
> - Upload failure blocks submit and shows a retryable error
>   state.
> - Hidden file fields are not uploaded or submitted.

"Upload failure blocks submit" is the operative line for the
"skip upload, fake reference" shortcut: a SPA that silently
swallows a failed PUT and submits anyway must fail this test.

**Risk:** the shortcut would be (a) on file selection, skip the
PUT and fabricate a `{object_key, content_type, size_bytes}`
locally to satisfy the form schema, (b) submit a stale uploaded
reference on a different file (so the SPA uploads file A but
submits with file B's reference), (c) cache a File handle in
sessionStorage and pretend it's "uploaded" across refresh. Each
would let the SPA "look like" it works without actually placing
an object in S3.

**Mitigation:** the SPA contract requires the PUT and tracks
explicit per-field upload state (idle/uploading/uploaded/
failed); the persisted reference is only the structured
`{object_key, content_type, size_bytes}` (no replayable URL);
sessionStorage cannot revive File handles; and the server-side
HEAD re-check at submit is the catch-all backstop. TG-4 names
"Upload failure blocks submit" as a tested behavior.

**Verdict:** Not a shortcut.

## C6 — Tests genuinely exercise upload → presign → submit → HEAD chain

**Pass with one documented deferral (full MinIO e2e).**

The test plan covers the chain at four layers:

**TG-1 (lines 217-228) — contract layer.** `FormFieldFile`
round-trips through publish/read with all attributes preserved,
publish-time negative cases for malformed `accept` /
`max_size_bytes`, and SPA Zod schema acceptance/rejection of
`file` shapes. This is the contract foundation the rest of the
chain rests on.

**TG-2 (lines 230-240) — presign endpoint.** Receipt-required
positive case; auth, unknown form, stale form, unknown field,
non-file field, content-type-outside-accept, and oversize
negative cases; "Successful response contains `upload_url`,
`object_key`, and `expires_at`, and does not expose S3
credentials." The boto3 client boundary is mocked: "Mock
`file_upload.py` or the boto3 client boundary; do not require
a real MinIO service for these contract tests" (line 240). This
is the right call for contract coverage — the live MinIO
exercise belongs at e2e.

**TG-3 (lines 242-256) — submit-side HEAD chain.** Eight
explicit cases:

> - A required visible file field with a matching S3 object
>   succeeds and persists the structured response.
> - Missing required file response returns 422.
> - Hidden file response returns 422, preserving beta-2
>   conditional semantics.
> - Object not found returns 422.
> - Object content type mismatch returns 422.
> - Object size mismatch returns 422.
> - Object key with the wrong prefix, wrong field id, invalid
>   application id segment, or a different application id than
>   another submitted file field returns 422.
> - Oversized response metadata returns 422 even if S3 exists.

The test boundary is fakable: "Use a fake file-upload service
or monkeypatched S3 `head_object` boundary so tests are
deterministic" (line 256). Crucially, this still exercises the
**chain** — the submit path calls into the file-upload service,
which calls `head_object`, which the test fakes — so the
production code path through `validate_application_responses`
→ `file_upload.head_object` is the same path the test
exercises. A "stub-out the entire S3 service in submit" cheat
would fail the negative cases (object not found, content-type
mismatch, size mismatch) because those tests need the
boundary to be real-ish (fakeable, but observable from the
caller as if it were S3).

**TG-4 (lines 258-267) — SPA file input upload flow.** As
detailed in C5, this exercises the SPA-side upload + submit
sequence including the failure path.

**TG-5 (lines 269-272) — full MinIO e2e is deferred:**

> Defer full MinIO-backed browser e2e. The local e2e suite can
> add this after the test harness has a stable way to inspect
> MinIO objects and intercept presigned PUTs. This proposal
> requires API and SPA component coverage in beta-3, with e2e
> tracked as a follow-up.

This is the one part of the chain that is not exercised end-to-
end in this slice. The deferral is documented and bounded:
"with e2e tracked as a follow-up." For a public-facing upload
surface, **a tracked follow-up backlog item is mandatory**
because without one the deferral could rot — but the API and
SPA component coverage in TG-2 / TG-3 / TG-4 still exercise
each link of the chain in isolation, and the C2 / C3 server-
side re-verification is what actually defends the production
path. Flagged to implementation, not the proposal gate.

The "trust the SPA" version of the chain would require **all**
of the following to be uncovered, not any one of them:

- TG-2 not exist (no presign-side validation).
- TG-3 not exist (no submit-side HEAD).
- TG-4 not exist (no SPA upload PUT verification).

All three are present and named. The chain is exercised at the
component boundary at each link, with the live MinIO version
deferred behind a documented follow-up.

**Risk:** the shortcut would be (a) test only the contract
shape and skip TG-3, so the submit-side HEAD chain has no
coverage and a regression that drops the HEAD call lands
silently, (b) test only TG-2 and TG-4 (the two endpoint layers)
and skip TG-3 so the integration between submit validator and
HEAD is uncovered, or (c) defer everything to TG-5 e2e which
is then deferred to follow-up — leaving zero coverage in this
slice.

**Mitigation:** TG-2 covers the presign endpoint with the boto3
boundary mocked, TG-3 covers the submit HEAD chain with the
service module faked, TG-4 covers the SPA upload PUT, and the
TG-5 deferral is bounded to "follow-up" with the implementation
expected to file a backlog entry at slice landing.

**Verdict:** Not a shortcut. One deferral (full MinIO e2e) is
explicitly documented and must be tracked to BACKLOG.

## Verdict reasoning

INIT-137 ships exactly the contour the gate watches for:

- The submit validator gets a real server-side `HEAD` against
  the live S3 object inside `validate_application_responses`,
  with `ContentLength == size_bytes` and `ContentType ==
  content_type` re-verified after β-2 visibility evaluation.
  TG-3 names eight cases including object-not-found,
  content-type-mismatch, size-mismatch, and application-id-
  segment-mismatch. No "trust the SPA" path: the SPA's
  structured file response is not accepted verbatim, only the
  contract shape; the live S3 metadata is what binds.

- The presigned PUT contract binds `Content-Type` into the
  signature so the SPA cannot upload an object whose stored
  metadata diverges from what was promised, and the submit
  HEAD re-reads that metadata for equality. The size bound is
  checked at presign time (`<= max_size_bytes`), at submit
  payload time (`<= max_size_bytes`), and at submit live-object
  time (`ContentLength == size_bytes`). Three layers of
  defense, all named in TG-2 and TG-3.

- The SPA performs a real `fetch(upload_url, {method: "PUT",
  headers: {"Content-Type": file.type}, body: file})` to the
  presigned URL with explicit per-field upload state tracking,
  failure-blocks-submit semantics, and a sessionStorage rule
  that prohibits reviving File handles across refresh. The
  persisted submit reference is `{object_key, content_type,
  size_bytes}`, never the presigned URL. TG-4 names the PUT
  and the failure-blocks-submit case.

- TG-1 + TG-2 + TG-3 + TG-4 cover the upload → presign →
  submit → HEAD chain at the contract, presign endpoint,
  submit validator, and SPA layers respectively, with the
  boto3 boundary mocked / faked at the right level for
  determinism. TG-5 (full MinIO e2e) is deferred with a named
  follow-up; this is acceptable because the chain is still
  exercised at every link in isolation and the C2 / C3 server-
  side re-verification is the actual defensive layer.

- Anti-scope (lines 274-286) explicitly forbids placeholder
  stubs, transitional code paths, and feature flags; the only
  documented deferral inside the slice is the S3 bucket
  lifecycle policy for orphan-object cleanup, which is a
  capacity/cost concern, not a correctness or security gap
  (orphans never enter `applications.responses`).

**Two implementation notes (not proposal-level shortcuts) to
lock at slice landing:**

1. **S3 lifecycle policy backlog entry.** Q6 defers the 24h
   prefix-expiry rule with "must be called out in the
   implementation notes or follow-up backlog." Implementation
   must file a BACKLOG item before β-3 lands, otherwise the
   orphan-object invariant has no owner.
2. **Full MinIO e2e backlog entry.** TG-5 defers the
   end-to-end browser-through-MinIO test with "tracked as a
   follow-up." Implementation must file a BACKLOG item before
   β-3 lands, otherwise the e2e gap could rot indefinitely.

Both are owner-tracking concerns at the implementation
boundary, not proposal-level shortcuts. The proposal itself
ships the full server-side defensive chain and the SPA upload
contract this slice needs.

Verdict: LOW.

SHORTCUT_DONE: plans/risk/init-137-shortcut.md
