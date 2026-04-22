# SLICE-022 Phase 8 — Multi-Concern Review (PR #66)

Reviewed: 2026-04-22
PR: `feat/slice-022-compliance` (#66), 41 files, +7858 / −2319 LOC
Inputs: `git diff origin/main...feat/slice-022-compliance`,
`.pipeline/proposal.md` §12, `product-strategy/tickets/SLICE-022.md`,
`plans/risk/slice-022-scope.md`, `AGENTS.md` §"One Concern Per PR".

## 1. Verdict

**`MULTI_CONCERN_ACCEPT_UNIFIED`**

Keep PR #66 as a single bundled drop covering WU-039, WU-040A,
WU-040B-correct, WU-040B-extract, WU-041A, and WU-041B. The seams
sketched in `.pipeline/proposal.md` §12 (PR A = rule lifecycle +
review; PR B = evidence flow; PR C = worker) are *logical* seams
across the WUs but they do **not** correspond to physical file
boundaries in the shipped code. Three shared modules straddle every
proposed cut, so splitting would either require a pre-refactor that
is absent from the current diff or produce three PRs that each
re-open the same files with additive diffs — no self-contained
reviewable units.

§12 itself authorizes this path explicitly:

> "Alternative single-PR bundling (PR A+B+C): acceptable at
> multi-concern review time if the reviewer prefers one coherent
> drop — the three migrations can be chained in a single PR
> (still linear per D12). […] final decomposition is subject to the
> multi-concern review gate and should not exceed three PRs."

Against AGENTS.md §"One Concern Per PR":

- "A PR that touches N independent concerns should be split into N
  PRs" — the six WUs here are **not** independent. They share one
  contracts module, one repository module, one primary service
  module, one test-helpers module, and one endpoint subpackage
  (`_shared.py` aggregator). The cross-module import graph is a
  tight interior, not six disjoint islands.
- "Additive changes go before behavioral changes" — no prior
  substrate exists to add onto: this slice introduces the entire
  compliance surface in one go (no pre-existing `compliance.py`,
  `compliance_rules` table, or evaluation migration to extend).
- The scope audit already rates this LOW
  (`plans/risk/slice-022-scope.md:1`): every change maps to one of
  the six enumerated WUs, no out-of-scope creep.

The shortcut audit (`plans/risk/slice-022-shortcut.md`) and the
scope audit concur the slice is a coherent unit; the work was
deliberately built as one feature surface with three linear
migrations and shared abstractions. Forcing a seam here creates
churn without reducing risk.

## 2. Concerns enumerated

Six WUs were in-flight in this branch:

| WU | Concern | Primary files |
|---|---|---|
| WU-039 | Compliance rule lifecycle API | `migrations/versions/wu-039_compliance_rules.py`; rule contracts in `contracts/compliance.py`; rule helpers in `repositories/compliance.py`; `create_rule`/`update_rule`/`list_rules`/`get_rule_read` in `services/compliance.py`; `api/v1/endpoints/compliance/rules.py`; `tests/test_compliance_rules.py` |
| WU-040A | Evidence submission API | `migrations/versions/wu-040a_compliance_evidence.py`; evidence contracts in `contracts/compliance.py`; evidence helpers in `repositories/compliance.py`; `submit_evidence`/`get_evidence_submission` in `services/compliance.py`; `api/v1/endpoints/compliance/evidence.py`; `tests/test_compliance_evidence.py` |
| WU-040B-correct | Officer correction API | `contracts/compliance_corrections.py`; `services/compliance_corrections.py` (imports `_evidence_from_row` from `services/compliance.py`); `api/v1/endpoints/compliance/evidence_correct.py`; `tests/test_compliance_ocr_correct.py` |
| WU-040B-extract | OCR extraction API | `contracts/compliance_extraction.py`; `infrastructure/ocr.py`; `services/compliance_extraction.py`; `api/v1/endpoints/compliance/evidence_extract.py`; `tests/test_compliance_ocr_extract.py` |
| WU-041A | Evaluation review API | `migrations/versions/wu-041a_compliance_evaluations.py`; evaluation contracts in `contracts/compliance.py`; evaluation helpers in `repositories/compliance.py`; `services/compliance_review.py` (imports `_compute_consequence_shape`, `_evaluation_from_row` from `services/compliance.py`); `api/v1/endpoints/compliance/evaluations.py`; `api/v1/endpoints/compliance/evaluations_run.py`; `tests/test_compliance_review_api.py` |
| WU-041B | Scheduled evaluation worker | `_evaluate_member_rule`, `run_scheduled_compliance_evaluations`, `_compute_period`, `_compute_rule_result`, `_compute_consequence_shape`, `_insert_evaluation_row` in `services/compliance.py`; `tasks/compliance.py`; scheduler wiring in `services/scheduler.py`; `tasks/__init__.py`; roster read helper in `services/roster.py`; `tests/test_compliance_evaluation_worker.py` |

Shared infrastructure spanning every WU: `contracts/compliance.py`
(244 LOC — rule / evidence / evaluation types co-located);
`repositories/compliance.py` (494 LOC — rule / evidence / evaluation
row access co-located); `services/compliance.py` (819 LOC — rule
writes, evidence writes, worker evaluation, shared row-mapping
helpers co-located); `api/v1/endpoints/compliance/__init__.py` +
`_shared.py` (169 LOC aggregator); `tests/compliance_helpers.py`
(347 LOC shared test fixtures).

## 3. Why the proposed §12 seams don't cut cleanly

The §12 split is logical — rules+review as a "substrate" PR, the
three-WU evidence flow as a "flow" PR, worker last. On paper it
reads clean. In the shipped code it cuts through shared modules
three times.

### Seam 1 — `services/compliance.py` (819 LOC monolith)

The file holds all three layers that the proposed PRs would
separate:

- WU-039 rule writes: `create_rule` (line 294), `update_rule` (367),
  `list_rules` (458), `get_rule_read` (438).
- WU-040A evidence writes: `submit_evidence` (481),
  `get_evidence_submission` (564).
- WU-041B worker logic: `_insert_evaluation_row` (584),
  `_evaluate_member_rule` (618), `run_scheduled_compliance_evaluations`
  (736), `_compute_period` (267), `_compute_rule_result` (190),
  `_compute_consequence_shape` (231).
- Shared helpers consumed by both sibling service modules and the
  worker: `_evidence_from_row`, `_evaluation_from_row`,
  `compliance_evaluator_actor`, `_merged_extracted_fields`,
  `_make_request`.

Dependency edges from the other "PR A/B" service modules back into
this monolith:

- `services/compliance_review.py:22–25` imports
  `_compute_consequence_shape` and `_evaluation_from_row` from
  `services/compliance.py`. Under §12's PR A (rules + review),
  `_compute_consequence_shape` would be the worker's logic (PR C) —
  so PR A would need a stub or a duplicate of that helper until PR C
  lands, or it would need the helper extracted into a fourth shared
  module before PR A.
- `services/compliance_corrections.py:20` imports
  `_evidence_from_row` from `services/compliance.py`. Under PR B
  (evidence flow), this is fine — but the helper lives in a module
  that would otherwise already contain all of PR A's rule code plus
  PR C's worker code.
- `tasks/compliance.py:13` imports `compliance_evaluator_actor` and
  `run_scheduled_compliance_evaluations` from
  `services/compliance.py`. PR C (worker) re-enters the same module
  that PRs A and B already modified.

To split cleanly, `services/compliance.py` would need to be
decomposed first into (e.g.) `compliance_rules.py`,
`compliance_evidence.py`, `compliance_evaluations.py`, and a
`_shared.py` that holds the row-mapping helpers and
`compliance_evaluator_actor`. That refactor is **not** in the
current diff. Shipping the split without it means each of the
three PRs rewrites portions of the same 819-line file, and the
diffs overlap.

### Seam 2 — `repositories/compliance.py` (494 LOC)

The repository module holds:

- Rule row access (WU-039): `get_rule`, `get_rule_for_update`,
  `list_rules_by_chapter`, `list_active_rules`, `insert_rule`,
  `update_rule_row`.
- Evidence row access (WU-040A, WU-040B-correct):
  `get_evidence`, `get_evidence_for_update`, `insert_evidence`,
  `update_evidence_after_extraction`, `update_evidence_correction`,
  `list_evidence_for_rule_period`.
- Evaluation row access (WU-041A, WU-041B): `get_evaluation`,
  `get_evaluation_for_update`, `insert_evaluation_if_absent`,
  `update_evaluation_review`.
- Roster enumeration scoped to compliance:
  `list_current_roster_members_by_chapter` (WU-041B).

The same split story as Seam 1: the §12 PRs would each rewrite
pieces of this file. The evidence flow PR (PR B) needs
`update_evidence_correction` and `list_evidence_for_rule_period`;
the worker PR (PR C) needs
`list_current_roster_members_by_chapter` and
`insert_evaluation_if_absent`; the rules+review PR (PR A) needs all
rule helpers plus the review-side evaluation helpers. No clean
physical cut exists without prior modularization.

### Seam 3 — `contracts/compliance.py` (244 LOC)

The contract module co-locates all read/write Pydantic models:
`ComplianceRuleCreate/Update/Read`, `EvidenceSubmissionCreate/Read`,
`ComplianceEvaluationRead`, `ComplianceEvaluationReviewRequest`,
plus the seven typed errors that cross WU boundaries. Splitting
would require three additions to the same file across three PRs,
or three new sub-contract modules (`compliance_rules.py`,
`compliance_evidence_core.py`, `compliance_evaluations.py`) that
the current diff does not create.

### Seam 4 — shared test fixture `tests/compliance_helpers.py`

`tests/compliance_helpers.py` (347 LOC, new) is used by every
compliance test file — rule tests, evidence tests, correct tests,
extract tests, review tests, worker tests. If it lands in PR A,
PRs B and C depend on a specific helper signature and can't be
reviewed without A; if it's duplicated, we ship three drifting
copies; if it's split, each PR reinvents fixtures. A single PR
avoids the fixture-ownership problem entirely.

### Seam 5 — endpoint subpackage aggregator

`api/v1/endpoints/compliance/__init__.py` and
`api/v1/endpoints/compliance/_shared.py` (169 LOC) are shared by
all six endpoint modules. The scope audit already flags
`_shared.py` as a DRY helper spanning the whole subpackage
(`plans/risk/slice-022-scope.md:199`). Splitting would mean either
landing the aggregator empty in PR A and progressively registering
routers in PRs B/C, or triplicating the helper. Either pattern is
worse than a single drop.

## 4. Migration chain

The three migrations are linear and ship together cleanly:

```
wu_038_permission_intent_expiry
 └─▶ wu_039_compliance_rules (WU-039)
      └─▶ wu_040a_compliance_evidence (WU-040A)
           └─▶ wu_041a_compliance_evaluations (WU-041A)
```

Per proposal §12 and D12 the chain is linear off `wu_038`, and the
`wu_041a` migration is the one that seeds the `compliance-evaluator`
service actor grants consumed by WU-041B. A three-PR split would
either (a) chain three separate migrations across three PRs — each
advancing the head by one revision — or (b) move the service-actor
seed out of `wu_041a` and into a PR-B-specific migration, which
violates D11/D12 ("service-actor grants seeded in the evaluations
migration", audit observation 6). Option (a) works mechanically but
gains nothing; option (b) breaks the synthesis binding. Both are
worse than chaining all three migrations in one PR.

## 5. Size signal

PR totals: 41 files, +7858 / −2319 LOC. The −2319 is almost
entirely pipeline doc regeneration
(`.pipeline/research.md`, `.pipeline/synthesis.md`,
`.pipeline/proposal.md`) which is not production code. Net
production code: roughly +4900 LOC spread across:

- Migrations: 322 LOC (three files)
- Contracts: 294 LOC (three files)
- Repository: 494 LOC (one file)
- Services: 1461 LOC (four files)
- Infrastructure (OCR stub): 44 LOC (one file)
- Endpoints: 519 LOC (eight files)
- Tasks + scheduler wiring: 97 LOC (two files)
- Tests: 1707 LOC (seven files + helpers + conftest)

This is the top end of "single coherent PR" size, but smaller than
what a split would cost. Splitting into three PRs at the §12 seams
would produce approximately:

- PR A (rules + review): ~1800–2200 LOC including partial
  `services/compliance.py`, partial `repositories/compliance.py`,
  partial `contracts/compliance.py`, rule + review endpoints + tests
  + two of the three migrations + shared helpers.
- PR B (evidence flow, three WUs): ~1600–1900 LOC including
  additional slices of the same three shared modules + evidence
  migration + OCR infrastructure + correction/extraction services
  + three endpoint files + three test files.
- PR C (worker): ~500 LOC, but re-opens `services/compliance.py`
  (worker functions) and `services/scheduler.py` and `tasks/__init__.py`.

Per-PR size is smaller, but the shared-module churn means no PR is
self-contained: each PR's diff overlaps the others in
`services/compliance.py`, `repositories/compliance.py`, and
`contracts/compliance.py`. Reviewers end up reading overlapping
diffs three times instead of one coherent module once.

## 6. Slice-level artifacts

`.pipeline/research.md`, `.pipeline/synthesis.md`,
`.pipeline/proposal.md`, `plans/risk/slice-022-audit.md`,
`plans/risk/slice-022-scope.md`, `plans/risk/slice-022-shortcut.md`
describe the slice as a whole. They are not per-WU and are already
consolidated in a pipeline-docs commit (`59202d4 docs: SLICE-022
pipeline artifacts`). These belong in whatever PR lands — single or
split — and do not drive the split decision.

## 7. Test-suite independence check

Every new test file imports from `tests/compliance_helpers.py`.
Under a three-PR split the helper owner-PR forces sequencing on the
other two; under bundling the suite is one coherent drop. The full
compliance test set runs green in the current branch
(`test_compliance_rules.py`, `test_compliance_evidence.py`,
`test_compliance_ocr_correct.py`, `test_compliance_ocr_extract.py`,
`test_compliance_review_api.py`,
`test_compliance_evaluation_worker.py`, plus the `test_roster.py`
additions for the `connection=` kwarg extension).

The `services/api/tests/test_roster.py:+47` addition (R7 /
audit M5 fix) is a cross-file test that pins the
`transition_roster_entry(..., connection=None)` signature
extension in roster's own test home — a deliberate placement the
audit records so the signature change lives where the function
lives rather than being smeared into compliance tests. That pin is
consumed by WU-041B but the extension itself is a backward-
compatible roster-service change, not compliance code.

## 8. Summary

Recommend accepting PR #66 as a single multi-concern drop covering
all six WUs (WU-039, WU-040A, WU-040B-correct, WU-040B-extract,
WU-041A, WU-041B) with the three-migration chain
`wu_039 → wu_040a → wu_041a`.

The §12 seams describe a logical decomposition that would be
appropriate if the shipped code had three disjoint service modules
and three disjoint contract modules, but the actual implementation
shares `contracts/compliance.py`, `repositories/compliance.py`, and
`services/compliance.py` across every WU, with
`services/compliance_review.py`, `services/compliance_corrections.py`,
and `tasks/compliance.py` importing helpers from the shared module.
No clean physical cut exists without a pre-split refactor that is
not in the current diff. The scope audit already rates the slice
LOW risk and well-bounded; the shortcut audit concurs. §12 itself
authorizes single-PR bundling at the multi-concern review gate.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
