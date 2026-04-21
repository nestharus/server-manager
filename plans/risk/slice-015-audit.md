# SLICE-015 Audit Risk Assessment (Revision 2)

**Rating: LOW** — design is sound for data integrity, safety, security, and
ops readiness.

Scope: `.pipeline/proposal.md` Revision 2 (WU-029A, WU-029B-materialize,
WU-029B-deliver, WU-029C) against `.pipeline/synthesis.md` D1–D14,
`.pipeline/research.md`, `product-strategy/tickets/SLICE-015.md`, and merged
SLICE-001..018 code.

Revision 2 resolves all four Revision 1 MEDIUM items (M1–M4). The earlier
Revision 1 R1/R2 resolutions (Discord nonce length, shared-txn materialize
enqueue) remain in force. No HIGH findings. All residual items are LOW and
bounded by either an existing binding decision (D1–D14) or an explicit
out-of-scope note.

## Resolved in Revision 2

### M1 — `_claim.claim_due_rows` generalization → RESOLVED

Rev 1 concern: generalizing `_claim.claim_due_rows` to support envelope claim
without a `claimed` status could (a) write `status = NULL` and corrupt
existing `scheduled_jobs` / `deferred_effects` callers, (b) raise on
`notification_envelopes` (no `status` column, only `delivery_status`), or
(c) break parameter ordering in the Composed SQL.

Revision 2 pins the fix at the spec level (proposal §WU-029A-repository,
§"Preserved"/SLICE-004, §4 tradeoff, §6 D6):

- When `claim_status is None`, the helper **must omit** the `status = %s` SET
  clause entirely — not emit `status = NULL` or an empty string, and not
  touch `delivery_status`.
- Existing scheduler/deferred-effect callers keep the default
  `claim_status="claimed"` and must remain unchanged and green.
- New test `test_claim_due_rows_with_claim_status_none_does_not_set_status`
  asserts the omit-SET behavior against envelope rows.

Current helper at `services/api/app/repositories/_claim.py:10-52` hardcodes
`SET status = 'claimed'` at line 35 inside a `sql.Composed`; the Rev-2 spec
requires conditional SQL construction with conditional parameter insertion.

Residual implementation-discipline check (see A1 below): phase-3 must ensure
the two existing callers (`claim_due_scheduled_jobs` at
`services/api/app/repositories/scheduler.py:112` and
`claim_due_deferred_effects` at
`services/api/app/repositories/deferred_effects.py:156`) pass their existing
regression tests unchanged.

### M2 — `emit()` → materialize enqueue atomicity → RESOLVED

Rev 1 concern: splitting the `notification_events` insert and its
`notifications_materialize` deferred effect enqueue across separate
transactions would silently drop notifications when the enqueue fails after
the event row has committed.

Revision 2 replaces `emit()` with a keyword-only contract
(`.pipeline/proposal.md:394-409`):

```python
def emit(
    db: PostgresDatabase | None,
    *,
    event: NotificationEventDraft,
    actor: ActorIdentity,
    connection: Connection[Any] | None = None,
) -> NotificationEventRead: ...
```

Either the caller passes its active `connection` and `emit()` performs both
writes through it, or the caller passes `db` and `emit()` owns the short
transaction. The service-level `deferred_effects.enqueue_effect()` must also
be extended to accept `connection: Connection | None = None`; when supplied,
it may not open or commit a separate transaction. Test
`test_emit_is_atomic_when_called_with_connection` forces an enqueue failure
and asserts the paired `notification_events` row is absent after rollback.

Current substrate confirms the migration is feasible: the repository-level
`deferred_effects.enqueue_effect()` at
`services/api/app/repositories/deferred_effects.py:31` already accepts a
connection and uses `INSERT ... ON CONFLICT (idempotency_key) DO NOTHING`,
so sharing the caller's transaction is clean. The service wrapper at
`services/api/app/services/deferred_effects.py:69` opens its own connection
today and needs the optional-connection extension described in Rev 2.

