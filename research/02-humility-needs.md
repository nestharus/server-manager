# Humility-specific synthesis

Phase 2 output. Synthesizes `research/01-problem-space.md` with the
live Humility server state from `NOTES.md` and user decisions captured
in `DECISIONS.md#D4` and `#D5`. Produced by Claude Code (orchestrator)
rather than an external agent, because it requires conversation
context that an external model would not have.

---

## 1. Source material

- **`research/01-problem-space.md`** — Discord guild management problem
  space (published 2026-04-11). Documents 6 problem categories, 12
  existing tools with coverage matrix, and 14 platform-constraint
  bullets. Evidence-led; no solutions proposed.
- **`NOTES.md`** — live audit of the Humility server state (channels,
  roles, bots, integrations, current breakage).
- **`DECISIONS.md#D4`** — user's answers to the research's open
  questions (full-review applications, forever retention, three pain
  points tied for priority).
- **`DECISIONS.md#D5`** — activity tracking with OCR as a newly-surfaced
  primary requirement.
- **`research/04-ocr-backends.md`** — landed 2026-04-11; evaluates
  11 OCR backends (classical OSS + cloud OCR + vision LLMs) against
  the game-screenshot use case. Cost at MVP volume is trivial. Mixed
  classical+LLM architecture recommended. See §4.4 for the findings
  absorbed into the design.

---

## 2. Humility context recap

From the live-server audit in `NOTES.md`:

- **Guild**: Humility, 84 members, created 2022-04-04, owner `nestharus`
- **Structural state**: chapter scaffolding (`Chapter*` template roles,
  `GUILD TEMPLATE` category with empty channels) but **zero chapters
  are currently populated**. Dark Nemesis was an old chapter that has
  since been retired — its name no longer appears anywhere active.
- **Role inventory**:
  - Server-wide staff: `⚔️ Administrator`, `⚔️ Moderator` (**empty**),
    `⚔️ Staff`, `⚔️ Trial Mod`
  - Chapter templates (singular, shared): `Chapter Officer`,
    `Chapter Member`, `Chapter Guild War`, `Chapter Applicant`,
    `Chapter`, `Chapter Public`
  - Members, Guest, Language EN/POR/JP/ES/THAI, Owner, Booster, Muted
  - ~12 bot-managed roles
