# SLICE-022 Phase 2 Synthesis: Binding Decisions (Compliance Evaluation Loop)

These decisions are binding for the SLICE-022 proposal, hookpoint research,
risk, test, and implementation phases. The proposal may choose mechanics
inside these boundaries, but it must not expand scope beyond the four
work units (WU-039, WU-040A, WU-040B-extract, WU-040B-correct, WU-041A,
WU-041B), introduce a parallel audit namespace for compliance, reshape the
existing `roster_entries` / `roster_transitions` aggregates, or short-
circuit the roster service when applying consequences.

## Inputs

- `.pipeline/research.md` — Phase 1 research report.
- `product-strategy/tickets/SLICE-022.md` — Acceptance Criteria (AC1–AC4),
  Work Units, Code Boundary.
- `AGENTS.md` — Live Server Principle, No Backwards Compatibility,
  migration discipline, Test/Code Agent separation.
- `product-strategy/proposal.md` — Activity and Compliance (rule registry,
  evidence intake, OCR-first pipeline, officer correction, automated
  evaluation, consequence routing).
- Existing code in worktree — roster uses `under_review` state (not
  `probation`); SLICE-020 worker pattern (`services/api/app/tasks/*.py`
  with root audit context); SLICE-018 roster service; SLICE-014 permission
  intent reconciliation; SLICE-024 roster transition patterns.

## Acceptance Criteria Reference

- AC1 — Authority-gated compliance rule CRUD (WU-039) with cadence,
  evidence requirements, and consequence policy; OCC via `aggregate_heads`.
- AC2 — Evidence submission stores attachment reference in pending state;
  extraction is a separate, explicit step (WU-040A + WU-040B-extract).
- AC3 — Officer correction overlays extracted fields while preserving
  `raw_text` and `attachment_ref`; OCC guarded (WU-040B-correct).
- AC4 — Scheduled evaluation worker is idempotent per
  `(member, rule, period)` and routes consequences through the roster
  service API (WU-041A + WU-041B).

## Decisions

### D1 — Consequence terminology alignment to shipped roster states

**Rationale.** SLICE-022 ticket/proposal use the word "probation"; the
shipped `roster_entries` aggregate uses `under_review`. Introducing a new
`probation` state would reshape roster, violate the scope guardrails, and
create a second parallel substrate for the same concept.

**Binding implications.**
- `compliance_rules.consequence_kind` is a `Literal["review", "under_review"]`:
  - `"review"` — operator-flagged manual evaluation review; no automatic
    roster change; an officer must explicitly approve/override before any
    downstream consequence.
  - `"under_review"` — on violation, automatically transition the roster
    entry to `under_review` via the roster service (see D10).
- All proposal/ticket text that references `probation` must be read as
  `under_review` for code-level contracts; no `probation` enum value or
  column is introduced.
- Wording in user-facing strings is still owned by the proposal; the
  contract/DB layer uses `under_review` exclusively.

**Non-goals.** Adding a new roster state; renaming existing roster states;
supporting both `probation` and `under_review` as aliases.

### D2 — Rule schema is flat + JSONB, versioned via `aggregate_heads`

**Rationale.** SLICE-014/018/020/024 all version aggregates through
`aggregate_heads` with an `rev` / `version` column and OCC `If-Match`.
Adding a redundant `version` column on `compliance_rules` would diverge
from that pattern and require special-case migration/reconciliation.
Rules vary enough by cadence + evidence + consequence that JSONB params
are the right flex point.

**Binding implications.** `compliance_rules` table:
- `id UUID PK`
- `chapter_id TEXT NOT NULL`
- `name TEXT NOT NULL`
- `cadence_kind TEXT NOT NULL CHECK (cadence_kind IN ('weekly','monthly','quarterly'))`
- `cadence_params JSONB NOT NULL DEFAULT '{}'`
- `evaluation_window_days INT NOT NULL CHECK (evaluation_window_days > 0)`
- `evidence_requirements JSONB NOT NULL` — list of
  `{"type": "...", "required": true|false}`
- `consequence_kind TEXT NOT NULL CHECK (consequence_kind IN ('review','under_review'))`
- `consequence_params JSONB NOT NULL DEFAULT '{}'`
- `active BOOLEAN NOT NULL DEFAULT TRUE`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `archived_at TIMESTAMPTZ NULL`

Versioning: `aggregate_heads` carries the rule's version; evaluations
snapshot the head version as `rule_version` (see D7). Partial unique
index `UNIQUE (chapter_id, name) WHERE archived_at IS NULL` blocks
duplicate active rules but permits archived names to be re-used.

