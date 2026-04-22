# SLICE-022 Research: Compliance Rule Evaluation With Evidence

Scope: Phase 1 research for `SLICE-022`, using the bound ticket, `AGENTS.md`, proposal/problem references, and the shipped trust, policy, chapter, notification, roster, read-model, and worker slices.

## 1. Existing compliance-adjacent tables

- There is no shipped compliance domain yet. A repo-wide search finds no `services/api/app/contracts/compliance*.py`, no `services/api/app/services/compliance*.py`, no `services/api/app/repositories/compliance.py`, and no compliance migrations. The only `ocr`-adjacent package under `services/api/app` is an empty infrastructure marker: `services/api/app/infrastructure/__init__.py`.
- The closest reusable persistence substrates are:
  - `policy_versions` for immutable versioned configuration content by `(policy_type, scope_kind, scope_id, version_number)`. See `migrations/versions/wu-005_policy_foundation.py`, `services/api/app/repositories/policies.py`, `services/api/app/services/policies.py`.
  - `roster_entries` and `roster_transitions` for member-in-chapter lifecycle and consequence routing. See `migrations/versions/wu-033_roster.py`, `services/api/app/contracts/roster.py`, `services/api/app/services/roster.py`.
  - `ticket_sla_triggers` for idempotent worker writes keyed by a unique business tuple plus `ON CONFLICT DO NOTHING`. See `migrations/versions/wu-037_ticket_sla_triggers.py`, `services/api/app/repositories/ticket_sla.py`, `services/api/app/services/ticket_sla.py`.
  - `deferred_effects` and `scheduled_jobs` for queued effects and scheduler dispatch. See `services/api/app/repositories/deferred_effects.py`, `services/api/app/services/scheduler.py`, `services/api/app/tasks/__init__.py`.
  - `notification_rules` and `notification_envelopes` for mutable rules plus downstream snapshot/version pinning. See `migrations/versions/wu-029a_notifications.py`, `services/api/app/services/notifications.py`.
  - `read_model_cursors` for cursor-based periodic projection work. See `migrations/versions/wu-031_read_models.py`, `services/api/app/services/read_models.py`.
- There is no `chapter_members` table. Chapter membership and member status in a chapter live on `roster_entries`. Chapter-level `probation` exists on `chapters.state`, while member-level review state is `roster_entries.status = 'under_review'`. See `services/api/app/contracts/chapters.py`, `services/api/app/contracts/roster.py`, `services/api/app/services/chapters.py`, `services/api/app/services/roster.py`.

## 2. ComplianceRule model + cadence shape

- The product docs and the slice ticket are aligned on chapter-scoped rules with consequences and versioning, but they do not use the same shape:
  - `product-strategy/proposal.md` describes `ComplianceRule` as `chapter_id`, `name`, `rule_type`, `parameters`, `consequence`, `active`, `season`, `version`.
  - `product-strategy/tickets/SLICE-022.md` narrows the slice contract toward `chapter_id`, `name`, cadence/evidence/consequence fields, and `version`.
- Existing versioning precedents split into two patterns:
  - Immutable configuration history: `policy_versions` with preview/confirm and version-number pinning. `services/api/app/services/policies.py` builds an aggregate id from `(policy_type, scope_kind, scope_id)` and appends immutable versions.
  - Mutable aggregate with OCC plus downstream pinned version/snapshot: `notification_rules` mutate in place with `version`, while `notification_envelopes` persist `rule_version` and `template_snapshot_json`.
- The roadmap is explicit that compliance-rule updates depend on the preview/confirm operating model but do not have to reuse the existing policy contract types. See `product-strategy/ai roadmap.md` under WU-039.
- No reusable cadence helper exists in the codebase:
  - `ticket_sla` models elapsed thresholds in seconds, not recurring calendar periods.
  - `scheduler.py` provides fixed worker intervals, not business-period computation.
  - `read_models.py` has staleness thresholds, also not recurring business cadence.
- Current evidence supports these research conclusions:
  - `ComplianceRule` is a greenfield aggregate.
  - Rule content should be historically interpretable, because both `proposal.md` and the slice ticket require evaluation history to remain meaningful after rule changes.
  - `rule_version` pinning on `ComplianceEvaluation` fits shipped precedent, but the exact storage shape is still a synthesis decision: immutable rule-version rows, mutable rule rows plus pinned snapshots, or both.
