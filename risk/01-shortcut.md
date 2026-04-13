# Shortcut risk assessment — proposals/01-v1-scope.md

Date: 2026-04-11
Assessor: claude-opus (shortcut)

## Verdict

**LOW**

The proposal is clean. It replaces every identified pre-research shortcut (SQLite, YAML-as-source-of-truth, CLI-driven provisioning, in-memory sessions) with principled alternatives and does not introduce new shortcuts in the process. JSONB columns store genuinely document-shaped data, not schema-avoidance dumps. The mixed OCR architecture follows a research recommendation with explicit hallucination controls. The saga model uses principled defaults (archive over delete) rather than punting on rollback. The few underspecifications are appropriate deferrals to implementation and hookpoint phases, not complexity hidden behind "out of scope." No compat shims, no feature flags, no dual-write layers, no carryover of wrong shapes from the pre-research draft.

## Findings

### Finding 1 — JSONB columns are appropriately scoped

- **Severity**: LOW
- **Pattern type**: SCHEMA SHORTCUT
- **Section of proposal**: §3 (Data model)
- **Description**: The schema uses 14 JSONB columns across 7 tables: `schema_json`, `component_plan_json`, `answers_json`, `attachments_json`, `opening_message_json`, `embeds_json`, `raw_event_json`, `primary_ocr_payload_json`, `fallback_ocr_payload_json`, `spec_json`, `dry_run_report_json`, `request_json`, `result_json`, `before_json`/`after_json`. Each one stores either external service payloads (OCR responses, Discord event structures), immutable versioned documents (form schemas, answer snapshots), or heterogeneous audit snapshots.
- **Why it matters**: JSONB-as-dumping-ground is one of the most common schema shortcuts. If any of these columns hid structured data that should be explicit columns, it would create query difficulty and silent schema drift.
- **Recommendation**: Accept, not actually a shortcut. Every JSONB column stores data whose structure is either externally defined (Discord, Google Vision, Gemini), version-dependent (form schemas and answers keyed to a specific version), or inherently heterogeneous (audit before/after snapshots that vary by operation type). Critically, the proposal uses explicit columns where the structure IS known — `activity_rules` has `metric_name`, `comparison_operator`, `threshold_value`, `window_days`, `breach_count_required`, `evaluation_mode` as proper typed columns, not a rules JSONB blob. That demonstrates the author distinguished "JSONB because the data is genuinely unstructured" from "JSONB because we haven't modeled it yet."

### Finding 2 — Form editing surface is underspecified

- **Severity**: LOW
- **Pattern type**: DEFER-AS-WORKAROUND
- **Section of proposal**: §4 (Applications subsystem)
- **Description**: The proposal says "Application forms should be DB-stored, not YAML-backed in production" and "A form edit creates a new version row." Initial form creation happens through the provisioning spec attachment (§7). But the proposal never describes how an operator edits a live form after provisioning. There is no `/form edit` command, no CLI import command, and no described operator surface for "change this chapter's application questions."
- **Why it matters**: Without a described editing path, implementers must invent one. The likely shortcuts at implementation time are: direct DB manipulation, re-running full provisioning, or quietly reintroducing YAML-as-source-of-truth for "just the form updates."
- **Recommendation**: Accept for proposal scope. The versioning model is correct and the hookpoint phase (§16) explicitly asks which pieces of the existing config loader survive. The editing surface is an implementation detail the hookpoint and implementation phases will resolve. This is appropriate deferral, not hidden complexity, because the underlying data model already supports the operation — only the UX trigger is unspecified.

### Finding 3 — No compatibility shims detected

