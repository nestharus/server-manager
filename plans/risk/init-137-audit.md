# INIT-137 — Audit risk gate

**Verdict:** LOW

Scope: BL-010 β-3 — public application forms can include
a single-file upload field. Adds presigned-PUT direct-to-
MinIO uploads via `POST /api/v1/public/applications/upload-url`,
a new `FormFieldFile` discriminated-union variant on the
shared `_BaseFormField` in
`services/api/app/contracts/applications.py`, S3 settings
in `services/api/app/core/settings.py`, an upload service
in `services/api/app/services/file_upload.py`, submit-time
`HEAD`-object verification in
`validate_application_responses`
(`services/api/app/services/applications.py`), and an SPA
file-input flow in
`services/web/src/features/public/ApplicationFormRoute.tsx`.

The audit gate inspects: receipt-required posture on the
new upload-url endpoint, content-type allowlist enforcement
at presign and submit (defense in depth), max-size
enforcement at presign and submit, object-key UUID
collision/guessability resistance, S3 `HEAD` existence
check before persistence, β-2 `visible_when` interaction
with file fields (hidden ⇒ no upload, no submitted
reference), PII discipline on submit response (no raw
URLs returned), DDoS posture (rate-limited presign
endpoint), boto3 endpoint URL trust boundary, and orphan-
object lifecycle handling.

Source proposal:
`proposals/28-init-137-file-upload.md`.
Source problem map: `research/28-bl-010-problem-map.md`.
β-2 ground state:
`proposals/27-init-136-multi-page-conditional.md` and
`plans/risk/init-136-audit.md`.

## A1 — Presigned-URL endpoint requires receipt (not anonymous)

**Surface:** Q3 (§2.3) locks the dependency tree:
"Authority is receipt-required, matching public submit.
The endpoint must depend on `verify_applicant_receipt` and
`authorize_public_intake`; it is public from a network
path perspective but not anonymous from an API authority
perspective."

**Existing primitives reused:**
- `verify_applicant_receipt` is already wired on
  `submit_public_application_endpoint`
  (`services/api/app/api/v1/endpoints/applications/public.py:32`)
  and resolves a `DiscordIdentity` from the receipt cookie/
  header. Same dependency on the upload-url endpoint
  enforces the same applicant-must-be-receipt-bound rule.
- `authorize_public_intake`
  (`services/api/app/services/authorization.py:24`) is the
  same gate the submit endpoint uses; pulling it onto the
  upload-url endpoint inherits whatever Cedar/policy guard
  the submit path already passes.
- Receipt TTL is `RECEIPT_TTL_SECONDS = 600`
  (`services/api/app/services/applicant_discord_auth.py:23`),
  matching Q3's locked 10-minute presign expiry.

**Anti-bypass posture:** Q3 also locks "It validates:
`form_definition_id` is the current public form
definition being answered. `field_id` exists on that form
and has `type == "file"`. The field is not author-hidden
by contract; runtime conditional visibility is still
rechecked at submit. `content_type` is exactly in
`field.accept`. `size_bytes <= field.max_size_bytes`.
`size_bytes > 0`." A crafted client with a stolen receipt
can still only mint URLs for the *current* public form's
file fields, with allowlisted content type and bounded
size.

**TG-2 coverage:** "Receipt-required request succeeds for
a current public form file field. Missing/invalid receipt
returns auth failure through the existing receipt path.
Unknown form id, stale form id, unknown field id, and
non-file field id fail." Direct test on the dependency
chain.

**Verdict:** Receipt-required is locked at the dependency-
injection layer, mirrors the existing public-submit
posture exactly, and is exercised by TG-2. Audit risk LOW
for A1.

## A2 — Content-type allowlist enforced at presign AND submit

**Defense-in-depth surface (Q3 + Q5):**

1. **Presign-time check (Q3, §2.3):** "`content_type` is
   exactly in `field.accept`." Client cannot mint a URL
   for a content type the form authoring did not approve.
2. **Presign-time signature binding (Q3, §2.3):** "The
   API must include the expected `Content-Type` in the
   presigned PUT parameters so the later `head_object`
   metadata can be checked against the contract." S3
   binds the signed `Content-Type`; a client uploading
   with a different header invalidates the signature.
