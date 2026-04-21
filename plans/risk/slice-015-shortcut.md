# SLICE-015 Shortcut Risk Assessment

**Rating: LOW**

## Scope

Reviewed `worktrees/slice-015/.pipeline/proposal.md` (Revision 1) against
`.pipeline/research.md`, `.pipeline/synthesis.md` D1-D14, `AGENTS.md`
§"No Backwards Compatibility" (lines 564-576) and §"No Deferred Stubs"
(lines 580-585), and the merged SLICE-001..018 substrate:

- `services/api/app/services/notification_events.py`
- `services/api/app/services/scheduler.py`
- `services/api/app/services/deferred_effects.py`
- `services/api/app/repositories/_claim.py`
- `services/api/app/repositories/deferred_effects.py`
- `services/api/app/repositories/scheduler.py`
- `services/api/app/services/mutations.py`
- `services/api/app/contracts/notifications.py`

Revision 1 closed the five shortcut items flagged in the prior assessment
pass (nonce encoding, claim-helper fiction, silent template rendering, batch
delivery duplicate path, destination channel unplumbed). The remaining items
are substrate reuse and implementation-time pins, not shortcuts.

## Findings

### S1. Existing notifications code — extended, not paralleled

`services/api/app/services/notification_events.py:27` `emit()` already takes
the caller's connection. Proposal §WU-029B-materialize
(`.pipeline/proposal.md:366-386`) extends it in place to enqueue a
`notifications_materialize` deferred effect in the same transaction.
`notification_events` remains the source table (proposal §5 Preserved,
lines 730-751). No parallel queue table, no `emit_v2`, no dual-write.
Existing contracts (`NotificationEventDraft`, `NotificationEventRead` at
`services/api/app/contracts/notifications.py:12-27`) are unchanged; new
rule and envelope contracts are additive. LOW.

### S2. Hardcoded `notification-dispatcher` actor — by design

The worker actor identity is fixed at `actor_kind="service",
actor_id="notification-dispatcher"` (`.pipeline/proposal.md:575-581`), and
the migration seeds the grant with the same id (`:186-190`). This matches
the existing service-actor convention — `member-onboarder`
(`migrations/versions/wu-012_trust.py:76-97`), `discord-provisioner`,
`chapter-lifecycle-worker` (`wu-019_chapter_lifecycle.py:107`). It is not
threaded from the originating user caller because worker operations are
deferred-effect service executions, not user mutations; the triggering
user actor is already captured on the source `notification_events` row via
`correlation_id` and on `activity_actions` from the original mutation.
D13 binds this (`.pipeline/synthesis.md:179`). LOW.

### S3. Discord nonce — deterministic 25-char token + local guard

Revision 1 replaced raw-UUID nonce with `envelope_nonce(envelope_id)`:
base32-encode the 16 UUID bytes, strip padding, truncate to 25 chars
(`.pipeline/proposal.md:635-650`). ~123 bits of collision space, within
Discord's limit, deterministic across retries. Paired with a local DB
guard: before Discord call, envelope is marked `delivered_in_flight`
(`.pipeline/proposal.md:557-560`); delivery service skips resend when
envelope is in `delivered` or `delivered_in_flight`
(`.pipeline/proposal.md:553-555`); ambiguous transport failure leaves
`delivered_in_flight` for operator reconciliation rather than retrying past
the Discord window (`:571-574`).

Nonce handles the in-window case (minutes); DB state handles all longer
retries. The proposal §Tradeoffs (`.pipeline/proposal.md:700-706`) names
this as belt-and-suspenders rather than claiming nonce is the primary
guarantee. Audit `L1` (`plans/risk/slice-015-audit.md:72-85`) tracks the
narrow "lease-exceeds-nonce-window after post-send crash" edge case.
LOW.

### S4. Claim helper reuse — substrate extension, not duplicated SQL

The prior concern was that `_claim.py:34-38` hardcodes
`SET status = 'claimed'`, while `notification_envelopes` has
`delivery_status` and must not set a `claimed` state. Revision 1 resolves
this by generalizing the shared helper with an optional `claim_status`
parameter (`.pipeline/proposal.md:263-271`, §5 Preserved lines 764-772).
Existing callers keep the `'claimed'` default; envelopes pass
`claim_status=None`, and the helper updates only claim ownership /
lease / `updated_at` without touching `delivery_status`. Both
`services/api/app/repositories/scheduler.py:112` and
`services/api/app/repositories/deferred_effects.py:156` continue to funnel
through the same helper; envelopes join the same funnel. No envelope-
specific copy of `SELECT ... FOR UPDATE SKIP LOCKED` SQL is introduced.
LOW.

