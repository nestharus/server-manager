# BUG-5 — Shortcut risk gate (local e2e chapter fixture)

**Verdict:** LOW

Source: `proposals/21-bug-5-chapter-fixture.md`,
`research/34-bug-5-chapter-fixture-rca.md`,
`infra/tests/e2e/lib/seed-authority-grants.mjs`,
`services/api/tests/chapter_selector_fixtures.py`.

## C1 — Real direct-SQL fixture (not "seed via API by impersonating an admin")

**Pass.**

The proposal forecloses the API-impersonation path explicitly and picks a
direct-SQL helper that mirrors the existing e2e DB-fixture pattern.

Q1 (proposal lines 56-72) names the three candidate ownership boundaries
(extend `seed-authority-grants.mjs` / new GitOps Job / new e2e helper script)
and picks Option c — a new e2e helper invoked from `19-web-ui.sh`. Options a
and b are rejected on ownership/wiring grounds, not on "API would be easier."

The RCA closes the API door from the other side
(`research/34-bug-5-chapter-fixture-rca.md:104-114`):

> The seeded officer from `seed-authority-grants.mjs` has application
> permissions only. That seed does not grant `chapter_template.write` or
> `chapter.write`, so the seeded officer identity cannot create the missing
> template/chapter through the chapter management API as currently
> bootstrapped.

The Substrate (proposal lines 152-172) names the actual write surface — direct
psql against the CNPG primary, not an HTTP path:

> follow the execution pattern already used by `seed-authority-grants.mjs`:
> require `KUBECONFIG_PATH` or `KUBECONFIG`; locate the CNPG primary pod in
> namespace `server-manager`; read the `server-manager-postgres-url` secret;
> execute one `psql -v ON_ERROR_STOP=1` SQL statement through `kubectl exec`.

Anti-scope (proposal lines 263-273) reinforces:

> Do not add an admin chapter creation flow.
> Do not touch chapter authority/grants beyond what the existing
> `seed-authority-grants.mjs` provides.

That rules out the "give the e2e officer `chapter_template.write` so we can
POST our way to a chapter" shortcut — the very escape hatch the RCA
identified.

## C2 — Foreign key dependencies handled in correct order (template → chapter → head)

**Pass.**

The RCA enumerates the FK chain explicitly
(`research/34-bug-5-chapter-fixture-rca.md:204-216`):

> A chapter fixture cannot be a single `chapters` row. The schema requires:
> - a `chapter_templates` row first (`wu-007a`, later made versioned by
>   `wu-018`);
> - a `chapters.template_id` value referencing that template;
> - a chapter aggregate head if the row is expected to appear in admin
>   chapter listings.

The proposal mirrors that chain in the SQL shape (lines 174-186), with CTEs
in dependency order:

> - `seed`: constants for `chapter-alpha`, `Alpha Chapter`, `e2e-template`,
>   the deterministic template UUID, empty JSON structures, and `active`.
> - `fail_closed_guard`: drift checks for incompatible existing template,
>   chapter, or head rows.
> - `inserted_template`: insert the minimal template if absent.
> - `inserted_chapter`: insert the active chapter if absent.
> - `inserted_head`: insert the aggregate head if absent.

Q4 (lines 106-122) pins the template identity (logical key `e2e-template`,
deterministic UUID derived from the seed key, `version=1`,
`schema_version=1`, empty JSON arrays for `channel_structure`,
`role_structure`, `default_permission_intents`) and explicitly forbids the
"reuse a default template" shortcut:

> The implementation must not look up or create a shared "default" template.

That matters — `services/api/tests/chapter_selector_fixtures.py:23-82`
already hand-rolls the same three rows in dependency order, and Q4 is
choosing the same self-contained shape rather than a hidden lookup that
could fail silently in a freshly migrated cluster.

Q5 (lines 126-141) is the only point that actually writes literal SQL into
the proposal:

