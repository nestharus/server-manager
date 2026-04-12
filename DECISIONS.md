# Decision log

Append-only log of architectural and workflow decisions for this project.
Each entry: **D#** — date — title — context — decision — consequences.

---

## D1 — 2026-04-11 — Adopt research-first workflow from ~/work/AGENTS.md

**Context**: Initial work on this project jumped straight from problem
statements ("I want a Discord bot to manage the server") to solutions
(daemon, applications subsystem, SQLite schema). Several decisions were
made prematurely, including hard-coding the Dark Nemesis chapter and
assuming SQLite for persistence. These were wrong: Dark Nemesis is no
longer an active chapter, and SQLite doesn't fit a cloud-hosted 24/7
service. User pushed back and pointed at the established
research → proposal → risk → hookpoints → implement pipeline from
`~/work/AGENTS.md`.

**Decision**:
1. All feature work on this project follows the phased pipeline:
   1. Research (gpt-high) — understand the problem space
   2. Proposal (gpt-high) — design a solution
   3. Risk (3x claude-opus parallel) — audit/scope/shortcut; all must be LOW
   4. Research hookpoints (gpt-high) — map to existing code
   5. Implement (gpt-high) — build
2. Each phase uses a different agent invocation. Claude Code (this
   session) orchestrates and synthesizes; it does not skip phases.
3. Existing pre-research code in `daemon/`, `forms/`, etc. is preserved
   but flagged as pre-research draft. It does not constrain the
   proposal. If the proposal discards it, fine.

**Consequences**:
- Slower start, better destination
- Research artifacts tracked in `research/`, proposals in `proposals/`,
  risk reports in `risk/`
- Dark Nemesis form YAML stays as a historical reference; it does not
  constrain the form system design

---

## D2 — 2026-04-11 — Cloud stack: Railway + Supabase, not SQLite

**Context**: I picked SQLite for state in the pre-research draft
because "it's simple." User pointed out this project is cloud-hosted
24/7, and their existing convention (per `~/work/AGENTS.md`) is
Railway + Supabase for the RFQ platform.

**Decision**:
- **Compute**: Railway (daemon container, always-on)
- **Database**: Supabase (managed Postgres)
- **No SQLite** in the production design, even "for simplicity"
- **No local-only deployment path** — the bot runs in the cloud or
  it's not deployed

**Consequences**:
- Daemon architecture must be stateless; state lives in Postgres
- No persistent-volume tricks; if Railway container restarts, no data
  is lost because it was never on disk
- Schema migrations need a proper tool (Alembic or Supabase migrations
  CLI) — revisit at proposal time
- Existing `daemon/db.py` (SQLite) is now historical and will be
  replaced

---

## D3 — 2026-04-11 — Preserve, do not delete, pre-research drafts

**Context**: When pivoting from the build-first approach to
research-first, there's a temptation to rm -rf the existing code.
Bad idea — some of it may survive as hookpoints. `discord_cli.py` is
unambiguously valuable as an inspection tool regardless of proposal.

**Decision**: Keep everything in the repo. Move nothing. When
proposal is approved, a hookpoints analysis (phase 4) tells us what to
keep, rewrite, or delete.

**Consequences**:
- Repo temporarily has both "pre-research" and "post-research" code
  coexisting
- `AGENTS.md` must clearly mark the boundary
- No silent deletions

---

## D4 — 2026-04-11 — MVP scope answers (user decisions after phase 1)

After `research/01-problem-space.md` landed, the user answered the
load-bearing open questions from the report:

- **Q: How selective is chapter membership?** → **(c) Full application
  review** with a multi-question form per chapter. Each chapter defines
  its own form; the pattern from the old Dark Nemesis form is
  representative of shape, not content.
- **Q: Operational data retention?** → **(a) Keep everything forever**
  (applications, ticket transcripts, chapter membership history,
  activity logs). Design for durable storage in Postgres, no TTL.
- **Q: Most acute pain today?** → **Applications + Tickets + Chapter
  provisioning**, all three. No moderation pain today because no mods
  currently exist (the `Moderator` role is empty; server has
  `Staff` + chapter-specific `Chapter Officer` people).

