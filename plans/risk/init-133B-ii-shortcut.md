---
ticket: INIT-133B-ii
gate: shortcut
verdict: LOW
inputs:
  - proposals/14-init-133B-ii-detail-transcript.md
  - proposals/13-init-133B-i-officer-queue.md
  - services/web/src/api/client.ts
  - services/api/app/contracts/applications_transcript.py
  - services/api/app/contracts/applications.py
  - plans/risk/init-133B-i-shortcut.md
---

# INIT-133B-ii — Shortcut risk gate

**Verdict:** LOW

## S1 — `ApiError` reused from β-i (no parallel error class)

**Choice:** §5 ("Component Contract Preview") and §11
("Hookpoint Preview" → Reuse) both name
`services/web/src/api/client.ts:70-84` `ApiError` and
`services/web/src/api/client.ts:100-115` `getJson` as the
shared error/fetch path. The two new client functions
`fetchOfficerApplication(id)` and
`fetchOfficerApplicationTranscript(id)` are added to the same
file (§3 "Modified files") and the proposal does not
introduce a parallel error class, parallel
`readErrorPayload`, or a new transport wrapper. The detail
route classifies `401`, `403`, `404`, `422`, Zod parse
failure, and 5xx by inspecting the existing `ApiError.status`
and `ApiError.payload` shape.

**Risk:** a parallel error class would split the two officer
surfaces (queue vs. detail) into divergent classification
logic, so a 401 on the detail page might not produce the same
auth-required panel β-i already ships.

**Mitigation:** §3 confines the change to extending
`client.ts` (not creating a sibling client module) and §11
explicitly lists the existing `getJson`/`ApiError` pair under
Reuse, not New.

**Verdict:** Not a shortcut.

## S2 — Zod schemas mirror Pydantic contracts strictly

**Choice:** The Pydantic side uses closed contracts:
`_ApplicationModel` has `model_config = ConfigDict(extra=
"forbid")` (`services/api/app/contracts/applications.py:21-22`)
and `_ApplicationTranscriptModel` has the same closure
(`services/api/app/contracts/applications_transcript.py:12-13`).
The proposal mirrors this on the SPA side as follows:

- `applicationReadSchema` is expanded to enumerate every
  field the detail route renders: `form_definition_id`,
  `form_version`, `form_snapshot`, `responses`, `queued_at`,
  `claimed_at`, `review_started_at`, `decided_at`,
  `withdrawn_at`, `created_at`, `updated_at` alongside the
  β-i fields (proposal §5 → "applicationReadSchema must stop
  relying on `.passthrough()` for fields this route
  renders"). This matches `ApplicationRead` at
  `services/api/app/contracts/applications.py:352-372` field-
  for-field for the rendered surface.
- The transcript schemas are a discriminated union, not a
  blob — see S4.

**Caveat (not blocking):** today's `applicationReadSchema`
calls `.passthrough()` (`services/web/src/api/client.ts:41-
51`), and the proposal text adds the rendered fields but does
not explicitly remove `.passthrough()`. Because the server
contract is `extra="forbid"`, extra fields cannot arrive on
the wire — `.passthrough()` is dead code, not a real laxness.
Worth removing during implementation, but the SPA cannot
silently render server-asserted unknown fields because the
server cannot emit them. Flag, not a shortcut.

**Risk:** an unenforced Zod schema would let the SPA render a
malformed contract response, mask backend drift, or skip
authorization-relevant gating fields.

**Mitigation:** the Pydantic source is closed; the Zod
schema enumerates every rendered field; transcript schemas
are a real discriminated union over the actual `type`
discriminator.

**Verdict:** Not a shortcut.

## S3 — Bridge does NOT use `Depends(get_current_actor)`, `verify_applicant_receipt`, or read `applicant_receipt` cookie

**Choice:** §6 ("Authorization Model") explicitly states:
"The bridge still ignores applicant receipts and browser-
supplied `X-Actor-*` headers, consistent with the existing
guard test (`services/api/tests/test_web_officer_applications
.py:660-758`). That guard must include all four officer
bridge routes after this slice." §7 ("API bridge tests")
expands the dependency-tree guard from list+claim to list+
claim+detail+transcript, "preserving the existing no
`get_current_actor`, no `CURRENT_ACTOR.get`, no
`verify_applicant_receipt`, no `applicant_receipt` source
assertions" (proposal §7 line referencing
`services/api/tests/test_web_officer_applications.py:723-758`).

§4 ("Bridge service calls") also keeps both new endpoints
`async def` only because `_build_officer_actor` awaits member
resolution, not because of any header- or cookie-reading
dependency. The bridge calls services as synchronous Python
functions (`read_application`, `require_application_read_
authority`, `read_application_transcript`) — no `Depends`-
injected actor.