Pin at implementation: the one-envelope delivery handler passes
`batch_size=1` with an `id = %s AND ...` ready predicate. Confirm the
helper's `ORDER BY` and `LIMIT` path does not surprise the single-row
case; no envelope-specific claim SQL.

### S5. Template engine — strict `substitute()`, not silent `safe_substitute()`

Revision 1 explicitly forbids `safe_substitute()` (.pipeline/proposal.md:476-479):
missing template keys raise `TemplateRenderError` at materialization time
and produce a skipped envelope with `reason = "template_missing_key"`;
unresolved `${missing_key}` text is never shipped to users. The renderer
is `string.Template.substitute()` over a flattened context (event_id,
event_type, correlation_id, causation_id, scope_kind, scope_id,
`payload_<key>` for each top-level payload key, rule_id). D11 binds this
and the envelope snapshot isolates delivery from later rule edits. LOW.

Observation, not a block: the `payload_<key>` flattening convention is a
deliberate simplification. Nested payload access (`target.id`) is not
supported. If a later slice needs nested access, the renderer changes to a
template language that supports it — no silent compatibility shim is
baked in. The test
`test_materialize_skips_when_template_has_missing_key`
(`.pipeline/proposal.md:508`) pins the strict-missing-key behavior.

### S6. Recipient resolution at materialize — honest scope handling

D10 resolves recipients at materialization time and snapshots
`recipient_discord_id` / `recipient_display` / `destination_channel_id`
onto the envelope (`.pipeline/proposal.md:433-455`). Delivery reads the
envelope only. `discord_role` recipients are persisted on the rule as
submitted (AC1), but materialized as `skipped` rather than faked via a
stub resolver (`.pipeline/proposal.md:440-444`, §Tradeoffs 719-723).
Explicit "no fake role resolver" scope boundary, not a hidden TODO. LOW.

### S7. Worker registration — no substrate hacks

Both handlers register via `register_scheduler_handler(...)` from
`services/api/app/services/scheduler.py:80`
(`.pipeline/proposal.md:356-364`, `:518-527`), imported at module load
through `services/api/app/tasks/__init__.py` in the pattern already in use
for other tasks. No direct `_HANDLER_REGISTRY` mutation, no side-channel
tick into `SchedulerLoop._tick()`, no new recurrence primitive. Research
§2.6 flagged three substrate options; the proposal picked "deferred
effects only" (§Tradeoffs lines 688-691). Consistent with SLICE-004.
`SchedulerLoop._tick()` already dispatches deferred effects at
`services/api/app/services/scheduler.py:180`. LOW.

### S8. Duplicated claim logic across materialize + deliver — no duplicate path

Materialize does not claim `notification_events` — `emit()` writes a
`deferred_effects` row and the existing `deferred_effect_worker_tick()` at
`services/api/app/services/deferred_effects.py:136` claims it. Zero new
claim SQL for materialize.

Delivery claims `notification_envelopes` via the generalized `_claim.py`
helper (S4), invoked from a single per-envelope deferred-effect handler.
Revision 1 explicitly removed the prior batch delivery helper path
(`.pipeline/proposal.md:922-935`): tests exercise delivery via the
registered handler or the one-envelope service function with a fake port
(`:529-533`). No production/test split entry point, no parallel "batch
catch-up" helper, no `deliver_pending_notifications(...)` batch function.
LOW.

### S9. Audit payload allowlist — repo convention

Proposal routes rule create and patch through
`services/api/app/services/mutations.py::mutate_entity` with
`payload_allowlist` covering the submitted rule fields
(`.pipeline/proposal.md:287-310`). This matches the pattern across the
repo:

- `services/api/app/services/chapters.py:160` —
  `payload_allowlist=set(request.model_dump(mode="json").keys())`
- `services/api/app/services/members.py:128` — same
- `services/api/app/services/roster.py:159` — same
- `services/api/app/services/chapter_templates.py:101` — same