- **Severity**: LOW
- **Pattern type**: COMPAT SHIM
- **Section of proposal**: §2, §4, §7, §9
- **Description**: The proposal makes clean breaks at every point where the pre-research draft used a different approach: SQLite to Postgres, YAML-as-source-of-truth to DB-stored with YAML as import only, CLI provisioning to slash command with confirmation, in-memory sessions to `draft` DB rows. At no point does the proposal introduce "for now" code paths, dual-write layers, feature flags, or transitional compatibility bridges.
- **Why it matters**: D1 and AGENTS.md explicitly forbid compat shims. This check confirms compliance.
- **Recommendation**: Accept. The proposal follows the no-compat-shim rule truthfully.

### Finding 4 — No pre-research code carryover of wrong shapes

- **Severity**: LOW
- **Pattern type**: PRE-RESEARCH CARRYOVER
- **Section of proposal**: §3, §4, §7, §8
- **Description**: Cross-checked `daemon/applications.py`, `daemon/db.py`, `daemon/claim.py`, `daemon/config.py`, and `daemon/__main__.py` against the proposal. The pre-research code uses SQLite, in-memory session state, YAML-as-source-of-truth chapters, a flat submissions table with TEXT status, and `ApplicationReviewView` with four buttons. The proposal replaces all of these: Postgres with UUIDs and proper FKs, `draft` DB rows instead of in-memory sessions, DB-stored chapters with provisioning saga, an `applications` table with ENUM status and a status history table, and a five-button review embed (adding Waitlist). The multi-step modal pattern survives but is a Discord platform constraint (5 components per modal), not a carryover of a wrong design.
- **Why it matters**: The specific failure mode is "proposal says it treats daemon/ as pre-research draft but secretly carries forward its shapes." That did not happen.
- **Recommendation**: Accept. The proposal evaluated and replaced pre-research patterns rather than inheriting them.

### Finding 5 — Mixed OCR architecture is research-justified, not defensive overengineering

- **Severity**: LOW
- **Pattern type**: DEFENSIVE OVERENGINEERING
- **Section of proposal**: §6 (Activity tracking subsystem)
- **Description**: The 9-step OCR pipeline (receive, preprocess, Google Vision, geometric parse, confidence score, three-outcome routing, Gemini fallback, hallucination controls, persist and evaluate) looks complex. But `research/04-ocr-backends.md` documents specific failure modes: dense layouts, dark themes, partial occlusion, multilingual names. Each pipeline step addresses a documented failure mode. Preprocessing handles dark/small text. Geometric grouping handles tabular layouts that line-break parsing cannot. Confidence scoring distinguishes good from bad reads. Gemini fallback handles screenshots where classical OCR fails entirely. Hallucination controls prevent the fallback from inventing data.
- **Why it matters**: If the complexity were unjustified, it would be a shortcut around committing to one clear path.
- **Recommendation**: Accept. The complexity is proportional to the documented problem. The alternative — calling Google Vision and hoping — would be the actual shortcut. The proposal also keeps preprocessing chapter-configurable and conditional, not blanket overprocessing.

### Finding 6 — OCR confidence thresholds are correctly absent from the proposal

- **Severity**: LOW
- **Pattern type**: SYMPTOM MASK
- **Section of proposal**: §6 (Activity tracking subsystem)
- **Description**: The proposal describes confidence-based routing (accept directly, flag for review, escalate to Gemini) without specifying exact threshold values. The proposal says thresholds should be informed by a "retained gold corpus" (§11) and empirical measurement of "row precision, score accuracy, roster match rate, fallback rate, and human-correction rate."
- **Why it matters**: Plausible-sounding hardcoded thresholds would be a symptom-masking shortcut — they would look rigorous but lack empirical basis. The proposal avoids this by deferring threshold selection to the implementation phase with an explicit calibration requirement.
- **Recommendation**: Accept. Deferring thresholds to empirical calibration is the right call. Hardcoding them in the proposal would have been the shortcut.

### Finding 7 — Saga rollback uses principled defaults