3. **Submit-time response check (Q5, §2.5):**
   "`content_type` must be in `field.accept`."
4. **Submit-time `HEAD` check (Q5, §2.5):** "`ContentType`
   must equal `content_type`." Even if the presigned
   binding were bypassed, the persisted object's metadata
   must round-trip through the validator.

**TG-2 coverage:** "`content_type` outside `field.accept`
returns 422" exercises the presign gate.
**TG-3 coverage:** "Object content type mismatch returns
422" exercises the submit gate against the `HEAD`
metadata.

**Allowlist surface (Q2, §2.2):** `accept` is a non-empty
list of MIME types. TG-1 covers "Empty `accept`",
"Non-MIME `accept` entries", "Duplicate MIME entries" at
publish time, so the allowlist itself cannot be authored
into a permissive degenerate.

**Residual risk:** the proposal does not specify whether
`accept` entries can be wildcards (e.g., `image/*`) or
must be fully-qualified (e.g., `image/png`). The Q3 rule
"`content_type` is exactly in `field.accept`" implies
fully-qualified equality, but a non-MIME validator at
publish could permit `image/*` if not strict. F1 below.

**Verdict:** Allowlist enforced at four layers (publish-
time validation, presign check, presign signature,
submit `HEAD` check). Audit risk LOW for A2, with one
finding (F1) on `accept` entry strictness.

## A3 — `max_size_bytes` enforced at presign AND submit

**Presign-time check (Q3, §2.3):**
"`size_bytes <= field.max_size_bytes`. `size_bytes > 0`."
The client must declare an exact `size_bytes` in the
presign request and the API rejects requests above the
field cap or non-positive.

**Submit-time response check (Q5, §2.5):**
"`size_bytes` must be positive and `<= field.max_size_bytes`."

**Submit-time `HEAD` check (Q5, §2.5):** "`ContentLength`
must equal `size_bytes`." This binds the persisted
object's true byte count to the submitted metadata; a
client cannot under-report size in `responses` to fit
under `max_size_bytes` while uploading a larger object.

**Publish-time bound (TG-1):** "`max_size_bytes <= 0`"
fails publish, so the field cap cannot be authored into
zero/negative degenerates.

**Default cap (Q2):** `max_size_bytes: int = 10 * 1024 *
1024` (10 MiB). A reasonable default for character-sheet
or screenshot artifacts, well under typical S3 multipart
thresholds.

**Presign signature on Content-Length:** Q3 explicitly
binds the expected `Content-Type` into the presigned PUT
parameters but does *not* explicitly require the signed
URL to bind `Content-Length`. boto3
`generate_presigned_url("put_object", Params=...)` will
sign whatever parameters the caller passes; if
`ContentLength` is in `Params`, S3 enforces it at upload
time as part of signature validation. If the
implementation omits `ContentLength` from `Params`, S3
will accept any Content-Length the client sends, and the
size guard reduces to "presign rejects pre-stated size >
cap" + "submit `HEAD` rejects actual size > cap" — still
defense-in-depth, but missing the upload-time abort. F2
below.

**TG-2 coverage:** "`size_bytes > max_size_bytes` returns
422" at presign.
**TG-3 coverage:** "Object size mismatch returns 422" at
submit (`HEAD ContentLength != size_bytes`); "Oversized
response metadata returns 422 even if S3 exists" at
submit response validation.

**Verdict:** Size cap is enforced at three locked layers
(publish, presign, submit-`HEAD`). Audit risk LOW for A3,
with one finding (F2) on whether the presigned URL itself
binds Content-Length so S3 aborts oversized uploads
before they consume bandwidth.

## A4 — Object key includes a UUID component (no collision/guessability)

**Key shape (Q3 + Q5):**
`applications/<application_id>/<field_id>/<uuid>`.

