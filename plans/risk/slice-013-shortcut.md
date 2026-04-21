# Shortcut risk assessment — SLICE-013 Chapter Provisioning

**Proposal:** `.pipeline/proposal.md` (Revision 3)
**Date:** 2026-04-20
**Overall verdict: LOW**

## Scope note

The prompt's Focus Areas are worded against a scheduler slice (lease duration,
poll interval, `max_attempts`, `batch_size`, handler registry source-of-truth,
scheduler-vs-deferred-effects duplicated claim query, lease lazy reclaim,
`services/api/app/tasks/__init__.py` empty module). None of that applies here.
SLICE-013 is chapter provisioning: WU-018 template versioning, WU-019 persisted
chapter lifecycle tables + transition endpoint, WU-020 Discord command handler.
It only *enqueues* one consequential deferred effect; no worker, no claim query,
no lease logic, no handler registry is added in this slice (proposal §2 anti-scope,
synthesis D12 lines 150-156). `services/api/app/tasks/__init__.py` is a
pre-existing SLICE-011 module re-exporting `register_scheduler_handler`
(four lines total) — not on SLICE-013's code boundary and not a stub.

I reframed the rubric onto what SLICE-013 actually ships and compared the current
Revision 3 proposal against AGENTS.md "No Backwards Compatibility" (lines 564-575),
"No Deferred Stubs" (lines 579-583), and "Scope Hygiene". The prior shortcut
assessment on this file rated MEDIUM against an earlier proposal revision that
parked the legacy in-memory chapter substrate alongside the new persisted one;
Revision 3 resolves that and the other named items, so the rating moves to LOW.

`.pipeline/research.md` does not exist in this worktree; the prototype research is
`prototyping/slice-013-chapter-provisioning/research.md` (proposal §1 source note).

## Verdict summary

The proposal preserves SLICE-003 template immutability through versioning rather
than a compatibility shim, uses the real `mutate_entity(connection=…)` seam for
in-transaction deferred-effect enqueue, pins a deterministic idempotency key that
includes `chapter_transition_id`, names the chapter row as the canonical
Discord-resource owner, and — new in Revision 3 — deletes the legacy in-memory
chapter substrate in place with post-implementation grep invariants, eliminating
the prior MEDIUM finding on parallel-parked legacy code.

No finding in the current revision rises to MEDIUM. One minor pre-implementation
cleanup item is flagged (a speculative-parameter hedge on `ChapterTemplateCreate`)
but does not block LOW.

## Findings

### F1 — Legacy chapter substrate replaced in place, not parked (resolved → LOW)

Prior shortcut assessment on this file (its F1, rated MEDIUM) flagged that the
earlier proposal revision parked these modules:

- `services/api/app/contracts/chapters.py` — `ChapterStatus` enum, integer
  `ChapterRead`/`ChapterCreate`/`ChapterUpdate` (current file lines 7-47).
- `services/api/app/services/chapters.py` — `ChapterService` over in-memory
  action/state stores, integer ids, `_heads: dict[int, int]`,
  `create_chapter`/`update_chapter`/`archive_chapter` (lines 54-186).
- `services/api/app/repositories/chapters.py` — `InMemoryChapterRepository`,
  `ChapterRecord(id: int, …)` (lines 25-102).
- `services/api/app/api/v1/endpoints/chapters.py` — `POST /api/v1/chapters`,
  `GET /{int}`, `PATCH /{int}`, `POST /{int}/archive` bound to the in-memory
  service.
- `services/api/app/core/factory.py:22-25, 37-52, 90-99` — wires
  `InMemoryChapterRepository` / `InMemoryActionStore` /
  `InMemoryStateChangeStore` / `ChapterService` into `app.state.chapter_service`.

Revision 3 deletes all of this in the same slice. Proposal.md:30 and §5 lines
455-457 state plainly: "SLICE-013 deletes/replaces the legacy in-memory
`ChapterService` / `InMemoryChapterRepository` / integer-id contracts / `/archive`
route as part of this slice; no parallel parked code." §3 WU-019 names each
artifact to delete (proposal.md:192-194, 240-254, 322-324, 326-329): `ChapterStatus`,
integer-id shapes, `ChapterRecord`, update/archive request types, compatibility
aliases, `_heads`, the action-store/state-change-store constructor wiring, and
the `/archive` route. The endpoints-module path is pinned — the single file
`services/api/app/api/v1/endpoints/chapters.py` is replaced, not shadowed by a
new `chapters/lifecycle.py` sibling (proposal.md:304).

Post-implementation grep invariants are written into the test plan
(proposal.md:353-358):