**Non-goals.** A dedicated `version` column on `compliance_rules`; an
event-sourced rule history separate from the standard audit projection;
per-evidence-type validator classes in the schema.

### D3 — Evidence schema keeps OCR output, corrections, and originals separate

**Rationale.** AC3 requires that correction preserves the raw text and
attachment. The cleanest way is an overlay column: the OCR result is
never mutated, and corrections write to a sibling JSONB column plus
correction metadata. Status transitions are CHECK-constrained so a row
can't claim to be `completed` without the OCR output.

**Binding implications.** `evidence_submissions` table:
- `id UUID PK`
- `rule_id UUID NOT NULL REFERENCES compliance_rules(id)`
- `member_id TEXT NOT NULL`
- `chapter_id TEXT NOT NULL`
- `attachment_ref TEXT NOT NULL` — opaque URL/path supplied by operator
- `raw_text TEXT NULL` — populated by OCR
- `extracted_fields JSONB NULL` — OCR output, never mutated
- `extracted_fields_corrected JSONB NULL` — officer overlay
- `extraction_status TEXT NOT NULL CHECK (extraction_status IN ('pending','running','completed','failed','corrected'))`
- `extraction_confidence NUMERIC(5,4) NULL` — 0–1
- `extraction_error TEXT NULL` — required when status='failed'
- `submitted_by_member_id TEXT NOT NULL`
- `submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `corrected_by_member_id TEXT NULL`
- `corrected_at TIMESTAMPTZ NULL`
- `correction_reason TEXT NULL`

CHECK constraints:
- `extraction_status='completed'` → `raw_text IS NOT NULL AND extracted_fields IS NOT NULL`
- `extraction_status='failed'` → `extraction_error IS NOT NULL`
- `extraction_status='corrected'` → `extracted_fields_corrected IS NOT NULL AND corrected_by_member_id IS NOT NULL AND correction_reason IS NOT NULL`

AC2 bind: submission creates row with `extraction_status='pending'`;
extraction is triggered separately. AC3 bind: correction writes overlay
and leaves `raw_text` + `attachment_ref` untouched.

**Non-goals.** Per-rule-type evidence sub-tables; mutating OCR output in
place; storing attachments inline (BYTEA/BLOB); versioning corrections
as a dedicated history table — history lives in the normal audit
projection (`activity_state_changes`).

### D4 — OCR provider is a pluggable Protocol with a stub default

**Rationale.** AC2/AC3 require that evidence intake and correction work
end-to-end, but the proposal explicitly scopes OCR as "extraction
pipeline" without pinning an engine. Introducing Tesseract / cloud APIs
inside this slice would drag in operational infrastructure beyond the
four work units. A Protocol + stub keeps the substrate complete and
deferred actual extraction to operator wiring.

**Binding implications.** `services/api/app/infrastructure/ocr.py`:
```python
class OcrExtractionResult(BaseModel):
    raw_text: str
    extracted_fields: dict
    confidence: Decimal

class OcrProvider(Protocol):
    async def extract(
        self, attachment_ref: str, rule_hint: str | None = None
    ) -> OcrExtractionResult: ...

class StubOcrProvider:
    async def extract(self, attachment_ref, rule_hint=None):
        raise NotImplementedError("OCR provider not configured")