- Cadence-specific open shape from the ticket:
  - `cadence_kind: Literal["weekly","monthly","quarterly"]`
  - `cadence_params: dict`
  - `evaluation_window_days: int`
  - `evidence_requirements: list`
- The codebase does not constrain what `cadence_params` should look like. That is fully greenfield.

## 3. EvidenceSubmission + OCR interface

- `proposal.md` and the ticket agree on the core invariants:
  - Evidence provenance must be preserved.
  - OCR is an extraction aid, not a decision-maker.
  - Raw evidence must remain available after extraction and after officer correction.
  - Low-confidence extraction must surface to human review.
- The exact field names differ between artifacts:
  - `proposal.md` uses `evidence_type`, `raw_data`, `extracted_data`, `extraction_confidence`, `submitted_by`, `submitted_at`.
  - The SLICE-022 ticket uses `attachment_ref`, `raw_text`, `extracted_fields`, `extraction_status`, `extraction_confidence`, `submitted_by`, `version`.
- There is no attachment storage subsystem in the codebase:
  - no upload endpoint,
  - no blob-storage client,
  - no storage settings,
  - no non-empty OCR/provider adapter.
  The only relevant settings are `google_cloud_vision_key` and `gemini_api_key` in `services/api/app/core/settings.py`.
- This means `attachment_ref` as an opaque string is consistent with current repo reality. Nothing in the codebase today can ingest or persist uploaded binary data directly.
- OCR provider state:
  - Code: no implementation.
  - Product research: `product-strategy/engineering research.md` says `D6` locks Google Cloud Vision as primary OCR and Gemini as fallback.
  - Proposal: `product-strategy/proposal.md` describes OCR conceptually but does not bind the service interface shape.
- For SLICE-022 research, the repo supports a pluggable OCR boundary in principle because `app/infrastructure` exists as the designated external-client layer, but there is no actual provider contract yet.
- AC2 in the ticket matches shipped patterns elsewhere: create durable state first, then perform follow-on work. That is compatible with:
  - a two-step API (`POST /evidence`, then `POST /evidence/{id}/extract`),
  - persisted `pending`/`running`/`completed`/`failed` statuses,
  - either sync extraction or queued extraction.
- Existing worker/effect infrastructure does not force async extraction, but it does provide a clean substrate if extraction should be deferred later. See `services/api/app/repositories/deferred_effects.py`, `services/api/app/services/scheduler.py`.

## 4. Officer correction + OCC pattern

- The codebase standard OCC pattern is:
  - read aggregate,
  - expose `etag` from aggregate version,
  - require `If-Match` on mutation,
  - map stale writes to `412 Precondition Failed`.
  See `services/api/app/api/v1/endpoints/roster.py`, `services/api/app/api/v1/endpoints/trust/_shared.py`, `services/api/app/services/mutations.py`.
- `services/api/app/services/notifications.py`, `services/api/app/services/roster.py`, and `services/api/app/services/trust.py` all follow the same shared mutation substrate through `mutate_entity(...)`.
- For evidence correction specifically, the research-supported precedent is:
  - the evidence row should remain the mutable aggregate carrying the current extracted/corrected fields and `version`,
  - raw attachment/raw OCR text should remain durable and not be overwritten by correction,
  - stale correction attempts should use the same `If-Match`/etag contract already used by roster transitions.
- The current codebase has no separate “corrections history” pattern for this domain. If correction history is needed beyond current fields plus audit trail, that is a synthesis/design decision rather than an existing precedent.

## 5. ComplianceEvaluation + scheduled worker algorithm

- The proposal and ticket both place evaluation in a periodic worker, not a Discord interaction. Relevant shipped worker patterns:
  - `services/api/app/tasks/ticket_sla.py` is a thin task wrapper over service logic.
  - `services/api/app/tasks/permission_expiry.py` adds a service actor, root audit context, batch size, and OCC-conflict tolerance.
  - `services/api/app/services/scheduler.py` runs periodic worker ticks in-process and already wires archive, deferred effects, ticket SLA, read-model, and permission-expiry workers.
- The current worker registration/runtime pattern is:
  - add a task module under `services/api/app/tasks/`,
  - configure it in `services/api/app/tasks/__init__.py`,
  - let `SchedulerLoop` call it on a fixed cadence.
