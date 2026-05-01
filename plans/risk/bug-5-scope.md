# BUG-5 — Scope risk gate

**Verdict:** LOW

BUG-5 adds a single new e2e-only fixture helper
(`infra/tests/e2e/lib/seed-chapter-fixture.mjs`) and a small extension to
`infra/tests/e2e/tests/19-web-ui.sh` so the public chapter dropdown has
the `chapter-alpha` / `Alpha Chapter` option Playwright is already
waiting on. The RCA (`research/34-bug-5-chapter-fixture-rca.md`
§"Why no chapter exists on humility-local") establishes that this is a
missing runtime fixture path — INIT-135 changed the local form seed and
the e2e/browser contract to require an active chapter, but no matching
local-cluster chapter/template seed was added — not a defect in the
chapter API, the public chapter endpoint, or the admin flow. The
proposal locks "Option c, a new e2e helper script invoked from
`19-web-ui.sh`" (§2 Q1) and rejects both extending
`seed-authority-grants.mjs` (Option a — would conflate authority and
chapter-lifecycle data) and a GitOps Job (Option b — out of scope for an
e2e-only fixture). Diff budget is under 220 lines across two files
(§6).

## Gate checks

### 1. Only adds `infra/tests/e2e/lib/seed-chapter-fixture.mjs` + extends `19-web-ui.sh`

**PASS.** §3 "Substrate" enumerates exactly two touched paths:

- New file `infra/tests/e2e/lib/seed-chapter-fixture.mjs` (≈120-180
  lines per §6), modeled on the execution pattern of the existing
  `seed-authority-grants.mjs` (require `KUBECONFIG`, locate the CNPG
  primary, read `server-manager-postgres-url`, run a single
  `psql -v ON_ERROR_STOP=1` through `kubectl exec`, print a JSON
  summary).
- `infra/tests/e2e/tests/19-web-ui.sh` (under 15 net lines per §6) for
  invoking the new seed before Playwright and a second invocation of
  the *already-existing* `seed-authority-grants.mjs` with
  `E2E_APPLICATION_SCOPE_KIND=chapter` /
  `E2E_APPLICATION_SCOPE_ID=chapter-alpha` so the chapter-scoped
  application target keeps officer queue/claim/detail/messages working.
  §3 is explicit that this "does not extend the authority helper; it
  uses the scope parameters it already provides."

§6 closes with: "Total budget: under 220 net lines, two files. No
service, repository, migration, contract, or unit-test fixture edits."
The repeated invocation of `seed-authority-grants.mjs` is a call-site
change inside `19-web-ui.sh`, not a modification of the helper, and is
covered by the "extends `19-web-ui.sh`" clause of this gate. ✅

### 2. No app/source code changes

**PASS.** §5 anti-scope and §6 diff budget jointly rule out every
runtime/source surface:

- "Do not modify `services/api/tests/chapter_selector_fixtures.py`."
- "Do not change `/api/public/chapters` behavior or ordering."
- "Do not add an Alembic migration."
- §6: "No service, repository, migration, contract, or unit-test
  fixture edits."