```

- Settings wire a concrete impl in production; tests mock the Protocol.
- AC2 still passes: evidence row is stored in `pending`; extraction
  endpoint returns `501 Not Implemented` / `503 Service Unavailable`
  when no provider is configured (see D5).
- No OCR libraries (Tesseract, PaddleOCR, cloud SDKs) are added as
  dependencies in this slice.

**Non-goals.** Shipping a real OCR engine in this slice; classifying
evidence types via OCR; confidence-based auto-approval.

### D5 — Extraction endpoint is synchronous

**Rationale.** Async extraction would require a new deferred-effect type
(queue, worker, retry semantics) that does not exist in the substrate
and is not enumerated in the work units. Synchronous invocation keeps
the HTTP/service boundary simple and makes AC2 testable without queue
infrastructure.

**Binding implications.**
- `POST /evidence/{id}/extract` synchronously calls
  `OcrProvider.extract(...)` and updates the evidence row to
  `completed` or `failed` inside the request.
- Response is `EvidenceExtractionRead` with the final row state.
- If the provider raises `NotImplementedError` (stub), the endpoint
  returns `501` so integration tests can assert the "OCR not
  configured" path.
- Scaling / long-running OCR is documented as deferred (see D15).

**Non-goals.** Adding a queue, background job, or deferred-effect table;
chunked/streaming OCR; partial-result streaming to the client.

### D6 — Officer correction preserves originals and is OCC-guarded

**Rationale.** AC3 explicitly requires that correction does not
overwrite the raw OCR output. Allowing correction while extraction is
still in-flight would race with the OCR writer and produce a
`corrected` row without an `extracted_fields` baseline, violating D3's
CHECK.

**Binding implications.**
- `POST /evidence/{id}/correct` body:
  `{"corrected_fields": dict, "correction_reason": str}` (non-blank).
- `If-Match` required; stale → `412`.
- Allowed only when `extraction_status IN ('completed','failed','corrected')`;
  attempts during `pending` or `running` → `409`.
- Successful correction sets `extracted_fields_corrected`,
  `corrected_by_member_id`, `corrected_at`, `correction_reason`, and
  transitions `extraction_status` to `corrected`.
- `raw_text` and `attachment_ref` are never updated by this endpoint.
- A follow-up correction overwrites the overlay; the prior overlay is
  captured in `activity_state_changes` via the standard audit
  projection — no bespoke history table.

**Non-goals.** Immutable correction history tables; inline markup of
`raw_text`; multi-field confidence per-correction.

### D7 — Evaluation schema snapshots rule version + consequence lineage

**Rationale.** Evaluations must be reproducible even after a rule is
updated (AC1 version change). A `rule_version` snapshot lets officers
see exactly which rule definition produced a result. AC4 idempotency
depends on a natural key; `(member, rule, period)` is the only
deterministic candidate. `review_status` + `consequence_applied` split
the "did we apply automatic consequence" question from "did an officer
sign off."

**Binding implications.** `compliance_evaluations` table:
- `id UUID PK`
- `rule_id UUID NOT NULL REFERENCES compliance_rules(id)`
- `rule_version BIGINT NOT NULL`
- `chapter_id TEXT NOT NULL`
- `member_id TEXT NOT NULL`
- `period_start DATE NOT NULL`
- `period_end DATE NOT NULL`
- `result TEXT NOT NULL CHECK (result IN ('compliant','violation','insufficient_evidence'))`
- `consequence_applied TEXT NOT NULL CHECK (consequence_applied IN ('none','review_queued','under_review_applied'))`
- `review_status TEXT NOT NULL CHECK (review_status IN ('pending','approved','overridden','not_required'))`
- `reviewer_id TEXT NULL`, `review_reason TEXT NULL`, `reviewed_at TIMESTAMPTZ NULL`
- `evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `evidence_ids JSONB NOT NULL DEFAULT '[]'`

`UNIQUE (member_id, rule_id, period_start, period_end)` — AC4
idempotency primary constraint.

**Non-goals.** Evaluation state machine beyond the enums above;
multi-rule composite evaluations; storing the raw evidence payload on
the evaluation row (use `evidence_ids` references).

### D8 — Scheduled worker mirrors SLICE-020 R2: root audit context + per-rule isolation

**Rationale.** SLICE-020 R2 and SLICE-018's SLA workers already
establish the "install root audit context, iterate, catch per-entity,
don't abort batch on individual failure" pattern. Compliance evaluation
is the same shape (background sweep + mutate via service APIs).

**Binding implications.** `services/api/app/tasks/compliance.py`
exposes `compliance_evaluation_worker_tick(db, *, now)`:
1. Install root audit context (service actor `compliance-evaluator`).
2. For each active rule:
   - Compute the current evaluation period from `cadence_kind` +
     `cadence_params` + `evaluation_window_days` (see D9).
   - Enumerate chapter members in scope.
   - For each `(member, rule, period)`:
     - `INSERT ... ON CONFLICT DO NOTHING` into
       `compliance_evaluations` (idempotency via the UNIQUE key).
     - On insert: compute `result` from available evidence; record
       `consequence_applied`, `review_status`.
     - If `consequence_kind='under_review'` AND `result='violation'`
       AND policy auto-applies: invoke the roster service to
       transition the member to `under_review` (see D10).
3. Catch exceptions per-rule, log as `exception`, continue batch.
4. `COMPLIANCE_EVALUATION_INTERVAL_SECONDS = 3600` (hourly) — lower
   churn than SLA/expiry sweeps.

**Non-goals.** Parallel fan-out across rules; cross-chapter
transactions; event-driven evaluation triggered on evidence submission.

### D9 — Cadence periods are deterministic calendar windows