- **Bot inventory** (12 bots): Captcha.bot (active), AmariBot
  (leveling, silent), HumilityTicketBot (dead tickets.bot v1 ghost,
  now running on tickets.bot v2 but still functionally broken),
  Apollo + sesh (overlapping, both unused), Zira (reaction roles, set
  up once, silent), Hydra (never actually used), D29 nestharus (auto
  voice channels, active), Midjourney (on-demand), Sx Bot (silent),
  Gather (deprecated as of 2026-04-11, replacement needed),
  server-manager (this project's bot).
- **Broken integrations**: the ticketsbot.net v1 backend is dead
  (service sunset 2025-03-05); Gather is deprecated but still live.

From the research + user answers:

- **Pain #1: Applications** — Gather's deprecation puts the
  recruitment flow at risk. No functional application system today.
  User confirmed they want **full-review applications with multi-question
  forms**, per chapter, with a **waitlist** state in addition to
  pending/approved/denied/interview.
- **Pain #2: Tickets** — HumilityTicketBot is a ghost of tickets.bot
  v1, now routed to v2 but the old stale panel doesn't work and the
  v2 dashboard can't be automated by this bot. User wants to walk
  away from tickets.bot entirely. Ticket volume historically: 3 test
  tickets in 4 years. Real user demand: unknown but assumed
  low-volume.
- **Pain #3: Chapter provisioning** — no chapters currently exist;
  the template scaffolding has been sitting unused. User wants new
  chapters to be **simple to bring up**, "automated with AI" meaning
  an agent-driven flow rather than manual Discord-admin clicking.
- **Pain #4 (new)**: **Activity point tracking.** User maintains daily
  in-game activity data by hand in a spreadsheet. This is a daily-cost
  pain point and not covered by any existing bot in the market.

Notably absent:
- **No moderation pain** — the `Moderator` role is empty; there are
  no moderators today. Chapter officers moderate their own chapters'
  members. The research flagged moderation tooling heavily, but that
  pain does not apply to Humility today.
- **No leveling/engagement/calendar pain** — AmariBot handles leveling
  silently and users are happy with it; Apollo + sesh are both unused,
  meaning there's no active event-scheduling demand.
- **No server-wide analytics demand** — not mentioned, not visible in
  the server layout.

---

## 3. Research findings applied to Humility

Walking the research's six problem categories and asking "does
Humility feel this today?":

| Research category | Humility status | MVP scope? |
|---|---|---|
| Onboarding / verification / gating | **Solved** by Captcha.bot; no pain. Rules + verification + language roles work. | **Out of scope.** Don't touch. |
| Moderation / reports / auditability | **Not felt.** No mods, no reports, no staff burnout. Staff role is lightly populated. | **Out of scope for v1.** Revisit if Humility adds mods later. |
| Applications / recruitment / staff queues | **Felt.** Gather deprecated, ticketsbot dead, no working path. User explicitly prioritized this. | **In scope — primary.** |
| Role / channel / chapter topology | **Partially felt.** Template is in place but no chapter has ever been populated. Role/channel caps are not yet a problem (room to grow). User wants one-command chapter creation. | **In scope — primary.** Treat as provisioning automation, not topology redesign. |
| Spam / scams / raids / privacy | **Not felt.** Captcha.bot provides the anti-raid gate; no reports of spam. | **Out of scope for v1.** |
| Bot sprawl / reliability / vendor dependence | **Felt acutely.** Two primary dependencies (Gather, ticketsbot.net) have died or are dying. This is *why* the project exists. | **Structurally addressed** — by building in-house, we eliminate the vendor-risk surface for these subsystems. |

Additional user-surfaced category (not in the research taxonomy):

| New category | Humility status | MVP scope? |
|---|---|---|
| Activity tracking (OCR-driven) | **Felt daily.** User tracks in-game activity by hand, wants screenshot upload → OCR → threshold flagging. | **In scope — primary**, pending OCR backend research. |

### Platform-constraint corrections relevant to the design

Worth highlighting so they propagate into the proposal phase:

- **Modals now accept selects, file upload, radio groups, and
  checkboxes** (not just text inputs). This kills the split-flow
  design in the pre-research `daemon/applications.py`. A single modal
  can collect the entire Dark Nemesis-style form in one interaction.
- **Discord audit log retention is 45 days** — any moderation/decision
  history the user wants to keep forever must be duplicated into our
  own storage, not left in Discord's audit log.
- **Component V2** (`IS_COMPONENTS_V2` flag) allows 40 components per
  message, loosening the old 5×5 action-row constraint. Gives
  flexibility for review panels and activity-log dashboards.
- **Thread-based approach** to per-ticket/per-application conversation
  is still the right call (no server-channel cap pressure), but note
  private-thread semantics: `SEND_MESSAGES` does not control thread
  posting; `SEND_MESSAGES_IN_THREADS` does. Trial Mod read-only
  requires this permission, not the usual one.
- **Category inheritance quirks**: once a channel overwrite diverges
  from its category, the category stops enforcing policy. Provisioning
  needs to set overwrites at channel level, not rely on category
  sync, for anything mission-critical.

---

## 4. Humility-specific needs (validated)

Consolidated requirements the proposal must address:

### 4.1 Applications subsystem

- **Per-chapter forms**: each chapter defines its own application
  form with custom question set. Question shape supports: short text,
  long text, numeric, single-select, multi-select, and (per the
  corrected platform constraints) file upload if needed.
- **Single-modal form** where possible. Forms with ≤5 inputs fit in
  one Discord modal. Multi-modal splitting only if a form exceeds 5
  components.
- **Blacklist per chapter**: user IDs can be banned from applying to
  a specific chapter. Checked at `/apply` time; blocked users get an
  ephemeral rejection.
- **Review workflow** with states: `pending → claimed → (interview |
  waitlist) → approved | denied`. The **waitlist** state is new —
  applications can sit in a queue before being fully approved/denied.
- **Claim semantics**: reviewing officer claims an application;
  channel/thread permissions narrow to claimer + applicant + admins.
  Other officers lose visibility.
- **Interview**: opens a private thread for back-and-forth between
  applicant and claimer. Applicant answers follow-up questions.
- **Approve**: mutates roles — removes `Chapter Applicant`, adds
  `Chapter Member` (or the chapter-specific equivalent, see 4.4).
- **Deny**: records reason, DMs applicant, archives the review thread.
  Applicant may or may not be auto-blacklisted depending on a per-
  chapter policy flag.
- **Waitlist**: marks the application as waiting without a decision.
  User can be converted to approved/denied later. No role mutation.
- **Handlers**: chapter officers of the chapter being applied to.
  Server-wide Staff + Administrators always retain override access.
- **Data retention**: forever. All applications, all decisions, all
  reasons, all conversation transcripts.

### 4.2 Tickets subsystem

- **Four ticket types** (per user's earlier clarification):
  - **Server support** — server-wide, handled by `Staff`
  - **Moderator** — server-wide, handled by `Moderator` (currently
    empty) + `Trial Mod` read-only. Built now but will have no
    handlers until mods are added.
  - **Chapter support** — per chapter, handled by that chapter's
    `Chapter Officer` members
  - **Chapter moderation incident** (in-game incident reports) —
    per chapter, handled by that chapter's officers
- **Claim-based visibility**: on claim, the thread narrows to claimer
  + requester + admins.
- **Transcripts**: every closed ticket produces a transcript stored
  in Postgres (retention: forever). No dependence on Discord audit log.
- **Trial Mod read-only**: for moderator tickets only, Trial Mods can
  see + read but not post. Enforced via parent-channel overwrite with
  `SEND_MESSAGES_IN_THREADS` denied, not `SEND_MESSAGES`.
- **Ticket volume**: low historically (3 tickets in 4 years, all test
  tickets). MVP should not be scale-optimized, but should not break on
  an order-of-magnitude traffic spike either.

### 4.3 Chapter provisioning subsystem

- **One-command chapter creation**: the user describes the chapter
  (name, game, form questions, activity rules) and the daemon +
  Claude Code orchestrator creates everything: category, roles,
  channels, form config, activity rules, panels.
- **Roles per chapter**: cloned from templates with chapter-specific
  names. For "Crimson Dawn" example: `Crimson Dawn Officer`,
  `Crimson Dawn Member`, `Crimson Dawn Applicant`, `Crimson Dawn`,
  `Crimson Dawn Guild War`, `Crimson Dawn Public`. Role cap is 250,
  six new roles per chapter means ~30 chapters before that becomes
  tight — plenty of headroom.
- **Category per chapter**: cloned from `GUILD TEMPLATE` structure
  with chapter-specific overwrites targeting the new chapter roles.
  Additional channels: `#<chapter>-applications` (review queue),
  `#<chapter>-tickets` (chapter support queue), `#<chapter>-incidents`
  (incident queue), `#<chapter>-activity` (where screenshots get
  posted for OCR).
- **Archive flow**: retiring a chapter moves its category + channels
  into an `archived-chapters` meta-category (or similar), preserves
  all data, but stops accepting new applications/tickets/activity.
- **Chapter registry**: in Postgres. One row per chapter, soft-delete
  semantics (archived_at timestamp).

### 4.4 Activity tracking subsystem (OCR)

This is the biggest unknown and the biggest time-saver.

- **Input**: chapter officer uploads a screenshot in
  `#<chapter>-activity` (or DMs the bot with a slash command).
- **OCR**: extract per-player activity rows. Output shape:
  `[{player_name, activity_points, (optional timestamp)}, ...]`
- **Identity mapping**: player in-game name → Discord member. Done
  via a per-chapter `member_roster` table that the officer populates
  once per player (or auto-populates from approved applications that
  captured `in_game_name`).
- **Persistence**: `activity_log` table with
  `(chapter_slug, member_id, date, points, source_message_id,
  source_image_url, extracted_player_name)`.
- **Thresholds**: per-chapter configurable daily target and
  configurable flagging rules. E.g., "flag any member with <50 points
  for 3 consecutive days."
- **Flagging**: daemon posts into a flagging channel (probably
  `#<chapter>-activity-flags` or a pinned message in
  `#<chapter>-activity`) listing members below threshold.
- **Confidence handling**: OCR results include a confidence score;
  low-confidence rows are flagged for manual review before being
  accepted into the log.
- **Backend**: see `research/04-ocr-backends.md` (landed 2026-04-11).
  Key findings for the proposal:
  - **Cost at MVP volume is trivial** across all candidates — from free
    (classical OSS) to ~$6/month (Sonnet 4.6 vision). Gemini Flash
    ~$0.87/month is the cheapest hosted option. Cost is not the decider.
  - **Game UIs lack a proper OCR benchmark** — confidence in any
    option is weaker than for document OCR. The research is explicit
    about this and recommends a mixed architecture.
  - **Two architectures to choose between**:
    1. **Classical OCR + row parser** (Tesseract or PaddleOCR).
       Portable, free, deterministic. Requires custom row grouping
       logic. Strong when screenshots are cropped to the relevant
       panel first.
    2. **Vision LLM with structured output** (Gemini / Claude / OpenAI).
       One-shot semantic extraction with schema-constrained JSON.
       Higher ceiling but hallucination risk — wrong-but-valid JSON.
    3. **Mixed**: classical OCR first, escalate ambiguous cases to
       a vision LLM. Contains spend, reduces hallucination exposure,
       keeps a portable fallback.
  - **Hallucination controls** (needed regardless of choice): return
    raw extracted text alongside normalized fields, require per-row
    evidence, validate row-count totals against the image, fall back
    to classical OCR on LLM uncertainty, flag low-confidence rows for
    human review before writing.
  - **Deployment shape**: classical OCR fits a small Railway container
    easily (Tesseract is lightest, PaddleOCR is moderate). Vision LLMs
    are zero-ops but add a vendor dependency.
  - **Privacy**: OpenAI's docs are the clearest on retention (30-day
    abuse logs default, ZDR available). Gemini free tier uses data
    for training, paid tier does not. Anthropic's public developer
    docs on retention need separate legal review.
  - **Leading recommendation from the research** (not a final pick):
    mixed architecture with PaddleOCR or Google Vision as the classical
    baseline and Gemini Flash as the LLM fallback. The proposal phase
    will make the call based on tolerance for vendor dependencies and
    preferred validation posture.

---

## 5. MVP priority ranking — three options for the user to pick

The user confirmed all three pain points (applications, tickets,
chapter provisioning) are acute, and added activity tracking as a
fourth. We can't build everything at once; we need to sequence.

### Option A — Applications first, then tickets, then OCR, then provisioning

1. Week 1-2: daemon skeleton, Supabase schema, applications subsystem
2. Week 2-3: tickets subsystem (reuses the claim + thread primitives)
3. Week 3-4: activity tracking (OCR)
4. Week 4-5: chapter provisioning automation

**Pros**: tackles the acute recruitment gap first (Gather replacement).
Applications and tickets share infrastructure. OCR is riskiest and
comes after the core is stable.
**Cons**: user keeps tracking activity by hand for ~3 weeks.

### Option B — Activity tracking first (biggest daily time save)

1. Week 1: daemon skeleton, Supabase schema, activity tracking (OCR)
2. Week 2: applications subsystem
3. Week 3: tickets subsystem
4. Week 4: chapter provisioning

**Pros**: the user's daily pain (spreadsheet tracking) is relieved
first. Provides immediate visible value before the longer-horizon
features.
**Cons**: activity tracking has the highest technical risk (OCR
accuracy, image identity mapping) and going first means the MVP's
first demo is the most likely to be rough. Gather and ticketsbot keep
limping along.

### Option C — Foundations first, then all features in parallel

1. Week 1: daemon skeleton + Supabase schema + Railway deploy +
   chapter registry (but no provisioning automation yet) — creates the
   substrate.
2. Week 2+: parallel work on applications, tickets, activity tracking.
   Provisioning automation last.

**Pros**: no feature is deliberately starved. Foundations are the
common dependency anyway, so this is optimal for critical-path
resolution.
**Cons**: longer before any single feature is usable end-to-end; the
user waits through a "nothing visible works yet" week.

### Recommendation

**Option C**, with a built-in weekly demo checkpoint: after the
foundations week, the user sees one feature go live each demo cycle
(applications → activity → tickets → provisioning). Foundations-first
avoids the classic MVP trap where every feature gets half-built against
a shifting base.

This is a recommendation, not a decision. The user picks.

---

## 6. Anti-scope (explicitly out for v1)

- **Moderation tooling** — no mods exist, deferred
- **Anonymous reporting** — deeper surface, deferred
- **Leveling / XP / engagement** — AmariBot handles it
- **Calendar / events** — Apollo and sesh exist, currently unused, no
  evidence of demand
- **Verification / CAPTCHA** — Captcha.bot handles it
- **Multi-server / control plane** — Humility-only target
- **Cross-server federation** — deferred
- **Auto-moderation** — out of scope
- **Spam/raid defense** — out of scope (handled by Captcha.bot + Discord
  AutoMod)
- **Analytics dashboards** — defer; logs in Postgres are the source of
  truth and can be queried directly
- **DSR/GDPR data export tools** — defer; database is under user's
  direct control via Supabase, manual export is sufficient at this
  scale
- **Mobile-first design** — Discord handles the UX surface; we don't
  ship a separate mobile client
- **Public web dashboard** — Railway hosts the daemon, not a dashboard.
  All operator actions happen via Discord interactions or via Claude
  Code running the CLI on the user's behalf.

---

## 7. Risk / tradeoff flags

These should be documented in the proposal phase and formally risk-
assessed, but listing now so they carry through:

1. **OCR accuracy on stylized game UIs** — the biggest technical
   unknown. If OCR is <90% accurate on row detection, the "save me
   time" value collapses because the user has to re-check every
   result. Deferred to `research/04-ocr-backends.md`.
2. **Player → Discord identity mapping** — a game screenshot has
   an in-game name, not a Discord ID. Mapping requires either a
   per-player roster maintained by officers, or a discovery step
   where the bot asks members to confirm their in-game name once.
3. **Role count growth** — 6 new roles per chapter × N chapters.
   Discord's cap is 250 roles. Humility currently has ~34 roles.
   Headroom for ~30 chapters. No near-term risk, but the chapters
   provisioning design should fail loudly if it would push past the
   cap.
4. **Category count** — 50 categories max, one per chapter plus
   meta-categories (Staff Ops, Archived). Headroom for ~45 live
   chapters. No near-term risk.
5. **"Forever retention" vs database size** — at current volume
   (low), this is not a concern. Design should use soft deletes and
   `archived_at` timestamps; actual deletion of data requires
   explicit admin action.
6. **Permission drift over time** — the research flagged this as a
   known trap. Chapter provisioning must set overwrites at the
   channel level, not rely on category inheritance, for
   mission-critical permissions (like Chapter Officer seeing their
   own applications).
7. **The bot has Administrator permission** — any mutation the
   code issues will succeed regardless of the target channel's
   overwrites. The *policy* boundary is this project's code + the
   mutation safety workflow in `AGENTS.md`. A bug in the daemon's
   role-mutation logic could, in theory, mass-mutate every role in
   the server. Proposal must address bounded-mutation patterns.
8. **Dependency on Supabase** — we are trading ticketsbot.net-style
   vendor risk for Supabase-style vendor risk. Mitigation: the
   database schema is ours, migrations are in-repo, and Postgres is
   Postgres — migration to self-hosted or a different provider is a
   dump/restore.
9. **Dependency on a vision model** (if we go LLM-vision for OCR)
   — same class of vendor risk. The activity tracking feature degrades
   gracefully if the vision model API is down: unprocessed images
   queue up and retry.
10. **Chapter officers are not yet hired for chapters that don't
    exist** — the MVP flow assumes officers exist per chapter. For
    the first chapter provisioned, the user is likely the only
    officer. Provisioning must handle "chapter with one officer"
    cleanly.

---

## 8. Open decisions deferred to the proposal phase

1. **OCR backend choice** — research is complete. Candidates narrowed
   to: (a) classical-only (PaddleOCR or Google Vision + row parser),
   (b) LLM-only (Gemini Flash one-shot structured output), or
   (c) mixed (classical primary, LLM fallback on low-confidence). User
   cost tolerance and vendor preference drives the final pick.
2. **Schema migration tool** — Alembic vs Supabase migrations CLI vs
   hand-rolled SQL files. Probably Alembic for Python ergonomics.
3. **Chapter activity rule DSL** — how officers express threshold
   rules. Candidates: YAML per chapter, DB column, DSL.
4. **Waitlist promotion mechanics** — manual only, or auto-promote
   on officer action, or some scheduled conversion.
5. **Application form revision policy** — can a chapter's form
   questions change after applications already exist under the old
   shape? Data model has to accommodate.
6. **Ticket routing for Chapter moderation incidents** — should an
   incident reported by a non-chapter-member go to that chapter's
   officers, or to server-wide Staff? Probably officers with escalation
   to Staff, but needs clarification.
7. **Concurrency** — how many in-flight applications per applicant
   per chapter (just one?). How many active tickets per requester
   (one? unlimited?). Rate limits.
8. **Testing strategy** — staging Discord server? Separate Humility
   "test" category? Mocks against a local Postgres? Proposal must
   address.

---

## 9. Gate review request (user)

This document is the phase-2 artifact. The user should review and
either green-light phase 3 (proposal drafting by `gpt-high`) or send
back with corrections.

**Specifically asking the user to confirm or adjust**:

- ✅ MVP prioritization — which option (A / B / C / other)?
- ✅ Is the waitlist state correctly understood? (After claim, before
  approve/deny, the reviewer can push the app to a waitlist instead
  of deciding now. Later, the reviewer can come back and approve/deny.)
- ✅ Is the four-ticket-type model still accurate even though
  `Moderator` is currently empty? (Build now, handlers arrive later.)
- ✅ Any priorities I missed from the "we also need various tools for
  managing guilds like this one" comment that should be in scope?

The OCR research is running in parallel and will land before the
proposal starts.