Caller migration is bounded: the only current `emit()` caller outside the
function itself is
`services/api/tests/test_notification_event_contract.py:35`. No merged
production code depends on the old positional signature, so the Rev-2
breaking-change risk is scoped to test updates.

### M3 — `delivered_in_flight` operator visibility → RESOLVED

Rev 1 concern: ambiguous transport failures leave envelopes permanently
`delivered_in_flight`, un-claimable by any worker, with no surface for
detection. A single bad Discord call could silently hang forever.

Revision 2 §WU-029B-deliver / §"Preserved"/SLICE-004 extends the existing
`query_degraded_state_summary()` at
`services/api/app/repositories/deferred_effects.py:289` with a read-only
`stuck_in_flight_envelopes` count for the `notifications` subsystem:

```sql
SELECT COUNT(*)
FROM notification_envelopes
WHERE delivery_status = 'delivered_in_flight'
  AND claimed_at < now() - INTERVAL '1 hour'
```

This reuses the degraded-state endpoint operators already monitor for
scheduled jobs and deferred effects. No new endpoint, no reconciliation
action — just visibility. Test
`test_degraded_state_summary_counts_stuck_in_flight_envelopes` pins the
counter.

### M4 — Rule mutation audit payload allowlist → RESOLVED

Rev 1 concern: undefined `payload_allowlist` on `notification_rule.create`
and `notification_rule.patch` would leave audit rows with empty or
incomplete payloads; `mutate_entity._redact_payload` at
`services/api/app/services/mutations.py:37-48` returns `{}` for `None` or
empty allowlists.

Revision 2 pins the exact key set (proposal §WU-029A-service):

```
{"trigger_json", "scope_kind", "scope_id", "recipients_json", "channel",
 "template_json", "actionable", "grouping", "enabled"}
```

The contract models also commit `NotificationRuleCreate.model_dump().keys()`
to be exactly this set, with HTTP-layer aliases `trigger`/`recipients`/
`template` so request bodies stay clean while the allowlist, repository row
map, and audit payload share one vocabulary. Test
`test_rule_create_audit_payload_includes_all_rule_fields` asserts the
activity-action `request_json` contains exactly these keys after a create.

## Per-focus-area findings

### F1. Materialize idempotency — LOW

Two partial unique indexes (proposal §WU-029A-migration):

- `uq_notification_envelopes__per_event`:
  `UNIQUE(source_event_id, rule_id, recipient_key) WHERE grouping='per_event'`
- `uq_notification_envelopes__per_root_cause`:
  `UNIQUE(rule_id, root_correlation_id, recipient_key) WHERE
   grouping='per_root_cause'`

`INSERT ... ON CONFLICT DO NOTHING` against these indexes prevents duplicate
envelopes on retry/replay (D8). `recipient_key` uses
`f"discord_user:{user_id}"` for resolved recipients and
`f"unresolved:<hash>"` for skipped ones, so every path produces a stable key
covered by the index. Unresolved-hash collision remains a minor spec
concern (F11 below). LOW.

### F2. Delivery worker claim correctness — LOW

Delivery claim uses `FOR UPDATE SKIP LOCKED` with predicate
`delivery_status='pending' AND attempts < max_attempts AND
(claimed_by IS NULL OR lease_until < now)` (proposal §WU-029A-repository,
§WU-029B-deliver-service). Worker 2's SELECT skips the row Worker 1 holds.
The "re-claim after expired lease" branch is correct because the winning
worker either committed the `delivered_in_flight` transition (making the
row un-claimable by predicate) or crashed before calling Discord (making
another worker's single send correct). No double-delivery path at the DB
layer. See F3 for the nonce-window interaction. LOW.

### F3. Discord nonce retry-window envelope — LOW

Discord's `enforce_nonce` window is a few minutes. The proposal (§WU-029C,
§4 tradeoff) layers defenses:

1. **Within window**: `envelope_nonce(envelope_id)` with `enforce_nonce=True`
   dedupes duplicate sends at Discord.
2. **Outside window**: the delivery service marks
   `delivery_status='delivered_in_flight'` *before* invoking the adapter
   (proposal §WU-029B-deliver-service step 4). Any post-window retry sees
   a non-pending row and short-circuits without calling Discord.

Residual narrow window: between the SKIP-LOCKED claim commit and the
`delivered_in_flight` write, the row is `pending` with a fresh
`lease_until`. If the worker crashes there and the lease expires, another
worker re-claims — but the first worker never reached Discord, so the
second worker's single send is the only send. No duplicate.

Keep `LEASE_SECONDS` well below Discord's nonce window in the runbook, for
defense-in-depth if a future refactor separates the claim and
`delivered_in_flight` writes. LOW.

### F4. Per-root-cause grouping semantics — LOW

Under `grouping='per_root_cause'`, the unique index omits `source_event_id`,
so multiple events sharing `correlation_id` insert one envelope; the
first-event insert wins, and all subsequent events hit
`ON CONFLICT DO NOTHING`. This is the binding D5 behavior and is asserted
by `test_multiple_events_same_root_correlation_one_envelope`.

Operator-visible consequence: envelope content reflects the first event
only; later events in the same correlation do not update the envelope view.
This is intentional (operational signal is "root X had an issue", not the
full incident timeline) but should be surfaced to rule authors:

**Runbook note**: *per_root_cause rules reflect the first event's content,
not the latest. Subsequent events in the same correlation are audited in
`notification_events` but do not amend the already-materialized envelope.*

LOW.

### F5. Recipient resolution timing / no retry path — LOW

Per D10, recipient and destination resolution happen at materialization
time and are snapshotted onto the envelope. Failure modes materialize
skipped envelopes with `last_error_json.reason`:

- Unsupported selectors (incl. `discord_role`): `recipient_key` uses an
  unresolved-hash, `delivery_status='skipped'`, no delivery effect enqueued.
- Missing `designated_channel_id`: `reason='destination_missing'`.
- `channel='thread'`: `reason='thread_channel_out_of_scope'`.
- Template missing key: `reason='template_missing_key'`.

If a later slice adds role membership resolution or thread delivery, the
previously skipped envelopes are **not** re-evaluated. Re-emitting the
source event would create a new `event_id` and new envelopes; the skipped
ones remain terminal per D10. Acceptable per the ticket — this is
operational state, not a bug.

**Runbook note**: *recipient-resolution skipped envelopes are terminal in
SLICE-015; later role/thread support needs an explicit re-resolution
mechanism.* LOW.

### F6. Template rendering snapshot isolation — LOW

Per D11, rendering uses strict `string.Template.substitute()` at
materialization time and snapshots `template_snapshot_json`,
`rendered_title`, `rendered_body` onto the envelope. The delivery worker
transmits only the snapshotted strings; rule PATCHes after materialization
cannot retroactively change in-flight envelope content. Test
`test_template_rendering_snapshot_isolates_from_later_rule_edits` asserts
this. Missing keys raise `TemplateRenderError` and materialize as skipped
envelopes rather than shipping `${missing_key}` text to users.

Template values are inserted unescaped into
`rendered_title`/`rendered_body`. Current event producers emit only IDs,
state names, and enum values — no user free text — so Discord-markdown /
`@everyone` injection is not a live risk. If a future producer ever routes
user free text through `payload_json`, it would reach Discord unescaped.
Producer allowlist discipline is documented in `notification_events.emit()`
today; surface it in rule-author docs so operators understand the
responsibility boundary. LOW.

### F7. Scheduler enqueue atomicity with mutation — LOW (resolved by Rev 2)

