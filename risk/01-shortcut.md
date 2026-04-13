# Shortcut risk assessment — proposals/01-v1-scope.md

Date: 2026-04-13
Assessor: claude-opus (shortcut)

## Verdict

**LOW**

The proposal systematically replaces every identified pre-research shortcut without introducing new ones. Forms move from YAML to DB. SQLite is replaced with Postgres. The modal-split rendering becomes a derived plan from a logical form model. OCR thresholds are explicitly deferred to calibration against a retained gold corpus rather than hardcoded. Provisioning complexity is proportionate to Humility's near-zero chapter volume. Every JSONB column stores genuinely document-shaped or vendor-defined data. The open questions in §16 are real design questions deferred to the correct phase boundary, not shortcuts masked as deferrals.

## Findings

### Finding 1 — Form editing path deferred to hookpoint phase

- **Severity**: LOW
- **Pattern type**: DEFER-AS-WORKAROUND
- **Section of proposal**: §4 (Applications) and §16 (Open questions)
- **Description**: The proposal moves forms from YAML to DB and makes YAML import-only. But the operator path for editing a DB-backed form after initial bootstrap is explicitly left as an open question for hookpoint phase. §16 asks: "What is the thinnest acceptable operator path for editing DB-backed application forms after initial bootstrap and provisioning, without reintroducing YAML as the source of truth?" If the only editing path that materializes is "write YAML, re-import," YAML becomes a shadow source of truth through the back door.
- **Why it matters**: Without a described editing path, implementers must invent one. The likely shortcuts at implementation time are: direct DB manipulation, re-running full provisioning, or quietly reintroducing YAML as source of truth for "just the form updates."
- **Recommendation**: Accept — not a shortcut because the proposal transparently flags it at the correct phase boundary. The underlying data model already supports the operation (immutable version rows); only the UX trigger is unspecified. The hookpoint phase must answer this before implementation proceeds.

### Finding 2 — No compatibility shims or feature flags detected

- **Severity**: LOW
- **Pattern type**: COMPAT SHIM
- **Section of proposal**: §4, §9, §14
- **Description**: Cross-checked against the full proposal. The web-form fallback for application intake (§4) is a concrete replacement surface using the same DB records, not a compatibility fork. The Phase 2a/2b split is staged delivery, not a feature flag. Deferred ticket types (`chapter_support`, `chapter_incident`, `moderator`) are excluded from the enum entirely rather than stubbed. §14 explicitly bans compat shims, dual-write paths, and feature flags. No violations found.
- **Why it matters**: D1 and AGENTS.md explicitly forbid compat shims. The proposal passes.
- **Recommendation**: Accept, not actually a shortcut.

### Finding 3 — JSONB columns are justified, not schema dumps

- **Severity**: LOW
- **Pattern type**: SCHEMA SHORTCUT
- **Section of proposal**: §3 (Data model)
- **Description**: The schema uses JSONB across multiple tables. Each was checked: `schema_json` and `component_plan_json` store hierarchical form definitions with variable question counts — inherently document-shaped. `answers_json` and `attachments_json` are immutable submission snapshots tied to a specific form version. OCR payload columns store vendor-defined responses from Google Vision and Gemini. `spec_json`, `validation_report_json`, `created_resources_json`, and `cleanup_report_json` on `provisioning_runs` store variable-length operational snapshots. Audit columns store mutation context that varies per operation type. `opening_message_json` and `embeds_json` capture Discord message structures. Critically, the proposal uses explicit columns where structure IS known: `activity_rules` has `metric_name`, `comparison_operator`, `threshold_value`, `window_days`, `breach_count_required`, `evaluation_mode` as proper typed columns. That demonstrates the author distinguished structured from genuinely document-shaped data.
- **Why it matters**: JSONB-as-dumping-ground is a classic shortcut. None of these columns hide stable-column data behind JSONB.
- **Recommendation**: Accept. The proposal's table notes after the schema explicitly justify each category.

### Finding 4 — No pre-research code carryover detected

- **Severity**: LOW
- **Pattern type**: PRE-RESEARCH CARRYOVER
- **Section of proposal**: §3, §4, §7, §8 vs `daemon/db.py`, `daemon/config.py`, `daemon/applications.py`
- **Description**: Cross-checked all five pre-research code files. The draft's SQLite schema (`slug TEXT PRIMARY KEY`, `INTEGER PRIMARY KEY AUTOINCREMENT`, `answers_json TEXT`, `status TEXT`) is entirely replaced by Postgres with UUIDs, proper enums, typed timestamps, and foreign keys. The draft's YAML-as-source-of-truth pattern (`daemon/config.py` loading forms from `forms/<slug>.yaml` with hardcoded step splitting into modal/followup_selects) is replaced by DB-stored form versions with a derived component plan. The draft's `ApplicationReviewView` with integer submission IDs, direct SQLite calls, and four buttons is replaced by a UUID-based design with proper status history and five buttons (adding Waitlist). The draft's in-memory `ApplicationSessionState` is replaced by `draft` DB rows. The claim helper's shape survives because it was independently validated by research — that is reuse, not carryover.
- **Why it matters**: The specific failure mode is a proposal that looks redesigned but secretly carries forward wrong shapes.
- **Recommendation**: Accept. Clean break from draft code.

