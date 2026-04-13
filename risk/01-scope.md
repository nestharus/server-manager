# Scope risk assessment — proposals/01-v1-scope.md

Date: 2026-04-11
Assessor: claude-opus (scope)

## Verdict

**MEDIUM**

The revised proposal has addressed most concerns from the earlier risk round: tickets are trimmed to `server_support` only, activity tracking is split into 2a/2b, provisioning drops the saga/resume/rollback engine, and transcript capture is simplified to close-time fetch. The scope is now much closer to achievable. The verdict remains MEDIUM because two unresolved concerns compound: the web-form contingency for application intake is a real scope expansion risk that hasn't been sized, and the ticket subsystem is building infrastructure for a workflow that has generated 3 cases in 4 years. Neither alone would block a LOW, but together they create enough budget uncertainty to warrant trimming before implementation begins.

## Findings

### Finding 1 — Web-form contingency is unsized scope risk

- **Severity**: MEDIUM
- **Direction**: OTHER
- **Section of proposal**: §4 (Applications subsystem), §14 (Anti-scope)
- **Description**: The proposal bets on Discord's newer component model (file upload, radio groups, checkbox groups in modals) for application forms. §16 acknowledges that `discord.py 2.7.1` support for these components is unverified. If the library cannot expose the required inputs, "richer web forms move into v1 as the replacement surface for the application intake workflow." The proposal correctly says this wouldn't change the data model or review flow, but the web surface itself — hosting, Discord OAuth, CORS, a frontend framework or static client, and styling — is not budgeted in the phase plan or cost model.
- **Why it matters**: This is a binary decision with material scope impact. If the contingency triggers, it adds an estimated 1-2 weeks of implementation work on top of Phase 1, which is already the densest feature phase. A one-person team discovering mid-Phase 1 that they need a web surface creates schedule pressure that cascades into later phases. The anti-scope in §14 excludes "general web reviewer dashboards" but explicitly carves out this intake form — so it's not anti-scope leakage, it's acknowledged-but-unsized scope.
- **Recommendation**: Resolve this during hookpoint research, before Phase 1 starts. If `discord.py` can't handle the required components, size the web fallback as an explicit Phase 1 sub-deliverable with its own definition of done. If `discord.py` can handle them, delete the contingency language. The decision should be made before implementation begins, not discovered during it.

### Finding 2 — Ticket subsystem has weak demand evidence

- **Severity**: MEDIUM
- **Direction**: TOO BIG
- **Section of proposal**: §5 (Tickets subsystem), §12 Phase 3
- **Description**: The research found 3 tickets across 4 years. ticketsbot.net is dead, but the historical volume suggests the capability was barely used even when available. The proposal has already trimmed to `server_support` only and simplified transcript capture to close-time fetch, which is the lightest credible implementation. Phase 3 still requires: a full state machine (open/claimed/closed), claim mechanics shared with applications, queue embeds, private thread lifecycle, paginated transcript persistence at close, requester-left-server handling, and end-to-end testing.
- **Why it matters**: The incremental cost is lower than a greenfield ticket system because the claim helper and thread infrastructure exist from Phase 1. But Phase 3 still competes for engineering attention with hardening applications and activity tracking — the subsystems with daily operational pain. At ~1 ticket per year, it may never repay its implementation cost.
- **Recommendation**: Keep `server_support` tickets in v1 scope but explicitly mark Phase 3 as deferrable if Phases 1-2b consume more budget than planned. If applications and activity tracking run long, a pinned "DM an admin for support" message covers the ticket gap with zero engineering cost. Revisit ticket demand 3 months after applications and activity tracking are live.

### Finding 3 — Roster management commands are unsequenced

- **Severity**: LOW
- **Direction**: ENTANGLED
- **Section of proposal**: §6 (Activity tracking subsystem), §12 (Sequencing plan)
- **Description**: Section 6 describes `/chapter roster link`, `rename`, `remove`, and `import` as first-class operational concerns: "the daemon should treat roster quality as a first-class operational concern, not as an afterthought behind OCR." But these commands don't appear in the Phase 2a or 2b definitions of done (§12). Phase 2a lists "roster bindings from applications" as a dependency, implying approved applicants auto-populate the roster. But real officers will also need to link existing members who joined before the system, rename players whose in-game names change, and correct OCR mismatches.
- **Why it matters**: If roster commands land in Phase 2a, they add scope to an already well-defined phase. If they land in Phase 2b, Phase 2a extraction summaries will show unmatched players with no correction path, making the phase less useful. This is a small gap but creates ambiguity about when the activity subsystem is operationally complete.
- **Recommendation**: Explicitly sequence `/chapter roster link` and `/chapter roster rename` into Phase 2a's definition of done — they're prerequisites for useful extraction summaries. Defer `/chapter roster import` (CSV) to Phase 2b or later; manual link commands cover early-stage roster building.

### Finding 4 — Observability depth exceeds single-operator need

- **Severity**: LOW
- **Direction**: TOO BIG
- **Section of proposal**: §10 (Observability)
- **Description**: The proposal specifies Prometheus-style counters and gauges (15+ named metrics), a health endpoint reporting gateway heartbeat and DB connectivity, 7 alerting scenarios, structured JSON logging with secret scrubbing, and blast-radius isolation between subsystems. This is a production-quality observability stack for a bot serving 84 members with one operator.
- **Why it matters**: Structured logging and secret scrubbing are justified — the bot has high privilege and the forever-retention requirement means audit data integrity matters. But Prometheus metrics, a formal health endpoint, and alerting rules are overhead for a system where the single operator will notice failures through Discord interactions not working. Railway provides built-in deploy logs, crash detection, and automatic restarts. The implementation time for the full observability spec is modest but real.
- **Recommendation**: Keep structured JSON logging and secret scrubbing (both are load-bearing for audit correctness). Keep a minimal health endpoint if Railway requires one for always-on service health checks. Defer Prometheus-style metrics and formal alerting rules until there's a concrete debugging need that logs don't cover. Add metrics incrementally when a specific subsystem proves hard to debug from logs alone.

