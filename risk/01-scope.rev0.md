# Scope risk assessment — proposals/01-v1-scope.md

Date: 2026-04-11
Assessor: claude-opus (scope)

## Verdict

**MEDIUM**

The proposal targets the right four pain points, sequences them defensibly, and keeps anti-scope clean. But the ticket subsystem is built for demand that doesn't exist (4 types against 3 tickets in 4 years), the OCR pipeline is the heaviest single deliverable yet treated as a routine middle phase, and the provisioning saga carries enterprise-grade resume/rollback for an operation that will run single-digit times. With trimming in tickets and provisioning plus honest phasing of OCR, the scope becomes achievable; without those adjustments the implementation budget is tight enough to risk stalling.

## Findings

### Finding 1 — Ticket subsystem is over-scoped for evidenced demand

- **Severity**: MEDIUM
- **Direction**: TOO BIG
- **Section of proposal**: §5 (Tickets subsystem)
- **Description**: The proposal builds four ticket types (`server_support`, `moderator`, `chapter_support`, `chapter_incident`) with full real-time transcript capture via gateway events, close-time reconciliation, `Trial Mod` read-only permission scaffolding, and ticket-to-application promotion. NOTES.md records 3 tickets in 4 years. The `moderator` type routes to an empty role. `chapter_support` and `chapter_incident` require chapters to exist, but no chapters exist and won't until Phase 4 — after Phase 3 ships tickets.
- **Why it matters**: Each ticket type requires its own routing logic, queue-channel placement, permission configuration, panel creation, and end-to-end testing. Four types quadruple the implementation surface for the subsystem with the weakest evidence of demand. Three of four types target organizational structures (moderators, chapters) that don't exist yet, producing code that passes tests but has never been exercised by real users.
- **Recommendation**: Ship v1 with `server_support` only. The schema can define all four enum values now — the cut is in handler code, panel creation, permission scaffolding, and testing. Add `chapter_support` and `chapter_incident` alongside Phase 4 provisioning, when chapters exist to route to. Defer `moderator` until the Moderator role is staffed.

### Finding 2 — OCR pipeline is the heaviest deliverable but under-acknowledged

- **Severity**: MEDIUM
- **Direction**: OTHER
- **Section of proposal**: §6 (Activity tracking subsystem)
- **Description**: The 9-step OCR pipeline includes: preprocessing (crop, grayscale, contrast, upscale, deskew), Google Vision integration, geometric row parsing by y-axis clustering and x-position sorting, per-row confidence scoring, three-way outcome routing, Gemini fallback with hallucination controls, roster fuzzy matching, a 5-button correction UI, and activity rule evaluation with consecutive/rolling modes. The geometric row parser is novel engineering with no cited library or reference. This is more technically uncertain than any other subsystem.
- **Why it matters**: The proposal sequences this as Phase 2, implying comparable effort to Phase 1 (applications) or Phase 3 (tickets). It is likely 2-3x either. The geometric parser alone — clustering OCR word boxes into rows, separating names from scores, handling header rows and UI chrome — could take as long as the entire applications subsystem. If Phase 2 stalls on parsing accuracy, every subsequent phase is delayed.
- **Recommendation**: Accept the scope (the pain justifies it) but split Phase 2 into 2a (upload, store in Supabase Storage, Vision API call, basic row extraction) and 2b (confidence scoring, Gemini fallback, correction UI, rule evaluation). Phase 2a is demoable and delivers partial value — officers can upload screenshots and see extraction results. Phase 2b adds the reliability and automation layers. This split prevents the OCR pipeline from becoming a monolithic blocker.

### Finding 3 — Provisioning saga is over-engineered for actual use frequency

- **Severity**: LOW
- **Direction**: TOO BIG
- **Section of proposal**: §7 (Chapter provisioning subsystem)
- **Description**: Provisioning includes an 8-step saga with `provisioning_runs` and `provisioning_steps` tables, per-step audit events, automatic resume-from-failure, reverse-ordered rollback with human-residue detection, dry-run cap checks with internal guardrails, and YAML/JSON spec attachment parsing. Humility has zero chapters. Realistic chapter creation volume is 1-3 chapters in the first year.
- **Why it matters**: At single-digit use, the operator will be watching every step in real time. Manual cleanup of a few Discord roles and channels after a failed step is trivial. The resume/rollback state machine, partial-resource detection, and "archive rather than delete if humans interacted" logic adds substantial implementation and testing weight for a path that will execute a handful of times.
- **Recommendation**: Keep the `provisioning_runs` table for audit. Cut `provisioning_steps`, automatic resume, and automatic rollback from v1. A sequential create script that records created Discord IDs and supports a manual `/chapters cleanup <run_id>` command delivers the same operational value. Upgrade to saga if chapter volume ever justifies it.

### Finding 4 — Discord component model bet is load-bearing but unverified