**Risk:** the same most-dangerous shortcut S3 of β-i — letting
the browser forge officer identity via `X-Actor-*` headers,
or laundering applicant-receipt identity into officer reads.

**Mitigation:** dependency-tree guard expanded to all four
officer bridge routes and re-asserts the four forbidden
sources. Identity flows only through `_build_officer_actor`
which is the same locked chain β-i defended (Pomerium
principal → officers group → Pomerium Discord snowflake →
real Discord member → `ActorIdentity(user, member_uuid)`).

**Verdict:** Not a shortcut.

## S4 — Transcript Zod schema is a discriminated union over the real Pydantic shape

**Choice:** §5 explicitly types the schema as
`z.ZodDiscriminatedUnion<"type", [...]>` with two member
schemas:

- `applicationTranscriptStateChangeEntrySchema` mirroring
  `ApplicationTranscriptStateChangeEntry`
  (`services/api/app/contracts/applications_transcript.py:16-
  24`): `type: "state_change"`, `occurred_at`, `change_type`,
  `from_state`, `to_state`, `actor_kind`, `actor_id`,
  `aggregate_seq`.
- `applicationTranscriptMessageEntrySchema` mirroring
  `ApplicationTranscriptMessageEntry`
  (`services/api/app/contracts/applications_transcript.py:27-
  34`): `type: "message"`, `occurred_at`, `message_seq`,
  `author_actor_kind`, `author_actor_id`, `visibility`,
  `body_markdown`.

The proposal also calls out that Q3 is locked to the actual
shipped `type` discriminator, explicitly correcting the draft
problem map's `kind` spelling: "Render transcript entries as
the shipped discriminated union, not the draft `kind`
spelling from the problem map" (§2 Q3). The Pydantic union
itself uses `Annotated[..., Field(discriminator="type")]` at
`services/api/app/contracts/applications_transcript.py:37-
40`, so the SPA matches by discriminator rather than guessing.
There is no `z.unknown()`, `z.any()`, or
`z.record(z.unknown())` blob in the typed surface.

**Risk:** a `z.unknown()` blob would defeat type safety for
transcript rendering, force runtime narrowing in the
component, and silently accept entry shapes that do not exist
on the server.

**Mitigation:** real discriminated union, real per-arm
schemas, and Q3 locked to the actual `type` discriminator
including a corrective note about the `kind`/`type` drift.

**Verdict:** Not a shortcut.

## S5 — No "TODO: handle 404" / "we'll add transitions later" in the proposal text

**Choice:** Both 404 paths are concretely mapped:

- Detail GET: §4 names `404 application_not_found` and §7
  asserts "missing id returns `404 application_not_found`."
- Transcript GET: §4 names `404 application_not_found` and
  `403 application_transcript_forbidden`; §7 asserts both.

`raise_known_application_error`
(`services/api/app/api/v1/endpoints/applications/_shared.py
:64-182`) is reused for detail-side error mapping and the
transcript bridge's mapper "preserves direct transcript
endpoint codes" (§4).

Anti-scope (§8) is concrete and ticket-routed, not deferred-
stub language: claim/transition controls go to INIT-133B-iii;
message append goes to INIT-133B-iii; no transcript
filter/pagination/SSE; no actor display-name lookup; no
field-definition renderer. Each item is owned by a named
follow-up, mirroring β-i's S10 pattern. There is no `TODO`,
no "for now", no "we'll add … later", no placeholder stub in
the proposal text.

**Risk:** half-finished error paths or "we'll add transitions
later" stubs would force β-iii to absorb a hidden surface, or
ship an officer-facing 500 instead of a structured 404/403.

**Mitigation:** every error branch (`401`, `403`, `404`,
`422`, Zod parse, network/5xx) is named for both bridge
routes; anti-scope routes deferrals to specific follow-up
tickets; mapper is reused, not duplicated.

**Verdict:** Not a shortcut.

## S6 — Tests exercise real bridge round-trips (not Playwright snapshots only)

**Choice:** §7 splits coverage into three real-round-trip
layers:

- **API bridge tests** in
  `services/api/tests/test_web_officer_applications.py`
  exercise actual FastAPI request/response cycles for both
  new routes: identity failures, `X-Actor-*` ignore,
  contract-shape happy path, authority denied (`403
  authority_decision_denied`), missing id (`404
  application_not_found`), transcript visibility for officer
  with `application.message`, transcript forbidden without
  it, and an expanded dependency-tree guard. Risk
  annotations are named (`detail_actor_binding`,
  `detail_actor_spoofing`, `detail_contract_shape`,
  `officer_transcript_visibility_regression`).