- `InMemoryChapterRepository` → 0 occurrences
- `ChapterStatus` → 0 occurrences
- `class ChapterRecord` → 0 occurrences
- `/archive` route → 0 occurrences under `/api/v1/chapters`
- integer `chapter_id` path/contract declarations → 0 occurrences

Against AGENTS.md §"No Backwards Compatibility" (lines 564-575) — "Find all
usages / Update all call sites / Delete old code / Run tests / No fallbacks" —
this matches the rule. No deprecated alias, no feature flag, no transitional
dual-routing. The prior MEDIUM is resolved.

### F2 — `discord_resources` dual-write: canonical owner named, retry worker
contract pinned (LOW)

D6 stores `partial_resources` in the deferred-effect payload; D7 names
`chapters.discord_resources` canonical. The prior shortcut F2 and the prototype
findings (`findings.md:57-61, 188`) both flagged silent-drift risk.

Revision 3 addresses both halves:

- Proposal §4 Tradeoffs (proposal.md:441): "the chapter row remains canonical
  per D7."
- Proposal §6 Resolved decisions (proposal.md:472): "Future
  `chapter_provisioning_retry` worker MUST re-read `chapters.discord_resources`
  before acting, not trust the effect payload snapshot. Chapter row is
  canonical (D7)."

The payload retains a snapshot for operator visibility and effect-row
idempotency, but the authoritative read is pinned to the chapter row. When the
retry worker slice lands, it inherits this contract rather than discovering
drift late.

### F3 — Active-transition gate is service-layer, which is correct layering (LOW)

`_verify_provisioning_complete(chapter)` is an IF-raise inside
`transition_chapter(…)` (proposal.md:276-295). A rogue direct SQL
`UPDATE chapters SET state='active'` would bypass it — but that's the same trust
model used by every aggregate in the repo (policies, authority, templates,
audit), because a DB-trigger completeness rule would have to unpack
`template_snapshot` JSONB shape (role names, channel names) and couple the
schema to that shape forever. The proposal does not claim structural enforcement
it does not implement. The column-level `CHECK (state IN (...))` bounds the
value space; the transition matrix itself is service-side. Consistent with
substrate, not a shortcut.

### F4 — `chapter_transitions` as same-transaction denormalized projection (LOW)

`activity_actions`/`activity_state_changes` remain authoritative;
`chapter_transitions` is a projection written inside the same
`mutate_entity()` transaction via `mutate_projection(connection)`
(proposal.md:302, 406). Proposal is explicit: "If an inconsistency is ever
discovered, `activity_actions` wins." Clear ownership boundary, single
transaction, not a parallel ledger. Both live or both rollback.

### F5 — Deferred-effect enqueue is atomic with the state change (clean)

`mutate_entity` accepts a caller-supplied connection
(`services/api/app/services/mutations.py:70, 191-197`). `enqueue_effect` accepts
a connection as its first positional argument
(`services/api/app/repositories/deferred_effects.py:31-37`). Proposal §3 WU-019
pins the failed-transition branch to the repository-level
`enqueue_effect(connection=…)` on the *same* connection the projection callback
is running on (proposal.md:300-301), explicitly rejecting the service-wrapper
that would open its own connection. Failed chapter state + effect row are one
transaction; rollback rolls both back. Prototype proof at
`findings.md:27-35` agrees.

### F6 — Template PATCH race: lock + unique-index defense-in-depth (clean)

Proposal §3 WU-018 locks the source row, then `SELECT … FOR UPDATE` across the
family to compute `max(version)`, then inserts at `current+1` (proposal.md:107-111).
`uq_chapter_templates__family_version(template_family_id, version)` is the DB
backstop; `IntegrityError` on that index is explicitly translated to
`StaleTemplateVersionError → 412`, not leaked as `500`. A dedicated test
covers "two PATCHes racing on the same `expected_current_version` produce one
accepted version and one 412, never a leaked `IntegrityError`/`500`"
(proposal.md:135). No optimistic-insert-and-hope shortcut.

### F7 — Idempotency key is deterministic and per-transition (clean)

Key: `chapter_provision_retry:{chapter_id}:{chapter_transition_id}`
(proposal.md:301, 347, 477). `deferred_effects.idempotency_key` is UNIQUE;
`enqueue_effect` runs `ON CONFLICT (idempotency_key) DO NOTHING RETURNING …`
and, if nothing returns, re-queries to return the canonical existing row
(`services/api/app/repositories/deferred_effects.py:40-102`). The collision
behavior is "return the existing row," not "silently drop the enqueue" — the
caller always gets an effect to reason over. Each
`provisioning_failed → provisioning` retry mints a new
`chapter_transitions.id`, so a fresh key is produced per attempt, which is the
property the sibling audit (F3) also confirmed.