Not a shortcut — it is the canonical pattern. Redacting `recipients_json`,
`template_json`, or `trigger_json` would hide the governed rule definition
from the audit surface, defeating D12. LOW.

Pin at implementation: key the allowlist by
`set(request.model_dump(mode="json").keys())` rather than a bespoke
literal set, so patch shapes stay in sync automatically. If operator
recipient IDs or free-text template copy are later reclassified as
PII-sensitive, the allowlist is the one place to change.

### S10. Idempotency via UNIQUE index — real, database-enforced

Two partial unique indexes (`.pipeline/proposal.md:167-172`):

- `uq_notification_envelopes__per_event` on
  `(source_event_id, rule_id, recipient_key) WHERE grouping = 'per_event'`
- `uq_notification_envelopes__per_root_cause` on
  `(rule_id, root_correlation_id, recipient_key) WHERE grouping = 'per_root_cause'`

Inserts use `INSERT ... ON CONFLICT DO NOTHING` (D8,
`.pipeline/proposal.md:493-497`). Partial-index split matches the binding
grouping contract and
`test_unique_index_prevents_duplicate_envelope_rows`
(`.pipeline/proposal.md:507`) pins it at the DB layer. The deferred-effect
side also has `ON CONFLICT (idempotency_key) DO NOTHING` at
`services/api/app/repositories/deferred_effects.py:66`, so
materialize / deliver replay is idempotent end-to-end. Real, not
optimistic. LOW.

### S11. Destination channel plumbing — explicit in Revision 1

Revision 1 adds a materialization-time resolution step
(`.pipeline/proposal.md:446-455`):

- `channel = "dm"`: store `destination_channel_id = NULL`; the Discord
  adapter opens/creates the DM with `recipient_discord_id`.
- `channel = "designated_channel"`: read
  `recipients_json.designated_channel_id` and snapshot it on the envelope;
  missing/blank field materializes a skipped envelope with
  `reason = "destination_missing"`.
- `channel = "thread"`: materialize a skipped envelope with
  `reason = "thread_channel_out_of_scope"`.

The adapter reads the envelope snapshot only. No stub read path, no
`destination_channel_id` column that's written by "something later". D10
binds this. LOW.

### S12. Envelope + delivery-effect transaction boundary

Revision 1 requires envelope inserts and `notifications_deliver`
deferred-effect enqueues to share one transaction
(`.pipeline/proposal.md:425-433`). If `deferred_effects.enqueue_effect()`
cannot accept a shared connection, the proposal extends it with
`connection: Connection | None = None` in the same PR
(`:378-386`, `:425-433`). Not a shim — it is a real substrate extension,
and it is the fix to the audit M2 orphan-envelope finding.

The "newly created" gate on delivery-effect enqueue
(`.pipeline/proposal.md:420-425`) is safe only because the two writes
share a transaction. LOW.

Pin at implementation: the materialize service must assert envelope insert
and delivery-effect enqueue use the same `Connection` object. If a future
caller accidentally splits them, the audit M2 orphan path returns
silently. A one-line precondition check in the service is appropriate;
not a TODO.

### S13. Unresolved recipient_key hash input

Proposal `.pipeline/proposal.md:416-419` uses
`recipient_key = "unresolved:<stable-selector-hash>"` for recipient-
resolution failures. "stable-selector-hash" is underspecified (also flagged
as audit `L2`, `plans/risk/slice-015-audit.md:87-97`). Shortcut risk is
that an implementation picks `hash(kind)` as the path of least resistance
and two different failing selectors with the same `kind` collide under the
unique index, silently dropping one skipped envelope. LOW because
SLICE-015 resolves only explicit-user selectors successfully (role
selectors defer out of scope and always skip), so real-world overlap is
narrow.

Pin at implementation: hash the full selector JSON (sorted keys), not
only `kind`. One line; do not defer with a TODO.

### S14. No backwards-compat shims, no deferred stubs

Checked against AGENTS.md §"No Backwards Compatibility" and §"No Deferred
Stubs":

- No transitional alias for `emit()` — extended in place
  (`.pipeline/proposal.md:730-751`).
- No feature flag gating materialization / delivery.
- No dual-write or deprecated column on `notification_events` — the table
  is unchanged; envelope state lives on a new table.