**Additional user-named priorities** (surfaced during the same
response):

- **Waitlist** for chapter applications. Applications should be able to
  land in a waitlist state, not just pending/approved/denied/interview.
- **Activity point tracking with OCR.** User currently tracks per-member
  daily activity points for a guild game by hand in a spreadsheet.
  Desired: upload screenshots to Discord, OCR extracts per-player
  points, system flags members below a configurable threshold. This
  is a *new* primary requirement, not mentioned in the original scope.
  Significant daily time-saver for the user.

**Defaults the user hasn't contradicted** (locked unless rejected):

- Chapter officers handle moderation of their own chapter's members
- Reports to staff are private (to the staff role), not anonymous.
  Anonymous reporting is a separate, deeper surface and is out of scope
  for v1.
- Server-wide Staff (and Administrators) always retain override access
  to chapter spaces. Chapter officers do NOT have autonomy that
  excludes server-wide staff.
- Privacy posture: gated; nothing beyond a lobby/rules channel is
  visible pre-verification.
- Target future state: one Humility server with many chapters. NOT a
  multi-tenant control plane across several Discord servers.

**Consequences**:
- Proposal must address four distinct subsystems (applications, tickets,
  chapter provisioning, activity tracking), not two.
- Activity tracking implies a dependency on a vision/OCR service — new
  cost line and new reliability surface. Subject to separate research
  before proposal.
- Full data retention changes the Postgres schema design (soft deletes
  only, archive tables, no TTL jobs).

---

## D5 — 2026-04-11 — Activity tracking (OCR) is an in-scope primary requirement

**Context**: During the phase-1 synthesis conversation, the user
revealed that they spend daily time tracking in-game activity points
by hand in a spreadsheet, and strongly wants a screenshot-upload →
OCR → threshold-flagging workflow. This was NOT in the original scope
statements and does not appear in any of my pre-research drafts.

**Decision**:
- Activity tracking is treated as a **first-class subsystem** of the
  proposed daemon, peer with applications/tickets/chapters, not as a
  v2 afterthought.
- The OCR backend (Tesseract vs PaddleOCR vs hosted Vision API vs
  Claude/Gemini Vision) is **not yet decided**. It needs its own
  narrow phase-1 research pass. Deferred to a dedicated prompt.
- Activity thresholds are **per-chapter** configuration. Each chapter
  specifies what "activity points" means, what daily target applies,
  and where flagged members are posted.
- MVP priority ordering between the four subsystems is **an open
  question for phase 2 synthesis** — the user should see options and
  pick.

**Consequences**:
- A second research task is added to phase 1: OCR backend options for
  game-screenshot extraction. Runs via `gpt-high`.
- Cost modeling for the project now includes per-image vision API
  usage (if hosted) or compute budget (if self-hosted).
- Schema design must accommodate per-chapter activity rules and
  per-member daily logs.

---

## D6 — 2026-04-11 — Phase 2 gate: locked decisions for proposal phase

**Context**: After `research/02-humility-needs.md` and
`research/04-ocr-backends.md` landed, user answered the OCR
architecture question and named Google Cloud Vision as the classical
baseline. Remaining decision points (MVP sequencing, waitlist
semantics, other tools, synthesis accuracy) were not answered
explicitly. Claude Code takes defaults from the synthesis and
documents them here so the user can veto if wrong.

### User-specified

- **OCR architecture**: **Mixed** — classical OCR primary, vision LLM
  fallback on low-confidence / ambiguous screenshots.
- **Classical OCR backend**: **Google Cloud Vision**
  (`DOCUMENT_TEXT_DETECTION` for dense-layout game leaderboards).
  First 1,000 units/month free, then `$1.50/1000`. Low ops, zero
  container weight.
- **Vision LLM fallback**: **not specified by user**. Claude Code
  default: **Gemini 3 Flash Preview on the paid tier**. Rationale:
  cheapest LLM-vision option per `research/04-ocr-backends.md`
  (~$0.87/month even if ALL images went through it at MVP volume;
  fallback usage will be a fraction of that), strong JSON-schema
  structured output, paid tier does NOT train on input data, matches
  the privacy posture we want for member-identifying screenshots.
  Alternative if user prefers Anthropic: Claude Haiku 4.5
  (~$1.88/month). User can override.