### F8 — Correlation context is not silently `uuid4()`-filled (clean)

`services/api/app/services/mutations.py:74-78` raises
`MissingCorrelationContextError` if `request.correlation_id is None` AND no
ambient audit context exists. No fresh `uuid4()` fallback. SLICE-013 reuses
`mutate_entity` end-to-end, inheriting this contract. The Discord handler
propagates correlation/causation headers through SLICE-006's `ApiClient`
(which the audit sibling validated in F12 of `slice-013-audit.md`). No
"helpful uuid4 fallback" is introduced in this slice.

### F9 — `services/api/app/tasks/__init__.py` is not a stub (clean)

The file has four lines: `from app.services.scheduler import register_scheduler_handler`
+ `__all__`. It is a completed re-export from SLICE-011 substrate, not on
SLICE-013's code boundary, not empty, and not touched by this slice. The
prompt's framing of it as a "listed in WU-008B code boundary" empty module is
a copy-paste from a different slice's prompt.

### F10 — Scheduler substrate concerns are N/A to SLICE-013 (clean)

The prompt's lease duration (5 min), poll interval (5 sec), `max_attempts`,
`batch_size`, handler-registry-in-DB question, `mark_failed`/`mark_completed`
ordering, lease lazy reclaim, and scheduler-vs-deferred_effects claim-query
duplication are all SLICE-004 / SLICE-011 substrate. SLICE-013 consumes the
substrate through `enqueue_effect(connection=…)` only and does not re-implement
or parameterize any of the above. The scheduler and deferred_effects
repositories share the `claim_due_rows(...)` helper in
`services/api/app/repositories/_claim.py`, so the claim-query duplication
question is already answered in `main`. D12 explicitly defers the
`chapter_provisioning_retry` worker to a follow-up slice — that's a named,
scoped deferral (permitted by AGENTS.md "No Deferred Stubs"), not a TODO.

### F11 — `required_bot_permissions` is a protocol constant, not a tunable (clean)

`required_bot_permissions: tuple[str, ...] = ("MANAGE_ROLES", "MANAGE_CHANNELS", "VIEW_CHANNEL")`
on `DiscordSettingsRead` (proposal.md:410-412) with "No new env var." These are
Discord protocol requirements, not a runtime tuning parameter that should have
been configurable. Compile-time constant is correct.

### F12 — `discord-provisioner` service actor grants are seeded via migration,
not fixture (clean)

The prior audit F6 was MEDIUM until Revision 3 moved the grant into the
WU-019 migration. Proposal.md:170-190 writes a global, non-expiring
`authority_grants` row via SQL, targeting the actual schema columns
(`grantee_id` plus JSONB `permissions` set, not hypothetical per-permission
rows) with a dedicated migration-level test
`test_discord_provisioner_service_actor_has_chapter_grants_after_migration`
(proposal.md:190, 350). A durable, audit-trail-visible insert — not a test-only
fixture that would silently diverge from production. No shortcut.

### F13 — One pre-implementation hedge to tighten: `ChapterTemplateCreate.template_family_id` (LOW, one-line fix)

Proposal.md:83 reads: "Add optional `template_family_id: UUID | None = None`
only if needed for internal creation helpers; public POST should not allow
caller-provided family ids unless explicitly required later."

