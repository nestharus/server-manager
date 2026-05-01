# BL-006 — Supported-surface risk gate

**Verdict:** LOW

BL-006 (proposals/31-bl-006-envelope-receipt-display.md, locked Option A
per research/46-bl-006-envelope-problem-map.md) is a SPA-only display
hardening slice. It changes one line of rendered copy in the public
application success view so that the already-returned `application_id`
appears as a support reference, and updates one web spec to assert the
reference is visible. Proposal §3 ("Unmodified substrate"), §5
("Anti-scope"), and §6 ("Diff budget") explicitly forbid any change to
the public submit response model, route, OpenAPI/client contract,
service, repository, migration, Discord daemon, officer queue, or e2e
DB-verification path. The slice never crosses the
`PublicApplicationSubmissionReceipt = {message, application_id}`
boundary that B1 / problem map §"What the proposal must lock" require
the create receipt to keep.

## Check results

### 1. No public API change — ✓ PASS

No changes to:

- `services/api/app/api/v1/endpoints/applications/public.py` (the
  public submit route at `:25` still returns
  `PublicApplicationSubmissionReceipt(message="Application received",
  application_id=…)` with status 201);
- `PublicApplicationSubmission` /
  `PublicApplicationSubmissionReceipt` contracts in
  `services/api/app/contracts/applications.py` — proposal §3
  ("Unmodified substrate") and §5 explicitly forbid widening the
  receipt model; `_ApplicationModel`'s `extra="forbid"` posture
  remains the public guarantee;
- `submit_public_application_with_receipt` service or any repository
  layer (proposal §3 "No service, repository, … changes");
- public chapters endpoint or any other public route;
- generated clients / OpenAPI schema (no contract diff to propagate);
- public-intake auth chain (`verify_applicant_receipt` +
  `authorize_public_intake`) — out of scope per proposal §3.

