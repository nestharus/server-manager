# Activity/Audit Model — Synthesis (Research → Proposal)

## Purpose

Bridges the Phase 1 research (`plans/research/activity-audit-model.md`)
into actionable needs that the proposal must address. Each need traces
back to a research finding and forward to a proposal scope decision.

## Need 1 — Canonical action/state-change split

**Research finding**: Section 1 establishes that actions (attempted
operations) and state changes (accepted business facts) are semantically
distinct. Co-mingling them in one stream makes the stream poor at both
audit and locking.

**Need**: The proposal must define two append-only record types with
clear ownership boundaries — one for attempted operations, one for
accepted business facts — and specify which stream drives audit vs
concurrency.

## Need 2 — Activity-derived optimistic locking replaces row version

**Research finding**: Section 2 concludes that activity-derived
versioning decouples concurrency, history, and business state from
entity rows. The current `ChapterRead.version` / `ChapterUpdate.version`
pattern couples three concerns to the entity row.

**Need**: The proposal must define the replacement concurrency contract
using HTTP `ETag` / `If-Match` semantics, specify that row `version`
fields are removed, and declare this a clean break (no dual support).

## Need 3 — Split schema with projection/head helpers

**Research finding**: Section 3 evaluates three schema shapes and
recommends Option C (split `activity_actions` + `activity_state_changes`
plus `aggregate_heads` helper and projection tables) as the practical
end state.

**Need**: The proposal must define the physical storage layers
(`activity_actions`, `activity_state_changes`, `aggregate_heads`,
projection tables) and specify the transactional boundaries between
them.

## Need 4 — Head-hash validator model

**Research finding**: Section 4 recommends a per-aggregate opaque head
hash carried by the accepted state-change stream, not a sequence-only
validator. The hash-chain approach unifies concurrency validation with
append-only history.

**Need**: The proposal must specify the head-hash model (previous head +
canonical change → new head), declare canonical serialization as a
prerequisite, and define the `ETag` semantics (opaque to clients, only
advanced by accepted state changes).

## Need 5 — Actor attribution on actions, not on business rows

**Research finding**: Section 5 establishes that actor attribution
belongs on the action record (actor kind, actor id, request surface,
correlation id, request payload). Business rows should not carry actor
metadata.

**Need**: The proposal must define the action record schema with actor
attribution fields and explicitly exclude actor/request metadata from
business projection tables.

## Need 6 — Diff capture alongside reconstruction payload

**Research finding**: Section 5 distinguishes between the reconstruction
primitive (canonical accepted fact for replay) and the audit readability
primitive (field-level business diff for human display).

**Need**: The proposal must define both `payload_json` (reconstruction)
and `diff_json` (audit display) on accepted state changes, and specify
that diff-only events are insufficient for rebuild.

## Need 7 — Indexing strategy for three query classes

**Research finding**: Section 6 identifies three hot query patterns —
current business reads (projections), concurrency checks (aggregate
heads), and audit/history (action + state-change tables) — each
requiring specific indexes.

**Need**: The proposal must specify the minimum required indexes on
`activity_actions`, `activity_state_changes`, and `aggregate_heads`, and
state that projection tables keep business indexes only.

## Need 8 — Chapters API migration as clean break

**Research finding**: Section 7 documents the contract break — `version`
leaves DTOs, `ETag` replaces it, stale writes move from `409` to `412`,
`created_at` may leave the business DTO, and the write path changes from
in-place row mutation to append-action + append-state-change +
advance-head + refresh-projection.

**Need**: The proposal must declare the chapters API migration as a
single cutover with no backwards-compatibility shim, define the new
write path, and take an explicit position on whether `created_at`
remains a business field or becomes history metadata.

## Need 9 — Projection rebuild tooling is mandatory

**Research finding**: Section 6 warns that adopting the ledger without
adopting projections and rebuild tooling is the main operational mistake.
Append-only tables grow forever; projections must be transactionally
aligned or deterministically rebuildable.

**Need**: The proposal must acknowledge projection rebuild as a
first-class operational requirement and include it in the downstream
implications, even though implementation is out of scope for the
proposal itself.

## Summary

Nine needs extracted from the activity/audit model research. All nine
must be addressed by the proposal to ensure the research conclusions
translate into actionable architecture.

| # | Need | Research section |
|---|------|-----------------|
| 1 | Canonical action/state-change split | §1 |
| 2 | Activity-derived optimistic locking replaces row version | §2 |
| 3 | Split schema with projection/head helpers | §3 |
| 4 | Head-hash validator model | §4 |
| 5 | Actor attribution on actions only | §5 |
| 6 | Diff capture alongside reconstruction payload | §5 |
| 7 | Indexing strategy for three query classes | §6 |
| 8 | Chapters API migration as clean break | §7 |
| 9 | Projection rebuild tooling mandatory | §6 |