### Finding 5 — OCR threshold deferral is honest staged delivery

- **Severity**: LOW
- **Pattern type**: SYMPTOM MASK
- **Section of proposal**: §6 (Activity tracking)
- **Description**: Phase 2a ships without confidence scoring, fallback, or automated rule evaluation. The proposal states: "The goal of Phase 2a is durable ingestion and operator-visible extraction, not fully trusted automation." Phase 2b adds confidence scoring, the three-way routing decision, Gemini fallback, hallucination controls, and correction tools. The anti-scope (§14) explicitly says: "No hardcoded OCR acceptance thresholds presented as settled design truths." §11 requires calibration against a retained gold corpus.
- **Why it matters**: "Flag for review" as a catch-all would be a symptom mask. Here it is an honest intermediate state for Phase 2a, with Phase 2b adding the real trust layer. The phasing contract is explicit about what each phase delivers.
- **Recommendation**: Accept. The split avoids shipping a half-baked trust layer.

### Finding 6 — Provisioning without saga is proportionate to volume

- **Severity**: LOW
- **Pattern type**: TRANSACTION SHORTCUT
- **Section of proposal**: §7 (Chapter provisioning) and §13 (Rollback plan)
- **Description**: The proposal uses sequential creation with incremental ID recording and explicit operator-driven cleanup instead of automatic saga rollback. If a run fails after creating roles but before channels, the operator reviews `created_resources_json` and drives cleanup with a recorded result in `cleanup_report_json`. There is no automatic resume-from-midpoint and no generic reverse-ordered rollback framework.
- **Why it matters**: For a guild with zero current chapters and expected single-digit lifetime chapter count, an enterprise saga engine would be the actual shortcut — complexity masking a problem that barely exists at this scale.
- **Recommendation**: Accept. The proposal's explicit cleanup path with recorded IDs is proportionate and auditable.

### Finding 7 — RLS deferral is justified for single-client architecture

- **Severity**: LOW
- **Pattern type**: OTHER
- **Section of proposal**: §9 (Deployment)
- **Description**: §9 disables RLS because "only the trusted daemon service role uses them." In v1, the daemon is the sole database client. There is no web app, no untrusted client, no multi-tenant access. RLS on a single trusted service-role connection adds configuration burden without security improvement.
- **Why it matters**: If the daemon were not the only client, disabling RLS would be a shortcut. The architecture genuinely has one trusted client.
- **Recommendation**: Accept. The proposal plans to add RLS when untrusted clients appear — the correct trigger.

### Finding 8 — Audit log is necessary, not duplicating Discord

- **Severity**: LOW
- **Pattern type**: DUPLICATED LOGIC
- **Section of proposal**: §3 and §8
- **Description**: `audit.audit_events` captures application-level mutation context: status transitions, role assignments, provisioning steps, OCR processing decisions, claim operations, blacklist additions. Discord's native audit log captures only API-level actions (role changes, channel edits) and retains them for 45 days. The proposal's audit table captures events Discord's log cannot and retains them indefinitely per the D4 retention decision.
- **Why it matters**: Duplicating Discord's audit log would be unnecessary complexity. This table covers a broader, different set of events.
- **Recommendation**: Accept, not duplication.

## Overall assessment

All 15 checklist items were evaluated against the proposal text, pre-research code, decision log, and research documents. No shortcut pattern was found at MEDIUM or HIGH severity. The proposal replaces every pre-research shortcut (SQLite, YAML-as-truth, hardcoded modal splits, integer IDs without history tracking, in-memory sessions) with designs that pull their weight. The deferrals in §14 are genuine anti-scope items that v1 does not need, not required functionality masked as "out of scope." The JSONB columns store genuinely variable data. The OCR phasing is honest. The provisioning complexity is proportionate. The one open question (form editing path) is transparently deferred to the correct phase.

## What a LOW verdict requires

The verdict is LOW because the proposal's design pulls its weight at every layer. No deferred complexity is masked as "out of scope." No JSONB column is a dumping ground. No threshold is presented as validated when it is not. No pre-research draft shape was carried forward uncritically. The open questions in §16 are real design questions at the correct phase boundary, not shortcuts wearing the mask of deferred decisions.