The "only if needed … unless explicitly required later" phrasing borders on
speculative-for-future. AGENTS.md (and this session's "Don't design for
hypothetical future requirements") prefers a decision ahead of implementation.
Pick one:

- **Preferred (a):** Do not add `template_family_id` to `ChapterTemplateCreate`
  in SLICE-013 at all. It isn't required by AC1, AC2, AC3, or AC4; PATCH
  resolves the family id from the source template row inside the service. The
  POST path always mints `template_family_id = new_template_id, version = 1`,
  so no caller-supplied field is needed.
- (b) Add it with explicit public-surface rejection (e.g. router layer strips
  it) and name a concrete SLICE-013 internal consumer.

LOW — a contract clarification, not a shortcut that undermines substrate. Worth
calling out so the implementer lands on (a) or (b) rather than shipping the
"only if needed" hedge as code.

## Summary table

| Focus area | Severity | Notes |
| --- | --- | --- |
| Compatibility shims / parallel legacy code | LOW | F1 — legacy `ChapterService`/`InMemoryChapterRepository`/integer-id contracts/`/archive` route deleted in place; grep invariants installed; endpoints path pinned. Prior MEDIUM resolved in Revision 3. |
| Duplicated logic | LOW | F4 — `chapter_transitions` same-transaction projection with `activity_actions` pinned authoritative. F10 — scheduler/deferred_effects share `claim_due_rows` helper (pre-existing substrate). |
| Hardcoded values | LOW | F11 — `required_bot_permissions` is a protocol constant. Lease/poll/batch/max_attempts are SLICE-004 substrate (N/A). |
| Source-vs-artifact confusion | LOW | F2 — `discord_resources` dual-write with chapter row pinned canonical and retry-worker re-read contract in §6. Handler registry is Python-only (no DB source-of-truth). |
| Symptom masking | LOW | F3 (gate), F5 (atomic enqueue), F7 (ON CONFLICT returns existing row), F8 (no silent uuid4 fallback). Discord handler failure path posts visible `provisioning_failed` transition and ephemeral error. |
| Deferred stubs | LOW | F9 — `tasks/__init__.py` is a completed re-export. F10 — `chapter_provisioning_retry` worker deferral is named and scoped per D12. F13 — one speculative-parameter hedge to tighten before implementation. |
| Fake transactions | LOW | F5 — `mutate_entity(connection=…)` + `enqueue_effect(connection=…)` on the same connection; projection + state change + effect enqueue are one transaction. |
| Precondition gate shortcut | LOW | F3 — service-layer gate, single mutation path, consistent with substrate trust model. |
| Idempotency key shortcut | LOW | F7 — deterministic per-transition key, ON CONFLICT returns existing row, `IntegrityError` on template family translated to 412 not 500. |
| Template versioning | CLEAN | F6 — lock + unique-index; PATCH creates new row; SLICE-003 immutability test revised additively, not broken. |
| Discord service-actor grants | CLEAN | F12 — migration INSERT + migration-level test, not a fixture hack. |
| Scheduler lease/poll/claim concerns | N/A | F10 — SLICE-004 substrate, not SLICE-013. |
| Pre-implementation cleanup | LOW (F13 one-liner) | Trim `ChapterTemplateCreate.template_family_id` "only if needed" hedge to option (a) or (b). |
| **Overall** | **LOW** | No shortcut undermines substrate; one-line contract hedge to clarify before code is written. |

## What LOW requires (all met, with one pre-implementation cleanup flagged)

1. **Replace the legacy chapter substrate inside SLICE-013, do not park it.**
   **Met** (proposal.md:30, 192-194, 240-254, 322-324, 326-329, 353-358, 455-457).
   `InMemoryChapterRepository`, `ChapterRecord`, `ChapterStatus`, integer-id
   shapes, `/archive` route, `_heads`, action-store/state-change-store
   wiring — all scheduled for deletion inside this slice, with grep invariants.

2. **Name the `chapter_provisioning_retry` worker contract's source of truth.**
   **Met** (proposal.md:472): "Future `chapter_provisioning_retry` worker MUST
   re-read `chapters.discord_resources` before acting, not trust the effect
   payload snapshot. Chapter row is canonical (D7)."

3. **Pin the endpoints module path.** **Met** (proposal.md:304):
   `services/api/app/api/v1/endpoints/chapters.py` is the single replacement
   file. No `chapters/lifecycle.py` sibling; no dual-routing.

4. **Atomic composition through the existing `mutate_entity(connection=…)` seam,
   not a parallel transaction.** **Met** (proposal.md:300-301; mutations.py:58-71,
   94-185, 191-197; deferred_effects.py:31-102).

5. **Typed errors, not silent skips, on every stale / invalid / missing path;
   race `IntegrityError` translated to 412 not 500.** **Met**
   (proposal.md:107-111, 135, 236, 273, 282-295, 317, 321; deferred_effects.py:40-102).

6. **Deterministic idempotency key that mints fresh on genuine retry and
   no-ops on duplicate.** **Met** (proposal.md:301, 347, 477).

7. **Migration: nullable → backfill → NOT NULL, plus required extensions
   enabled.** **Met** (proposal.md:61-77).

8. **Service-actor grants seeded by a migration (audit-visible) rather than a
   test fixture.** **Met** (proposal.md:170-190, 350).

9. **No new deferred stubs or speculative "for later" parameters introduced.**
   **Mostly met** — one pre-implementation cleanup item (F13):
   trim `ChapterTemplateCreate.template_family_id: UUID | None = None only if needed …`
   (proposal.md:83) to a concrete decision before code is written. Preferred
   resolution: drop the field entirely in SLICE-013 (AC1-AC4 do not require it;
   POST always mints a new family id; PATCH resolves family id from the source
   row server-side).

With F13's one-line contract tightening, the proposal is shortcut-clean. The
architectural core — template versioning with family lineage, copy-on-instantiate
snapshot, text-id aggregate, single-transaction transition + same-connection
deferred-effect enqueue, deterministic per-transition idempotency key,
migration-seeded service-actor grants, in-place legacy substrate deletion with
grep invariants — is sound and free of substrate-undermining shortcuts.