D9 binds that every `notification_events` insert enqueues a
`notifications_materialize` deferred effect in the same transaction.
Revision 2's emit() signature (see M2 resolution above) guarantees this by
accepting a caller connection. Projection code inside a `mutate_entity`
transaction passes the mutation's active connection to `emit()`; callers
outside a transaction pass `db` and `emit()` owns the short transaction
that covers both writes. The negative test
`test_emit_is_atomic_when_called_with_connection` forces the enqueue to
raise and asserts the event row is also absent.

Residual: the proposal requires `deferred_effects.enqueue_effect()` (service
wrapper at `services/api/app/services/deferred_effects.py:69`) to accept
`connection: Connection | None = None`. Phase-3 implementation must honor
that — see A2 below. LOW.

### F8. Rule disable/delete semantics — LOW

- **Disable** (`enabled=false` PATCH): the materialization rule-select
  includes `WHERE enabled=TRUE`, so a disabled rule stops producing new
  envelopes. Existing pending envelopes already snapshot-rendered remain
  deliverable — correct, because the operator intent was "stop future
  traffic," not "cancel what was already owed." Phase-3 must make the
  `enabled=TRUE` filter explicit and test
  `test_disabled_rule_does_not_materialize`.
- **Delete**: envelopes reference rules via
  `rule_id ... ON DELETE RESTRICT`, and no DELETE endpoint is proposed.
  Rules with any envelope history cannot be physically removed. If a
  later slice adds delete, snapshot fields on envelopes keep the
  in-flight content self-sufficient. LOW.

### F9. Authority and service-actor grants — LOW

Migration seeds `notification-dispatcher` with exactly
`["notification.read", "notification.deliver"]` at
`scope_kind='global'`, using the `INSERT ... WHERE NOT EXISTS` idempotent
pattern proven in `migrations/versions/wu-012_trust.py:61-97` and
`wu-019_chapter_lifecycle.py:107`. Downgrade/upgrade cycles are safe.
`notification.write` is explicitly excluded per D12 so workers cannot
mutate rules — isolates delivery failure state from rule definitions
(AC4). Test `test_notification_dispatcher_service_grants_seeded` should
also assert the grant's `permissions` array does **not** contain
`notification.write`. LOW.

### F10. Rule mutation audit payload allowlist — LOW (resolved by Rev 2)

Covered by the M4 resolution above. The exact allowlist key set matches
the persisted column names (`_json` suffixes), public HTTP bodies use
clean aliases, and the test asserts exact-key equality on the
activity-action `request_json`. Audit reviewers can reconstruct exactly
"who approved which rule, with which trigger, recipients, template, and
grouping." LOW.

### F11. Concurrent rule PATCH vs in-flight materialize — LOW

Materialize reads rule rows without `FOR UPDATE`. If a PATCH advances the
rule version between "load enabled rules" and "insert envelope", Postgres
row-level read consistency ensures the SELECT observes either the
pre-PATCH or post-PATCH row, not a partial mix. The envelope's
`rule_version` column records the snapshot, making the audit trace
unambiguous. Already-rendered envelopes are further isolated by the
snapshot fields (F6). This is the binding D11 behavior. LOW.

### F12. Migration safety (wu-029a chain) — LOW

Proposal §WU-029A sets `down_revision = "wu_012_trust"`. The current
post-SLICE-018 migration head chain is:
`wu_008b_deferred_effect → wu_014_authority_api → wu_018_chapter_templates
→ wu_019_chapter_lifecycle → wu_033_roster → wu_011_members →
wu_012_trust`, with `wu_012_trust` as HEAD (confirmed by `down_revision`
on each migration file). The proposal's `down_revision` target is valid
for the current branch state.

Migration adds two new tables (`notification_rules`,
`notification_envelopes`) with new indexes, FKs (`ON DELETE RESTRICT` into
`notification_events`, which exists), and an idempotent service-grant seed.
No backfill, no ALTER on shared tables, no long locks. Down-migration drops
the new tables and the seeded grant row only. LOW.

## Additional LOW findings

### L1. Unresolved recipient key hash must be pinned