- Idempotency precedent for WU-041B is strongest in `ticket_sla_triggers`:
  - a business-key unique constraint,
  - repository insert with `ON CONFLICT DO NOTHING`,
  - reruns become no-ops for already-applied work.
  See `migrations/versions/wu-037_ticket_sla_triggers.py`, `services/api/app/repositories/ticket_sla.py`.
- Batch/idempotent sweep precedent is strongest in permission expiry:
  - service actor `permission-expirer`,
  - module-level batch constant,
  - tolerate OCC conflicts and retry next tick.
  See `migrations/versions/wu-038_permission_intent_expiry.py`, `services/api/app/tasks/permission_expiry.py`, `services/api/app/services/permissions.py`.
- Member iteration source:
  - There is no `chapter_members` relation.
  - The closest live chapter-membership surface is `roster_entries`.
  - `proposal.md` says compliance runs for each member in chapter roster with `status: active`.
  - That matches shipped roster semantics better than using chapter state or applications.
- Evaluation shape from artifacts:
  - `proposal.md` defines `member_id`, `chapter_id`, `rule_id`, `rule_version`, `period`, `evidence_ids`, `result`, `evaluated_at`, `consequence_applied`.
  - The ticket adds review-specific fields such as `review_status`, `reviewer_id`, and `review_reason`.
- The codebase has no existing period-calculation library, no evaluation table, and no member-evidence join logic. Those are greenfield.
- The slice ticket’s unique key `(member_id, rule_id, period_start, period_end)` matches shipped idempotent-worker precedent and is not contradicted by any existing schema.
- Shared code-structure precedent for the new worker favors module-level constants and small dispatch maps over inline string soup. Examples: `services/api/app/services/permissions.py`, `services/api/app/services/chapters.py`, `services/api/app/services/leadership_handoff_applications.py`, `services/api/app/contracts/authority.py`.

## 6. Consequence routing through roster

- AC4 says consequences must route through roster, and existing shipped semantics support that:
  - roster member statuses are `active`, `on_leave`, `under_review`, `removed`;
  - there is no roster status literally named `probation`.
  See `services/api/app/contracts/roster.py`, `migrations/versions/wu-033_roster.py`.
- Chapter `probation` is a chapter governance state, not a member consequence. See `services/api/app/contracts/chapters.py`, `services/api/app/services/chapters.py`.
- `proposal.md` says compliance consequences can place a member “under review.” That aligns directly with roster’s shipped `under_review` transition and does not require inventing a new roster state.
- Current roster mutation path is:
  - API endpoint parses `If-Match`, enforces authority, then calls
  - `app.services.roster.transition_roster_entry(...)`, which uses OCC and records a `roster_transitions` row.
- There is no helper today named `apply_probation(...)`, and there is no precedent for bypassing roster service logic with raw SQL when a subsystem wants a member state consequence.
- Research conclusion:
  - “review” maps naturally to a compliance evaluation awaiting officer action with no roster change.
  - “probation” in the ticket does not have a 1:1 shipped roster state; the nearest current member-level consequence surface is roster `under_review`.
  - Synthesis must decide whether ticket-language “probation” means “transition roster entry to `under_review` and notify” or requires a broader new roster/status model.

## 7. Migration plan

- Current Alembic head for this branch is `wu_038_permission_intent_expiry`. See `migrations/versions/wu-038_permission_intent_expiry.py`.
- There is no existing compliance schema to alter, so this domain is greenfield from the migration perspective.
- A chain aligned with the ticket/work-unit boundaries would start from `wu_038_permission_intent_expiry`:
  - `wu-039_compliance_rules`
  - `wu-040a_compliance_evidence`
  - `wu-041a_compliance_evaluations`
- Nothing in the current artifacts suggests a separate persistence object only for review actions; the roadmap and ticket both treat review as part of the `ComplianceEvaluation` aggregate. That argues for review fields living with evaluations unless synthesis decides otherwise.
- If OCR extraction becomes async in the first pass, there is still no obvious need for a separate migration just for scheduler plumbing, because the repo already has generic scheduler/deferred-effect tables.

## 8. Service actor grants

- Shipped precedent is to seed narrow global service-actor grants in migrations:
  - `roster-syncer` in `wu-033_roster.py`
  - `notification-dispatcher` in `wu-029a_notifications.py`
  - `read-model-projector` in `wu-031_read_models.py`
  - `sla-worker` in `wu-037_ticket_sla_triggers.py`
  - `permission-expirer` in `wu-038_permission_intent_expiry.py`
