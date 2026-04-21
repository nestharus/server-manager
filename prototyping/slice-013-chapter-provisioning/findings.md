# Prototype Findings: slice-013-chapter-provisioning

## Questions answered

### Q1: Discord provisioning workflow
- **Status:** Partially answered.
- **Finding:** The minimum Discord surface needed is `Guild.create_category`, `Guild.create_role`, and `Guild.create_text_channel(..., overwrites=...)`, plus the `Forbidden`/`HTTPException`/`TypeError` exception classes. One handler can walk this sequence, accumulate created resource IDs, and return a typed `ProvisioningResult` carrying `created_resources` and `cleanup_required` on failure. Partial failure is recoverable if — and only if — every created resource ID is captured **before** the next call is attempted (append-as-you-go, not on success).
- **Evidence:** `prototype/discord_provisioning.py` runs the success path and an injected second-role failure; the failing case emits the first role's ID in `cleanup_required`. Research cross-checks the method signatures against `discordpy.readthedocs.io` v2.3.2.
- **Agreement:** Agree with prototype's conclusion that the flow fits inside the existing `InteractionRegistry` + `ApiClient` seam.
- **Caveats:**
  - The prototype uses a hand-rolled `MockDiscordHTTPException`, not real `discord.Forbidden`/`discord.HTTPException`. The real exception types carry `.status`, `.code`, and `.text` — distinguishing a retriable 5xx from a permanent 403 requires reading those fields. The prototype does not prove we can map them correctly.
  - Only text channels were exercised. Voice channels, threads, and `Guild.edit_role_positions(...)` for ordering were not exercised, yet the template includes `role_structure.ordinal` and permission intents keyed by `channel_name` (including voice-style defaults in existing code).
  - The prototype did not exercise the post-creation `set_permissions()` fallback, which is the only way to repair an overwrite that Discord rejected at creation time.
- **Magnitude implication:** As expected. Discord surface is small in happy-path, larger once real exception mapping + role ordering + voice channels land.

### Q2: Lifecycle + optimistic locking
- **Status:** Partially answered.
- **Finding:** A 5-state machine fits the slice: `proposed`, `provisioning`, `active`, `provisioning_failed`, `archived`. A typed `InvalidChapterTransitionError` rejects invalid paths *before* any write. Transition shape (one version increment per accepted transition) is demonstrated.
- **Evidence:** `prototype/lifecycle_state_machine.py` — transition matrix, valid path, retry path, invalid path.
- **Agreement:** Agree with the state set and transition matrix as a starting point.
- **Caveats:**
  - The prototype increments an in-memory `version`; it does **not** integrate with the real `mutate_entity()` OCC or with `aggregate_heads.current_seq`. The claim "one version increment per accepted transition" is inferred from shape, not measured end-to-end.
  - The ticket's stated state set is only `proposed -> provisioning -> active`. The prototype adds `provisioning_failed` and `archived` without a product decision. `archived` in particular is not in slice scope per "Known challenges" on the ticket — the prototype flagged `proposed -> archived` as an operator escape hatch but this is a product question.
  - Transition matrix does not yet distinguish who can cause each transition (operator vs worker vs Discord handler). Authority checks are not prototyped.
- **Magnitude implication:** As expected for the matrix; slightly larger once the `mutate_entity()` wiring, authority checks, and `ChapterTransition` audit row land.

### Q3: Failed provisioning deferred effect
- **Status:** Answered.
- **Finding:** One accepted mutation can atomically degrade chapter state and insert one consequential deferred-effect row, provided the callback uses the repository-level insert on the passed-in connection (not the service-level wrapper that opens its own connection). A rollback after enqueue rolls both back.
- **Evidence:** `prototype/failed_provision_deferred_effect.py` — `show_successful_atomic_failure_write()` and `show_rollback_proof()`.
- **Agreement:** Agree that the existing `mutate_entity(connection=...)` seam is sufficient and no second concurrency mechanism is required.
- **Caveats:**
  - In-memory transaction, not Postgres. Real behavior under `FOR UPDATE` contention on `aggregate_heads` plus a `deferred_effects` insert is not measured. This is shape-only.
  - The prototype uses one idempotency key shape `chapter:{id}:provisioning-cleanup:v{version}`. Retry-key semantics (per-attempt vs per-chapter-version) is flagged as open.
- **Magnitude implication:** Smaller than feared — no new primitive needed.