Proposal §WU-029B-materialize specifies
`recipient_key = "unresolved:<stable-selector-hash>"` for failed
resolution. "stable-selector-hash" is underspecified. Two distinct
recipient selectors that both fail to resolve could hash-collide and
collapse under the partial unique index, hiding one skipped envelope.

Practically narrow — SLICE-015 skips all `discord_role` selectors, so the
populated case is users only — but phase-3 must pin the hash input (e.g.
`json.dumps(selector, sort_keys=True)` through a stable digest) and
document the exact algorithm in the repository docstring.

### L2. `emit()` side-effect is an implicit contract change

The Rev-2 `emit()` signature converts "insert one notification event" into
"insert + enqueue materialize." Every existing caller becomes an implicit
producer of materialization work. Current production callers: none; the
only test caller is `test_notification_event_contract.py:35`. The
idempotency_key `f"notifications:materialize:{event_id}"` coalesces
duplicate emits. D9 binds the new behavior. Phase-3 commit message should
call out the new semantic so future producers do not re-open the
"insert-only" assumption.

### L3. Envelope state transitions are not routed through `mutate_entity`

Delivery state transitions (`pending → delivered_in_flight → delivered |
failed | skipped`) update envelope rows directly in the delivery service
and write no `activity_actions` row. This is consistent with D6 (delivery
is operational state, not governed mutation) and with how scheduler and
deferred-effect state changes are handled. Envelope columns (`attempts`,
`last_error_json`, `claimed_by`, `discord_message_id`, `delivered_at`)
capture enough to reconstruct the delivery history, and
`stuck_in_flight_envelopes` from M3 surfaces stragglers. LOW.

### L4. Trigger `payload_filters` operates against redacted payload

`notification_events.emit()` persists payloads filtered by the caller's
`payload_allowlist`
(`services/api/app/services/notification_events.py:14-24`).
`NotificationTrigger.payload_filters` match against the persisted (possibly
redacted) dict, not the producer's original kwargs. A rule that filters on
a key the producer did not allowlist will silently never match. This is
the correct contract — the allowlist is the producer's privacy boundary —
but rule-author documentation must make the constraint visible. LOW.

### L5. `per_event` and `per_root_cause` coexistence is not a collision

The two partial unique indexes each carry their own
`WHERE grouping='...'` predicate, so a recipient targeted by both a
per-event rule and a per-root-cause rule for the same correlation emits
two envelopes (one per index, each with a distinct `grouping` value).
Operators correctly receive both notifications; this is the binding D5
behavior. LOW.

### L6. Materialization reads rule rows without `FOR UPDATE`

Confirmed LOW by Postgres read consistency (F11). The envelope
`rule_version` column records the snapshot against which the envelope was
rendered, so audit review can reconstruct which rule state produced any
envelope. LOW.

## Phase-3 implementation-discipline gates

These are the surviving "must-check-during-implementation" items. None
raise the audit severity above LOW; they are the acceptance gates for
implementing the Rev-2 design correctly.

1. **A1 — claim helper regression**: `_claim.claim_due_rows` with
   `claim_status=None` must omit the `status = %s` SET clause entirely and
   drop its placeholder from `params`. The two existing callers
   (`claim_due_scheduled_jobs`, `claim_due_deferred_effects`) must pass
   their existing regression tests unchanged, writing `status='claimed'`
   exactly as today. The new envelope claim test must observe no write to
   any `status` or `delivery_status` column during claim.

2. **A2 — `enqueue_effect()` connection injection**: the service wrapper
   at `services/api/app/services/deferred_effects.py:69` must be extended
   to accept `connection: Connection | None = None`; when supplied, it
   must use that connection and must not open `db.connection()` or commit
   a separate transaction. The materialize service passes its own
   connection; `emit()` in the wu-029b path does the same. Negative test
   `test_emit_is_atomic_when_called_with_connection` proves rollback
   atomicity.