```sql
INSERT INTO aggregate_heads (
  aggregate_type,
  aggregate_id,
  current_seq,
  latest_change_id
)
VALUES ('chapter', 'chapter-alpha', 1, NULL)
```

The chapter row's `template_snapshot` JSON (lines 188-201) carries the
template UUID, family id, version, schema version, and the same empty
structures — the snapshot is consistent with `services/api/app/services/
chapters.py`, so the inserted chapter will not diverge from what the service
layer would have produced if it had been creating the chapter itself.

The single-transaction wrap (line 175: "Use a single transaction with CTEs")
also rules out the partial-failure shortcut where, e.g., the template lands
but the head doesn't.

## C3 — No "TODO: add roster later" stubs

**Pass.**

Roster is addressed head-on in the RCA, not deferred.
`research/34-bug-5-chapter-fixture-rca.md:218-227`:

> No evidence shows that the e2e chapter fixture needs roster side effects.
>
> `services/api/app/services/chapters.py:180-229` creates only a proposed
> chapter projection plus the mutation/audit state change. It does not seed
> roster rows, chapter officer grants, or chapter roles.

The chapter-scoped authority concern the RCA flags as adjacent
(`research/34-bug-5-chapter-fixture-rca.md:229-235`) — application
read/message/transition checks evaluate against the submitted application's
target scope — is handled in Substrate step 4 (proposal lines 213-218):

> Reuse `seed-authority-grants.mjs` once more with
> `E2E_APPLICATION_SCOPE_KIND=chapter` and
> `E2E_APPLICATION_SCOPE_ID=chapter-alpha` so claim, detail, transitions,
> and messages continue through the chapter-scoped application target. This
> does not extend the authority helper; it uses the scope parameters it
> already provides.

That is real wiring — `seed-authority-grants.mjs:13-14` already accepts
`E2E_APPLICATION_SCOPE_KIND` / `E2E_APPLICATION_SCOPE_ID` env vars and
threads them into the grant insert (lines 99-100, 113-114). The proposal
does not add a TODO; it identifies the existing knob and turns it.

Anti-scope (proposal lines 263-273) hard-blocks roster stubs:

> Do not add Discord roles or channels for the seeded chapter.
> Do not modify `services/api/tests/chapter_selector_fixtures.py`.
> Do not change `/api/public/chapters` behavior or ordering.

Test plan (TG-3, lines 250-261) verifies the chapter-scoped officer flow
end-to-end (claim, detail, transcript, message append, transitions) rather
than punting roster verification — a "TODO add roster later" implementation
would fail TG-3 because the officer flow asserts post-claim behavior on the
chapter-scoped application.

## C4 — Uses node + the established e2e seed pattern (matches seed-authority-grants.mjs)

**Pass.**

Note on the check wording: the gate names "node + pg client", but the actual
pattern in `seed-authority-grants.mjs` is **node + `kubectl exec` against the
CNPG primary running `psql`** — there is no `pg` npm dependency. What the
gate is actually asking is "does this match the existing helper's execution
shape," and the answer is yes; the implementer should not introduce a `pg`
client.

`seed-authority-grants.mjs` is the reference shape:

| Element | Location |
|---|---|
| `KUBECONFIG_PATH` / `KUBECONFIG` env requirement | `seed-authority-grants.mjs:7, 16-18` |
| `kubectl(...)` helper via `execFileSync` | `seed-authority-grants.mjs:20-25` |
| CNPG primary pod selector (`role=primary`) | `seed-authority-grants.mjs:37-46` |
| Read `server-manager-postgres-url` secret, base64 decode | `seed-authority-grants.mjs:47-58` |
| `sqlLiteral` helper using `E''` form | `seed-authority-grants.mjs:27-35` |
| Single `psql -v ON_ERROR_STOP=1 -At -c <sql>` exec | `seed-authority-grants.mjs:125-140` |
| JSON summary on stdout | `seed-authority-grants.mjs:160-168` |

The proposal Substrate (lines 158-166) mirrors every line of that contract:

> - require `KUBECONFIG_PATH` or `KUBECONFIG`;
> - locate the CNPG primary pod in namespace `server-manager`;
> - read the `server-manager-postgres-url` secret;
> - execute one `psql -v ON_ERROR_STOP=1` SQL statement through `kubectl exec`;
> - use a local SQL literal helper for any string inserted into SQL;
> - print a JSON summary with `chapter_id`, `chapter_name`, `template_id`,
>   `template_name`, and `outcome`.

No new client library, no port-forward + raw socket path, no
`server-manager-api`/HTTP path. The 120-180 line budget for the helper
(line 278) is consistent with reusing this pattern, since
`seed-authority-grants.mjs` itself is ~169 lines including the CTE SQL.

The contract-derived assertion (proposal lines 168-172) is also a clean
extension of the existing pattern — `seed-authority-grants.mjs:9-12`
already reads `infra/tests/fixtures/web-ui/contract.json` and pulls the
identity from it. The new helper does the same to derive
`chapter-alpha` / `Alpha Chapter` and fail loudly if the contract drifts.

## C5 — Idempotency is real (queries DB, doesn't just count rows)

**Pass.**

Q2 (proposal lines 75-95) defines idempotency in terms of structural drift
checks, not row counts:

> - If the template, chapter, and `aggregate_heads` row already match the
>   fixture, return `chapter fixture already present; no-op`.
> - If none of the rows exist, insert the template, then chapter, then head.
> - If a partial compatible fixture exists, insert only the missing
>   dependency row needed to reach the complete fixture.
> - If `chapters.id = 'chapter-alpha'` exists with a different name, state,
>   or template association, abort.
> - If the fixture template identity exists with a different schema,
>   version, or non-empty structures, abort.
> - If an `aggregate_heads` row for `('chapter', 'chapter-alpha')` exists
>   with a non-fixture sequence/change shape, abort rather than rewriting
>   history.

Each rule is a field-shape predicate, not a `count(*) > 0` check. The
"abort if exists with different X" rules are fail-closed: a divergent
existing row will block the run and surface the drift, rather than letting
the helper paper over it by inserting a second row or by no-oping on count.

The SQL shape names a `fail_closed_guard` CTE (line 178) and three separate
`inserted_*` CTEs (lines 181-183), so the final SELECT can distinguish:

> final `SELECT`: one of `inserted chapter fixture`, `repaired partial
> chapter fixture`, or `chapter fixture already present; no-op`.

That three-state outcome is what makes the idempotency claim auditable from
the JSON summary — a count-based check could not produce a stable
`repaired partial chapter fixture` report, because it has no notion of
which dependency row was missing.

The unit-test fixture
(`services/api/tests/chapter_selector_fixtures.py:23-82`) already
demonstrates the same three-row shape, and Q4 + Q5 force the e2e helper to
match it by field, not by presence — `template_id`, `template_family_id`,
`version=1`, `schema_version=1`, empty JSON arrays for the three
structures, `aggregate_type='chapter'`, `aggregate_id='chapter-alpha'`,
`current_seq=1`, `latest_change_id=NULL`.

TG-1 (proposal lines 226-234) reinforces this with an externally-visible
post-condition:

```bash
kubectl exec ... -- psql ... -Atc \
  "select count(*) from chapters where id = 'chapter-alpha' and state = 'active'"
```

Expected: `1`. Note this is a post-seed verification of fixture presence,
not the seed's own idempotency check — the seed makes the structural
decisions, then the test gate confirms the chapter is active and queryable.

## Findings worth carrying into implementation

Not blockers — verdict is LOW — but the implementation phase should preserve:

1. **No `pg` npm dependency.** The check wording says "node + pg client" but
   the actual reference pattern in `seed-authority-grants.mjs` is `node +
   kubectl exec psql`. Adding `pg` would diverge from the established e2e
   helper shape and require new image/dep wiring. Stick with `kubectl exec`
   into the CNPG primary running `psql`.