The helper writes the minimum chapter projection (`chapter_templates`
+ `chapters` + `aggregate_heads`) directly through `psql`, mirroring
the unit-test minimum-row shape established in
`services/api/tests/chapter_selector_fixtures.py:33-80` (per RCA
§"Foreign key / template dependency") rather than calling production
endpoints. Nothing under `services/**`, `migrations/**`, or
`infra/tests/fixtures/web-ui/contract.json` is mutated. The helper
*reads* `contract.json` only to assert the expected fixture identity
("must … assert they are exactly `chapter-alpha` and `Alpha Chapter`.
If the contract changes, this seed should fail"), which is a fail-loud
guard, not a write. ✅

### 3. No GitOps changes (e2e fixture, not local bootstrap)

**PASS.** §2 Q1 explicitly rejects Option b:

> Option b, a new GitOps Job: this fixture is tied to the e2e web
> contract (`chapter-alpha` / `Alpha Chapter`), not general local
> bootstrap data. A Job would also require kustomization wiring and
> cluster apply/reconcile behavior for a single Playwright fixture
> that can be seeded immediately in test setup.

§5 anti-scope reinforces: "Do not add a GitOps Job or kustomization
resource for this e2e-only fixture." The proposal does not touch
`gitops/channels/local/applications/server-manager/kustomization.yaml`
or any sibling manifest. The chapter-fixture data lives in the e2e
test setup, not in cluster GitOps state — consistent with the RCA
§"INIT-135 spec intent" which already classified this as an e2e
contract dependency rather than a local-cluster bootstrap dependency.
The fixture is reset/created per-e2e-run, not reconciled into the
desired-state tree. ✅

### 4. No new dependencies

**PASS.** §3 prescribes the helper's execution shape as a direct copy
of `seed-authority-grants.mjs`'s mechanism: `kubectl exec` into the
CNPG primary pod and run `psql -v ON_ERROR_STOP=1`. The required
toolchain (`kubectl`, the in-cluster `psql`, Node for the `.mjs`
runner, the existing `KUBECONFIG_PATH`/`KUBECONFIG` env contract) is
already present anywhere `seed-authority-grants.mjs` runs today —
which is the same `19-web-ui.sh` test 19 environment that will host
the new helper. No npm package, no new CLI binary, no new container
image, no new secret. The "local SQL literal helper for any string
inserted into SQL" mentioned in §3 is an inline utility, not an
imported library. ✅

### 5. No Discord roles/channels created for the fixture

**PASS.** §5 anti-scope: "Do not add Discord roles or channels for the
seeded chapter." §2 Q4 ("Template dependency") locks the template's
`channel_structure`, `role_structure`, and `default_permission_intents`
to *empty JSON arrays*, "matching the unit-test minimum-row fixture."
That guarantees the fixture cannot fan out into Discord side effects
even by template-driven provisioning.

The RCA §"Roster / authority side effects" independently confirms this
is safe: `services/api/app/services/chapters.py:180-229` "creates only
a proposed chapter projection plus the mutation/audit state change. It
does not seed roster rows, chapter officer grants, or chapter roles."
Because the helper bypasses the API entirely and writes the minimum
projection rows via SQL, there is no code path through which Discord
provisioning could fire. ✅

### 6. No changes to chapter creation API or admin flows

**PASS.** §5 anti-scope: "Do not add an admin chapter creation flow"
and "Do not change `/api/public/chapters` behavior or ordering." The
helper does not call
`services/api/app/api/v1/endpoints/chapter_templates.py:57-74`,
`services/api/app/api/v1/endpoints/chapters/base.py:119-136`,
`services/api/app/services/chapters.py`, or
`services/api/app/api/v1/endpoints/web.py:64-69`. The RCA §"Chapter
creation API" already established why an API-driven seed is infeasible
under the current authority model anyway: "The seeded officer from
`seed-authority-grants.mjs` has application permissions only. That
seed does not grant `chapter_template.write` or `chapter.write`, so
the seeded officer identity cannot create the missing template/chapter
through the chapter management API as currently bootstrapped."

The proposal sidesteps this entirely by writing directly to
`chapter_templates`, `chapters`, and `aggregate_heads` through the
existing CNPG primary `kubectl exec` pattern — the same pattern used
by `seed-authority-grants.mjs` for `authority_grants` and by
`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`
for `form_definitions` (per RCA §"What seeds chapters today").
Production read paths (the public chapter list at
`services/api/app/repositories/public_chapters.py:12-24`, the admin
read at `services/api/app/repositories/web.py:8-22`) are unchanged;
the fixture just supplies rows for them to read. ✅

## Findings

- **Idempotency posture is fail-closed.** §2 Q2 makes the helper
  fail-closed under partial drift: it must abort if `chapter-alpha`
  exists "with a different name, state, or template association," if
  the fixture template identity exists "with a different schema,
  version, or non-empty structures," or if the aggregate head exists
  "with a non-fixture sequence/change shape." That mirrors the
  fail-closed posture of `seed-public-intake-form.yaml` and prevents
  the helper from silently rewriting hand-curated chapter rows in a
  long-lived dev cluster — keeping it safe for the per-test cluster
  bring-up that test 19 actually runs.
- **Hardcoded fixture id is contract-driven.** §2 Q3 keeps
  `chapter-alpha` as the literal `chapters.id` because
  `infra/tests/fixtures/web-ui/contract.json:102-121` already
  hardcodes `chapter-alpha` as the SPA option value and submit target.
  The helper's "assert the contract still says
  `chapter-alpha`/`Alpha Chapter`, otherwise fail" guard turns this
  into a load-bearing tripwire if INIT-135's contract is later
  edited — exactly the kind of cross-coupling the gate wants visible.
- **Authority helper reused, not extended.** §3 Substrate calls the
  second `seed-authority-grants.mjs` invocation out explicitly: "This
  does not extend the authority helper; it uses the scope parameters
  it already provides." The chapter-scoped officer authority grant is
  achieved by parameterizing the existing tool, not by editing it,
  which preserves gate criterion 1's "two files" envelope.
- **Diff budget headroom.** §6 caps the implementation at ~220 lines
  across two files. The helper is structured around CTEs
  (`seed`, `fail_closed_guard`, `inserted_template`, `inserted_chapter`,
  `inserted_head`, final `SELECT` of one of three outcome strings) and
  reuses the `seed-public-intake-form.yaml` SQL shape rather than
  inventing a new bootstrap pattern, which keeps this on the small
  end of the budget.
- **Fix is at the correct ownership boundary.** RCA §"Candidate
  intervention points, not fixes" enumerated five candidate locations;
  §2 Q1 picks "a dedicated e2e DB fixture helper adjacent to
  `infra/tests/e2e/lib/seed-authority-grants.mjs`" — the only one that
  matches the fixture's actual lifetime (per-e2e-run) and ownership
  (the e2e contract). GitOps would be a permanent local-cluster row;
  contract-fixture identity-derivation would change INIT-135's
  contract; an API-level seed would require new authority grants.
  None of those are required to make test 19 pass.

## Verdict

**LOW.** All six gate checks pass. The proposal is a narrow,
e2e-only fixture delta — one new helper plus one extended test
runner — that reuses the existing `kubectl exec`/`psql` substrate
from `seed-authority-grants.mjs` and the minimum-row template/chapter/
aggregate shape from `services/api/tests/chapter_selector_fixtures.py`.
Anti-scope clauses pin out the four design-change escape hatches
(admin chapter UI, GitOps Job, Alembic seed migration, public chapter
endpoint behavior change) that the RCA's candidate-intervention list
would otherwise have invited. Cleared for shortcut gate.

SCOPE_DONE: plans/risk/bug-5-scope.md