### Q4: Template instantiation model
- **Status:** Answered.
- **Finding:** Copy-on-instantiate is required. A live `template_id` reference alone would let a later template edit retroactively change a chapter's operational configuration, which breaks replay/reconciliation. `template_id` should be retained as provenance alongside the snapshot.
- **Evidence:** `prototype/template_instantiation.py` — template edit after provisioning; chapter snapshot keeps original channel count; `template_id` preserved.
- **Agreement:** Agree.
- **Caveats:** The snapshot is a deep copy of `channel_structure`, `role_structure`, and `default_permission_intents` as JSON. Whether this snapshot also needs the template's `version` at instantiation time is not exercised and is useful provenance.
- **Magnitude implication:** As expected — copy is mechanically trivial; the size lives in deciding where to store it (see Q5).

### Q5: Snapshot storage location
- **Status:** Partially answered (blocked on product decision).
- **Finding:** The snapshot works mechanically inside `Chapter.configuration`, but doing so violates the proposal boundary that reserves `Chapter.configuration` for non-operational metadata. The governance-clean alternatives are (a) a dedicated `chapter_template_snapshot` field on the aggregate, or (b) a separate `chapter_provisioning_plans` child table keyed by chapter + attempt.
- **Evidence:** `prototype/template_instantiation.py` (mechanics), `research.md` constraint section (governance boundary).
- **Agreement:** Agree that this is a governance finding, not a Python limitation.
- **Caveats:** The prototype did not implement alternative (a) or (b). Either is untested.
- **Magnitude implication:** Larger than "just use `configuration`" by one aggregate-field migration and one contract.

### Q6: Idempotent retry anchor
- **Status:** Partially answered.
- **Finding:** Name-only duplicate detection is not safe. The deferred-effect payload plus chapter-aggregate `partial_resources` list together provide a durable anchor for retry and cleanup; both paths store the same resource IDs. A canonical owner must be chosen (chapter aggregate vs deferred-effect payload vs new `chapter_provisioning_attempts` child table).
- **Evidence:** `prototype/failed_provision_deferred_effect.py` — `partial_resources` persisted in both chapter record and effect payload.
- **Agreement:** Agree that some durable anchor is required.
- **Caveats:**
  - Two sources of truth (chapter.partial_resources and effect payload) can drift. The prototype does not choose an owner, it just shows both can hold the data.
  - The "discover what Discord already has" problem (re-running after the API row is lost) is not exercised. If the deferred-effect row and aggregate both get corrupt, only Discord itself knows what exists. Name-based reconciliation may still be needed as a last resort.
- **Magnitude implication:** Larger than expected by a canonical-owner decision and possibly a child table.

---

## Refined magnitude estimates

**Slices:** `SLICE-013` (WU-018, WU-019, WU-020)
**Prior magnitude in roadmap:** `VS-005 -> L-XL (leans L)` per ticket.
**Refined magnitude after prototype:** **Substantial, leans toward the upper end of L (close to L/XL boundary).**

**Reasoning:**
- Core Discord provisioning sequence and in-transaction deferred-effect enqueue both fit existing seams (compresses the estimate).
- Three items push the estimate up:
  1. Template mutability contradiction (SLICE-003 D9 "immutable" vs SLICE-013 AC1 "PATCH with 412") requires a real product/proposal reconciliation plus a template-versioning design, not just a PATCH endpoint.
  2. The `Chapter.configuration` governance conflict forces either a proposal revision or a new aggregate field/child table — a schema + contract change that is real work.
  3. Partial-resource ownership, idempotency-key lifecycle, and real `discord.py` exception mapping (retriable vs permanent) are each non-trivial and were only shape-proven by the prototype.
- On balance the slice is still L in engineering hours, but enough governance and design surface is unresolved that a confident L claim is not supportable yet. Call it "L pending product decisions, XL if any of the three push into scope."

---

## Recommendations for implementation proposal

### 1. Chapter state machine

Recommended states: `proposed`, `provisioning`, `active`, `provisioning_failed`, `archived`.

Recommended transitions:
- `proposed -> provisioning` (operator-initiated provision)
- `proposed -> archived` (operator escape hatch before any Discord work — needs product sign-off)
- `provisioning -> active` (provisioning handler reports success)
- `provisioning -> provisioning_failed` (provisioning handler reports typed failure)
- `provisioning_failed -> provisioning` (operator-initiated retry)
- `provisioning_failed -> archived` (operator abandon, *after* cleanup effect is at least enqueued)
- `active -> archived` (likely out of slice scope — defer to archive slice)