2. **Compute the deterministic template UUID, don't `randomUUID()`.** Q4
   says "deterministic UUID derived from the `e2e-template` seed key."
   `seed-authority-grants.mjs:60-61` uses `randomUUID()` for member/grant
   ids because their identity is per-row, not fixture-stable. The chapter
   template id must be reproducible across reseeds so the
   `template_id`/`template_family_id` reference and the chapter's
   `template_snapshot` JSON resolve to the same UUID every run — this is
   what makes idempotency rule 1 ("rows already match") possible.

3. **`aggregate_heads.latest_change_id = NULL` is intentional.** Q5's
   literal SQL writes `NULL`. The minimum-row fixture in
   `services/api/tests/chapter_selector_fixtures.py` does the same. An
   "improvement" that synthesizes a fake change id (or reads from
   `outbox_events` / a non-existent change ledger) would violate Q2's
   abort-on-drift rule for non-fixture sequence/change shapes and would
   probably introduce a new FK that doesn't exist in the cluster.

4. **Step ordering in `19-web-ui.sh` matters.** Substrate steps 1-5
   (proposal lines 205-218) put the chapter seed *before* the
   chapter-scoped re-invocation of `seed-authority-grants.mjs`. Reversing
   this would seed an authority grant against a chapter scope id that does
   not yet have a corresponding `chapters` row, which is fine for the
   `authority_grants` insert in isolation but would mask a chapter-seed
   failure in TG-3 when officer transitions resolve the application
   target. Keep the order.

5. **Single transaction, single `psql` invocation.** Substrate line 162
   ("execute one `psql -v ON_ERROR_STOP=1` SQL statement through `kubectl
   exec`") plus Q2's all-or-nothing idempotency posture combine to a
   structural rule: do not split the template/chapter/head inserts across
   multiple `psql` calls. A multi-call implementation could land the
   template, then bail before the chapter or head, leaving a partial state
   that "repaired partial chapter fixture" exists to surface but not to
   create.

6. **TG-2 contract assertion piggybacks on the contract-derivation in the
   helper.** The helper reads `contract.json` (proposal lines 168-172) and
   asserts `chapter-alpha` / `Alpha Chapter`. TG-2 then curls
   `/api/public/chapters` and expects `{"id":"chapter-alpha","name":"Alpha
   Chapter"}`. If the contract changes in the future, the helper will fail
   first with a clear message rather than silently seeding a stale fixture
   that TG-2 catches as a downstream HTTP mismatch. Preserve that
   ordering — fail at the seed, not at the curl.

## Verdict

LOW. No shortcuts. The proposal:

- Picks a direct-SQL e2e helper invoked from `19-web-ui.sh`, with the RCA
  closing the API path because the seeded officer does not hold
  `chapter_template.write` / `chapter.write`, and anti-scope explicitly
  forbidding admin-chapter-creation surfaces.
- Inserts in dependency order (template → chapter → aggregate head) inside
  a single transaction, with a self-contained `e2e-template` and no
  shared-default lookup, mirroring the unit-test fixture shape from
  `chapter_selector_fixtures.py` field-for-field.
- Handles roster head-on (RCA shows it isn't needed for chapter projection)
  and addresses chapter-scoped authority by reusing the existing
  `E2E_APPLICATION_SCOPE_KIND` / `E2E_APPLICATION_SCOPE_ID` knob in
  `seed-authority-grants.mjs` rather than punting with a TODO.
- Mirrors the `seed-authority-grants.mjs` execution pattern (KUBECONFIG,
  CNPG primary pod, postgres-url secret, `kubectl exec psql`, `sqlLiteral`,
  JSON summary) — same shape, no new client library.
- Defines idempotency as fail-closed structural drift checks across
  template / chapter / head, not row counts, with a three-outcome final
  SELECT (`inserted` / `repaired partial` / `already present; no-op`) that
  is auditable from the JSON summary.

SHORTCUT_DONE: plans/risk/bug-5-shortcut.md