- **Severity**: MEDIUM
- **Direction**: OTHER
- **Section of proposal**: §4 (Applications subsystem), §16 (Open questions)
- **Description**: The synthesis (research/02) required "Web UI for forms (richer than Discord modals)." The proposal drops web UI to anti-scope (§14) and bets on Discord's newer component model — file upload, radio groups, checkbox groups in modals. §16 acknowledges that discord.py 2.7.1 support for these components is unverified. The entire form rendering strategy depends on this assumption.
- **Why it matters**: If discord.py 2.7.1 doesn't expose file upload or radio/checkbox components in modals, the form rendering collapses to text-only modals — the exact limitation the research identified as insufficient. The proposal reads as though Discord modals will definitely work, when the underlying capability is listed as an open question.
- **Recommendation**: Not a scope cut — this is a hookpoint-phase verification item. But the proposal should name a fallback explicitly: if Discord's component model doesn't support the required input types via discord.py, web forms enter v1 scope as a replacement, not a v2 addition. Without this fallback acknowledgment, the anti-scope boundary is silently conditional.

### Finding 5 — Chapter-scoped tickets built before chapters exist

- **Severity**: MEDIUM
- **Direction**: ENTANGLED
- **Section of proposal**: §5 (Tickets), §12 (Sequencing)
- **Description**: `chapter_support` and `chapter_incident` route to chapter officer roles and place panels in chapter member-facing channels. Phase 3 (tickets) ships before Phase 4 (provisioning). No chapters, chapter channels, or chapter officer roles exist at Phase 3 completion. These ticket types cannot be tested against real routing or exercised by real users until Phase 4 is done.
- **Why it matters**: Building ticket types against organizational structure that hasn't been created means the routing code is validated only against mocks or stubs. When chapters are finally provisioned, the ticket routing may need adjustment — but tickets are "done" and attention has moved on. This is a sequencing entanglement: the ticket subsystem has a hidden dependency on provisioning that the proposal doesn't acknowledge.
- **Recommendation**: Defer chapter-scoped ticket types to Phase 4 or a Phase 4.5, where they can be built and tested against real chapter infrastructure. This aligns with Finding 1's recommendation to ship `server_support` only in Phase 3.

### Finding 6 — Cost-benefit of ticket transcript infrastructure

- **Severity**: LOW
- **Direction**: TOO BIG
- **Section of proposal**: §5 (Tickets subsystem)
- **Description**: Transcript capture uses a hybrid approach: real-time gateway event writes for every message in ticket threads, plus close-time reconciliation to backfill missed events. This requires gateway event listeners, message storage (`ticket_messages` table), and a reconciliation pass. For a server with ~1 ticket per year, this is substantial infrastructure for minimal content.
- **Why it matters**: The hybrid transcript approach is well-designed for a high-volume ticket system. At Humility's volume, a close-time-only full-history fetch (no gateway listeners) would capture the same content with simpler implementation. The real-time component only matters if tickets generate enough messages that some could be missed during a daemon restart — unlikely at current volume.
- **Recommendation**: Simplify to close-time-only transcript capture in v1. If ticket volume grows enough that daemon restarts during active conversations become a concern, add gateway event writes then.

### Finding 7 — Activity screenshot storage growth is manageable

- **Severity**: LOW
- **Direction**: OTHER
- **Section of proposal**: §9, §17 (Deployment, Cost model)
- **Description**: Forever retention (D4) means activity screenshots accumulate indefinitely. At 150-600 images/month at ~0.5-2MB each, storage grows 75MB-1.2GB/month. Supabase free tier provides 1GB storage. The cost model recommends Pro tier ($25/month, 100GB storage) for production.
- **Why it matters**: If the project starts on free tier "briefly" (§17's cheapest option), storage will saturate within 1-3 months of active OCR uploads. This isn't a problem on Pro tier but shortens the free-tier runway.
- **Recommendation**: Accept. The cost model correctly recommends Pro tier. No scope change needed.

## Overall assessment

The proposal correctly identifies the four pain points — applications, activity tracking, tickets, and provisioning — and builds each with appropriate architectural depth. The schema is well-reasoned, the sequencing follows Option C correctly, and the anti-scope boundaries are clean. Applications and activity tracking are well-calibrated to evidenced pain.

The verdict is MEDIUM because of three compounding concerns. First, the ticket subsystem builds four types with full transcript infrastructure for a workflow averaging less than one ticket per year, consuming implementation budget that could go toward hardening OCR or applications. Second, the OCR pipeline — the most technically uncertain and implementation-heavy subsystem — is treated as a routine Phase 2 when it deserves explicit phasing acknowledgment. Third, the provisioning saga carries resume/rollback machinery for an operation that will run a handful of times.

These concerns compound into an implementation budget that is tight for one person plus agent. Any one concern alone would be LOW. Together they create enough schedule risk that the later phases (tickets, provisioning) could drag while early phases (applications) accumulate unaddressed maintenance needs.

With the recommended trims — one ticket type, simplified provisioning, and split OCR phasing — the remaining scope is credibly achievable, well-proportioned, and properly sequenced. The verdict would move to LOW.

## What a LOW verdict requires

The verdict is LOW if the scope is credibly achievable, proportionate to the problem, and does not entangle or starve features.

The verdict is MEDIUM if the scope needs trimming or rebalancing but is not fundamentally wrong.

The verdict is HIGH if the scope is so wrong (too ambitious or too narrow) that the proposal should be rewritten before implementation.