**Rationale.** AC4 idempotency requires a deterministic `(period_start,
period_end)` for each tick. Drifting windows (e.g., "last 7 days from
now") would insert new rows on every tick.

**Binding implications.** Period boundaries:
- `weekly` — Monday 00:00 UTC → Sunday 23:59:59 UTC (ISO week).
- `monthly` — 1st of month 00:00 UTC → last day 23:59:59 UTC.
- `quarterly` — calendar quarter boundaries (Jan–Mar, Apr–Jun,
  Jul–Sep, Oct–Dec) in UTC.

The "current" period = the period containing
`now - INTERVAL 'evaluation_window_days'`, i.e., cadence evaluates the
most recently completed window. `cadence_params` allow fine-grained
offsets (e.g., `{"week_offset": -1}` to evaluate the prior week
explicitly). `period_start` / `period_end` are stored on the evaluation
row so changes to rule params don't retroactively duplicate history.

**Non-goals.** Rolling windows; per-chapter timezone offsets; sub-daily
cadence.

### D10 — All consequences route through the roster service API

**Rationale.** AC4 specifies consequence routing through the roster
service. Compliance directly mutating `roster_entries` would bypass
service-layer authority, duplicate state-machine logic, and break
audit provenance.

**Binding implications.**
- The compliance worker/service never mutates `roster_entries`
  directly; it calls the roster service (e.g.,
  `roster_service.transition_to_under_review(...)` or equivalent
  action, modeled on SLICE-024's reassignment pattern).
- If that exact entry-point does not yet exist in `services/roster.py`,
  the implementation adds it alongside existing transitions — not as a
  compliance-specific helper — and it accepts a `reason` (e.g.,
  `compliance_violation`) for audit.
- Service actor `compliance-evaluator` holds `roster.transition`
  scoped per SLICE-008 hierarchy (global grant covers all chapters).
- On consequence success, the evaluation row records
  `consequence_applied='under_review_applied'`; on failure, it records
  the error via the standard audit projection and retries next tick
  (idempotent).

**Non-goals.** Introducing a new consequence dispatch table; emitting
Discord-facing events from compliance directly (roster already emits
its own projections).

### D11 — Authority permissions enumerate compliance + carve out substrate role

**Rationale.** SLICE-014/018/020 establish permissions as opaque strings
granted via `authority_grants`. Compliance adds both user-facing and
internal substrate permissions; they must be distinct so officers can
review without being able to forge evaluations, and the worker can
write evaluations without being able to override them.

**Binding implications.** New permission strings:
- `compliance_rule.read`, `compliance_rule.write` — CRUD on rules.
- `compliance_evidence.submit` — member submission.
- `compliance_evidence.correct` — officer correction (D6).
- `compliance_evidence.extract` — trigger OCR (D5).
- `compliance_evaluation.read` — read evaluation history.
- `compliance_evaluation.review` — override/approve results.

Service actor `compliance-evaluator` is seeded with:
- `compliance_rule.read`
- `compliance_evaluation.write` — internal substrate permission,
  distinct from `.review`; worker writes, officers review.
- `roster.transition` at chapter scope (global grant covers all
  chapters per SLICE-008 hierarchy).

**Non-goals.** Per-rule ACLs; per-evidence-type permissions; Discord
role mapping in this slice.

### D12 — Migration chain is linear off `wu_038`

**Rationale.** Live Server Principle: migrations chain forward only.
`wu_038_permission_intent_expiry` is the current head. Three tables +
an actor grant fit the slice; consolidation vs. split is an
implementation choice but the chain order is fixed.

**Binding implications.**
- Chain order:
  `wu_038_permission_intent_expiry → wu_039_compliance_rules →
   wu_040a_compliance_evidence → wu_041a_compliance_evaluations`.
- `wu_041a_compliance_evaluations` seeds the `compliance-evaluator`
  service actor with the grants from D11.
- Each downgrade is a no-op (live-server convention).
- The implementation may collapse these three into a single migration
  if desired; it must not split them across unrelated migrations.

**Non-goals.** Backfilling rules/evidence from historical data; cross-
slice migrations that bundle SLICE-022 tables with later slices.

### D13 — Constants-only dispatch for compliance audit actions

**Rationale.** AGENTS.md + every prior slice forbids f-string or
dynamic action/change types. Compliance adds its own vocabulary; it
must be declared up front and allowlisted for payload shapes.

**Binding implications.** Action/change type vocabulary (extend
existing dicts in `app/contracts/audit.py` or add `COMPLIANCE_*`):
- `compliance_rule.create` / `compliance_rule.created`
- `compliance_rule.update` / `compliance_rule.updated`
- `compliance_rule.archive` / `compliance_rule.archived`
- `evidence_submission.submit` / `evidence_submission.submitted`
- `evidence_submission.correct` / `evidence_submission.corrected`
- `evidence_submission.extract` / `evidence_submission.extracted`
- `evidence_submission.extraction_failed`
- `compliance_evaluation.create` / `compliance_evaluation.created`
- `compliance_evaluation.review` / `compliance_evaluation.reviewed`
- `compliance_evaluation.override` / `compliance_evaluation.overridden`
- `compliance_evaluation.consequence_applied`

Payload allowlists are narrow per action and declared alongside the
constant.

**Non-goals.** Free-form metadata dicts; derived action names from
arguments; shared vocabulary with roster/authority subsystems.

### D14 — Test boundaries are per-WU and each test docstrings the AC

**Rationale.** Test/Code Agent separation requires the test surface
to be enumerable up front. Each AC maps to a specific test; each WU
carries its own test file so the code agent can satisfy them in
isolation.

**Binding implications.** Required tests (one test per bullet; each
docstring names the AC or guardrail it enforces):

WU-039 `test_compliance_rules`:
- AC1 — create persists cadence + evidence requirements + consequence.
- AC1 — update with `If-Match` advances version.
- AC1 — stale `If-Match` → `412`.
- Unique `(chapter_id, name) WHERE archived_at IS NULL`.
- `cadence_kind` CHECK validation.
- `consequence_kind` CHECK validation (`review` | `under_review`).

WU-040A `test_compliance_evidence`:
- AC2 — submit creates row with `extraction_status='pending'`.
- AC2 — GET returns pending state.
- FK integrity: evidence rule FK to `compliance_rules`.
- Submission actor covers member and officer paths.

WU-040B-correct `test_compliance_ocr_correct`:
- AC3 — correction updates `extracted_fields_corrected`.
- AC3 — correction preserves `raw_text` + `attachment_ref`.
- AC3 — OCC `412` on stale `If-Match`.
- Correction rejected during `pending` / `running` → `409`.
- `correction_reason` required non-blank → `422`.

WU-040B-extract `test_compliance_ocr_extract`:
- OCR provider invoked; evidence transitions `pending → completed`.
- OCR failure transitions to `failed` with `extraction_error`.
- OCR not configured → `501`/`503`.
- Multiple extractions idempotent (same result).

WU-041A `test_compliance_review_api`:
- AC1 — review endpoint updates `review_status`.
- Override advances `consequence_applied` if policy requires.
- OCC `412` on stale `If-Match`.
- Authority required (`compliance_evaluation.review`).

WU-041B `test_compliance_evaluation_worker`:
- AC4 — idempotent per `(member, rule, period)`.
- AC4 — consequence routes through roster service API.
- Worker failure in one rule does not abort the batch.
- Period computation per `cadence_kind`.
- Insufficient evidence → `result='insufficient_evidence'`,
  `consequence_applied='none'`.

**Non-goals.** Cross-WU integration tests in this phase; end-to-end
Discord-triggered compliance tests; property-based tests on cadence
math.

### D15 — Explicit out-of-scope fence

**Rationale.** Scope creep in compliance is a known risk: OCR, file
upload, async queues, and trust-signal integration each have proposal
hooks. Naming them as out-of-scope here prevents the implementation
phase from expanding the substrate.

**Binding implications.** The following are out of scope for SLICE-022
and must not land in this slice:
- OCR engine implementation — pluggable Protocol + stub only (D4).
- Async extraction queue — synchronous only (D5); scaling deferred.
- File upload endpoint — `attachment_ref` is an opaque operator-
  supplied string.
- Per-rule-type evidence validators — `evidence_requirements` is
  JSONB; no schema dispatch.
- Multi-member / batch consequences — consequences are per-evaluation.
- Evidence deletion / GDPR flows.
- Discord-triggered evidence submission — HTTP intake only.
- Trust-signal integration — compliance violations do NOT auto-
  generate trust signals in this slice.

**Non-goals.** Re-introducing any of the above through back-channels
(e.g., a hidden `attachment_upload` endpoint, a shadow trust-signal
write path, or a synchronous "but actually async" extraction hook).

## Guardrails (apply to every decision above)

- Follow SLICE-014, SLICE-018, SLICE-020, SLICE-024 patterns for
  service-layer authority, OCC via `aggregate_heads`, and audit
  projection.
- Service-layer authority checks precede every mutation; no repository-
  level bypass.
- Multi-aggregate mutations in a single service op share one
  connection (existing contract).
- Constants-only audit dispatch (D13); no f-string vocabulary.
- Worker installs root audit context (SLICE-020 R2 precedent).
- Migration chain is linear, one head forward (D12).
- Roster state vocabulary is `under_review`, not `probation` (D1).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