- `claim_status=None` is a forward-compatible default on a shared helper;
  existing callers keep current behavior via the default `'claimed'`
  literal.
- Migration is new tables only. `down_revision = "wu_012_trust"` is the
  current head. No backfill, no column mutations on shared tables, no
  renames. Downgrade drops the two new tables and the seeded grant
  cleanly (audit `L10`).
- Out-of-scope features (acknowledgements, digests, role resolution,
  thread delivery, recurring schedules, email/SMS, cross-guild
  federation, template registry) are listed in §2 Out of Scope
  (`.pipeline/proposal.md:73-87`) and §D14
  (`.pipeline/synthesis.md:188-196`), not stubbed. Rule rows persist
  `channel='thread'` and `discord_role` recipients exactly as submitted,
  but materialize as skipped envelopes with reason strings — a bounded
  design choice, not a TODO placeholder.

LOW.

### S15. Magic constants reuse shared scheduler defaults

- `LEASE_SECONDS = 300` and `DEFAULT_MAX_ATTEMPTS = 3` come from
  `services/api/app/services/scheduler.py:27-30`. Notifications reuse them
  for deferred-effect claim, per `deferred_effect_worker_tick(...)`
  (`services/api/app/services/deferred_effects.py:141-148`). Envelope
  `max_attempts = 3` default in the migration
  (`.pipeline/proposal.md:149`) matches.
- 25-char nonce truncation is a Discord API constraint
  (`.pipeline/research.md:12`), not a magic number.
- No subsystem-specific constants smuggled into the shared scheduler
  module.

LOW. Keep the delivery-path lease well below Discord's nonce window
(audit `L1`).

## Summary

| # | Area | Severity | Note |
|---|---|---|---|
| S1 | `emit()` extended, no parallel queue | LOW | |
| S2 | Hardcoded `notification-dispatcher` actor | LOW | Matches existing service-actor convention |
| S3 | Discord nonce 25-char token + local guard | LOW | Revision 1 fix: base32 truncated + `delivered_in_flight` |
| S4 | Claim helper generalized via `claim_status=None` | LOW | Substrate extension, no duplicate SQL |
| S5 | Strict `substitute()` + skipped-on-missing-key | LOW | Revision 1 fix: no `safe_substitute()` |
| S6 | Recipient resolution at materialize | LOW | No fake role resolver; `skipped` for unsupported kinds |
| S7 | Handler registration via `register_scheduler_handler` | LOW | |
| S8 | No duplicated claim entry paths; batch helper removed | LOW | Revision 1 fix |
| S9 | Rule CRUD `payload_allowlist` = `model_dump.keys()` | LOW | Repo convention |
| S10 | ON CONFLICT DO NOTHING + partial unique indexes | LOW | Real, DB-enforced |
| S11 | `destination_channel_id` resolved at materialize | LOW | Revision 1 fix |
| S12 | Envelope+delivery-effect share one transaction | LOW | Revision 1 fix; pin boundary at implementation |
| S13 | `unresolved:<selector-hash>` underspecified | LOW | Pin hash input (full selector JSON, sorted keys) |
| S14 | No compat shims, no deferred stubs | LOW | |
| S15 | Constants reuse scheduler defaults | LOW | Keep lease < Discord nonce window |

No MEDIUM / HIGH shortcut findings. Revision 1 already addressed the five
items that would otherwise have counted (nonce encoding, claim helper
fiction, silent `safe_substitute`, batch delivery duplicate path,
destination channel unplumbed).

### Implementation pins (one-liners, not blockers)

- S4: envelope handler uses `batch_size=1` with an `id = %s` ready predicate
  in `claim_due_rows(...)`; do not add an envelope-specific claim SQL.
- S12: add a precondition assertion in the materialize service that the
  envelope insert and the `notifications_deliver` enqueue run on the same
  `Connection`.
- S13: `unresolved:` key hashes the full selector JSON (sorted keys), not
  only `kind`.
- S15: keep `LEASE_SECONDS` in the delivery path well below Discord's
  nonce window (audit `L1`).

## Rating

**LOW.** Proposal is clear of shortcut-class concerns and ready for
implementation once the pin items above are noted in the WU-029A /
WU-029B commits.
