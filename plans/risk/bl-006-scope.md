# BL-006 Scope risk gate

Verdict: **PASS**

Reviewed:

- `proposals/31-bl-006-envelope-receipt-display.md`
- `research/46-bl-006-envelope-problem-map.md`
- `services/web/src/features/public/ApplicationFormRoute.tsx`
- `services/web/tests/ApplicationFormRoute.spec.tsx`
- `services/api/tests/test_public_application_contracts.py`
- `services/api/tests/test_public_application_route.py`
- `services/api/app/contracts/applications.py`

## Findings

### 1. SPA-only change + 1 contract test — PASS

Proposal §3 "Modified files" declares exactly one production-code surface
and one new test surface, both inside the SPA workspace
`services/web/`:

- `services/web/src/features/public/ApplicationFormRoute.tsx` — extend
  the success/status update after `submitPublicApplication(payload)` so
  the rendered success view includes `Reference: <application_id>` when
  the body includes `application_id`. The proposal explicitly preserves
  "the submit payload, auth redirect behavior, draft preservation,
  upload checks, and API endpoint unchanged."
- `services/web/tests/ApplicationFormRoute.spec.tsx` — extend the
  existing submit-success path or add a focused success test asserting
  that the success/status view renders the application id string,
  preferably as visible text such as
  `Reference: 11111111-1111-4111-8111-111111111111`.

The "contract test" in the gate maps to TG-2's static API contract
guard. §3 "Contract guard" explicitly relies on the **existing**
coverage in `services/api/tests/test_public_application_contracts.py`
and `services/api/tests/test_public_application_route.py`, which already
assert the minimal `{message, application_id}` receipt dump and the
exact public route response keys. New work is bounded: "If those tests
are not exact enough at implementation time, tighten them rather than
changing production API or contract code." That is at most a tightening
of the one already-present contract guard, with zero new contract test
files. §6 diff budget repeats the bound: "API static contract guard:
zero production diff; tighten existing API tests only if the current
exact-envelope assertions are insufficient."

The change surface is therefore one SPA production file, one SPA spec
file, and (at most) tightened assertions in the pre-existing static API
contract guard — within the "SPA-only change + 1 contract test"
envelope.

### 2. No API body changes — PASS

§2 Q1 "Public submit response contract" locks Option A: the public
submit response body remains exactly:

```json
{
  "message": "Application received",
  "application_id": "<uuid>"
}
```

Q1 is explicit that "this is a contract decision for future slices. The
public submit response is a create acknowledgment, not a public
application read surface. Future BL slices must respect that boundary."

§2 Q3 "Anti-scope" forbids the alternatives: "No API body changes. Do
not add Option B fields such as `submitted_at` in this slice. Do not
return mutable lifecycle state. Do not return target scope, form
definition/version, correlation id, applicant id, responses, form
snapshots, owner/reviewer data, decision data, timestamps, version,
ETag, or any `ApplicationRead`-style field. Do not implement Option C.
The public submit response must not become `ApplicationRead`."

§3 "Unmodified substrate" enumerates the locked surfaces: "No API
endpoint changes. No Pydantic contract changes. No OpenAPI/client
contract widening. No service, repository, migration, Discord daemon,
officer queue, or e2e DB verification changes." §5 anti-scope and §6
diff budget repeat the API lock: "No migrations, no API contracts, no
generated clients, no Discord daemon, no officer UI, no infrastructure,
and no policy changes are budgeted."

The current receipt at
`services/api/app/contracts/applications.py:419` is
`PublicApplicationSubmissionReceipt(message: str, application_id: UUID)`
under `_ApplicationModel`'s `extra="forbid"`; per Q1 and Q3 the slice
leaves that exact shape untouched. The TG-2 contract guard exists
specifically to fail if anyone widens it.

### 3. No Discord/officer integration — PASS

§3 "Unmodified substrate" forbids both surfaces directly: "No service,
repository, migration, **Discord daemon, officer queue**, or e2e DB
verification changes."

§5 "Anti-scope" reinforces the rule for both downstream consumers and
adjacent applicant flows: "Do not integrate the receipt with Discord,
officer queues, support console lookups, applicant status checking,
notifications, or transcript/detail views. Those consumers need
purpose-built authenticated or internal read surfaces when commissioned."

§5 also bars adjacent UI plumbing that would touch officer/support
surfaces: "Do not use this slice to introduce copy-to-clipboard
controls, routing by application id, local persistence of the receipt,
or mobile/third-party client contracts. The only user-facing hardening
is displaying the already-returned id as a support reference after
successful submit."

The problem map at `research/46-bl-006-envelope-problem-map.md`
"Current consumers" already records that the officer queue does not
consume the public submit response (it uses `/web/officer/applications`)
and the Discord daemon does not consume it either. The proposed change
is confined to the applicant success view and does not introduce a
producer or consumer relationship to either surface.

### 4. No new dependencies — PASS

§3 "Modified files" names only an existing TSX route component and an
existing spec file under `services/web/`. No `package.json`, no
`pnpm-lock.yaml`, no Python `pyproject.toml`/`requirements.txt`, no
Helm/kustomize manifest, no CI workflow, and no runner script appears in
the modified-files list.

§3 "Unmodified substrate" excludes every common dependency surface: API
endpoints, Pydantic contracts, OpenAPI/client contract, services,
repositories, migrations, Discord daemon, officer queue, e2e DB
verification. §6 diff budget repeats: "No migrations, no API contracts,
no generated clients, no Discord daemon, no officer UI, no
infrastructure, and no policy changes are budgeted."

The work is a small string-formatting change in
`ApplicationFormRoute.tsx` plus a render assertion in the existing
Vitest/Testing-Library spec; both already have everything they need from
the SPA's existing toolchain. No new npm package, Python package, Go
module, or system binary is named anywhere in the proposal or research.
The optional tightening of `services/api/tests/test_public_application_contracts.py`
and `services/api/tests/test_public_application_route.py` likewise stays
within the existing pytest stack.

## Conclusion

The slice is SPA-bounded for production code (one TSX file) plus one
SPA spec, with the existing API contract guard preserved (tightened only
if necessary) — within the "SPA-only change + 1 contract test"
envelope. The public submit response body is locked verbatim by Q1/Q3
and the anti-scope, with no API/Pydantic/OpenAPI changes budgeted. No
Discord daemon, officer queue, support console, or applicant
status-check integration is introduced; in fact each is named in the
anti-scope. No new package, runner, or toolchain dependency is added on
either side of the workspace. Each gate check passes against an
explicit proposal section. Scope risk is acceptable.

SCOPE_DONE: plans/risk/bl-006-scope.md