The existing exact-envelope guards already enforce the contract:
`services/api/tests/test_public_application_contracts.py:75-109` round-
trips `{message, application_id}` and rejects extras;
`services/api/tests/test_public_application_route.py:211-213` asserts
`set(body) == {"message", "application_id"}`. Proposal §3 ("Contract
guard") permits *tightening* these assertions if implementation finds
them not exact enough, but explicitly forbids any production-side
contract change. The TG-2 acceptance criteria require the existing
exact-envelope assertion to hold post-slice, so a future BL widener
that tries to ride this slice would still trip the guard.

### 2. No env vars / migrations / GitOps / Pomerium / Authentik changes — ✓ PASS

| Surface | Pre | Post | Status |
|---|---|---|---|
| Process / Settings env vars (API + web build env) | unchanged | unchanged — proposal §3 forbids any non-SPA / non-spec change | ✓ |
| Alembic / DB migrations | β-3 head | unchanged — proposal §3 "No … migration … changes" | ✓ |
| GitOps manifests (`gitops/channels/local/**`) | post-INIT-137 set | unchanged — proposal §6 "no infrastructure" | ✓ |
| Pomerium routes / auth blueprint | post-INIT-137 set | unchanged — not touched | ✓ |
| Authentik blueprint | post-INIT-134 set | unchanged — not touched | ✓ |
| Kong ingress / rate-limit plugins | post-INIT-135 / -137 set | unchanged — not touched | ✓ |
| OPAL Helm values / Cedar policy bundle | INIT-115 set | unchanged — no policy or AuthZ behavior touched | ✓ |
| Discord daemon | unchanged | unchanged — proposal §3 + §5 forbid Discord follow-up integration | ✓ |
| Officer queue (`/web/officer/applications`) | unchanged | unchanged — proposal §5 forbids officer integration | ✓ |
| e2e DB / notification verification (`infra/tests/e2e/lib/playwright/browser-flow.mjs:131`) | reads `application_id` from receipt | unchanged — receipt body keys are byte-identical, so the verification path keeps working | ✓ |
| Web client parser (`services/web/src/api/client.ts:121`) | already parses optional `application_id` | unchanged — the field has been on the wire since the receipt was minted; only the SPA's display of it changes | ✓ |

The slice introduces zero new env vars (none in API, none in web build,
none in GitOps), zero ConfigMap / Secret / InfisicalSecret edits, zero
migrations, and zero policy/AuthN/AuthZ/ingress edits.

### 3. SPA bundle hash-bump is visible / operator-aware — ✓ PASS

The web build pipeline hashes asset filenames
(`services/web/dist/assets/index-C_kfvkHd.js`,
`services/web/dist/assets/index-Q4fzm_aT.css`, etc.). Editing
`services/web/src/features/public/ApplicationFormRoute.tsx:671` to
include `Reference: <application_id>` in the success status string
will change the entry-bundle hash on the next build, which is the
intended, expected, and operator-visible signal that the SPA changed:

- the hashed filename in `services/web/dist/index.html` flips, so
  GitOps diffs / image digests / CDN cache-bust signals all reflect a
  real SPA change rather than a silent in-place mutation;
- the hash-bump is the *only* user-visible deployment signal; there is
  no parallel API hash or env signal because the API contract is
  unchanged;
- this matches the supported-surface posture ("operator-aware"): an
  operator inspecting the next deploy will see exactly one moving
  part — the SPA bundle — and can map it back to the BL-006 commit
  via the standard image-tag / GitOps trail.

The hash-bump does not affect:

- the public submit URL, method, payload shape, response status, or
  response body keys;
- service-worker caching behavior (none in scope);
- backwards compatibility for any client that ignores `application_id`
  (the field is already on the wire).

### 4. Supported test/spec surfaces remain operator-runnable — ✓ PASS

Proposal §4 names exactly two acceptance gates and both run inside
already-collected lanes:

- TG-1: `pnpm --filter @humility/web test -- ApplicationFormRoute.spec.tsx`
  — extends `services/web/tests/ApplicationFormRoute.spec.tsx`, which
  already exists, already mocks the receipt body
  (`{"message": "Application received", "application_id":
  "11111111-1111-4111-8111-111111111111"}` per problem map §"Current
  consumers"), and already runs in the web vitest lane.
- TG-2: `pytest services/api/tests/test_public_application_contracts.py
  services/api/tests/test_public_application_route.py` — both files
  already exist, already enforce the exact-envelope contract, and are
  already collected by the API pytest lane.

No new test directory, no new conftest, no new pytest marker, no new
vitest project, no new CI lane. Operator invocation for both gates is
byte-identical to today.

## Findings

None blocking. Three observations worth surfacing for implementation:

- **Web client parser already tolerates `application_id`.** The
  problem map confirms `services/web/src/api/client.ts:121` already
  parses `application_id` as optional; the field has been on the wire
  since the receipt was minted. The slice only needs to consume that
  parsed value in the success view, not extend the parser. Avoid
  re-typing the parser — it is out of supported-surface scope.
- **The compat fixture and contract fixture already mirror the
  receipt shape.** `services/web/tests/compat.spec.ts:134` and
  `infra/tests/fixtures/web-ui/contract.json:140` mock the same
  `{message, application_id}` body. Proposal §3 does not require
  touching them; the slice should not add a third mock copy. If the
  vitest spec needs the literal id, reuse the existing fixture id
  (`11111111-1111-4111-8111-111111111111`).
- **Tightening the API exact-envelope assertion is allowed, widening
  is not.** Proposal §3 ("Contract guard") permits making the existing
  guards stricter if a future BL would otherwise sneak a field
  through. Implementation should *not* loosen any current assertion,
  add `application_id`-shaped response keys, or relax the
  `extra="forbid"` posture on `PublicApplicationSubmissionReceipt`.

## Verdict reasoning

LOW.

1. **Public API surface (gate 1)**: zero touches. The public submit
   route, response status, response body keys (`{"message",
   "application_id"}`), error shape, auth chain, and Cedar request
   shape are byte-identical. The receipt body is already what the
   slice reads; the slice only renders an existing field.
2. **Cross-cutting infra surfaces (gate 2)**: zero env / migration /
   GitOps / Pomerium / Authentik / OPAL / Cedar / Kong /
   InfisicalSecret edits. Anti-scope is unusually explicit (proposal
   §3 + §5 + §6). Discord daemon, officer queue, support console,
   and applicant status flow are explicitly excluded so the slice
   does not accidentally turn the create receipt into a read surface.
3. **SPA bundle visibility (gate 3)**: the only moving part is the
   web entry-bundle hash, which is the standard operator-visible
   signal that the SPA changed. It maps 1:1 to the
   `ApplicationFormRoute.tsx` edit and is exactly the "small
   hash-bump (visible)" posture the gate requires. No service worker
   or cache-invariant assumption is broken.
4. **Test/spec collection surface (gate 4)**: both TG-1 and TG-2 run
   in lanes that already exist and already exercise the same files
   the slice touches. No new collection lane, no new fixture
   directory, no new operator command.

The slice has zero blocking findings against the supported-surface
gate. Implementation can proceed without a supported-surface re-gate,
provided the implementer:

- keeps `PublicApplicationSubmissionReceipt` exactly `{message,
  application_id}` and preserves `_ApplicationModel`'s
  `extra="forbid"`;
- keeps the public submit route handler, status code, and response
  body keys byte-identical;
- keeps the change inside
  `services/web/src/features/public/ApplicationFormRoute.tsx` and
  `services/web/tests/ApplicationFormRoute.spec.tsx` (plus optional
  tightening of the existing API contract guards);
- keeps Discord daemon, officer queue, e2e DB-verification flow,
  GitOps manifests, Pomerium / Authentik / Kong / OPAL /
  InfisicalSecret surfaces untouched;
- accepts the SPA entry-bundle hash-bump as the sole operator-
  visible deployment signal.

Verdict: **LOW**.

SUPPORTED_SURFACE_DONE: plans/risk/bl-006-supported-surface.md
