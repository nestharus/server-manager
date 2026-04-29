# INIT-133B-ii — Audit risk gate

**Verdict:** LOW

Scope under audit: `proposals/14-init-133B-ii-detail-transcript.md` —
two read-only officer bridge endpoints (`GET /officer/applications/{id}`
and `GET /officer/applications/{id}/transcript`), one Pomerium prefix
addition, one Solid detail route, and Zod schema extensions. β-i's
audit invariants (M1 binding, X-Actor lock, applicant_receipt
exclusion, ETag emission scoped to mutations, `raise_known_application_error`
reuse) are preserved.

## A1..A8 — Findings

### A1 — Transcript bridge error mapper not explicitly named
**Concern:** The proposal lists `403 application_transcript_forbidden`
and `404 application_not_found` as the transcript bridge's expected
error codes (proposal §4 line 85, §4 line 92), but does not lock
*which* mapper produces them. The detail bridge is locked to
`raise_known_application_error`, which does NOT handle
`ApplicationMessageAppendForbiddenError`
(`services/api/app/api/v1/endpoints/applications/_shared.py:64-182`).
If the implementer reflexively reuses `raise_known_application_error`
on the transcript path, the message-forbidden error would re-raise
unmapped → 500 instead of 403. The direct transcript endpoint solves
this with a dedicated `_raise_application_transcript_error`
(`services/api/app/api/v1/endpoints/applications/transcript.py:22-36`).
**Evidence:**
- `services/api/app/api/v1/endpoints/applications/_shared.py:64-182`
  (no branch for `ApplicationMessageAppendForbiddenError`).
- `services/api/app/api/v1/endpoints/applications/transcript.py:22-36`
  (correct mapper for transcript, currently `_`-prefixed/private).
- `proposals/14-init-133B-ii-detail-transcript.md:91-92` (loose
  "Its mapper preserves direct transcript endpoint codes" without
  naming the helper).
**Severity:** LOW
**Recommendation:** Implementation should either (a) extract
`_raise_application_transcript_error` from
`endpoints/applications/transcript.py` into a shared helper and
import it from `web.py`, or (b) inline an equivalent isinstance
chain on the bridge handler. Either is fine; the proposal should be
explicit so the mapper does not silently get replaced with
`raise_known_application_error`. Add an API test asserting transcript
GET without `application.message` authority returns 403
`application_transcript_forbidden` (proposal §7 line 178 already
plans this — keep it).

### A2 — Pomerium prefix ordering correctly preserves first-match-wins
**Concern:** The new `prefix: /applications/` route must NOT shadow
`path: /applications/queue` (β-i officer queue, distinct gate) or
the bare `path: /applications` form (public, served by catch-all).
**Evidence:** Proposal locks insertion immediately after
`prefix: /applications/queue/` and before `prefix: /admin`
(`proposals/14-init-133B-ii-detail-transcript.md:77`). Current
queue routes are at
`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:67-78`
and the catch-all at
`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:91-94`.
First-match-wins semantics mean `/applications/queue` resolves to
its dedicated path entry (line 68), `/applications/<uuid>` falls to
the new prefix, and bare `/applications` falls through to the
catch-all because Pomerium prefix matching with a trailing slash
does not match the bare path.
**Severity:** LOW
**Recommendation:** Implement the route exactly at the locked
position. Test plan already covers this in
`infra/tests/test_applicant_discord_pomerium.py` extension (proposal
§3 line 54). Keep that extension and assert ordering: bare
`/applications` → catch-all, `/applications/queue` → queue path,
`/applications/<uuid>` → new prefix.