- **Severity**: LOW
- **Pattern type**: TRANSACTION SHORTCUT
- **Section of proposal**: §7, §13
- **Description**: The provisioning saga records each step with created Discord IDs and DB IDs, supports resume and explicit reverse-ordered rollback, and uses "archive over delete" when humans may have interacted with created resources. The rollback does not specify compensation for every edge case (e.g., role assigned to a user between creation and rollback). The default — prefer archival and disablement — covers these cases without silent data destruction.
- **Why it matters**: A fake transaction or "leave orphaned roles" approach would be a shortcut. The saga framework is real, with step-level tracking and a principled default for ambiguous cases.
- **Recommendation**: Accept. The saga design pulls its weight. The unspecified edge cases are inherent saga complexity, not shortcuts, and the "archive over delete" default is the correct conservative behavior.

### Finding 8 — Supabase RLS deferral is justified

- **Severity**: LOW
- **Pattern type**: OTHER
- **Section of proposal**: §9 (Deployment)
- **Description**: The proposal disables RLS because "only the trusted daemon service role uses them" in v1. The daemon and `discord_cli.py` are both operator-controlled code running with service credentials. RLS would add configuration burden with no security improvement because there are no untrusted clients.
- **Why it matters**: If the daemon were not the only client, disabling RLS would be a shortcut around configuring it. But the architecture genuinely has one trusted service.
- **Recommendation**: Accept. The proposal plans to add RLS when a web app introduces untrusted client access. That is the correct time to introduce it.

### Finding 9 — Audit events are not duplicating Discord

- **Severity**: LOW
- **Pattern type**: DUPLICATED LOGIC
- **Section of proposal**: §3, §8
- **Description**: `audit.audit_events` captures business-logic events: mutation planning, DB state transitions, OCR processing decisions, provisioning steps, and role-change sequences. Discord's audit log only captures actions performed through Discord's API (role changes, channel edits) and retains them for 45 days. The proposal's audit table captures events Discord's log does not (draft-to-submitted transitions, claim operations, blacklist additions, OCR escalation decisions) and retains them indefinitely.
- **Why it matters**: If the audit table duplicated Discord's existing audit log, it would be unnecessary complexity. It does not.
- **Recommendation**: Accept. The audit surface covers a different and broader set of events than Discord provides.

### Finding 10 — Moderator ticket type routing to empty role is forward-compatible design

- **Severity**: LOW
- **Pattern type**: DEFER-AS-WORKAROUND
- **Section of proposal**: §5 (Tickets subsystem)
- **Description**: The `moderator` ticket type routes to the `Moderator` role. NOTES.md confirms no one currently holds this role. Tickets would go to a queue channel visible only to Moderators, and no one would see them until the role is populated.
- **Why it matters**: This could be a half-solution — a ticket type that sends cases into a void. But the routing is structurally sound. When someone is assigned the Moderator role, they immediately gain visibility into the queue. No code changes are needed.
- **Recommendation**: Accept. The ticket type is not creating a broken workflow; it is creating a dormant one that activates correctly when the precondition (role assignment) is met. This is forward-compatible design, not a half-built shortcut.

## Overall assessment

The proposal replaces pre-research shortcuts cleanly without introducing new ones. The JSONB usage is disciplined (document-shaped data only, with explicit columns where structure is known). The OCR pipeline's complexity matches the research-documented problem space. The saga model is real, not a transactional handwave. The sole underspecification — the form editing operator surface — is an appropriate deferral to the hookpoint phase, not hidden complexity. No compat shims, no carryover of wrong shapes, no "we'll figure it out later" disguised as anti-scope.

The verdict is LOW because the design pulls its weight at every layer examined.

## What a LOW verdict requires

The verdict is LOW if the proposal's design pulls its weight at every layer — no deferred complexity masked as "out of scope," no JSONB dumping grounds, no plausibly-but-unproven thresholds, no carryover of wrong shapes from the pre-research draft.

All ten findings are LOW. No finding identified a shortcut that, if removed, would require design changes. The form editing surface underspecification (Finding 2) is a gap the hookpoint phase is positioned to fill, not complexity the proposal is avoiding.