Two UUIDv4 components per key:
- `application_id`: reserved by the upload-url endpoint
  per Q5 ("the upload-url endpoint generates a UUID that
  is reserved as the application object namespace and
  embeds it in the object key").
- `<uuid>`: per-object suffix.

UUIDv4 collision probability is negligible (122 random
bits per UUID; product of two UUIDs is 244 random bits).
Guessability is bounded by the same entropy — even with
`field_id` and the `applications/` prefix known, an
attacker cannot enumerate live keys.

**Server-side key construction:** Q3 + §3 ("API service")
locks key generation inside `file_upload.py`, not from
client input: "Generate object keys under
`applications/<application_id>/<field_id>/<uuid>`, where
`application_id` is a UUID reserved by the upload-url
service before submit." A client cannot submit a chosen
key for the upload URL.

**Submit-time key parsing (§3 Submit validation):**
"_submit_application_internal should resolve the
application id before persistence. If visible file
responses are present, it uses the shared application id
parsed from their `object_key` values." The validator
must reject keys that do not match the prefix shape, do
not match the submitted `field_id`, or disagree across
multiple file fields' application_ids. TG-3 covers
"Object key with the wrong prefix, wrong field id,
invalid application id segment, or a different
application id than another submitted file field returns
422."

**Application-id coordination across multiple file
fields:** the proposal locks "all submitted file
responses to use the same application id" but the
upload-url request body (Q3) does not include an
`application_id` parameter. A SPA with two file fields
would receive two different `application_id` values
unless either (a) the SPA reuses the first response's
embedded `application_id` for subsequent presign requests
(but the request schema has no field for it), (b) the
upload-url endpoint persists per-receipt state to reuse
the same UUID, or (c) the SPA is implicitly limited to
one file field per form by an unstated invariant. F3
below.

**Verdict:** UUID collision and guessability are
structurally bounded. Server-side key construction
prevents client-chosen keys. One real design gap (F3) on
how multi-file-field forms coordinate a shared
application_id. Audit risk LOW for A4, with the F3
finding requiring resolution before β-3 forms can author
two file fields.

## A5 — Submit verifies the S3 object exists (HEAD) before persisting

**`HEAD` requirement (Q5, §2.5):** "The service must
`HEAD` the S3 object. `ContentLength` must equal
`size_bytes`. `ContentType` must equal `content_type`."

**Call site (§3 Submit validation):** the `HEAD` check
runs inside `validate_application_responses`, which is
invoked from `_submit_application_internal` before the
application row is inserted (matching β-2's
"server-authoritative validator-before-persist" model).

**Non-existence is a 422, not a 5xx (§2.5):** "Reject
validation failures as 422 via the existing public submit
error mapping. Missing objects, mismatched metadata,
oversized objects, wrong content type, unknown response
keys, hidden file responses, and malformed file response
objects are validation errors." The error normalization
is locked in §3 ("API service"): "Normalize boto3
`ClientError` failures into application validation errors
instead of leaking S3 internals."

**Bypass surface — race between presign and submit:**
1. Applicant requests presign URL (10-min expiry).
2. Applicant uploads object to S3.
3. Applicant submits with object reference.
4. `HEAD` succeeds, validation passes, application
   persisted.

Between steps 2 and 3, an attacker who learned the
object key cannot meaningfully poison the row because the
submit reverifies content_type/size against `HEAD`. Even
if the attacker overwrote the object with different
bytes, the `HEAD` would surface a content-type or size
mismatch (assuming the attacker doesn't replicate
identical metadata), and S3 PUT-object overwrites require
the same signed URL or a separate IAM grant the public
applicant does not have.

**TG-3 coverage:** "Object not found returns 422", "A
required visible file field with a matching S3 object
succeeds and persists the structured response", "Object
content type mismatch returns 422", "Object size
mismatch returns 422." Direct exercise on the four
failure modes.

**Test isolation:** "Use a fake file-upload service or
monkeypatched S3 `head_object` boundary so tests are
deterministic." TG-3 isolates from a live MinIO so the
contract is exercised at the validator layer.

**Verdict:** `HEAD`-before-persist is locked at the
algorithm, call-site, and test-plan layers. Audit risk
LOW for A5.

## A6 — Hidden file field doesn't require upload AND doesn't accept submitted reference

**Hidden semantics (Q2, §2.2):** "File fields may use
beta-2 `page` and `visible_when`; when hidden, the
browser does not upload or submit the reference and the
server does not require it."

**β-2 visibility integration (§3 Submit validation):**
"Modify `validate_application_responses` in
`services/api/app/services/applications.py` so file
fields participate in the existing visibility, required-
field, unknown-field, and per-type validation pass. The
validation must happen after beta-1 chapter-selector
form selection and beta-2 visibility evaluation, using
the same effective form snapshot that is persisted."

This locks the order:
1. β-1 chapter-selector form selection.
2. β-2 visibility evaluation (per-field `visible_when`).
3. β-3 file-field validation, applied only to *visible*
   file fields.

A hidden file field is filtered out before the required-
field check, so its absence does not trip the 422.
A hidden file field's submitted reference is rejected by
the existing β-2 "hidden field rejection" branch
(INIT-136 algorithm step 5), which TG-3 exercises:
"Hidden file response returns 422, preserving beta-2
conditional semantics."

**Anti-bypass via SPA:** the SPA must not request a
presign URL for a hidden file field (Q3: "The field is
not author-hidden by contract; runtime conditional
visibility is still rechecked at submit"). The
presign endpoint's runtime visibility recheck closes the
"presign URL for hidden field" loophole — even if the SPA
were defective, the API rejects the presign request
itself.

**TG-4 coverage:** "Hidden file fields are not uploaded
or submitted." Browser-side enforcement.
**TG-3 coverage:** "Hidden file response returns 422,
preserving beta-2 conditional semantics." Server-side
enforcement.

**Visibility predicate sources (β-2 lock):**
`visible_when` predicate sources are restricted to scalar
content fields (`short`, `long`, `number`, `select`,
`boolean`); a `file` field cannot be a predicate source
(its response is a structured object, not a scalar). The
proposal does not add `file` to the supported source-type
list, which is the safe default. INIT-136 §2.1 lists the
allowed source types and excludes `multi_select` and
`chapter_select`; β-3 inherits that restriction.

**Verdict:** Hidden file fields are filtered at four
layers (SPA render, SPA payload assembly, presign-time
visibility recheck, submit-time visibility recheck).
Audit risk LOW for A6.

## A7 — PII: file URLs not returned to non-officers; submit response excludes raw URLs

**Submit response shape (Q4, §2.4):** "File fields in
`responses` carry structured references, not raw URLs:
`{"object_key": "...", "content_type": "...", "size_bytes":
...}`. The application row persists that object exactly
in `responses`. Do not persist the presigned URL; it is
temporary bearer authority and should never become
application state."

**Public submit receipt unchanged:** the existing
`PublicApplicationSubmissionReceipt` returns
`{message, application_id}` only
(`services/api/app/api/v1/endpoints/applications/public.py:25-47`).
β-3 does not extend the receipt to include file URLs or
object keys. The applicant's confirmation flow returns to
the SPA via the receipt bearer the applicant already
holds, not through new file metadata.

**Officer readback explicitly deferred (Q7 anti-scope):**
"File-served-back endpoint for officers. Officer review
UI for opening applicant uploads." A future officer
attachment-serving endpoint will authorize on
`object_key`, not on a stored URL.

**Presigned-URL response surface (Q3):** the presign
response contains `upload_url`, `object_key`, and
`expires_at`. The `upload_url` is a write-only bearer
URL scoped to the receipt-holding applicant for 10
minutes; it is *not* a download URL. TG-2 covers
"Successful response contains `upload_url`, `object_key`,
and `expires_at`, and does not expose S3 credentials."

**`responses` JSONB persistence:** the structured
reference object is persisted in the existing JSONB
column without a presigned-URL field, so a future
officer surface that reads `responses` will see only the
opaque key. There is no historical row containing a raw
URL that a later endpoint could accidentally return.

**Residual risk:** if a future officer surface naively
generates a presigned `GET` URL from the `object_key` and
returns it in an officer-facing API response, that URL
would be a temporary download bearer leakable through
browser history, error monitors, or client logs. β-3
does not introduce that surface, but the audit notes
that the future officer-readback endpoint must follow
the same "structured reference, no raw URLs" discipline
or stream bytes through a server-authorized handler. F4
below (observation, not blocker).

**Verdict:** No raw URLs in submit response, in
`responses` JSONB, or in officer-readable surfaces (which
do not exist yet). Audit risk LOW for A7, with one
forward-looking observation (F4).

## A8 — DDoS: presign endpoint inherits the public-intake rate limit

**Existing rate-limit posture:** the Kong plugin
`public-intake-rate-limit` is configured at 5/min, 50/hour,
local policy
(`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:6-12`)
and applied via Ingress on path
`/api/v1/public/applications` (Prefix) and
`/api/v1/public/chapters` (Prefix). The web ingress
(`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`)
applies the same plugin on `/api/public/applications`
(Prefix), `/api/public/chapters` (Prefix), and
`/api/applications` (Prefix).

**Path inheritance:** the new endpoint is locked at
`POST /api/v1/public/applications/upload-url` (Q3, §3
"API endpoint": "Mount it under the existing applications
router family so the final path is
`POST /api/v1/public/applications/upload-url`"). The SPA-
facing path is `/api/public/applications/upload-url`.

Both paths sit *under* the existing Prefix rules
(`/api/v1/public/applications/...` ⊂
`/api/v1/public/applications`; same for the SPA-facing
path), so the Kong rate-limit plugin matches without an
ingress change.

**No new ingress block needed:** the proposal's §3
("API endpoint") and §3 ("SPA") are silent on ingress
YAML edits, which is correct because Prefix matching
already covers the new path. An audit trip-wire: the
implementation must not introduce a *new* ingress entry
for the upload-url path, which would create a parallel
rule outside the rate-limit plugin's scope.

**Rate-limit budget for a real flow:** an applicant
filling a form with N file fields makes N+1 public-intake
requests (one upload-url per field plus one submit), all
under the 5/min budget. With the default 10-MiB cap and
a reasonable form size (≤ 3 file fields), the budget
holds for a normal applicant; a malicious actor cannot
mint more than 5 presigned URLs per receipt-holding
identity per minute.

**Submit-time DDoS surface:** an attacker minting URLs
without uploading consumes only Kong rate-limit budget
and S3 PUT capacity (zero, since no upload happens).
Orphan keys are harmless beyond storage cost, which the
24h lifecycle policy reclaims (Q6, A10).

**Authority-bound DDoS:** because the endpoint requires
a receipt (A1), an unauthenticated attacker cannot mint
URLs at all — they would first need to complete the
Discord OAuth applicant flow. The rate limit is a
secondary defense for receipt-holding abuse.

**Residual risk:** the 5/min budget is shared with the
submit endpoint. A burst of presign requests can
exhaust the budget for a legitimate submit. This is the
same trade-off β-1 and β-2 accepted for the global
public-intake gate; β-3 does not change it.

**Verdict:** Rate limit applies via Prefix routing
without ingress changes. Authority gate (A1) makes the
attack surface receipt-bound. Audit risk LOW for A8,
with one trip-wire observation: implementation must not
introduce a new ingress entry that escapes the existing
plugin scope.

## A9 — S3 endpoint URL is settings-driven, not user-controlled

**Settings boundary (§3 Dependencies and settings):**
"Add S3 settings to `services/api/app/core/settings.py`:
`s3_endpoint`, `s3_region`, `s3_bucket`, `s3_access_key_id`,
and `s3_secret_access_key`. Keep the existing GitOps env
names unchanged because `api-deployment.yaml` already
provides them."

**Trust source:** `api-deployment.yaml` injects the
endpoint from `S3_ENDPOINT` (set by the GitOps deployment
manifests, not by request input). The
`object-storage-bucket-credentials-infisicalsecret.yaml`
syncs credentials from Infisical. There is no request-
side path that lets a client influence the boto3
endpoint URL.

**Audit interpretation of the gate item:** the gate
item reads "boto3 doesn't accept arbitrary endpoints" —
boto3 itself *does* accept any well-formed `endpoint_url`
because that is its design (an S3-compatible client must
be able to address arbitrary endpoints). The substantive
gate is whether the *endpoint URL is itself trusted
input* — and it is, because it is sourced from
deployment-controlled settings. The proposal's §3
("API service") locks this: "Build a MinIO-compatible
`boto3.client(...)`. Do not let callers construct S3
clients directly in endpoint or application-submit
modules." Centralizing client construction in
`file_upload.py` removes the temptation to thread an
endpoint URL through call sites where it could be
overridden.

**Credential exposure:** §3 ("API service") and Q4
explicitly forbid exposing credentials in the presign
response. TG-2 covers "does not expose S3 credentials."
Pre-signed URLs by design contain only a signed query
string, not the secret access key.

**Operational risk:** if a deployment-side
misconfiguration sets `S3_ENDPOINT` to an attacker-
controlled host, all applicant uploads would route there.
This is true of any S3-compatible deployment and not
specific to β-3; the GitOps trust chain (Infisical
secrets + deployment manifests reviewed in PR) is the
boundary. F5 below (observation).

**Verdict:** Endpoint URL is settings-driven, not
request-input-driven. Centralized client construction
prevents callers from threading arbitrary endpoints.
Audit risk LOW for A9, with one operational observation
(F5).

## A10 — Orphan handling deferred but documented

**Orphan source:** an applicant requests a presigned URL
(reserving an `application_id` UUID and an object-key
namespace), uploads the object, and never submits — or
submits a payload that fails validation, leaving the S3
object alive without a corresponding application row.

**Lifecycle lock (Q6, §2.6):** "Objects are not tied to
an application until submit succeeds. Orphaned objects
from presigned URLs that were never submitted are
handled by S3 bucket lifecycle policy with a 24h expiry
on the application-upload prefix. Configuring that
lifecycle policy is deferred and must be called out in
the implementation notes or follow-up backlog."

**Anti-scope (§5):** "S3 lifecycle policy
implementation; document the needed 24h cleanup rule as
deferred." The deferral is named explicitly in the
backlog discipline, not silently dropped.

**Audit interpretation:** β-3 does *not* require the
lifecycle policy to land in the same PR; it requires a
documented 24h cleanup expectation that a follow-up
ticket will implement. The audit confirms (a) the
documented expectation exists in the proposal, (b) the
anti-scope acknowledges the deferral, and (c) no
contract or behavior in β-3 depends on lifecycle cleanup
having already happened (orphans accumulate harmlessly
under the prefix until the policy lands).

**Storage-cost surface during the deferral window:** at
the default 10-MiB cap and 5/min Kong rate limit per
receipt-holding identity, a sustained orphan-creating
attacker can deposit ~5 × 10 MiB = 50 MiB/min
(theoretical max if every presign is followed by a real
upload). For local MinIO this is negligible; for a
production deployment the lifecycle policy should land
before β-3 ships there. F6 below.

**Verdict:** Deferral is documented at proposal,
implementation-notes, and anti-scope layers. β-3
behavior is independent of lifecycle policy enforcement.
Audit risk LOW for A10, with one finding (F6) on the
deferral's production-deployment dependency.

## Findings

### F1 — `accept` entry strictness (wildcards vs. fully-qualified MIME)

**Severity:** medium-low (correctness, allowlist
permissiveness).

**Where:** publish-time validation of `FormFieldFile.accept`
in `services/api/app/contracts/applications.py` (the new
β-3 variant) and the presign-time check in
`services/api/app/services/file_upload.py`.

**Risk:** Q3 locks "`content_type` is exactly in
`field.accept`", which implies fully-qualified MIME
equality. TG-1 covers "Non-MIME `accept` entries" but
does not name whether `image/*` is rejected as non-MIME
or accepted as a wildcard. If publish-time validation
permits `image/*` but presign uses strict equality, no
content type would ever match and the field would be
unusable. Conversely, if presign treats `image/*` as a
wildcard, the allowlist becomes broader than the
publish-time intent.

**Action:** lock the `accept` entry validator to
fully-qualified `type/subtype` MIME strings (regex
e.g., `^[a-z]+/[a-z0-9.+-]+$`), reject wildcards at
publish time, and document in TG-1 that `image/*` and
`*/*` fail publish. This keeps the presign equality
check and the publish allowlist semantics aligned.
Add a TG-1 case for "wildcard `accept` entry fails
publish."

### F2 — Presigned URL must bind Content-Length so S3 aborts oversized uploads

**Severity:** medium (defense-in-depth completeness;
bandwidth and orphan-storage cost).

**Where:** presigned URL generation in
`services/api/app/services/file_upload.py`.

**Risk:** Q3 explicitly binds `Content-Type` into the
presigned PUT parameters but does not explicitly bind
`Content-Length`. boto3
`generate_presigned_url("put_object", Params={...})`
signs whatever `Params` keys are passed; if the
implementation passes `ContentType` but omits
`ContentLength`, S3 will accept any body size up to its
own object cap (5 GiB for single PUT). The submit-time
`HEAD ContentLength == size_bytes` check will reject the
oversized object at validation time, so the application
row is never created — but the upload bandwidth is
already consumed, the orphan object sits in the bucket
until lifecycle reclaim, and the 422 error gives an
attacker a feedback loop to confirm cap discovery
without paying compute on the API side.

**Action:** the implementation must pass
`ContentLength=size_bytes` (the exact requested size, not
`max_size_bytes`) into the boto3 `generate_presigned_url`
`Params` dict so S3 enforces the size at upload time,
not just at submit time. Add a TG-2 or TG-3 case that
mocks the boto3 client and asserts `ContentLength` is in
the signed params. Alternatively, switch to
`generate_presigned_post` with a
`content-length-range` condition, which gives S3 a
hard upload-time abort.

If the implementation cannot bind `ContentLength` (e.g.,
because the SPA's `fetch(...PUT, body: file)` cannot
reliably set the header in all browsers), document the
fallback: presign rejects requested-size > cap (Q3),
submit `HEAD` rejects actual-size > cap (Q5), and S3 PUT
itself enforces only the bucket's policy cap. The
defense-in-depth claim in the audit gate item ("URL
embeds limit") is satisfied by `Content-Length` binding,
not by the request-side `size_bytes` check alone.

### F3 — Multi-file-field application_id coordination

**Severity:** medium (design gap; unblocks β-3 forms
with two file fields).

**Where:** the upload-url contract in
`services/api/app/contracts/applications.py` and the
upload-url service in
`services/api/app/services/file_upload.py`.

**Risk:** Q5 locks "all submitted file responses to use
the same application id" and "If a malicious or stale
submit references a conflicting application id, the
normal insert uniqueness failure is treated as
validation/duplicate failure." The validator rejects
mismatched application_ids across file fields, but the
upload-url request (Q3) has no `application_id` field, so
two presign calls for two file fields each receive a
*different* server-generated UUID — making mismatched
IDs the default outcome for any form with multiple file
fields. The applicant cannot submit such a form
successfully unless the SPA coordinates somehow.

The proposal does not name a coordination mechanism. Three
options exist:
- **(a) SPA passes the prior `application_id` back**:
  extend the upload-url request body with an optional
  `application_id` field; the endpoint reuses it when
  provided, generates a new one when omitted.
- **(b) Endpoint persists per-receipt state**: track
  the receipt → reserved-application_id mapping in a
  short-lived store so subsequent presign calls under
  the same receipt return the same `application_id`.
- **(c) Limit β-3 to one file field per form**: add a
  publish-time validator that rejects forms with more
  than one `type: "file"` field; revisit when β-4
  adds multi-file or multi-field-coordination.

**Action:** lock one of the three options before β-3
ships. Option (a) is the lowest-coupling change (one
optional contract field, idempotent server-side), but
needs a guard preventing receipt holders from passing
*another* applicant's `application_id` into their
presign call (e.g., reject if the namespace is already
referenced by a persisted application). Option (c) is
the cheapest stopgap that does not block the BL-010
goal: a "single-file upload" feature naturally aligns
with one file field per form for β-3, with multi-file-
field coordination owned by a follow-up. Add a TG-1 case
covering whichever option is locked (e.g., publish
rejects a form with two `type: "file"` fields).

### F4 — Future officer-readback endpoint must follow no-raw-URL discipline

**Severity:** low (forward-looking observation, β-3
itself is clean).

**Where:** future officer attachment-serving endpoint
(deferred per Q7 anti-scope).

**Risk:** when a future slice adds officer readback, a
naive implementation might generate a presigned `GET`
URL from `object_key` and return it in the officer-
facing API response. That URL becomes a temporary
bearer download token, leakable through browser history,
client-side error monitors, screen recordings, and
anywhere else the officer surface logs response bodies.
β-3 sets the precedent that `responses` JSONB stores
opaque keys, not URLs; the future readback must keep
that precedent.

**Action:** when the officer-readback slice opens, the
audit for that slice must lock either (a) byte-streaming
through a server-authorized handler that does not return
a URL to the client, or (b) very short-lived presigned
`GET` URLs with strict `Content-Disposition: attachment`
and no caching, scoped to a specific officer-authority
check at request time. Document this expectation in the
β-3 implementation notes or BL-010 follow-up backlog
entry, since it is the single most likely place for a
future PII regression.

### F5 — `S3_ENDPOINT` deployment-config trust boundary

**Severity:** low (operational observation).

**Where:** GitOps deployment manifests injecting
`S3_ENDPOINT` and `api-deployment.yaml`.

**Risk:** the audit item asks whether boto3 endpoint URLs
are validated. The substantive answer is that the
endpoint URL is settings-driven, not user-input-driven.
The residual surface is a deployment-side
misconfiguration (a malformed or attacker-controlled
`S3_ENDPOINT` value) that would route applicant uploads
to the wrong host. This is true of any S3-compatible
deployment and is not introduced by β-3.

**Action:** document the operational expectation that
`S3_ENDPOINT` is reviewed at deployment-PR time and
sourced from Infisical with the same trust model as
existing `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY`. No
β-3 contract change is required; this is a follow-up for
the GitOps review checklist.

### F6 — Lifecycle-policy deferral is local-deployment-friendly, must precede production

**Severity:** low (deployment-stage gating).

**Where:** S3 bucket lifecycle policy on the
`server-manager` MinIO bucket (Q6 deferral).

**Risk:** β-3 ships without the 24h orphan-cleanup
lifecycle rule. Locally this is fine because storage is
unbounded ephemeral MinIO. In a production-like
deployment with bounded object storage, sustained
orphan-creating presign-without-submit traffic
accumulates objects until the policy lands.

**Action:** open a follow-up backlog entry referencing
Q6 of this proposal, scoped to "configure 24h lifecycle
policy on the `applications/` prefix in the
`server-manager` bucket." Gate any production deployment
of β-3 on that ticket landing first. Add a "production-
deploy precondition" line to the BL-010 β-3 backlog
entry so the deferral cannot be lost.

## Verdict reasoning

INIT-137 holds the audit gate at LOW risk:

- **Receipt-required (A1):** the upload-url endpoint
  reuses `verify_applicant_receipt` and
  `authorize_public_intake` from the existing public-
  submit endpoint. TG-2 directly tests
  receipt-required posture. No anonymous access path.
- **Content-type allowlist (A2):** enforced at four
  layers — publish-time MIME validation, presign-time
  equality check, presign-time signature binding, and
  submit-time `HEAD ContentType` check. F1 flags an
  ambiguity on wildcard MIME entries that should be
  resolved by strict fully-qualified validation.
- **Size cap (A3):** enforced at publish, presign, and
  submit-`HEAD`. F2 flags whether the presigned URL
  itself binds `Content-Length` so S3 aborts oversized
  uploads at upload time, closing the bandwidth-and-
  orphan-cost gap.
- **Object-key UUIDs (A4):** server-side construction
  with two UUIDv4 components (244 bits total). F3 flags
  the multi-file-field application_id coordination gap
  — the validator rejects mismatched IDs but the
  presign contract has no mechanism for the SPA to
  reuse a single ID across file-field calls.
- **`HEAD`-before-persist (A5):** locked at the
  validator algorithm and call-site layers. TG-3
  exercises object-not-found, content-type mismatch,
  and size mismatch cases.
- **Hidden file fields (A6):** filtered at SPA render,
  SPA payload assembly, presign-time visibility recheck,
  and submit-time visibility recheck — inheriting β-2's
  visibility pass without introducing a parallel path.
- **PII / no raw URLs (A7):** `responses` stores
  structured `{object_key, content_type, size_bytes}`
  references, never URLs; the public submit receipt is
  unchanged. F4 is a forward-looking note for the
  deferred officer-readback slice.
- **Rate-limit posture (A8):** the new endpoint sits
  under the existing `/api/v1/public/applications`
  Prefix rule and inherits the Kong
  `public-intake-rate-limit` plugin without an ingress
  edit. Receipt-required posture (A1) is the primary
  authority gate.
- **boto3 endpoint trust (A9):** the endpoint URL is
  settings-driven (Infisical + GitOps), not user-input-
  driven; centralized client construction in
  `file_upload.py` prevents callers from threading
  arbitrary endpoints. F5 is an operational observation.
- **Orphan deferral (A10):** documented at proposal,
  implementation-notes, and anti-scope layers. β-3
  contract behavior is independent of policy
  enforcement. F6 flags the production-deploy
  precondition.

Verdict: LOW.

AUDIT_DONE: plans/risk/init-137-audit.md