3. **A3 — unresolved-recipient hash algorithm**: pin the exact input
   normalization (e.g.
   `hashlib.sha256(json.dumps(selector, sort_keys=True).encode()).hexdigest()[:16]`)
   in the repository/service docstring, and assert it in a test that two
   distinct unresolved selectors produce distinct `recipient_key` values.

4. **A4 — rule SELECT filter**: materialization rule-select includes
   `AND enabled = TRUE` explicitly. Add `test_disabled_rule_does_not_materialize`
   to the WU-029B-materialize test file.

5. **A5 — dispatcher grant exclusion**: extend
   `test_notification_dispatcher_service_grants_seeded` to assert
   `notification.write NOT IN permissions` for the dispatcher grant row.

6. **A6 — audit allowlist test strictness**: the Rev-2-added
   `test_rule_create_audit_payload_includes_all_rule_fields` must assert
   **exact** key-set equality (not subset) against
   `activity_actions.request_json` for the recorded
   `notification_rule.create` action.

## Severity Summary

| Item | Severity | Area |
|---|---|---|
| M1 | RESOLVED (Rev 2) | `_claim.claim_due_rows` conditional SET clause |
| M2 | RESOLVED (Rev 2) | `emit()` → materialize enqueue shared-txn atomicity |
| M3 | RESOLVED (Rev 2) | `delivered_in_flight` visibility via `stuck_in_flight_envelopes` |
| M4 | RESOLVED (Rev 2) | Rule mutation `payload_allowlist` pinned + test |
| R1 | RESOLVED (Rev 1) | Discord 25-char deterministic nonce |
| R2 | RESOLVED (Rev 1) | Materialize handler envelope + delivery-effect shared txn |
| F1 | LOW | Partial unique indexes prevent duplicate envelopes |
| F2 | LOW | `FOR UPDATE SKIP LOCKED` delivery claim is correct |
| F3 | LOW | Nonce window + `delivered_in_flight` defense-in-depth |
| F4 | LOW | per_root_cause first-event-wins (documented) |
| F5 | LOW | Materialize-time recipient resolution is terminal for skipped |
| F6 | LOW | Template snapshot isolates in-flight envelopes |
| F7 | LOW | Atomic `emit()` + materialize enqueue (via M2) |
| F8 | LOW | Rule disable/delete semantics (FK RESTRICT, no DELETE) |
| F9 | LOW | Service-actor grants idempotent, `notification.write` excluded |
| F10 | LOW | Audit payload allowlist is complete (via M4) |
| F11 | LOW | Rule PATCH vs in-flight materialize race (read-consistent) |
| F12 | LOW | Migration new-tables-only; `wu_012_trust` is valid down_revision |
| L1 | LOW | Unresolved-recipient hash algorithm must be pinned (A3) |
| L2 | LOW | `emit()` side-effect is an implicit contract change |
| L3 | LOW | Envelope state transitions bypass `activity_actions` (per D6) |
| L4 | LOW | Trigger `payload_filters` observes post-redaction payload |
| L5 | LOW | Cross-grouping envelope generation is intentional |
| L6 | LOW | Materialize reads rules without `FOR UPDATE` (safe) |

No HIGH findings. No remaining MEDIUM findings. Six phase-3 implementation
gates (A1–A6) remain as acceptance checks for correctly executing the
Rev-2 design.

## Revision History

- **Revision 2 (this doc)**: All four Revision 1 MEDIUM items (M1–M4)
  resolved at the spec level by proposal Revision 2. Added per-focus-area
  findings F1–F12 covering the audit prompt checklist. Confirmed
  `wu_012_trust` as valid `down_revision` (L10 resolved). Converted the
  Revision 1 Phase-3 gates into A1–A6 implementation-discipline gates.
- **Revision 1**: Identified M1–M4 and preserved R1/R2 resolutions from
  proposal Revision 1 (Discord nonce length; materialize shared-txn
  envelope + delivery-effect enqueue).