- **Component tests** in
  `services/web/tests/officer-detail.spec.ts` use the same
  Playwright fixture-driven route-mock pattern β-i validated
  (`services/web/tests/officer-queue.spec.ts:44-114`), and —
  critically — assert mocked HTTP round-trips (correct
  endpoint, correct headers, correct response handling), not
  visual snapshots.
- **E2E** in `infra/tests/e2e/tests/19-web-ui.sh` and
  `infra/tests/e2e/lib/playwright/browser-flow.mjs` does a
  real post-claim navigation to `/applications/{id}` and
  asserts detail metadata plus a state-change transcript
  entry for the claim transition — i.e., it round-trips
  through Pomerium → web → bridge → Postgres, not a
  Playwright snapshot.

The β-i shortcut gate already validated this same three-
layer pattern (S6 there); §7 here extends rather than
replaces it.

**Risk:** UI snapshot-only coverage would mask a missing or
mis-wired bridge endpoint, a Zod schema that silently parses
the wrong shape, or an authorization regression.

**Mitigation:** real FastAPI bridge tests, mocked-round-trip
component tests with named risk annotations, and a real
post-claim Postgres-backed e2e leg.

**Verdict:** Not a shortcut.

## S7 — Detail page does NOT add any action UI (read-only contract)

**Choice:** §2 Q7 ("Anti-scope: read-only detail only") and
§8 ("Anti-scope") are explicit and concrete:

- "No claim button" — claim stays on the queue page (β-i).
- "No message composer, no transition controls" — owned by
  INIT-133B-iii.
- "No transcript filter UI" — out of slice.
- "No actor display-name lookup; show actor kind plus
  shortened actor id only" — out of slice.
- "No optimistic-locking mutation path, no live updates, and
  no new identity/authority model" — out of slice.

§7 ("Component tests") includes the structural assertion
"No button/form issues `POST/PUT/PATCH/DELETE` from the
detail route" with risk annotation `group=TG-5;
named_risk=read_only_surface_regression; level=component`,
which is a structural test (it cannot be silently regressed
by a future copy change). §3 ("Modified files") modifies
`ApplicationQueueRoute.tsx` only to add a navigation
affordance to the detail route — claim behavior is "kept …
unchanged."

The bridge mirrors this — both new endpoints are `GET` only,
no `If-Match`, no mutation body (§4 last paragraph).

**Risk:** smuggling a claim button or message composer onto
the detail page would prematurely overlap β-iii's surface,
require optimistic locking on a route that the proposal
deliberately keeps If-Match-free, and force the test plan
into mutation territory before the message append authority
work in β-iii lands.

**Mitigation:** named anti-scope at both the route and
endpoint level, structural component test that asserts no
mutation HTTP verbs are issued, and bridge endpoints declared
as `GET`-only without any `If-Match` plumbing.

**Verdict:** Not a shortcut.

## Verdict reasoning

This proposal inherits β-i's locked identity chain
(`_build_officer_actor`, no `Depends(get_current_actor)`, no
`applicant_receipt`, no `X-Actor-*`) and extends it
mechanically to two new read-only `GET` endpoints, with the
dependency-tree guard expanded to all four officer bridge
routes. The transcript Zod schema is a real discriminated
union over the shipped Pydantic `type` discriminator, with
both arms enumerated to mirror the closed
`ConfigDict(extra="forbid")` contract; the detail Zod schema
enumerates every rendered field of `ApplicationRead`. Error
mapping reuses `raise_known_application_error` and the
existing transcript endpoint's status codes rather than
duplicating them in the bridge. Tests are layered: real
FastAPI bridge round-trips for the two new routes, mocked-
round-trip Playwright assertions for the SPA, and a real
post-claim e2e navigation that asserts both the rendered
metadata and a transcript state-change entry. Anti-scope is
concrete: no claim button, no message composer, no transition
controls, no transcript filter UI, no actor display-name
lookup, no live updates, no `If-Match`, no new identity or
authority model — each deferral routed to a named follow-up
(INIT-133B-iii) rather than left as a TODO.

The single observation is the legacy `.passthrough()` on
`applicationReadSchema` that the proposal does not explicitly
remove; because the server contract is `extra="forbid"` no
extra fields can arrive on the wire, so `.passthrough()` is
dead code rather than a real laxness. Worth tightening during
implementation, but not a behavior-bearing shortcut.

**Verdict: LOW.**

SHORTCUT_DONE: plans/risk/init-133B-ii-shortcut.md
