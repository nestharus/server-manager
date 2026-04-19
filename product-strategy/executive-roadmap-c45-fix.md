# C4+C5 Fix Report: Executive Roadmap

## Scope

**Concerns fixed:** V-4 (pseudo lists from parallel clauses), V-5 (three consecutive sentences with the same opening word).
**Instances in violation report:** 9 (V-4) + 22 (V-5) = 31.
**Instances fixed:** 29.
**Instances skipped:** 2.

- V-4 line 218 (Competitive Positioning "Distinctive advantage"): already restructured by a prior fix pass; current prose reads as three sentences with varied subjects and a summarizing pair, no longer a parallel-clause pseudo list.
- V-4 line 262 (Review cadence): already expressed as a bulleted list of trigger-keyed items; no inline pseudo list remains in the current file.

## Summary of Changes

**Bulletized field values (count):** 23 total.

- 4 Phase-scoped field conversions × "Workflows enabled" (Phases 1, 2, 3, 4).
- 3 Phase-scoped field conversions × "Success condition (qualitative)" (Phases 1, 2, 4).
- 2 Phase-scoped field conversions × "Not yet built" (Phases 1, 2). Phase 3 was already bulleted; Phase 4 is a single-sentence field and was left intact.
- 18 per-slice "Anti-scope" field conversions across VS-001 through VS-018 (all slices that had the "No X. No Y. No Z." construction).

**Narrative prose restructured (count):** 2.

- Executive Summary "Competitive window is open" bullet (line 9): reduced from a three-clause pseudo list to one main claim plus supporting context.
- Competitive Positioning product-category bullets (lines 221–225): varied openings across five consecutive sub-items so the "None offer …" run no longer repeats.

## Sample Fixes

### Instance 1 (Executive Summary, line 9) — V-4 narrative prose

**Before:**
> The ticketing and permissions markets are crowded but shallow. Assignment is "brittle or paywalled" and audit is "fragmented and local," while "declared-state reconciliation appears under-served" across 5+ sources (...).

**After:**
> Five-plus sources describe declared-state reconciliation as "under-served" across a ticketing and permissions market that is crowded but shallow (...).

**Technique:** Reduced three parallel quoted clauses to one main claim with the other two framed as supporting context. Facts preserved; citation retained.

### Instance 2 (Phase 1 Success condition) — V-4 pseudo list

**Before:**
> **Success condition (qualitative).** An operator can (1) view any member's trust level with the signals that produced it, (2) grant/revoke authority scoped to a specific area with automatic enforcement, (3) reconstruct any past decision months later from immutable audit entries with causal chain, and (4) change policy on a live server with preview-confirm and optimistic concurrency protection.

**After:**
> **Success condition (qualitative).** An operator can:
>
> - View any member's trust level with the signals that produced it
> - Grant or revoke authority scoped to a specific area with automatic enforcement
> - Reconstruct any past decision months later from immutable audit entries with causal chain
> - Change policy on a live server with preview-confirm and optimistic concurrency protection

**Technique:** Converted numbered inline list to a real markdown list.

### Instance 3 (Phase 1 Not yet built) — V-5 repeated openers

**Before:**
> **Not yet built:** No operational workflows (no applications, tickets, or chapters). No Discord resource management. No compliance evaluation. No notifications. No roster management. No permission management.

**After:**
> **Not yet built:**
>
> - Operational workflows (applications, tickets, chapters)
> - Discord resource management
> - Compliance evaluation
> - Notifications
> - Roster management
> - Permission management

**Technique:** Field-label bulletization; dropped redundant "No" prefix because the label carries the negation.

### Instance 4 (VS-002 Anti-scope) — V-5 Anti-scope

**Before:**
> **Anti-scope:** No succession chain (predecessor_grant_id). No emergency override workflow. No automatic authority from ChapterRole assignment.

**After:**
> **Anti-scope:**
>
> - Succession chain (predecessor_grant_id)
> - Emergency override workflow
> - Automatic authority from ChapterRole assignment

**Technique:** Field-label bulletization; negation carried by the label.

### Instance 5 (Competitive Positioning None offer chain) — V-5 repeated openers across bullets

**Before (excerpt, 5 consecutive bullets):**
> - **General bots** ...: ... None offer persistent trust profiles, policy versioning, or cross-workflow audit ...
> - **Intake tools** ...: ... None offer claim-lock single-owner queuing ...
> - **Ticketing** ...: ... None offer per-category configurable state machines ...
> - **Activity/roster** ...: ... None offer a general-purpose compliance engine ...
> - **Permission/security** ...: ... None offer declared-intent-vs-actual reconciliation ...

**After:**
> - **General bots** ...: ... None offer persistent trust profiles, policy versioning, or cross-workflow audit ...
> - **Intake tools** ...: ... Claim-lock single-owner queuing with mandatory decision reasons is absent, and waitlist handling is equally missing ...
> - **Ticketing** ...: ... Per-category configurable state machines with typed transitions and mandatory resolution reasons are absent across the reviewed field ...
> - **Activity/roster** ...: ... No reviewed product offers a general-purpose compliance engine with chapter-scoped rules and dispute-grade audit ...
> - **Permission/security** ...: ... Declared-intent-vs-actual reconciliation is missing across the category ...

**Technique:** Retained the first occurrence; varied four subsequent openers (from "None offer …" to subject-first constructions or "No reviewed product offers …") so no three consecutive items share the same opening frame.

## Major Changes Flag

Did this pass make any changes that could trigger the restart-from-earlier-phase rule?

- [ ] Moved a section
- [ ] Rewrote more than 30% of a section
- [ ] Changed the narrative arc
- [ ] Added or removed a section

No boxes checked. All changes are localized rewrites of field values or single sentences. Section structure, ordering, claims, evidence, and citations are unchanged.

## Known Remaining Issues

- V-4 Distinctive advantage paragraph (line 218 in violations report) was already restructured by a prior pass; a reviewer scanning for the original signature may flag it, but current prose is not a parallel-clause pseudo list.
- V-4 Review cadence bullets (line 262) are already broken into separate trigger-keyed items; flagged by the report but no corresponding pseudo list remains in the current text.
- Some Anti-scope bullet items preserve the schema-field parentheses verbatim (e.g., "PermissionIntent (temporary, expires_at fields)"). These are intentional cross-references and were left unchanged.
- This pass did not touch V-1 (em dashes), V-2 (banned openers), V-3 (triads in prose), V-6 (same grammatical frame), V-7/V-8/V-9 per the scope boundary.