### A3 — Trailing-slash on `/applications/` becomes auth-gated
**Concern:** Today, `/applications/` (with trailing slash) falls to
the public catch-all alongside the bare `/applications` form. After
this slice, `/applications/` matches `prefix: /applications/` and
becomes auth-gated. A user typing the form URL with a trailing
slash would be redirected to the IDP. This is a behavior change for
a previously-public path.
**Evidence:**
- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:91-94`
  (current public catch-all).
- `proposals/14-init-133B-ii-detail-transcript.md:13` ("keeps bare
  `/applications` public through the catch-all" — bare only,
  trailing-slash variant not addressed).
- `research/22-init-133B-ii-problem-map.md:86-95` (Q1 only locks
  `path:/applications` (bare) public).
**Severity:** LOW
**Recommendation:** Either accept the regression (typing
`/applications/` is unusual; SPA's own routing canonicalizes), or
add an explicit `path: /applications/` entry above the new prefix
that routes to the public catch-all destination. Document the
choice in the route-policy test
(`infra/tests/test_applicant_discord_pomerium.py`). No security
impact; this is UX-only.

### A4 — Detail GET reuses `_build_officer_actor` exactly; no X-Actor or applicant_receipt path
**Concern:** Audit must confirm β-i's M1 binding, X-Actor lock, and
applicant_receipt exclusion are preserved on the new bridge routes.
**Evidence:**
- `services/api/app/api/v1/endpoints/web.py:67-116`
  `_build_officer_actor` constructs `ActorIdentity` purely from
  Pomerium principal + Discord member resolution; no header
  reads beyond Pomerium claims.
- Proposal §4 line 23-25 explicitly reuses `_build_officer_actor`
  "exactly as the bridge identity boundary".
- Proposal §6 line 165 commits to extending the structural guard
  test at `services/api/tests/test_web_officer_applications.py:723-758`
  ("forbidden_callables" + grep on `applicant_receipt`,
  `verify_applicant_receipt`, `CURRENT_ACTOR.get`,
  `get_current_actor`) so the four-route set covers detail and
  transcript.
**Severity:** LOW
**Recommendation:** Confirm during implementation that the dep-tree
guard expected route set on
`services/api/tests/test_web_officer_applications.py:737-740` is
expanded to include `/api/v1/web/officer/applications/{application_id}`
and `/api/v1/web/officer/applications/{application_id}/transcript`.
This is the structural enforcement that prevents future regressions.

### A5 — Read-only flow: no `parse_if_match_strong`, no `set_etag`
**Concern:** The audit must verify the proposal does not leak
If-Match semantics or ETag emission into a read endpoint.
**Evidence:** Proposal §4 line 94 ("No `If-Match` parsing, no
mutation body, and no ETag requirement are introduced in this
read-only slice"). The direct lifecycle GET at
`services/api/app/api/v1/endpoints/applications/lifecycle.py:109-122`
does call `set_etag`; the bridge intentionally diverges. The
transcript direct endpoint at
`services/api/app/api/v1/endpoints/applications/transcript.py:39-56`
also does not set ETag — bridge mirrors that behavior.
**Severity:** LOW
**Recommendation:** Implementation should confirm neither bridge
handler imports `parse_if_match_strong` or `set_etag`. The β-iii
slice (transitions on detail) will reintroduce ETag emission when
mutation surfaces are added; deferring it here is correct. No test
needed — absence of these helpers is verifiable in code review.

### A6 — Authorization delegation paths correct, no bypass
**Concern:** Detail GET delegates to `read_application` →
`require_application_read_authority`; transcript GET delegates to
`read_application_transcript` → `read_application_messages`. Audit
must confirm officer-group membership alone is insufficient and
authority gates fire.
**Evidence:**
- `services/api/app/services/applications.py:365-390`
  `require_application_read_authority` raises `PermissionError`
  unless actor is the applicant or has any of
  `APPLICATION_READ_PERMISSIONS` on `form_snapshot.target_scope`.
- `services/api/app/services/application_messages.py:160-202`
  `read_application_messages` raises
  `ApplicationMessageAppendForbiddenError` unless actor is the
  applicant or has `application.message` authority on the
  application's scope.
- `services/api/app/services/application_transcript.py:49-73`
  delegates message-visibility gate to `read_application_messages`
  before merging state changes.
- The `_build_officer_actor` resolution returns
  `ActorIdentity(actor_kind="user", actor_id=str(member.id))` —
  the same identity shape `require_application_read_authority`
  expects. No officer-group fallthrough.
**Severity:** LOW
**Recommendation:** Add API tests for both authorization shapes:
detail GET with officer-group-only (no application authority) → 403
`authority_decision_denied`; transcript GET with `application.review`
authority but no `application.message` authority → 403
`application_transcript_forbidden`. Proposal §7 lines 176-178
already plans these. Note: a state where detail succeeds but
transcript fails is correct (and matches direct endpoint
semantics).

### A7 — Frontend bootstrap reuses `onMount` pattern; no `createEffect` second-arg pitfalls
**Concern:** Audit asks whether the detail route avoids the broken
`createEffect` second-arg pattern that has previously caused issues
in the SPA.
**Evidence:** β-i's `ApplicationQueueRoute`
(`services/web/src/features/officer/ApplicationQueueRoute.tsx:112-114`)
uses `onMount(() => { void bootstrap(); })` exclusively — no
`createEffect`. The proposal §5 line 28-29 commits to "the same
route-local signal pattern as `ApplicationQueueRoute`, which
already bootstraps principal state and data in `onMount`". The
optional mention of TanStack Query (proposal §5 line 153) is
hedged on "stays route-local"; if used, it does not require
`createEffect`.
**Severity:** LOW
**Recommendation:** Implementation must keep `onMount` as the
bootstrap entry. If TanStack Query is introduced, it must be
configured route-locally and not as a global QueryClient that would
leak across routes. Component test
`services/web/tests/officer-detail.spec.ts` (proposal §3 line 44)
covers the auth-gate-before-fetch invariant — keep it.

### A8 — Test-plan coverage for failure modes is comprehensive
**Concern:** Audit asks whether failure modes (404, 403, 401), Zod
parse failure, network/5xx, and component-level auth states are
exercised.
**Evidence:** Proposal §7 lines 173-198:
- API: identity 401 missing, identity 401 invalid, officer-group
  403, member-resolution 422, authority 403, not-found 404 — all
  enumerated for both detail and transcript.
- Component: anonymous, non-officer, missing-Discord-claim,
  happy-path render, 403/404/422/Zod-parse/network/5xx panels,
  read-only surface (no mutation buttons).
- E2E: extends `19-web-ui.sh` after the existing claim leg with a
  navigation to `/applications/{claimed_application_id}` and
  asserts (1) detail metadata reflects the claimed state and (2)
  transcript includes a state-change entry for the claim.
**Severity:** LOW
**Recommendation:** During implementation, ensure the e2e Postgres
assertion remains read-only — the new leg should only assert that
reads render, not that any new state was created. Proposal §7 line
198-199 says "Write the detail assertion result into the existing
session artifact or a sibling `web-ui-detail.json`"; verify this
sibling artifact is documented in the test fixture surface so the
validator does not flag it as unexpected.

## Verdict reasoning

The proposal is a faithful read-only extension of β-i. It reuses
the locked actor-construction helper, delegates authorization to
existing service-layer gates (`require_application_read_authority`
and `read_application_messages`'s visibility gate), keeps the SPA
on the validated `onMount` bootstrap pattern, extends the
structural dep-tree guard to four routes, and correctly orders the
new Pomerium prefix between the queue routes and the public
catch-all. The only material implementation-guidance gap is A1
(which mapper handles `ApplicationMessageAppendForbiddenError` on
the transcript bridge) — a code-review concern, not a security or
architectural blocker. Findings A2-A8 confirm β-i invariants are
preserved. A3 is a minor UX behavior change (`/applications/` with
trailing slash becomes auth-gated) with no security impact. No
HIGH or MEDIUM regression risk found.

AUDIT_DONE: plans/risk/init-133B-ii-audit.md