- Worker code then materializes a matching `ActorIdentity(actor_kind="service", actor_id=...)` and runs under that identity. See `services/api/app/tasks/permission_expiry.py`, `services/api/app/services/ticket_sla.py`.
- For SLICE-022, the codebase supports a `compliance-evaluator` service actor following this same pattern. The exact permission strings are still open because the compliance authority namespace does not exist yet.
- The minimum capability categories implied by the ticket are:
  - read rule/evidence/evaluation data,
  - read chapter roster membership,
  - write evaluations,
  - trigger roster-side consequences through the roster mutation path,
  - possibly emit notifications if consequence handling notifies officers directly.
- If OCR extraction is asynchronous, the same migration-seeded service-actor pattern is available for an `ocr-extractor`, but the repo does not force a second actor if extraction remains synchronous.

## 9. Prototyping questions

- OCR provider decision has a real conflict in the artifacts:
  - the ticket prompt suggests a pluggable interface with a stubbed/mock default for tests,
  - `product-strategy/engineering research.md` says provider choice is already locked to Google Cloud Vision primary plus Gemini fallback.
  Synthesis needs to decide whether SLICE-022 should ship only the interface/test seam now, or ship the first real provider adapter immediately.
- Attachment storage semantics are completely open in code:
  - no upload API,
  - no storage client,
  - no storage settings.
  `attachment_ref` as opaque URL/path is the only shape clearly supported by current reality.
- Cadence semantics are fully open:
  - weekly/monthly/quarterly can be calendar-boundary periods,
  - rolling windows,
  - or season-aware periods.
  No shipped helper constrains this.
- Evaluation period and evidence window semantics are also open:
  - whether evidence is keyed to the same `[period_start, period_end]`,
  - whether late submissions can count,
  - whether the worker evaluates only the current period or can backfill.
- Consequence semantics remain partially mismatched:
  - proposal language uses `notification_only`, `flag_for_review`, `auto_probation`,
  - ticket language uses `review` and `probation`,
  - shipped roster language uses `under_review`.
- Sync versus async extraction remains open:
  - sync is simpler and consistent with a direct “extract now” endpoint,
  - async has stronger precedent if OCR latency or provider retries matter, because deferred effects and scheduler plumbing already exist.

## 10. Open questions for synthesis

- Should compliance rules reuse the immutable `policy_versions` table directly, or use a dedicated compliance rule table plus immutable version/snapshot rows of their own?
- What is the canonical rule shape for this slice: the older `proposal.md` model (`rule_type`, `parameters`, `consequence`, `season`) or the ticket’s narrowed cadence/evidence/consequence contract?
- Is `rule_version` alone sufficient on `ComplianceEvaluation`, or does this slice also need a rule snapshot field the way notifications persist `template_snapshot_json`?
- Does ticket-language `probation` mean a new member-level state, or does it intentionally route to shipped roster `under_review` as the member consequence surface?
- Should evidence keep both `attachment_ref` and an `evidence_type`, since `proposal.md` distinguishes `game_api`, `screenshot`, and `manual_report`, while the ticket currently centers attachment/OCR fields?
- Is OCR extraction in scope as a real provider-backed implementation for SLICE-022, or only as a provider interface plus test seam with production wiring deferred?
- If extraction is asynchronous, should it use deferred effects, a dedicated scheduled job, or a direct scheduler tick pattern?
- How are weekly/monthly/quarterly periods defined exactly, and which timezone anchors them for a chapter?
- Does evaluation review support only `confirm` and `override`, or also `request_evidence` as described in the AI roadmap?
- What authority model should officer correction and evaluation review use: chapter-scoped compliance permissions, roster permissions, or a combination?

## Final summary

- The compliance subsystem is still greenfield in code; the only reusable pieces are the generic versioning, OCC, scheduler, notification, deferred-effect, and roster substrates.
- Rule versioning is clearly required by product docs and shipped precedent, but the storage shape is still open between `policy_versions`-style immutable history and domain-specific rule-version rows.
- OCR has no implementation today; the repo only exposes settings placeholders and an empty infrastructure layer, while engineering research says Google Vision primary and Gemini fallback are already strategically locked.
- Member-level consequences should route through roster semantics, and the shipped roster consequence surface is `under_review`, not a literal member `probation` state.
- The highest-value synthesis questions are rule-shape normalization, cadence/period semantics, attachment/OCR scope, and whether ticket-language `probation` maps to existing roster `under_review` or requires a broader model change.