Invariants: exactly one version increment per accepted transition (via `mutate_entity()`); terminal state `archived` has an empty successor set; typed `InvalidChapterTransitionError` must fire *before* any write.

Open product decisions: whether `proposed -> archived` is allowed in this slice; whether `active -> archived` is in or out of scope (ticket "Known challenges" suggests out).

### 2. Template instantiation strategy

**Copy-on-instantiate**, not live reference. At `POST /api/v1/chapters`:
- Deep-copy `channel_structure`, `role_structure`, `default_permission_intents`.
- Store alongside the snapshot: `template_id`, `template_version_at_snapshot`, `instantiated_at`.
- Retain `template_id` as pure provenance; later template edits must not mutate provisioned chapters.

Storage location (pick **one**, blocked on proposal clarification):
- **Preferred:** dedicated `Chapter.provisioning_plan` (JSONB) field on the aggregate. Keeps everything on the chapter row, respects `configuration`'s documented governance boundary, and supports retry reconciliation with a single `SELECT`.
- **Alternative:** `chapter_provisioning_plans` child table keyed by `(chapter_id, attempt_id)`. Useful if per-retry plans need history.
- **Rejected:** store inside `Chapter.configuration`. Violates proposal governance boundary; prototype proved mechanics but flagged as out-of-bounds.

### 3. Discord provisioning sequencing + idempotency

Recommended order (one step at a time, append-as-you-go capture):
1. Create category (persist `category_id` immediately on return).
2. Create each role in `role_structure` ordered by `ordinal` (persist each `role_id` immediately on return).
3. Call `Guild.edit_role_positions(...)` once to lock ordering.
4. Create each channel with `overwrites=` built from `default_permission_intents` resolved against the freshly created roles (persist each `channel_id` immediately on return).
5. Any post-creation overwrite repair via `set_permissions(...)` if needed.
6. `POST /api/v1/chapters/{chapter_id}/transitions` with `to_state=active` and the collected resource IDs as the transition payload.

Idempotency:
- Every created resource ID is captured to `partial_resources` *before* the next call attempt.
- On retry, the handler reads the persisted `partial_resources` / provisioning plan and **skips any kind+slug pair that already has an ID**. Remaining steps are attempted fresh.
- Name collision is not safe as a primary anchor; use persisted IDs. Name matching is only a last-resort reconciliation aid.
- Per-attempt idempotency key recommended over per-chapter (see §4).

### 4. Deferred effect payload + retry semantics

**Subsystem/effect type:**
- `subsystem = "discord"`
- `effect_type = "chapter_provisioning_cleanup"`

**Consequence model:** `consequence_level = "consequential"`, `precondition_state = "unchecked"` at enqueue time. Worker does not execute until an operator (or an automated validator) marks it `valid`.

**Idempotency key:** `chapter:{chapter_id}:provisioning-cleanup:attempt-{attempt_id}` — per-attempt, not per-chapter-version, so retries produce a fresh effect tied to a fresh attempt. (Open question surfaced by prototype.)

**Payload shape (minimum):**
```
{
  "chapter_id": "...",
  "attempt_id": "...",
  "partial_resources": [ {"kind": "...", "id": ..., "name": "..."}, ... ],
  "failed_step": "create_role",
  "discord_error": { "class": "HTTPException", "status": 500, "code": 0, "text": "..." }
}
```

**Retry semantics:**
- Effect worker retries until `max_attempts`, then terminates at `status='failed'` and requires operator intervention — reuse existing deferred-effect behavior; no new policy.
- Retrying *provisioning* itself is a separate chapter lifecycle transition (`provisioning_failed -> provisioning`) and must read the persisted plan + partial_resources before re-contacting Discord.
- Cleanup effect and retry provisioning are two different operator actions. The slice should make that distinction explicit in both API docs and handler contracts.

### 5. Template update path resolution (SLICE-003 D9 vs SLICE-013 AC1)

This is a real contradiction:
- `SLICE-003` D9 / `test_chapter_template_foundation.py` asserts no update surface — templates are immutable.
- `SLICE-013` AC1 requires `PATCH /api/v1/chapter-templates/{template_id}` with 412 on stale write.

Recommended resolution (**template versioning**):
- Keep each `chapter_templates` row immutable in-place per SLICE-003.
- Model the "PATCH" in the ticket as **new template version** semantics: the PATCH endpoint accepts the template identity and the expected current `version`, and either (a) mutates an operator-visible "current version" pointer while retaining prior versions, or (b) inserts a new row sharing a `template_family_id` with monotonically increasing `version`.
- Snapshots taken at chapter provisioning (§2) already preserve the exact version used, so mutability of "current version" does not break provisioned chapters.
- 412 behavior maps cleanly to `mutate_entity()` stale-write rejection on the pointer row.