### Defaults Claude Code is taking (veto opportunity)

- **MVP sequencing**: **Option C** — foundations first (daemon
  skeleton + Supabase schema + Railway deploy + CI), then parallel
  feature delivery with weekly demo checkpoints in the order
  applications → activity tracking → tickets → chapter provisioning.
  Rationale: no feature is starved, the shared substrate is the
  critical path, everything else blocks on it, weekly visibility
  catches course corrections early.
- **Waitlist semantics**: **pre-decision holding pattern**. An
  officer who has claimed an application can approve, deny, interview,
  or push it into a `waitlist` state. Waitlisted applications don't
  mutate roles; applicant remains `Chapter Applicant`. Later, the same
  or another officer can pull the application back and decide. The
  alternative interpretation ("approved-but-no-slot" post-approval
  queue) was considered and rejected — that's really capacity gating,
  a different and more complex feature. If the user meant that one,
  they should correct this.
- **Additional guild-management tools for v1**: **none added beyond
  the four subsystems already scoped**. Candidate extensions (roster
  management, DKP, raid signups, banking, etc.) listed in the
  synthesis §4 are noted but not in v1 scope.
- **Synthesis §4 (requirements) and §7 (risks)**: **accepted as-written**
  absent user corrections.

### Consequences

- Proposal phase (gpt-high) can proceed immediately.
- If any default is wrong, the proposal gets revised and re-risked.
- The Vision LLM fallback choice is a sub-decision revisitable at
  proposal time if the user prefers Anthropic/OpenAI, or if Gemini
  paid-tier API procurement is an issue.

---

## D7 — 2026-04-11 — Phase 3 gate: proposal-phase defaults + gate ownership correction

**Context**: After `proposals/01-v1-scope.md` landed, Claude Code
asked the user for a phase-3 gate review. The user corrected: "I'm not
the one to review this. The risk assessment is the review." That
matches `~/work/AGENTS.md` and the pipeline in `AGENTS.md`: the
proposal gate is the 3x parallel `claude-opus` risk assessment, not
human review. Human review is the right gate for research and
synthesis phases (where scope is being set), not for proposals (where
the risk model is the control).

**Decision**:
1. The proposal phase's **gate is the 3x `claude-opus` risk
   assessment**, full stop. No user review step between proposal and
   risk.
2. `AGENTS.md` is updated to spell this out explicitly and remove the
   "at phase gates" user-review language for phases that are
   actually model-gated.
3. Five flagged items from the proposal ship with defaults:
   - **Staging Discord guild**: yes, it will be created. Treated as a
     setup dependency. User has to create it at some point during
     phase 0; the implementation plan accounts for this as a manual
     prerequisite.
   - **Migration tool**: **Alembic**. Justified in proposal §9.
   - **Activity rules storage**: **DB rows, not YAML**. Officers edit
     from Discord, not from Git. Opposite of the forms-in-YAML
     decision and intentional.
   - **Ticket-to-application promotion**: **kept in v1 scope**. Low
     marginal implementation cost, prevents data loss for users who
     accidentally use the wrong queue.
   - **Supabase tier**: **budget for Pro at ~$25/month**. Free tier
     auto-pauses after 1 week of inactivity and has tight limits that
     will bite live data; Pro is the safer posture.
4. Proposal ships to risk assessment as-written. If risk returns
   MEDIUM or HIGH on any axis, the proposal is revised and re-risked.
   The defaults above are not sacred — risk findings can override
   them.

**Consequences**:
- Risk assessment runs next, in parallel across 3 `claude-opus`
  invocations (audit, scope, shortcut).
- `AGENTS.md` "When to Ask the User" section is corrected to clarify
  that proposal phase is model-gated, not human-gated.
- If all three risks return LOW, phase 5 (hookpoint research) starts
  without further user gate.