### Finding 5 — Existing bot boundary is implicit, not explicit

- **Severity**: LOW
- **Direction**: OTHER
- **Section of proposal**: §2 (Architecture), §4-§7 (Subsystems)
- **Description**: Captcha.bot and AmariBot are explicit keeps (per NOTES.md and research). The proposal never mentions either by name. The boundary is implicitly clean: Captcha.bot handles server entry verification (Guest → Member roles), while the daemon handles chapter membership (Chapter Applicant → Chapter Member roles). AmariBot handles Discord-side XP/leveling, while the daemon handles in-game activity OCR. But this boundary is never stated.
- **Why it matters**: During implementation, the developer needs to know which roles and permission surfaces are owned by which bot. If the daemon accidentally assigns a role that Captcha.bot uses for its verification flow, or if role hierarchy positioning puts chapter roles above the verification stack, the bots could interfere with each other. The risk is low at Humility's scale, but the proposal should make the boundary explicit.
- **Recommendation**: Add a short subsection (one paragraph) to §8 or §15 naming Captcha.bot and AmariBot, listing which roles and channels they own, and confirming the daemon will not modify those resources. This is documentation scope, not implementation scope.

### Finding 6 — Activity 2a/2b split is well-calibrated

- **Severity**: LOW
- **Direction**: TOO BIG (mitigated)
- **Section of proposal**: §6, §12 Phases 2a/2b
- **Description**: The revised proposal splits the OCR subsystem into Phase 2a (upload, store, Vision, basic extraction) and Phase 2b (confidence scoring, Gemini fallback, correction UI, rule evaluation). Phase 2a delivers operator-visible value — officers can upload screenshots and see extraction results — without requiring calibrated thresholds, fallback routing, or the full correction UI.
- **Why it matters**: This is exactly the right decomposition. Phase 2a proves storage and OCR integration against real screenshots. Phase 2b adds trust and automation. If 2b slips, officers still have durable extraction summaries they can review and correct manually — already better than the current spreadsheet.
- **Recommendation**: Accept. This addresses the previous review's major OCR concern.

### Finding 7 — Provisioning simplification is proportionate

- **Severity**: LOW
- **Direction**: TOO BIG (mitigated)
- **Section of proposal**: §7, §12 Phase 4
- **Description**: The revised proposal drops the saga state machine, automatic resume-from-midpoint, and generic reverse-ordered rollback. Instead, it records created resource IDs incrementally and offers explicit cleanup for failed runs. Phase 4 is sequenced last with the widest dependency surface.
- **Why it matters**: This is right-sized for Humility's expected chapter volume (low single digits). Manual cleanup of a failed provisioning run using recorded IDs is practical when runs happen rarely. The audit trail is preserved without the implementation weight of an orchestration engine.
- **Recommendation**: Accept. If the owner creates chapters frequently enough that manual cleanup becomes painful, upgrade to a more automated path then.

### Finding 8 — Forever retention is sustainable at this scale

- **Severity**: LOW
- **Direction**: OTHER
- **Section of proposal**: §3 (Data model), §17 (Cost model)
- **Description**: D4 locks forever retention. At 84 members with daily activity logs, the largest table (activity_log) grows at roughly 30k rows/year per chapter. Screenshot storage at 150-600 images/month at ~1MB average is 150MB-600MB/month. The cost model recommends Supabase Pro ($25/month, 100GB storage) for production.
- **Why it matters**: At this scale, forever retention is a non-issue for years. The schema uses soft deletes and archive timestamps. No TTL is needed. Supabase Pro handles the storage growth comfortably. The one note: if the project starts on free tier "briefly" (§17's cheapest option), screenshot storage will saturate free-tier limits within 2-3 months of active OCR uploads.
- **Recommendation**: Accept. The cost model correctly recommends Pro tier for production. No scope change needed, but the proposal could note that free-tier runway shortens quickly once activity uploads begin.

## Overall assessment

The revised proposal has meaningfully improved since the first risk round. Tickets are trimmed to `server_support` only. Activity tracking is split into 2a/2b with proportionate definitions of done. Provisioning drops the enterprise-grade saga in favor of recorded IDs and explicit cleanup. Transcript capture is simplified to close-time fetch. These changes directly address the previous review's major findings.

The verdict remains MEDIUM because of two compounding concerns. First, the web-form contingency for application intake is a binary decision with material scope impact that hasn't been resolved or sized — if it triggers mid-Phase 1, it adds real work that isn't budgeted. Second, the ticket subsystem is still building production infrastructure for a workflow averaging less than one case per year, competing for engineering attention with subsystems that have daily operational pain.

These are softer concerns than the first review identified. Neither is a fundamental scope error — they're budget risks. With the phased sequencing already in place, the practical impact is manageable: if Phase 1 runs long because the web form triggers, Phase 3 naturally slips, and the total scope self-adjusts. The explicit path to LOW is resolving the web-form question during hookpoint research and marking Phase 3 as deferrable.

## What a LOW verdict requires

The verdict is LOW if the scope is credibly achievable, proportionate to the problem, and does not entangle or starve features.

The verdict is MEDIUM if the scope needs trimming or rebalancing but is not fundamentally wrong.

The verdict is HIGH if the scope is so wrong (too ambitious or too narrow) that the proposal should be rewritten before implementation.