If product refuses versioning, the only honest options are to revise SLICE-003 D9 explicitly or descope AC1. Escalate before writing migration code.

### 6. Discord bot permissions required (expanded surface)

Required guild permissions for the bot role to complete the sequence in §3:
- `Manage Channels` (create category, create text/voice channels, set channel overwrites).
- `Manage Roles` (create roles, edit role positions, set per-role channel overwrites). Bot's own role must be **above** any role it assigns overwrites for.
- `View Channels` (implicit — needed to operate inside the guild).
- `Send Messages` (to confirm results in the operator channel per existing handler pattern).

Additional when voice channels or threads enter scope (out-of-slice now, likely in-scope later):
- `Connect`, `Speak` on voice categories for overwrite testing.
- `Create Public Threads` / `Manage Threads` if templates ever include threads.

Runtime check: at provision start the handler should read `guild.me.guild_permissions` and fail fast with a typed `ChapterProvisioningPreconditionError` if `manage_roles` or `manage_channels` is missing — cheaper than partial provisioning + cleanup.

---

## New risks surfaced

- **Real `discord.py` exception mapping was not exercised.** The prototype used a synthetic exception. Distinguishing retriable 5xx, 429 rate limits, and permanent 403 is required for a non-naive retry policy; that mapping is a non-trivial design surface in its own right.
- **`Chapter.configuration` governance conflict.** The prototype exposed it but did not resolve it. Shipping the snapshot in `configuration` silently repurposes a boundary the proposal documents as non-operational.
- **Dual source of truth for partial resources.** Storing `partial_resources` on both the chapter aggregate and the deferred-effect payload can drift. A canonical owner is not chosen.
- **Role-position ordering was not prototyped.** The role structure has `ordinal`, but `Guild.edit_role_positions(...)` and its failure modes were not exercised. Ordering failures mid-provisioning are a separate partial-state case.
- **Bot-role-hierarchy precondition.** The bot must be ranked above every role it assigns permissions to. Not a prototype artifact — a latent runtime failure mode.
- **Idempotency-key lifecycle is undefined.** Reusing the same key across retries is a product decision with observable consequences for effect-row history and operator UX.
- **`ChapterTransition` audit row not modeled.** The ticket lists it as a schema object but the prototype does not exercise it; it will compete with `mutate_entity()` state-change logging if not designed carefully.
- **Proposal-vs-slice contradiction on template mutability is still live.** Prototype flagged it, did not resolve it. Treat as early-exit trigger if unresolved before implementation.

---

## Remaining unknowns

- Who owns `partial_resources` canonically: chapter aggregate, deferred-effect payload, or a new `chapter_provisioning_attempts` table?
- Can `provisioning_failed -> archived` be chosen by an operator while a cleanup effect is still `precondition_state=unchecked`, or must the archive transition block until cleanup is `valid` / `completed`?
- Per-attempt vs per-version idempotency keys for retries.
- Real `discord.py` exception surface mapping (retriable vs permanent vs rate-limited) and how that maps onto `precondition_state`.
- Whether `template_version_at_snapshot` is required or whether `template_id + instantiated_at` is enough.
- Whether voice channels / threads / role ordering stay out of scope for this slice (ticket implies yes; the template structure implies eventually no).
- How `ChapterTransition` audit rows relate to `aggregate_heads.current_seq` and `mutate_entity()` state-change logging — specifically whether it is a view over state-changes or a separate table.
- Concrete resolution of SLICE-003 D9 vs SLICE-013 AC1: versioning, proposal revision, or descope.

---

## Recommendation

**Commission a short follow-up (product + architecture, not more code) before implementation**, specifically to:

1. Resolve the template mutability contradiction (pick template-versioning, proposal revision, or AC1 descope).
2. Decide the snapshot storage location (dedicated `provisioning_plan` field vs child table vs revised `configuration` boundary).
3. Name the canonical owner of `partial_resources` and the idempotency-key lifecycle.

With those three decisions settled, the slice is implementable at a confident L. Without them, starting implementation risks either silent proposal drift or a mid-slice schema rewrite.

The Discord workflow, lifecycle matrix, and atomic deferred-effect enqueue are sound and can be proposed as-is.
